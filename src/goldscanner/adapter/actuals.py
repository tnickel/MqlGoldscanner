"""Ist-Werte (Actuals) — zwei Wege (Konzept §1.3/§7.1):

1. PRIMÄR: MQL5-Exporter `mql5/CalendarExport.mq5` — offiziell, historisch,
   mit Actual/Forecast/Previous. Das Skript schreibt in den gemeinsamen
   Dateien-Ordner aller Terminals (FILE_COMMON), dieser Finder liest ihn.
2. Fallback (S3): Nasdaq-JSON für einzelne Tage (liefert actual+consensus;
   robots.txt sperrt /api/ → ToS-grau, nur wenige gezielte Abrufe/Tag).

Actuals werden NACHGETRAGEN (actual_first bleibt der Ersteintrag — Point-in-time)."""
from __future__ import annotations

import csv
import os
from datetime import date, timedelta
from pathlib import Path

import requests

from .. import config
from ..db import Db, _titel_normalisiert

CSV_NAME = "goldscanner_calendar.csv"


def mt5_csv_pfade() -> list[Path]:
    """Kandidaten für den Common-Files-Ordner (FILE_COMMON aller Terminals)."""
    appdata = os.environ.get("APPDATA", "")
    kandidaten = []
    if appdata:
        kandidaten.append(Path(appdata) / "MetaQuotes" / "Terminal" / "Common" / "Files" / CSV_NAME)
    lokal = os.environ.get("LOCALAPPDATA", "")
    if lokal:
        kandidaten.append(Path(lokal) / "MetaQuotes" / "Terminal" / "Common" / "Files" / CSV_NAME)
    return [p for p in kandidaten if p.exists()]


def mt5_actuals_einlesen(db: Db) -> dict:
    """Liest die neueste Exporter-CSV und trägt Actuals nach (falls vorhanden)."""
    pfade = mt5_csv_pfade()
    if not pfade:
        return {"ok": False, "grund": "Kein Exporter-CSV gefunden — CalendarExport.mq5 "
                                       "einmal im Terminal ausführen (siehe mql5/README)."}
    pfad = max(pfade, key=lambda p: p.stat().st_mtime)
    actuals: dict[tuple[str, str], str] = {}
    von = (date.today() - timedelta(days=800)).isoformat()
    bis = (date.today() + timedelta(days=60)).isoformat()
    with pfad.open(encoding="utf-8-sig", newline="") as handle:
        for zeile in csv.DictReader(handle, delimiter=";"):
            if zeile.get("actual", "") in ("", None):
                continue
            d = (zeile.get("date") or "")[:10].replace(".", "-")   # 2026.09.23 → ISO
            if not d:
                continue
            schluessel = (d, _titel_normalisiert(zeile.get("event", "")))
            actuals.setdefault(schluessel, zeile["actual"].strip())
    geaendert = db.actual_nachziehen("mt5", von, bis, actuals)
    return {"ok": True, "datei": str(pfad), "actuals": len(actuals),
            "nachgetragen": geaendert}


def nasdaq_actuals_tag(datum: date, settings: dict) -> dict[str, str]:
    """Actuals EINES Tages über den inoffiziellen Nasdaq-JSON-Endpunkt
    (Fallback). Rückgabe: titel-normalisiert → actual-Wert."""
    url = f"https://api.nasdaq.com/api/calendar/economicevents?date={datum.isoformat()}"
    header = {
        "User-Agent": config.user_agent(settings.get("kontakt_fuer_useragent", "")),
        "Accept": "application/json",
    }
    antwort = requests.get(url, headers=header, timeout=20)
    antwort.raise_for_status()
    daten = antwort.json().get("data", {}) or {}
    roh = daten.get("rows", []) or []
    actuals: dict[str, str] = {}
    for e in roh:
        if (e.get("country") or "").strip().lower() != "united states":
            continue
        wert = (e.get("actual") or "").strip()
        if wert:
            actuals[_titel_normalisiert(e.get("eventName", ""))] = wert
    return actuals


def nasdaq_actuals_nachtragen(db: Db, settings: dict,
                              tage: list[date] | None = None) -> dict:
    """Trägt Actuals für die letzten Werktage nach (Standard: heute + gestern).
    Höflich: max. 3 gezielte Abrufe."""
    tage = tage or [date.today(), date.today() - timedelta(days=1)]
    gesamt = 0
    fehler: list[str] = []
    for d in tage[:3]:
        try:
            actuals = nasdaq_actuals_tag(d, settings)
            gesamt += db.actual_nachziehen(
                "nasdaq", d.isoformat(), d.isoformat(),
                {(d.isoformat(), titel): wert for titel, wert in actuals.items()})
        except Exception as exc:
            fehler.append(f"{d}: {type(exc).__name__}")
    return {"ok": not fehler, "nachgetragen": gesamt, "fehler": fehler}
