# -*- coding: utf-8 -*-
"""Stufe-6-Tests: Daemon-Zeitplan, Verifikation (point-in-time + Kennzahlen),
MT5-Export-CSV, Scout, DB v6."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from goldscanner import config
from goldscanner.betrieb import daemon, mt5_export, scout, verifikation
from goldscanner.db import Db


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "test.db")


def _bar(tag: str, hoch=100.0, tief=90.0, close=95.0, offen=95.0):
    return {"time": int(datetime.fromisoformat(f"{tag}T00:00:00+00:00").timestamp()),
            "open": offen, "high": hoch, "low": tief, "close": close,
            "volumen": 0}


def _matrix_speichern(db, woche: str, as_of: str, tage: list[dict]) -> None:
    matrix = {"woche": woche, "bis": woche, "modell": "test",
              "tage": tage, "erzeugt_am": as_of}
    db.prognose_speichern(woche, "test", json.dumps(matrix), as_of=as_of)


# ── Daemon-Zeitplan ─────────────────────────────────────────────────────────

def test_zeitplan_taeglich():
    jetzt = datetime(2026, 9, 23, 12, 0)              # Mittwoch
    termin = daemon.geplant_fuer("tageslauf", jetzt)
    assert (termin.year, termin.month, termin.day, termin.hour) == (2026, 9, 23, 6)
    assert daemon.faellig("tageslauf", termin.isoformat(), jetzt) is False
    # letzter Lauf gestern → heute 06:30 ist fällig
    assert daemon.faellig("tageslauf",
                          (termin - timedelta(days=1)).isoformat(), jetzt) is True


def test_zeitplan_sonntag():
    jetzt = datetime(2026, 9, 23, 12, 0)              # Mittwoch
    termin = daemon.geplant_fuer("wochenlauf", jetzt)  # letzter So 18:00
    assert termin.weekday() == 6 and termin.hour == 18
    assert termin.date() == date(2026, 9, 20)
    assert daemon.faellig("wochenlauf", termin.isoformat(), jetzt) is False
    assert daemon.faellig("wochenlauf", None, jetzt) is False  # >6 h her
    frisch = datetime(2026, 9, 20, 17, 0)             # vor dem Termin
    assert daemon.faellig("wochenlauf", frisch.isoformat(), jetzt) is True


# ── Verifikation: point-in-time + Mathematik ───────────────────────────────

def test_verifikation_point_in_time_und_mathematik(db):
    # Kurse: Di/Mi/Do einer Woche; TR(Di)=10 (ohne Vortag → vs. open),
    # TR(Mi): max(120,80,100)-min(...)=40, TR(Do): 25
    db.raten_speichern("XAUUSD", "d1", [
        _bar("2026-09-22", hoch=105, tief=95, close=100),
        _bar("2026-09-23", hoch=120, tief=80, close=110),
        _bar("2026-09-24", hoch=130, tief=105, close=125),
    ])
    # Prognose VOR der Woche (as_of Montag) — die einzige gültige für Di-Mi
    _matrix_speichern(db, "2026-09-21", "2026-09-21T18:00:00", [
        {"datum": "2026-09-22", "wochentag": "Dienstag", "p_klima": 0.4,
         "p_stat": 0.3, "schwelle_usd": 30.0, "q10_usd": 15.0, "q90_usd": 45.0,
         "richtung": {"p_hoch": 0.6, "symbol": "▲"}},
        {"datum": "2026-09-23", "wochentag": "Mittwoch", "p_klima": 0.45,
         "p_stat": 0.7, "schwelle_usd": 35.0, "q10_usd": 20.0, "q90_usd": 50.0,
         "richtung": {"p_hoch": 0.2, "symbol": "▼"}},
    ])
    # Nachträglich geänderte Version (as_of Do) darf für Di/Mi NICHT zählen
    _matrix_speichern(db, "2026-09-21", "2026-09-24T20:00:00", [
        {"datum": "2026-09-22", "wochentag": "Dienstag", "p_klima": 0.99,
         "p_stat": 0.99, "schwelle_usd": 1.0, "q10_usd": 0.0, "q90_usd": 1.0},
        {"datum": "2026-09-23", "wochentag": "Mittwoch", "p_klima": 0.99,
         "p_stat": 0.99, "schwelle_usd": 1.0, "q10_usd": 0.0, "q90_usd": 1.0},
    ])
    prot = verifikation.nachziehen(db, config.DEFAULT_SETTINGS,
                                    heute=date(2026, 9, 26))
    assert prot["ok"] and prot["neu"] == 2 and prot["ohne_prognose"] == 1
    zeilen = {z["datum"]: z for z in db.verifikationen()}
    di, mi = zeilen["2026-09-22"], zeilen["2026-09-23"]
    # point-in-time: die Montag-Version gilt (nicht die 99 %-Fälschung von Do)
    assert di["p_stat"] == pytest.approx(0.3)
    assert di["as_of_prognose"].startswith("2026-09-21")
    # TR: Di = max(105,95,95)-min(...) = 10, Schwelle 30 → nicht eingetreten
    assert di["tr_usd"] == pytest.approx(10.0) and di["eingetreten"] == 0
    assert di["in_band"] == 0                          # 10 < q10=15
    # Mi: TR = 120-80 = 40 > 35 → eingetreten; 40 ∈ [20,50] → in Band
    assert mi["tr_usd"] == pytest.approx(40.0) and mi["eingetreten"] == 1
    assert mi["in_band"] == 1
    # Richtung: Mi close 110 > Di close 100 → ▲ (p_hoch 0.2 sagte ▼)
    assert mi["richtung_eingetreten"] == 1
    # Kennzahlen: LLM fehlt → llm_delta None
    kz = verifikation.kennzahlen(db.verifikationen())
    assert kz["n_tage"] == 2
    assert kz["llm_delta_nutzt"] is None
    # Brier p_stat: (0.3-0)² + (0.7-1)² ; Brier p_klima: (0.4-0)² + (0.45-1)²
    assert kz["n_bewegung"] == 2
    assert kz["brier_stat"] == pytest.approx((0.09 + 0.09) / 2)
    assert kz["brier_klima"] == pytest.approx((0.16 + 0.3025) / 2)


def test_verifikation_llm_delta(db):
    db.raten_speichern("XAUUSD", "d1", [
        _bar("2026-09-22", hoch=105, tief=95, close=100),
        _bar("2026-09-23", hoch=120, tief=80, close=110),
    ])
    _matrix_speichern(db, "2026-09-21", "2026-09-21T18:00:00", [
        {"datum": "2026-09-22", "p_klima": 0.5, "p_stat": 0.5,
         "schwelle_usd": 5.0, "q10_usd": 1.0, "q90_usd": 99.0},
    ])
    matrix_llm = {"woche": "2026-09-21", "bis": "2026-09-21", "modell": "t+llm",
                  "erzeugt_am": "2026-09-21T19:00:00",
                  "tage": [{"datum": "2026-09-22", "p_klima": 0.5, "p_stat": 0.5,
                            "schwelle_usd": 5.0, "q10_usd": 1.0, "q90_usd": 99.0}],
                  "llm": {"ok": True, "tage": [
                      {"datum": "2026-09-22", "p_finale_pct": 90.0,
                       "abweichung_pp": 40.0}]}}
    db.prognose_speichern("2026-09-21", "t+llm", json.dumps(matrix_llm),
                          as_of="2026-09-21T19:00:00")
    verifikation.nachziehen(db, config.DEFAULT_SETTINGS,
                            heute=date(2026, 9, 26))
    zeile = db.verifikationen()[0]
    assert zeile["p_finale"] == pytest.approx(0.9)     # LLM-Version (jüngste ≤ Tag)
    assert zeile["eingetreten"] == 1                   # TR=10 > 5
    kz = verifikation.kennzahlen(db.verifikationen())
    # LLM verschlechtert: (0.9-1)² vs (0.5-1)² → Brier finale < stat
    assert kz["llm_delta_nutzt"] == pytest.approx(0.25 - 0.01)


# ── MT5-Export ──────────────────────────────────────────────────────────────

def test_mt5_export_csv(tmp_path, monkeypatch):
    matrix = {"woche": "2026-09-21", "tage": [
        {"datum": "2026-09-21", "wochentag": "Montag", "p_klima": 0.36,
         "p_stat": 0.36, "schwelle_usd": 78.0, "q10_usd": 41.0, "q50_usd": 77.0,
         "q90_usd": 112.0, "warnstufe": "ruhig",
         "richtung": {"p_hoch": 0.51, "symbol": "▬"}},
        {"datum": "2026-09-22", "wochentag": "Dienstag", "p_klima": 0.44,
         "p_stat": 0.19, "schwelle_usd": 94.0, "q10_usd": 40.0, "q50_usd": 70.0,
         "q90_usd": 111.0, "warnstufe": "ruhig",
         "richtung": {"p_hoch": 0.54, "symbol": "▬"}},
    ], "llm": {"ok": True, "tage": [
        {"datum": "2026-09-21", "p_finale_pct": 38.0},
        {"datum": "2026-09-22", "p_finale_pct": 21.5}]}}
    # Common-Files-Suche neutralisieren (kein Terminal im Test)
    import goldscanner.betrieb.mt5_export as ex
    monkeypatch.setattr("goldscanner.adapter.actuals.mt5_csv_pfade", lambda: [])
    ergebnis = ex.schreibe_export(matrix)
    assert ergebnis["ok"]
    pfad = Path(ergebnis["dateien"][0])
    assert pfad.exists() and pfad.name == "goldscanner_prognose.csv"
    zeilen = ex.lese_export(pfad)
    assert len(zeilen) == 2
    assert zeilen[0]["datum"] == "2026-09-21"
    assert zeilen[0]["p_bewegung"] == "38.0"
    assert zeilen[0]["richtung_p_hoch"] == "51.0"
    assert zeilen[1]["p_bewegung"] == "21.5"


# ── Scout ──────────────────────────────────────────────────────────────────

SCOUT_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>t</title>
<item><title>Gold rises on Fed hints - Example Gold News</title>
  <source url="https://www.examplegoldnews.com/feed">Example Gold News</source>
  <description>gold price analysis</description></item>
<item><title>Gold price today - Example Gold News</title>
  <source url="https://examplegoldnews.com/rss">Example Gold News</source>
  <description>XAUUSD moves</description></item>
<item><title>Gold price today again - Example Gold News</title>
  <source url="https://www.examplegoldnews.com/">Example Gold News</source>
  <description>gold</description></item>
<item><title>Dollar steady - Known Site</title>
  <source url="https://www.kitco.com/x">Known Site</source>
  <description>dollar</description></item>
</channel></rss>"""


def test_scout_domains_und_vorschlaege(db):
    zaehler, beispiele = scout.sammle_domains(SCOUT_RSS, fenster_tage=30)
    assert zaehler["examplegoldnews.com"] == 3
    assert "kitco.com" in zaehler                       # gefunden …
    neu = 0
    for domain, n in zaehler.most_common(30):
        if domain in scout.BEKANNT or n < 3:
            continue
        if db.scout_vorschlag_speichern(domain, n, beispiele.get(domain, "")):
            neu += 1
    assert neu == 1                                     # … aber bekannt → raus
    vorschlaege = db.scout_vorschlaege("offen")
    assert len(vorschlaege) == 1
    assert vorschlaege[0]["domain"] == "examplegoldnews.com"
    assert vorschlaege[0]["score"] == 3
    db.scout_status_setzen(vorschlaege[0]["id"], "angenommen")
    assert db.scout_vorschlaege("angenommen")[0]["status"] == "angenommen"


# ── DB v6 ──────────────────────────────────────────────────────────────────

def test_db_v6_daemon_und_verifikation(db):
    db.daemon_status_schreiben("tageslauf", True, "kurse+12")
    db.daemon_zeit_setzen("tageslauf")
    db.daemon_zeit_setzen("tageslauf")                  # idempotent
    zeiten = db.daemon_zeiten()
    assert list(zeiten) == ["tageslauf"]
    assert db.daemon_letzter_status(1)[0]["job"] == "tageslauf"
    db.verifikation_speichern({"datum": "2026-09-22", "woche": "2026-09-21",
                               "as_of_prognose": "x", "p_stat": 0.5,
                               "eingetreten": 1})
    db.verifikation_speichern({"datum": "2026-09-22", "woche": "2026-09-21",
                               "as_of_prognose": "x", "p_stat": 0.7,
                               "eingetreten": 0})       # REPLACE, kein Duplikat
    assert len(db.verifikationen()) == 1
    assert db.verifikationen()[0]["eingetreten"] == 0
