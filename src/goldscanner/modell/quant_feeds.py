"""Quant-Feeds (S3): implizite Volatilität.

- GVZ-Historie (Cboe CSV, seit 2009): 30-Tage-IV aus GLD-Optionen — das
  Backtest-Feature (verifizierte URL aus dem Konzept §7.4).
- iv30 aktuell (GLD-Options-JSON): nur gegenwärtiger Wert, für die Live-Matrix.
Beides wird in quant_series gespeichert (schluessel 'gvz'/'iv30') und von der
Matrix als letzte VERFÜGBARE Beobachtung VOR dem Zieltag gelesen (kein Look-ahead).
"""
from __future__ import annotations

import csv
import io
from datetime import date

import requests

from .. import config
from ..db import Db

GVZ_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv"
GLD_OPTIONS_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/GLD.json"


def parse_gvz_csv(text: str) -> dict[str, float]:
    """Echtes Format: 'DATE,GVZ\\n09/22/2026,23.590000' → {'2026-09-22': 23.59}.
    Die letzte Spalte gewinnt (robust, falls OHLC-Varianten auftauchen)."""
    werte: dict[str, float] = {}
    for zeile in csv.reader(io.StringIO(text)):
        if len(zeile) < 2 or zeile[0].strip().upper() == "DATE":
            continue
        try:
            monat, tag, jahr = zeile[0].split("/")
            d = date(int(jahr), int(monat), int(tag))
            werte[d.isoformat()] = float(zeile[-1])
        except (ValueError, IndexError):
            continue
    return werte


def gvz_aktualisieren(db: Db, settings: dict) -> dict:
    """Lädt die GVZ-Historie einmal, speichert Roh-Snapshot (Hash-Dedup)
    und upsertet die Serie. Rückgabe: Status."""
    ua = config.user_agent(settings.get("kontakt_fuer_useragent", ""))
    antwort = requests.get(GVZ_URL, timeout=30, headers={"User-Agent": ua})
    antwort.raise_for_status()
    neu_snapshot = db.snapshot_speichern("gvz", antwort.text)
    serie = parse_gvz_csv(antwort.text)
    db.quant_speichern("gvz", serie)
    return {"ok": True, "werte": len(serie), "snapshot_neu": neu_snapshot,
            "letzter_tag": max(serie) if serie else None}


def iv30_aktuell(settings: dict) -> float | None:
    """Aktueller iv30 aus dem GLD-Options-JSON (15 min verzögert)."""
    ua = config.user_agent(settings.get("kontakt_fuer_useragent", ""))
    antwort = requests.get(GLD_OPTIONS_URL, timeout=30,
                           headers={"User-Agent": ua, "Accept": "application/json"})
    antwort.raise_for_status()
    daten = antwort.json().get("data", {}) or {}
    iv = daten.get("iv30")
    return float(iv) if iv is not None else None


def gvz_vor(db: Db, ziel_datum: str) -> float | None:
    """Letzter GVZ-Wert STRENG vor dem Ziel-Datum (t−1-Information)."""
    serie = db.quant_laden("gvz")
    fruehere = [tag for tag in serie if tag < ziel_datum]
    return serie[max(fruehere)] if fruehere else None
