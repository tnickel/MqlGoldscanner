# -*- coding: utf-8 -*-
"""Ankertests für Regeltermine — handverifizierte Kalenderdaten."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from goldscanner.adapter.regeltermine import (alle_regeltermine, dst_wechsel,
                                              gc_termine, us_feiertage)


def test_gc_fnd_februar_liefermonat():
    """FND des Feb-Kontrakts = letzter Geschäftstag des Januars: Fr 30.01.2026."""
    termine = {t.titel: t for t in gc_termine(2026)}
    fnd = termine["GC First Notice Day Feb"]
    assert fnd.datum == date(2026, 1, 30)


def test_gc_ltd_februar():
    """LTD = drittletzter Geschäftstag des Liefermonats Feb 2026: Mi 25.02.2026
    (Geschäftstage von hinten: 27 Fr, 26 Do, 25 Mi)."""
    termine = {t.titel: t for t in gc_termine(2026)}
    ltd = termine["GC Last Trade Day Feb"]
    assert ltd.datum == date(2026, 2, 25)


def test_gc_opex_februar():
    """Options-Verfall des Feb-Kontrakts = 4. letzter Geschäftstag Jan 2026
    (30, 29, 28, 27 → Di 27.01.2026)."""
    termine = {t.titel: t for t in gc_termine(2026)}
    opex = termine["GC Options-Verfall Feb"]
    assert opex.datum == date(2026, 1, 27)


def test_us_feiertage_2026():
    tage = {titel: d for d, titel in us_feiertage(2026)}
    assert tage["MLK Day (US)"] == date(2026, 1, 19)          # 3. Montag Januar
    assert tage["Thanksgiving (US)"] == date(2026, 11, 26)    # 4. Donnerstag
    assert tage["Independence Day (US)"] == date(2026, 7, 3)  # 04.07.=Sa → Fr davor


def test_dst_2026():
    dst = {t.titel: t.datum for t in dst_wechsel(2026)}
    assert dst["US-Zeitumstellung (DST beginnt)"] == date(2026, 3, 8)   # 2. So. März
    assert dst["US-Zeitumstellung (DST endet)"] == date(2026, 11, 1)    # 1. So. Nov
    assert dst["EU-Zeitumstellung (DST beginnt)"] == date(2026, 3, 29)  # letzter So.
    assert dst["EU-Zeitumstellung (DST endet)"] == date(2026, 10, 25)


def test_zeitraum_filter_und_dedup():
    """Ein Termin je Datum (gold-relevanter gewinnt) und Zeitraum-Filter."""
    termine = alle_regeltermine(date(2026, 1, 25), date(2026, 2, 1))
    daten = [t.datum for t in termine]
    assert daten == sorted(daten) == sorted(set(daten))       # je Datum genau einer
    titel = [t.titel for t in termine]
    assert "GC First Notice Day Feb" in titel                 # 30.01. überlebt
    assert all(date(2026, 1, 25) <= d <= date(2026, 2, 1) for d in daten)
