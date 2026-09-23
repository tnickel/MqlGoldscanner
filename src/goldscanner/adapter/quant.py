# -*- coding: utf-8 -*-
"""Quant-Feed-Adapter (S5, Konzept §7.4): Makro- und Positionierungsdaten.

Alle Feeds sind offiziell und maschinenlesbar (live verifiziert 23.09.2026):
- FRED ohne Key: DFII10 (Realzins 10J — wichtigster Makrotreiber), T10YIE,
  DGS10, DTWEXBGS (breiter Dollar), VIXCLS. Format `observation_date,SERIE`,
  fehlende Werte = "." → werden übersprungen. 1 Tag Verzug → Features nutzen
  nur Werte ≤ t−2 (konservativ, kein Look-ahead).
- CFTC Disaggregated (Socrata 72hh-3qpy, Gold-Code 088691): Managed-Money-
  Nettoposition wöchentlich. **Stichtag ≠ Veröffentlichung** (Dienstag-
  Stichtag, Freitag-Veröffentlichung) → nutzbar erst ab Stichtag+4
  Kalendertage (cot_wert_vor).
- SPDR-GLD-Bestände (NYSE Arca, Tonnen) direkt als XLSX — Weiterverbreitung
  laut ToS untersagt, private Nutzung ok.
- LBMA bewusst nicht dabei: reiner Preis, Broker-Kurse sind besser.

Speicher: quant_series (Tag, Schlüssel) — Upsert, kein Delta-Archiv nötig
(Werte sind endgültig, im Gegensatz zu Kalender-Snapshots).
"""
from __future__ import annotations

import io
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from .. import config

FRED_SERIEN: dict[str, str] = {
    "fred_dfii10": "DFII10",      # Realzins 10J
    "fred_t10yie": "T10YIE",      # Inflations.erwartung
    "fred_dgs10": "DGS10",        # Nominalzins 10J
    "fred_dtwexbgs": "DTWEXBGS",  # breiter Dollar-Index
    "fred_vixcls": "VIXCLS",      # Aktien-Vola (Regime)
}
COT_DATASET = "72hh-3qpy"         # Disaggregated Futures Only
COT_CODE = "088691"               # Gold
GLD_URL = ("https://api.spdrgoldshares.com/api/v1/historical-archive"
           "?product=gld&exchange=NYSE&lang=en")
# Stichtag (Di) → Veröffentlichung (Fr, 15:30 ET) → sicher nutzbar ab +4 Tage
COT_VERFUEGUNG_VERZUG_TAGE = 4


def parse_fred_csv(inhalt: str) -> dict[str, float]:
    """FRED-CSV → {datum_iso: wert}; '.'-Lücken werden übersprungen."""
    werte: dict[str, float] = {}
    zeilen = inhalt.strip().splitlines()
    for zeile in zeilen[1:]:
        teile = zeile.split(",")
        if len(teile) < 2:
            continue
        tag, roh = teile[0].strip(), teile[1].strip()
        if not roh or roh == ".":
            continue
        try:
            werte[tag] = float(roh)
        except ValueError:
            continue
    return werte


def fred_abruf(schluessel: str, serie: str, settings: dict) -> dict[str, float]:
    ua = config.user_agent(settings.get("kontakt_fuer_useragent", ""))
    r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={serie}",
                     headers={"User-Agent": ua, "Accept": "text/csv,*/*"}, timeout=30)
    r.raise_for_status()
    if "observation_date" not in r.text[:200]:
        raise ValueError("FRED-Antwort ist kein erwartetes CSV")
    return parse_fred_csv(r.text)


def parse_cot_json(daten: list[dict]) -> dict[str, float]:
    """CFTC-Socrata-JSON → {stichtag_iso: managed-money-netto}."""
    netto: dict[str, float] = {}
    for z in daten:
        lang = z.get("m_money_positions_long_all")
        kurz = z.get("m_money_positions_short_all")
        stichtag = z.get("report_date_as_yyyy_mm_dd")
        if lang is None or kurz is None or not stichtag:
            continue
        netto[str(stichtag)[:10]] = float(lang) - float(kurz)
    return netto


def cot_abruf(settings: dict) -> dict[str, float]:
    ua = config.user_agent(settings.get("kontakt_fuer_useragent", ""))
    url = (f"https://publicreporting.cftc.gov/resource/{COT_DATASET}.json"
           f"?cftc_contract_market_code={COT_CODE}&$limit=2000"
           f"&$order=report_date_as_yyyy_mm_dd%20DESC")
    r = requests.get(url, headers={"User-Agent": ua,
                                   "Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    daten = r.json()
    if not isinstance(daten, list) or not daten:
        raise ValueError("CFTC-Antwort leer")
    return parse_cot_json(daten)


def cot_wert_vor(netto: dict[str, float], datum: str) -> float | None:
    """Letzter COT-Stichtag, der zum Zeitpunkt `datum` VERÖFFENTLICHT war
    (Stichtag+4 Kalendertage <= datum) — verhindert Look-ahead."""
    grenze = (date.fromisoformat(datum) - timedelta(days=COT_VERFUEGUNG_VERZUG_TAGE)
              ).isoformat()
    beste = None
    for stichtag, wert in netto.items():
        if stichtag <= grenze and (beste is None or stichtag > beste[0]):
            beste = (stichtag, wert)
    return beste[1] if beste else None


def parse_gld_xlsx(inhalt: bytes) -> dict[str, float]:
    """SPDR-XLSX → {datum_iso: tonnen}. Sheet „Historical Archive" wählen
    (erstes Sheet ist ein Disclaimer), Spalten „Date" („18-Nov-2004") und
    „Tonnes of Gold" — tolerant gesucht, das Layout ändert sich gelegentlich."""
    xl = pd.ExcelFile(io.BytesIO(inhalt))
    sheet = next((s for s in xl.sheet_names if "historical" in s.lower()),
                 xl.sheet_names[-1])
    tabelle = xl.parse(sheet)
    tag_spalte = tonnen_spalte = None
    for spalte in tabelle.columns:
        name = str(spalte).strip().lower()
        if tag_spalte is None and name in ("date", "datum"):
            tag_spalte = spalte
        if tonnen_spalte is None and "tonnes" in name:
            tonnen_spalte = spalte
    if tag_spalte is None or tonnen_spalte is None:
        raise ValueError(f"GLD-XLSX-Spalten nicht erkannt: {list(tabelle.columns)[:6]}")
    werte: dict[str, float] = {}
    for _, zeile in tabelle.iterrows():
        tag, wert = zeile[tag_spalte], zeile[tonnen_spalte]
        if pd.isna(wert):
            continue
        if isinstance(tag, str):
            for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
                try:
                    tag = pd.to_datetime(tag, format=fmt)
                    break
                except ValueError:
                    continue
            else:
                continue
        if not isinstance(tag, (datetime, pd.Timestamp)):
            continue
        try:
            werte[tag.strftime("%Y-%m-%d")] = float(wert)
        except (TypeError, ValueError):
            continue          # z. B. "US Holiday" in der Tonnen-Spalte
    return werte


def gld_abruf(settings: dict) -> dict[str, float]:
    ua = config.user_agent(settings.get("kontakt_fuer_useragent", ""))
    r = requests.get(GLD_URL, headers={"User-Agent": ua, "Accept": "*/*"},
                     timeout=40)
    r.raise_for_status()
    if not r.content.startswith(b"PK"):
        raise ValueError("GLD-Antwort ist kein XLSX (Formatwechsel?)")
    return parse_gld_xlsx(r.content)


def quant_abruf(db, settings: dict) -> dict:
    """Alle Quant-Feeds holen und in quant_series upserten. Jede Quelle
    einzeln fehler-tolerant. Rückgabe: {ok, quellen: {name: {ok, n, fehler?}}}."""
    protokoll: dict = {"ok": True, "quellen": {}}

    def _hole(name: str, fn, *args) -> None:
        eintrag: dict = {"ok": False, "n": 0}
        try:
            werte = fn(*args)
            db.quant_speichern(name, werte)
            eintrag.update(ok=True, n=len(werte),
                           letzter=max(werte) if werte else None)
        except Exception as exc:
            eintrag["fehler"] = f"{type(exc).__name__}: {exc}"[:200]
            protokoll["ok"] = False
        protokoll["quellen"][name] = eintrag

    for schluessel, serie in FRED_SERIEN.items():
        _hole(schluessel, fred_abruf, schluessel, serie, settings)
        time.sleep(0.8)
    _hole("cot_mm_netto", cot_abruf, settings)
    _hole("gld_tonnen", gld_abruf, settings)
    return protokoll
