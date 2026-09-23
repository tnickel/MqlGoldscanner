# -*- coding: utf-8 -*-
"""Quellen-Launch-Check (Stufe 1): Erreichbarkeit der geplanten Kern-URLs
(Konzept §7) mit dem EHRLICHEN User-Agent — der erste Wächter-Baustein.

Wächter-Prinzip: HTTP 200 beweist nichts — erwartet wird auch der passende
Content-Type ODER eine Inhalts-Signatur (JSON beginnt mit { bzw. [, ICS mit
BEGIN:VCALENDAR, RSS mit <, CSV enthält Komma+Zeilenumbruch, XLSX = ZIP 'PK').
"""
from __future__ import annotations

import time

import requests

from . import config


def katalog() -> list[dict]:
    """Kernquellen aus dem Konzept §7 (am 23.09.2026 verifiziert)."""
    return [
        # Block 1 — Kalender & Termine
        {"name": "ForexFactory Woche (JSON)", "url": "https://nfs.faireconomy.media/ff_calendar_thisweek.json", "kategorie": "Kalender", "erwartet": "json", "nur_kopf": False},
        {"name": "BLS Release-Kalender (ICS)", "url": "https://www.bls.gov/schedule/news_release/bls.ics", "kategorie": "Kalender", "erwartet": "ics", "nur_kopf": False},
        {"name": "BEA Release-Kalender (ICS)", "url": "https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics", "kategorie": "Kalender", "erwartet": "ics", "nur_kopf": False},
        {"name": "Fed Terminkalender (JSON)", "url": "https://www.federalreserve.gov/json/calendar.json", "kategorie": "Kalender", "erwartet": "json", "nur_kopf": False},
        {"name": "TreasuryDirect Auktionen (JSON)", "url": "https://www.treasurydirect.gov/TA_WS/securities/announced?format=json", "kategorie": "Kalender", "erwartet": "json", "nur_kopf": False},
        # Block 4 — Quant
        {"name": "Cboe GVZ-Historie (CSV)", "url": "https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv", "kategorie": "Quant", "erwartet": "csv", "nur_kopf": False},
        {"name": "FRED Realzins DFII10 (CSV)", "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10", "kategorie": "Quant", "erwartet": "csv", "nur_kopf": False},
        {"name": "CFTC COT Gold 088691 (JSON)", "url": "https://publicreporting.cftc.gov/resource/6dca-aqww.json?cftc_contract_market_code=088691&%24limit=1", "kategorie": "Quant", "erwartet": "json", "nur_kopf": False},
        {"name": "LBMA Gold PM (JSON)", "url": "https://prices.lbma.org.uk/json/gold_pm.json", "kategorie": "Quant", "erwartet": "json", "nur_kopf": False},
        {"name": "SPDR GLD Archiv (XLSX)", "url": "https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en", "kategorie": "Quant", "erwartet": "xlsx", "nur_kopf": True},
        # Block 2/3 — News & Community
        {"name": "FXStreet RSS News", "url": "https://www.fxstreet.com/rss/news", "kategorie": "News", "erwartet": "xml", "nur_kopf": False},
        {"name": "Google News RSS (EN)", "url": "https://news.google.com/rss/search?q=gold+price+when:7d&hl=en-US&gl=US&ceid=US:en", "kategorie": "News", "erwartet": "xml", "nur_kopf": False},
        {"name": "Bing News RSS", "url": "https://www.bing.com/news/search?q=gold+price&format=rss", "kategorie": "News", "erwartet": "xml", "nur_kopf": False},
        {"name": "ActionForex Gold Feed", "url": "https://www.actionforex.com/tag/gold/feed/", "kategorie": "Community", "erwartet": "xml", "nur_kopf": False},
        {"name": "Goldreporter (DE)", "url": "https://www.goldreporter.de/feed/", "kategorie": "Community", "erwartet": "xml", "nur_kopf": False},
        {"name": "GOLD.DE RSS", "url": "https://www.gold.de/rss.php", "kategorie": "Community", "erwartet": "xml", "nur_kopf": False},
    ]


def _typ_passt(erwartet: str, content_type: str) -> bool:
    ct = (content_type or "").lower()
    return {
        "json": lambda: "json" in ct,
        "csv": lambda: any(x in ct for x in ("csv", "octet-stream", "text/plain")),
        "ics": lambda: "calendar" in ct or "text/plain" in ct,
        "xml": lambda: "xml" in ct or "rss" in ct,
        "xlsx": lambda: any(x in ct for x in ("octet-stream", "excel", "spreadsheet")),
    }.get(erwartet, lambda: True)()


def _signatur_passt(erwartet: str, anfang: bytes) -> bool:
    text = anfang[:256].decode("utf-8", errors="ignore").lstrip()
    return {
        "json": lambda: text.startswith(("{", "[")),
        "csv": lambda: "," in text and "\n" in text,
        "ics": lambda: text.startswith("BEGIN:VCALENDAR"),
        "xml": lambda: text.startswith("<"),
        "xlsx": lambda: anfang[:2] == b"PK",
    }.get(erwartet, lambda: False)()


def _bewerte(eintrag: dict, status: int, content_type: str, groesse: int,
             anfang: bytes, dauer_ms: int, fehler: str | None) -> dict:
    if fehler:
        return {**eintrag, "status": 0, "content_type": "", "groesse": 0,
                "dauer_ms": dauer_ms, "ok": False, "hinweis": f"Transportfehler: {fehler}"}
    if status != 200:
        hinweis = {401: "blockiert (401 — Rechte/ToS?)", 403: "blockiert (403 — Bot-Schutz?)",
                   429: "Drosselung (429) — seltener abfragen",
                   404: "nicht gefunden (404) — Quelle prüfen"}.get(
                       status, f"HTTP {status}")
        return {**eintrag, "status": status, "content_type": content_type,
                "groesse": groesse, "dauer_ms": dauer_ms, "ok": False, "hinweis": hinweis}
    typ_ok = _typ_passt(eintrag["erwartet"], content_type)
    signatur_ok = _signatur_passt(eintrag["erwartet"], anfang)
    if typ_ok or signatur_ok:
        return {**eintrag, "status": status, "content_type": content_type,
                "groesse": groesse, "dauer_ms": dauer_ms, "ok": True,
                "hinweis": "OK (" + (content_type or "?").split(";")[0] + ")"}
    return {**eintrag, "status": status, "content_type": content_type,
            "groesse": groesse, "dauer_ms": dauer_ms, "ok": False,
            "hinweis": f"Format verdächtig: erwarte {eintrag['erwartet']}, "
                       f"erhalten {content_type or 'unbekannt'} — 200 allein beweist nichts"}


def pruefen(settings: dict, je_quelle=None) -> list[dict]:
    """Prüft sequenziell (höflich: 0,8 s Abstand). Rückgabe: Liste Ergebnisse."""
    ua = config.user_agent(settings.get("kontakt_fuer_useragent", ""))
    ergebnisse: list[dict] = []
    for eintrag in katalog():
        start = time.monotonic()
        try:
            if eintrag.get("nur_kopf"):
                antwort = requests.head(eintrag["url"], timeout=20,
                                        headers={"User-Agent": ua}, allow_redirects=True)
                e = _bewerte(eintrag, antwort.status_code,
                             antwort.headers.get("Content-Type", ""),
                             int(antwort.headers.get("Content-Length") or 0),
                             b"", int((time.monotonic() - start) * 1000), None)
                if e["ok"]:
                    e["hinweis"] = "OK (nur Kopf geprüft)"
            else:
                antwort = requests.get(eintrag["url"], timeout=25,
                                       headers={"User-Agent": ua}, stream=True)
                anfang = b""
                with antwort:
                    anfang = antwort.raw.read(16 * 1024, decode_content=True)
                e = _bewerte(eintrag, antwort.status_code,
                             antwort.headers.get("Content-Type", ""),
                             int(antwort.headers.get("Content-Length") or len(anfang)),
                             anfang, int((time.monotonic() - start) * 1000), None)
        except requests.RequestException as exc:
            e = _bewerte(eintrag, 0, "", 0, b"", int((time.monotonic() - start) * 1000),
                         f"{type(exc).__name__}: {str(exc)[:120]}")
        ergebnisse.append(e)
        if je_quelle:
            je_quelle(e)
        time.sleep(0.8)   # höflicher Abstand, kein Hammering
    return ergebnisse
