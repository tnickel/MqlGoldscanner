"""News-Adapter (S4): Gold-relevante RSS-Feeds → news_items (Delta-Prinzip).

Konzept §7.2 (live verifiziert 23.09.2026, ehrlicher UA, je 1 Abruf):
- FXStreet news/analysis (30 Items; Cloudflare-empfindlich → höflich bleiben)
- Google-News-RSS EN/DE (100 Items, Links sind Redirects, Publisher im
  <source>-Tag bzw. Titelsuffix " - Publisher")
- Bing-News-RSS (wenige Items, direkte Links)
- FXEmpire news/forecasts (20 Items mit reichen Kategorien)
- Investing Commodities-RSS (10 Items)
- Nasdaq-Feed im Probejahr 2026: ReadTimeout → bewusst NICHT dabei.

Jedes Item bekommt einen SHA-256-Dedup-Hash (Quelle + normierter Titel);
unveränderte Items werden nie erneut destilliert (Token-Delta-Prinzip).
Der Analytiker liest ausschließlich aus der DB, nie live (Konzept §4).
"""
from __future__ import annotations

import hashlib
import html as html_mod
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from .. import config

# (id, url) — Reihenfolge = Abrufreihenfolge; art nur zur Info im Journal
QUELLEN: list[tuple[str, str]] = [
    ("fxstreet_news", "https://www.fxstreet.com/rss/news"),
    ("fxstreet_analysis", "https://www.fxstreet.com/rss/analysis"),
    ("google_news_en",
     "https://news.google.com/rss/search?q=gold+price+when:7d&hl=en-US&gl=US&ceid=US:en"),
    ("google_news_de",
     "https://news.google.com/rss/search?q=goldpreis+when:7d&hl=de&gl=DE&ceid=DE:de"),
    ("bing_news", "https://www.bing.com/news/search?q=gold+price&format=rss"),
    ("fxempire_news", "https://www.fxempire.com/api/v1/en/articles/rss/news"),
    ("fxempire_forecasts", "https://www.fxempire.com/api/v1/en/articles/rss/forecasts"),
    ("investing_commodities", "https://www.investing.com/rss/news_11.rss"),
]

# Gold-Relevanz: 3 = Gold direkt, 2 = Makro-Treiber (Fed/Dollar/Zins), 1 = Kontext
_STARK = re.compile(r"\bgold\b|goldpreis|xau|bullion|goldbarren", re.I)
_TREIBER = re.compile(
    r"\bfed\b|fomc|powell|dollar|\bdxy\b|treasury|yields?|inflation|\bcpi\b|\bpce\b|"
    r"\bnfp\b|payroll|jobless|rate[ -](hike|cut)|interest rate|safe[ -]?haven|"
    r"central bank|geopolit|\bgld\b|etf flows?", re.I)


def gold_relevanz(titel: str, beschreibung: str = "", kategorien: str = "") -> int:
    if _STARK.search(titel) or _STARK.search(kategorien):
        return 3
    if _STARK.search(beschreibung) or _TREIBER.search(titel):
        return 2
    if _TREIBER.search(beschreibung):
        return 1
    return 0


_TAG_RE = re.compile(r"<[^>]+>")
_LEER_RE = re.compile(r"\s+")


def _text_bereinigt(roh: str | None) -> str:
    """HTML-Tags raus, Entities dekodieren, Whitespace normalisieren."""
    if not roh:
        return ""
    ohne_tags = _TAG_RE.sub(" ", roh)
    dekodiert = html_mod.unescape(ohne_tags)
    return _LEER_RE.sub(" ", dekodiert).strip()


def _hash(quelle: str, titel: str, url: str) -> str:
    norm_titel = _LEER_RE.sub(" ", titel or "").strip().lower()
    norm_url = (url or "").split("?")[0].rstrip("/")
    return hashlib.sha256(f"{quelle}|{norm_titel}|{norm_url}".encode("utf-8")).hexdigest()


def _pubdate_iso(roh: str | None) -> str | None:
    if not roh:
        return None
    try:
        dt = parsedate_to_datetime(roh)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_rss(inhalt: str, quelle: str) -> list[dict]:
    """RSS-2.0 → Liste normalisierter Items (titel, link, beschreibung,
    autor, veroeffentlicht, publisher, kategorien)."""
    root = ET.fromstring(inhalt)
    items: list[dict] = []
    for it in root.findall(".//item"):
        titel = _text_bereinigt(it.findtext("title"))
        if not titel:
            continue
        link = (it.findtext("link") or "").strip()
        beschreibung = _text_bereinigt(it.findtext("description"))[:400]
        publisher = _text_bereinigt(it.findtext("source")) or ""
        if not publisher and " - " in titel:
            # Google-News-Muster: "Überschrift - Publisher"
            publisher = titel.rsplit(" - ", 1)[-1].strip()
        items.append({
            "quelle": quelle,
            "titel": titel,
            "url": link,
            "zusammenfassung": beschreibung,
            "autor": _text_bereinigt(it.findtext("creator")) or None,
            "veroeffentlicht": _pubdate_iso(it.findtext("pubDate")),
            "publisher": publisher,
            "kategorien": ", ".join(filter(None, [
                _text_bereinigt(c.text) for c in it.findall("category")]))[:200],
        })
    return items


def _hole_feed(url: str, settings: dict, timeout: int = 25) -> str:
    ua = config.user_agent(settings.get("kontakt_fuer_useragent", ""))
    r = requests.get(url, headers={
        "User-Agent": ua,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }, timeout=timeout)
    r.raise_for_status()
    if "<rss" not in r.text[:600] and "<feed" not in r.text[:600]:
        raise ValueError("Antwort ist kein RSS/XML (evtl. Block-/Fehlerseite)")
    return r.text


def sammle_news(db, settings: dict) -> dict:
    """Alle Feeds einmal abrufen, Gold-Filter, Fensterfilter, in DB legen.
    Rückgabe: Protokoll {ok, quellen: {id: {ok, items, gold, neu, fehler?}}}."""
    fenster_tage = int(settings.get("news_fenster_tage", 7))
    abstand = max(0.8, float(settings.get("rate_min_interval_s", 2.0)) * 0.4)
    grenze = datetime.now(timezone.utc) - timedelta(days=fenster_tage)
    protokoll: dict = {"ok": True, "neu": 0, "quellen": {}}
    for name, url in QUELLEN:
        eintrag: dict = {"ok": False, "items": 0, "gold": 0, "neu": 0}
        try:
            items = parse_rss(_hole_feed(url, settings), name)
            eintrag["items"] = len(items)
            frisch = []
            for i in items:
                rel = gold_relevanz(i["titel"], i["zusammenfassung"], i["kategorien"])
                if rel <= 0:
                    continue
                veroeffentlicht = i.get("veroeffentlicht")
                if veroeffentlicht:
                    try:
                        dt = datetime.fromisoformat(veroeffentlicht)
                        if dt < grenze:
                            continue
                    except ValueError:
                        pass
                frisch.append({
                    "quelle": name, "url": i["url"], "titel": i["titel"],
                    "autor": i["autor"], "veroeffentlicht": veroeffentlicht,
                    "dedup_hash": _hash(name, i["titel"], i["url"]),
                    "gold_relevanz": rel, "zusammenfassung": i["zusammenfassung"],
                })
            eintrag["gold"] = len(frisch)
            eintrag["neu"] = db.news_speichern(frisch)
            eintrag["ok"] = True
        except Exception as exc:
            eintrag["fehler"] = f"{type(exc).__name__}: {exc}"
            protokoll["ok"] = False
        protokoll["quellen"][name] = eintrag
        protokoll["neu"] += eintrag["neu"]
        time.sleep(abstand)
    return protokoll
