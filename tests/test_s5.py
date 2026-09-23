# -*- coding: utf-8 -*-
"""Stufe-5-Tests: Quant-Parser (FRED/COT/GLD), COT-Veröffentlichungsverzug,
Logit-Parameter-Recovery, Isotonic/PAVA, Session-Empirie, DB v5."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from goldscanner import config
from goldscanner.adapter import quant
from goldscanner.db import Db
from goldscanner.modell import kalibrierung as kal
from goldscanner.modell import richtung
from goldscanner.modell import session as session_modul


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "test.db")


# ── FRED-Parser ─────────────────────────────────────────────────────────────

def test_fred_csv_parser():
    inhalt = ("observation_date,DFII10\n"
              "2026-09-18,2.61\n"
              "2026-09-21,2.62\n"
              "2026-09-22,.\n")
    werte = quant.parse_fred_csv(inhalt)
    assert werte == {"2026-09-18": 2.61, "2026-09-21": 2.62}   # Lücke übersprungen


# ── COT: Parser + Veröffentlichungsverzug (kein Look-ahead) ────────────────

def test_cot_parser_und_t4_regel():
    daten = [
        {"report_date_as_yyyy_mm_dd": "2026-09-15T00:00:00.000",
         "m_money_positions_long_all": 142394,
         "m_money_positions_short_all": 9278},
        {"report_date_as_yyyy_mm_dd": "2026-09-08T00:00:00.000",
         "m_money_positions_long_all": 145804,
         "m_money_positions_short_all": 10832},
    ]
    netto = quant.parse_cot_json(daten)
    assert netto["2026-09-15"] == pytest.approx(133116.0)
    # Dienstag-Stichtag 2026-09-15 ist erst ab 2026-09-19 nutzbar (+4 Tage)
    assert quant.cot_wert_vor(netto, "2026-09-18") == pytest.approx(134972.0)
    assert quant.cot_wert_vor(netto, "2026-09-19") == pytest.approx(133116.0)


# ── GLD-XLSX-Parser (Synthese) ─────────────────────────────────────────────

def test_gld_xlsx_parser(tmp_path):
    import pandas as pd
    tabelle = pd.DataFrame({"Date": ["2026-09-22", "2026-09-23"],
                            "GLD Shares Outstanding": [None, None],
                            "Tonnes": [3405.2, 3407.9]})
    buffer = tmp_path / "gld.xlsx"
    tabelle.to_excel(buffer, index=False)
    werte = quant.parse_gld_xlsx(buffer.read_bytes())
    assert werte == {"2026-09-22": 3405.2, "2026-09-23": 3407.9}


# ── Logit: Parameter-Recovery + BSS gegen Baseline ────────────────────────

def test_logit_recovery_trennbare_daten():
    rng = np.random.default_rng(7)
    x = rng.normal(size=(800, 1))
    X = np.column_stack([np.ones(800), x])
    beta_wahr = np.array([-0.3, 2.5])
    p = 1 / (1 + np.exp(-(X @ beta_wahr)))
    y = (rng.random(800) < p).astype(float)
    beta, standard = richtung.logit_fit(X, y)
    assert beta[1] > 1.5 and beta[1] < 4.0            # Richtung & Größenordnung
    vorhersagen = richtung.logit_predict(X, beta, standard)
    assert vorhersagen.min() > 0 and vorhersagen.max() < 1


def test_walk_forward_synthesesignal_schlaegt_baseline(db):
    """Konstruiert: Aufwärtstag-Wahrscheinlichkeit hängt vom SMA-Abstand ab —
    nur R1+ kann das lernen, die konstante Baseline nicht."""
    rng = np.random.default_rng(11)
    n = 600
    sma20_dist = rng.normal(0, 0.015, n)
    rsi = rng.normal(0, 0.2, n)
    mom5 = rng.normal(0, 0.01, n)
    logit = -0.2 + 150.0 * sma20_dist
    p = 1 / (1 + np.exp(-logit))
    y = (rng.random(n) < p).astype(float)
    zeilen = []
    start_datum = date(2023, 1, 2)
    for i in range(n):
        zeilen.append({
            "datum": (start_datum + __import__("datetime").timedelta(days=i)).isoformat(),
            "wochentag": (start_datum + __import__("datetime").timedelta(days=i)).weekday(),
            "y": float(y[i]),
            "sma20_dist": float(sma20_dist[i]), "mom5": float(mom5[i]),
            "rsi14_s": float(rsi[i]),
            "d_realzins5": 0.0, "d_dollar5": 0.0, "gvz_level": 1.0,
            "cot_z": 0.0, "gld_delta5_pct": 0.0,
        })
    ergebnis = richtung.walk_forward(zeilen)
    assert ergebnis["tor_t5_bestanden"]
    beste = next(e for e in ergebnis["ergebnisse"]
                 if e["konfiguration"] == ergebnis["beste_konfiguration"])
    assert beste["bss"] > 0.01


# ── Isotonic / PAVA ─────────────────────────────────────────────────────────

def test_pava_monoton_und_anker():
    # Handrechnung: x=[1,2,3,4], y=[0,1,0,1] → PAVA = [0.5,0.5,0.5,0.5]? Nein:
    # Sortierte y = [0,1,0,1]: 0<1 ok, 1>0 → Pool(1,0)=0.5, 0.5<1? 0.5>… → Pool
    # mit letztem: [0, 0.5, 0.5, 1] ist die monotone Lösung (0 ≤ 0.5 ≤ 0.5 ≤ 1).
    fit = kal.isotonic_pava([1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 0.0, 1.0])
    assert all(fit[i] <= fit[i + 1] + 1e-12 for i in range(len(fit) - 1))
    assert fit == pytest.approx([0.0, 0.5, 0.5, 1.0])
    # Original-Reihenfolge bleibt erhalten (unsortierte Eingabe)
    fit2 = kal.isotonic_pava([4.0, 1.0, 3.0, 2.0], [1.0, 0.0, 0.0, 1.0])
    assert fit2 == pytest.approx([1.0, 0.0, 0.5, 0.5])


def test_isotonic_modell_stufen():
    m = kal.IsotonicModell([0.1, 0.2, 0.3, 0.4, 0.5],
                           [0.0, 0.0, 1.0, 1.0, 1.0])
    assert m.predict(0.05) == pytest.approx(0.0)
    assert m.predict(0.35) == pytest.approx(1.0)
    assert m.predict(10.0) == pytest.approx(1.0)


# ── Session-Empirie ─────────────────────────────────────────────────────────

def _h1_bar(zeit_iso: str, hoch=10.0, tief=9.0, close=9.5, offen=9.4):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    dt = datetime.fromisoformat(zeit_iso).replace(tzinfo=ZoneInfo("UTC"))
    return {"time": int(dt.timestamp()), "open": offen, "high": hoch,
            "low": tief, "close": close, "volumen": 0}


def test_asia_range_nur_bis_0800():
    # September = CEST (UTC+2): Bars mit Berliner Beginn < 08:00 zählen zur
    # Asia-Range — 05:00 UTC = 07:00 Berlin zählt, 06:00 UTC = 08:00 Berlin
    # beginnt genau zur Grenze und zählt NICHT mehr, 08:00 UTC sowieso nicht.
    bars = [
        _h1_bar("2026-09-21T05:00", hoch=11.0, tief=9.5),    # Berlin 07:00 → Asia
        _h1_bar("2026-09-21T06:00", hoch=10.5, tief=9.0),    # Berlin 08:00 → Grenze
        _h1_bar("2026-09-21T08:00", hoch=12.0, tief=8.0),    # Berlin 10:00 → nicht Asia
    ]
    lage = session_modul.asia_range_und_gap(bars, "2026-09-21")
    assert lage["ok"] and lage["bars"] == 1
    assert lage["range_usd"] == pytest.approx(11.0 - 9.5)


def test_bedingte_bewegungs_p_anker():
    zeilen = [
        {"datum": "2026-09-01", "range_0800": 5.0, "range_tag": 30.0},
        {"datum": "2026-09-02", "range_0800": 6.0, "range_tag": 12.0},   # kein Bewegungstag
        {"datum": "2026-09-03", "range_0800": 10.0, "range_tag": 50.0},
        {"datum": "2026-09-04", "range_0800": 11.0, "range_tag": 55.0},
    ]
    # Schwelle 40: Bewegungstage = 2 von 4 (50 %). Heute Asia 10 (=0.25×40):
    # Bucket ±0.25×40 → Asia in [4, 16] → alle 4 Tage → 2/4 = 50 %
    erg = session_modul.bedingte_bewegungs_p(zeilen, 40.0, 10.0)
    assert erg["ok"] and erg["n_bucket"] == 4
    assert erg["p_bedingt"] == pytest.approx(0.5)
    assert erg["p_ohne_bedingung"] == pytest.approx(0.5)


# ── DB v5: kalibrierung ────────────────────────────────────────────────────

def test_db_v5_kalibrierung(db):
    db.kalibrierung_speichern("richtung", "R2_makro", "platt",
                              '{"a": 1.0, "b": 0.2}', 600, 300, 0.249, 0.25, 0.004)
    zeilen = db.kalibrierungen("richtung")
    assert len(zeilen) == 1 and zeilen[0]["bss"] == pytest.approx(0.004)
    assert db.kalibrierungen() == zeilen                      # ohne Filter auch


def test_richtungs_symbol_zentriert_auf_baserate():
    assert richtung.richtungs_symbol(0.70, 0.52) == "▲▲"
    assert richtung.richtungs_symbol(0.58, 0.52) == "▲"
    assert richtung.richtungs_symbol(0.52, 0.52) == "▬"
    assert richtung.richtungs_symbol(0.45, 0.52) == "▼"
    assert richtung.richtungs_symbol(0.30, 0.52) == "▼▼"
