"""Kalender-Adapter (S2): Wirtschafts- und Spezialtermine aus offiziellen,
maschinenlesbaren Quellen — jeder Abruf landet als Roh-Snapshot in der DB
(Hash-Dedup = Point-in-time-Archiv), geparst wird ausschließlich aus dem
Snapshot. Der Analytiker liest nie live (Konzept §4).

Quellen (Konzept §7.1, verifiziert 23.09.2026):
- ForexFactory thisweek-JSON  (keine Actuals! — dafür Nasdaq/MT5 später)
- BLS Release-Kalender (ICS)   — NFP/CPI/PPI/JOLTS mit exakter Uhrzeit
- BEA Release-Kalender (ICS)   — GDP/PCE
- Fed calendar.json (BOM!) + Termine — FOMC/Minutes/Reden (inoffizieller
  Endpunkt auf offizieller Domain, von der Fed-Website selbst genutzt)
- TreasuryDirect announced (JSON) — Auktionen 2y–30y

Alles wird nach UTC normalisiert (Quell-Zeitzone bleibt in der Quelle
erhalten); Sommerzeit über zoneinfo. Dedup gegen andere Quellen passiert
beim LESEN (dedup_ereignisse), jede Quelle ersetzt ihr eigenes Fenster
idempotent (Delete+Insert).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from .. import config
from ..db import Db

BERLIN = ZoneInfo("Europe/Berlin")
NEW_YORK = ZoneInfo("America/New_York")

# Priorität beim Dedup (kleiner = gewinnt): FF vor BLS/BEA vor Fed vor Treasury
PRIO_FF, PRIO_BLS, PRIO_BEA, PRIO_FED, PRIO_TREASURY, PRIO_REGEL = 1, 2, 2, 3, 4, 6

# Gold-Relevanz-Klassen: (regex auf Titel, Klasse, Wichtigkeit 1-3, Gold-Relevanz 0-5)
_KLASSEN: list[tuple[str, str, int, int]] = [
    (r"non[- ]?farm|nfp|employment situation", "nfp", 3, 5),
    (r"\bcpi\b|consumer price", "cpi", 3, 5),
    (r"\bpce\b|personal income and outlays", "pce", 3, 5),
    (r"fomc|federal open market|federal funds rate|interest rate decision", "fomc", 3, 5),
    (r"\badp\b", "adp", 2, 4),
    (r"\bgdp\b|gross domestic", "gdp", 3, 4),
    (r"\bppi\b|producer price", "ppi", 2, 4),
    (r"retail sales", "retail_sales", 2, 4),
    (r"\bism\b", "ism", 2, 4),
    (r"powell|chair (of the board|powell)", "fed_rede", 2, 4),
    (r"jobless claims|initial claims|unemployment claims", "claims", 2, 3),
    (r"durable goods", "durable_goods", 2, 3),
    (r"consumer confidence|consumer sentiment", "konsumstimmung", 2, 3),
    (r"jolts", "jolts", 1, 3),
    (r"\becb\b|european central bank", "ezb", 2, 3),
    (r"speech|testimony|remarks|hearing", "rede", 1, 2),
    (r"minutes", "minutes", 2, 3),
    (r"treasury|auction", "auktion", 1, 2),
    (r"gold|xau", "gold_sonstiges", 1, 3),
]


def klassifiziere(titel: str) -> tuple[str, int, int]:
    """(klasse, wichtigkeit, gold_relevanz) — Fallback 'sonstiges', 1, 1."""
    t = (titel or "").lower()
    for muster, klasse, wichtigkeit, relevanz in _KLASSEN:
        if re.search(muster, t):
            return klasse, wichtigkeit, relevanz
    return "sonstiges", 1, 1


def _event(quelle: str, prio: int, zeit_utc: datetime | None, datum_iso: str,
           titel: str, waehrung: str = "USD", forecast: str = "",
           previous: str = "", actual: str = "") -> dict:
    klasse, wichtigkeit, relevanz = klassifiziere(titel)
    return {
        "quelle": quelle, "prioritaet": prio,
        "zeit_utc": zeit_utc.astimezone(timezone.utc).isoformat() if zeit_utc else None,
        "datum": datum_iso, "titel": titel,
        "klasse": klasse, "wichtigkeit": wichtigkeit, "gold_relevanz": relevanz,
        "waehrung": waehrung, "forecast": forecast or None,
        "previous": previous or None, "actual": actual or None,
    }


# ── ICS-Parsing (BLS/BEA) ────────────────────────────────────────────────

def ics_events(text: str, quelle: str, prio: int) -> list[dict]:
    """Parst VEVENT-Blöcke: SUMMARY + DTSTART (TZID/UTC/date-only).
    TZID 'US-Eastern' wird auf America/New_York gemappt."""
    entfaltet: list[str] = []
    for zeile in text.splitlines():
        if zeile.startswith((" ", "\t")) and entfaltet:
            entfaltet[-1] += zeile[1:]
        else:
            entfaltet.append(zeile)
    events: list[dict] = []
    summary = dtstart = None
    for zeile in entfaltet:
        if zeile == "BEGIN:VEVENT":
            summary, dtstart = None, None
        elif zeile.startswith("SUMMARY:"):
            summary = zeile[8:].strip()
        elif zeile.startswith("DTSTART"):
            dtstart = zeile.split(":", 1)[1].strip()
            params = zeile.split(":", 1)[0].split(";", 1)[1] if ";" in zeile else ""
            dtstart = (dtstart, params)
        elif zeile == "END:VEVENT" and summary and dtstart:
            wert, params = dtstart
            tz_name = ""
            for teil in params.split(";"):
                if teil.startswith("TZID="):
                    tz_name = teil[5:].strip()
            tz = NEW_YORK if tz_name in ("US-Eastern", "America/New_York") else None
            if re.fullmatch(r"\d{8}", wert):                      # Ganztägig
                d = date(int(wert[:4]), int(wert[4:6]), int(wert[6:8]))
                events.append(_event(quelle, prio, None, d.isoformat(), summary))
            elif wert.endswith("Z"):
                dt = datetime.strptime(wert, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                events.append(_event(quelle, prio, dt, dt.date().isoformat(), summary))
            else:
                naive = datetime.strptime(wert, "%Y%m%dT%H%M%S")
                dt = naive.replace(tzinfo=tz or NEW_YORK)
                events.append(_event(quelle, prio, dt, dt.date().isoformat(), summary))
    return events


# ── ForexFactory ─────────────────────────────────────────────────────────

def ff_events(text: str) -> list[dict]:
    """ff_calendar_thisweek.json — Felder title/country/date/impact/forecast/
    previous. KEIN actual (Deep-Research-Befund). Behalten: USD komplett,
    andere Währungen nur bei High Impact."""
    import json
    roh = json.loads(text)
    events: list[dict] = []
    for e in roh:
        waehrung = e.get("country", "").strip()
        impact = e.get("impact", "Low")
        if waehrung != "USD" and not (waehrung in ("EUR", "GBP", "JPY", "CNY")
                                      and impact == "High"):
            continue
        try:
            zeit = datetime.fromisoformat(e["date"])            # mit Offset
        except (KeyError, ValueError):
            continue
        events.append(_event("ff", PRIO_FF, zeit, zeit.date().isoformat(),
                             e.get("title", ""), waehrung,
                             str(e.get("forecast", "") or ""),
                             str(e.get("previous", "") or "")))
    return events


# ── Fed calendar.json ────────────────────────────────────────────────────

def fed_events(text: str) -> list[dict]:
    """Inoffizieller JSON-Endpunkt der Fed-Website (BOM entfernen!).
    Entries: title/month('2026-09')/days('23' oder '27-28')/time('10:05 a.m.'|'')."""
    import json
    if text.startswith("﻿"):
        text = text[1:]
    daten = json.loads(text)
    events: list[dict] = []
    for e in daten.get("events", []):
        titel = (e.get("title") or "").strip()
        monat = e.get("month", "")
        days = str(e.get("days", "")).strip()
        zeit_text = str(e.get("time", "")).strip()
        if not titel or not monat or not days:
            continue
        erster_tag = re.match(r"\d{1,2}", days)
        if not erster_tag:
            continue
        try:
            d = date(int(monat[:4]), int(monat[5:7]), int(erster_tag.group(0)))
        except ValueError:
            continue
        dt = None
        m = re.match(r"(\d{1,2}):(\d{2})\s*([ap])\.?m\.?", zeit_text.lower())
        if m:
            stunde = int(m.group(1)) % 12 + (12 if m.group(3) == "p" else 0)
            dt = datetime(d.year, d.month, d.day, stunde, int(m.group(2)),
                          tzinfo=NEW_YORK)
        events.append(_event("fed", PRIO_FED, dt, d.isoformat(), titel))
    return events


# ── TreasuryDirect ───────────────────────────────────────────────────────

_ERWUENSCHTE_TERMINE = {"2-Year", "5-Year", "7-Year", "10-Year", "20-Year", "30-Year"}


def treasury_events(text: str) -> list[dict]:
    import json
    roh = json.loads(text)
    events: list[dict] = []
    for e in roh:
        typ = e.get("securityType", "")
        term = e.get("securityTerm", "")
        if typ not in ("Note", "Bond") or term not in _ERWUENSCHTE_TERMINE:
            continue                      # Bills/FRN/CMB raus
        d = datetime.fromisoformat(e["auctionDate"]).date()
        # Auktionsuhrzeit term-abhängig → bewusst Ganztages-Termin
        events.append(_event("treasury", PRIO_TREASURY, None, d.isoformat(),
                             f"US-Auktion {term} {typ}"))
    return events


# ── Abruf-Orchestrierung ─────────────────────────────────────────────────

_QUELLEN = [
    # (id, url, accept, parser)
    ("ff", "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
     "application/json", ff_events),
    ("bls", "https://www.bls.gov/schedule/news_release/bls.ics",
     "text/calendar,text/plain,*/*", lambda t: ics_events(t, "bls", PRIO_BLS)),
    ("bea", "https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics",
     "text/calendar,text/plain,*/*", lambda t: ics_events(t, "bea", PRIO_BEA)),
    ("fed", "https://www.federalreserve.gov/json/calendar.json",
     "application/json", fed_events),
    ("treasury", "https://www.treasurydirect.gov/TA_WS/securities/announced?format=json",
     "application/json", treasury_events),
]


def wochenabruf(db: Db, settings: dict) -> dict:
    """Holt alle Kalender-Quellen einmal, archiviert Snapshots (Hash-Dedup),
    parst aus dem Snapshot und ersetzt die Events je Quelle idempotent.
    Rückgabe: Status je Quelle + Gesamtzahl."""
    ua = config.user_agent(settings.get("kontakt_fuer_useragent", ""))
    status: dict[str, dict] = {}
    gesamt = 0
    for quell_id, url, accept, parser in _QUELLEN:
        try:
            antwort = requests.get(url, timeout=25,
                                   headers={"User-Agent": ua, "Accept": accept})
            if antwort.status_code != 200:
                hinweis = f"HTTP {antwort.status_code}"
                if quell_id == "bls" and antwort.status_code == 403:
                    hinweis += (" — BLS verlangt eine Kontakt-Adresse im User-Agent: "
                                "Einstellungen → Netz → Kontakt-Adresse eintragen")
                status[quell_id] = {"ok": False, "hinweis": hinweis}
                continue
            text = antwort.text
            neu = db.snapshot_speichern(quell_id, text)
            events = parser(text)
            db.events_ersetzen(quell_id, events)
            gesamt += len(events)
            status[quell_id] = {"ok": True, "events": len(events),
                                "snapshot_neu": neu}
        except Exception as exc:  # Quelle darf nicht den Lauf killen
            status[quell_id] = {"ok": False,
                                "hinweis": f"{type(exc).__name__}: {str(exc)[:120]}"}
    # Regeltermine für ±5 Wochen auffrischen (idempotent)
    from . import regeltermine
    heute = date.today()
    von, bis = heute - timedelta(days=7), heute + timedelta(days=42)
    db.events_ersetzen("regel", [t.als_event() for t in
                                 regeltermine.alle_regeltermine(von, bis)])
    gesamt += sum(1 for _ in regeltermine.alle_regeltermine(von, bis))
    status["regel"] = {"ok": True}
    return {"ok": all(s.get("ok") for s in status.values()),
            "status": status, "events_gesamt": gesamt}


# ── Leseseite: Dedup über Quellen ───────────────────────────────────────

def _dedup_schluessel(e: dict) -> tuple:
    stunde = e["zeit_utc"][:13] if e.get("zeit_utc") else None
    klasse = e.get("klasse")
    if klasse in ("sonstiges", "rede", "auktion"):
        titel = re.sub(r"[^a-z0-9]+", " ", e["titel"].lower()).strip()
        return (e["datum"], stunde, titel[:40])
    return (e["datum"], stunde, klasse)


def dedup_ereignisse(events: list[dict]) -> list[dict]:
    """Gleiche Termine aus mehreren Quellen zählen einmal — die Quelle mit
    der höchsten Priorität (kleinste Nummer) gewinnt, FF-Events bringen
    Forecast/Previous mit."""
    beste: dict[tuple, dict] = {}
    for e in events:
        schluessel = _dedup_schluessel(e)
        if schluessel not in beste or e["prioritaet"] < beste[schluessel]["prioritaet"]:
            beste[schluessel] = e
    return sorted(beste.values(),
                  key=lambda e: (e["zeit_utc"] or e["datum"],
                                 -(e.get("gold_relevanz") or 0)))
