# -*- coding: utf-8 -*-
"""Community-Adapter (S4, Konzept §7.3): Chart-Community-Konsens.

Deterministische Vorverarbeitung (das LLM destilliert nur, rechnet nie):
- TradingView-Ideas-RSS (OANDA:XAUUSD): Richtung je Idee aus Titel/Beschreibung
  (bullish/bearish/long/short/…), häufigste Kursmarken als Level-Cluster.
  ToS: privat/Anzeige — Daten bleiben lokal, kein Weiterverteilen.
- FXStreet Analysis + FXEmpire Forecasts: Analysten-Sentiment je Artikel
  (deterministische Schlagwort-Zählung).
- Kitco Weekly Survey (HTML, kein RSS): Best-Effort-Regex auf die
  bullish/bearish/neutral-Prozente; scheitert leise (Seite ändert sich oft).

Retail-Bias als Kontraindikator: ist die Community extrem einseitig
(≥ 70 % eine Richtung), wird ein Kontra-Flag gesetzt (Konzept §6).
"""
from __future__ import annotations

import re
import time
from collections import Counter

import requests

from .. import config
from .news import _hole_feed, parse_rss

_BULLISH = re.compile(
    r"\bbullish\b|\blong\b|\bbuy\b|upside|rally|breakout|aufwärts|steig", re.I)
_BEARISH = re.compile(
    r"\bbearish\b|\bshort\b|\bsell\b|downside|breakdown|rejection|rückwärts|fall", re.I)
_LEVEL = re.compile(r"\$?\s?([1-9][0-9]{3})(?:[.,]([0-9]+))?")
_TAUSENDER = re.compile(r"([0-9]),([0-9]{3})(?![0-9])")


def richtung_aus_text(titel: str, beschreibung: str) -> str:
    """'bullish' | 'bearish' | 'neutral' — Schlagwortzählung auf Titel+Text."""
    text = f"{titel} {titel} {beschreibung}"  # Titel doppelt: wiegt schwerer
    auf = len(_BULLISH.findall(text))
    ab = len(_BEARISH.findall(text))
    if auf > ab:
        return "bullish"
    if ab > auf:
        return "bearish"
    return "neutral"


def level_cluster(texte: list[str], top: int = 3) -> list[dict]:
    """Häufigste 4-stellige Kursmarken, gerundet auf 10er-Cluster.
    Tausender-Kommas ("4,230") werden vorher zu "4230" normalisiert."""
    zaehler: Counter[int] = Counter()
    for text in texte:
        normalisiert = _TAUSENDER.sub(r"\1\2", text)
        for m in _LEVEL.finditer(normalisiert):
            cluster = int(m.group(1)) // 10 * 10
            if 1000 <= cluster <= 9990:
                zaehler[cluster] += 1
    return [{"level": lvl, "nennungen": n} for lvl, n in zaehler.most_common(top)]


def tradingview_konsens(settings: dict) -> dict:
    feed = parse_rss(_hole_feed(
        "https://www.tradingview.com/feed/?symbol=OANDA:XAUUSD", settings),
        "tradingview")
    richtungen = [richtung_aus_text(i["titel"], i["zusammenfassung"]) for i in feed]
    zaehler = Counter(richtungen)
    n = len(richtungen) or 1
    lange = zaehler.get("bullish", 0)
    kurze = zaehler.get("bearish", 0)
    anteil_lange = lange / n
    anteil_kurze = kurze / n
    return {
        "ok": True, "items": len(feed),
        "long": lange, "short": kurze, "neutral": zaehler.get("neutral", 0),
        "anteil_long_pct": round(anteil_lange * 100, 1),
        "anteil_short_pct": round(anteil_kurze * 100, 1),
        "levels": level_cluster([f'{i["titel"]} {i["zusammenfassung"]}' for i in feed]),
        "retail_extrem": anteil_lange >= 0.7 or anteil_kurze >= 0.7,
        "beispiele": [i["titel"] for i in feed[:5]],
    }


def analysten_sentiment(settings: dict) -> dict:
    """FXStreet Analysis + FXEmpire Forecasts: nur Gold-Relevante zählen."""
    from .news import gold_relevanz
    artikel: list[dict] = []
    for name, url in (
        ("fxstreet_analysis", "https://www.fxstreet.com/rss/analysis"),
        ("fxempire_forecasts", "https://www.fxempire.com/api/v1/en/articles/rss/forecasts"),
    ):
        try:
            for i in parse_rss(_hole_feed(url, settings), name):
                if gold_relevanz(i["titel"], i["zusammenfassung"], i["kategorien"]) >= 2:
                    artikel.append({"quelle": name, "titel": i["titel"],
                                    "richtung": richtung_aus_text(
                                        i["titel"], i["zusammenfassung"])})
        except Exception:
            continue  # Quelle darf fehlen — die andere zählt weiter
        time.sleep(0.8)
    zaehler = Counter(a["richtung"] for a in artikel)
    n = len(artikel) or 1
    return {
        "ok": bool(artikel), "artikel": len(artikel),
        "bullish": zaehler.get("bullish", 0),
        "bearish": zaehler.get("bearish", 0),
        "neutral": zaehler.get("neutral", 0),
        "anteil_bullish_pct": round(zaehler.get("bullish", 0) / n * 100, 1),
    }


def kitco_survey(settings: dict) -> dict | None:
    """Kitco Weekly Survey: Prozentangaben im HTML suchen (Best-Effort).
    Rückgabe None, wenn die Seite sich nicht parsen lässt (häufig geändert)."""
    try:
        ua = config.user_agent(settings.get("kontakt_fuer_useragent", ""))
        r = requests.get(
            "https://www.kitco.com/news/category/weekly-gold-survey",
            headers={"User-Agent": ua, "Accept": "text/html,*/*"}, timeout=20)
        r.raise_for_status()
    except Exception:
        return None
    html = re.sub(r"<[^>]+>", " ", r.text)
    html = re.sub(r"\s+", " ", html)
    fund = {}
    for wort in ("bullish", "bearish", "neutral"):
        m = re.search(rf"(\d{{1,3}})\s*(?:%|percent|procent)\s*(?:of\s*(?:the\s*)?\w+\s*)?"
                      rf"(?:are\s*|is\s*|said\s*)?{wort}", html, re.I)
        if not m:
            m = re.search(rf"{wort}[^0-9%]{{0,40}}?(\d{{1,3}})\s*(?:%|percent)", html, re.I)
        if m:
            wert = int(m.group(1))
            if 0 <= wert <= 100:
                fund[wort] = wert
    if len(fund) < 2:
        return None
    return {"ok": True, **fund, "quelle": "kitco_weekly_gold_survey"}


def sammle_community(settings: dict) -> dict:
    """Alle Community-Quellen (jede einzeln fehler-tolerant) + Gesamt-Konsens."""
    ergebnis: dict = {"quellen": {}}
    try:
        ergebnis["quellen"]["tradingview"] = tradingview_konsens(settings)
    except Exception as exc:
        ergebnis["quellen"]["tradingview"] = {"ok": False,
                                              "fehler": f"{type(exc).__name__}: {exc}"}
    time.sleep(0.8)
    try:
        ergebnis["quellen"]["analysten"] = analysten_sentiment(settings)
    except Exception as exc:
        ergebnis["quellen"]["analysten"] = {"ok": False,
                                            "fehler": f"{type(exc).__name__}: {exc}"}
    try:
        ergebnis["quellen"]["kitco"] = kitco_survey(settings)
    except Exception as exc:
        ergebnis["quellen"]["kitco"] = None

    tv = ergebnis["quellen"]["tradingview"]
    an = ergebnis["quellen"]["analysten"]
    konsens = "neutral"
    if tv.get("ok") and an.get("ok"):
        # Konsens = Mehrheit unter Ideas UND Analysten; Kontra-Flag bei Retail-Extrem
        tv_seite = ("bullish" if tv["anteil_long_pct"] > tv["anteil_short_pct"] + 10
                    else "bearish" if tv["anteil_short_pct"] > tv["anteil_long_pct"] + 10
                    else "neutral")
        an_seite = ("bullish" if an["anteil_bullish_pct"] > 50
                    else "bearish" if an["bullish"] > 0 and an["bearish"] > an["bullish"]
                    else "neutral")
        konsens = tv_seite if tv_seite == an_seite else "neutral"
    ergebnis["konsens"] = konsens
    ergebnis["retail_kontra_flag"] = bool(tv.get("retail_extrem"))
    ergebnis["ok"] = bool(tv.get("ok") or an.get("ok"))
    return ergebnis
