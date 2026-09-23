# -*- coding: utf-8 -*-
"""Ankertests für die Klimatologie — synthetische Reihen mit bekanntem Ergebnis."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from goldscanner.klimatologie import (punkte_in_time_bewertungen, quantil,
                                      schwelle_naechster_tag, warnstufe,
                                      wochentags_statistik)

_START = datetime(2024, 1, 1, tzinfo=timezone.utc)   # ein Montag


def _bar(tage_nach_start, tr, close=1000.0):
    t = int((_START + timedelta(days=tage_nach_start)).timestamp())
    return {"time": t, "open": close, "high": close + tr / 2,
            "low": close - tr / 2, "close": close, "volumen": 0}


def _serie(montag_trs, dienstag_trs=None):
    dienstag_trs = dienstag_trs or [100.0] * len(montag_trs)
    bars = []
    for woche, (mo, di) in enumerate(zip(montag_trs, dienstag_trs)):
        bars.append(_bar(7 * woche, mo))
        bars.append(_bar(7 * woche + 1, di))
    return bars


def test_quantil_anker():
    assert quantil([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert quantil([1.0, 2.0, 3.0, 4.0], 0.0) == 1.0
    assert quantil([1.0, 2.0, 3.0, 4.0], 1.0) == 4.0
    assert quantil([5.0], 0.3) == 5.0


def test_warnstufen_zentriert_an_basisrate():
    assert warnstufe(0.20) == "ruhig"
    assert warnstufe(0.33) == "normal"
    assert warnstufe(0.43) == "normal"      # die Basisrate selbst ist „normal"
    assert warnstufe(0.50) == "erhöht"
    assert warnstufe(0.70) == "extrem"


def test_konstante_range_keine_bewegungstage():
    bars = _serie([100.0] * 20)
    bewertungen = punkte_in_time_bewertungen(bars, k=1.0, fenster=13,
                                             min_vorgaenger=6)
    # Montag: 1. Bar hat keine TR → 13 bewertet; Dienstag: 14 bewertet
    assert len(bewertungen) == 27
    assert not any(b["bewegung"] for b in bewertungen)   # TR nie > Schwelle
    stats = wochentags_statistik(bars, k=1.0, fenster=13)
    assert stats["je_wochentag"][0]["n"] == 13
    assert stats["je_wochentag"][1]["n"] == 14
    assert stats["je_wochentag"][0]["p_roh"] == 0.0


def test_schock_nach_ruhiger_phase():
    """13 ruhige Montage (TR 100), dann 7 heiße (TR 300): die letzten 7 sind
    Bewegungstage → 7 von 13 bewerteten Montagen."""
    bars = _serie([100.0] * 13 + [300.0] * 7)
    stats = wochentags_statistik(bars, k=1.0, fenster=13)
    montag = stats["je_wochentag"][0]
    assert montag["n"] == 13
    assert montag["treffer"] == 7
    assert montag["p_roh"] == round(7 / 13, 4)      # p_roh wird auf 4 Stellen gerundet


def test_schwelle_naechster_tag_handgerechnet():
    bars = _serie([100.0] * 13 + [300.0] * 7)
    schwelle = schwelle_naechster_tag(bars, wochentag=0, k=1.0, fenster=13)
    # letzte 13 Montags-TRs: 6×100 + 7×300 → rel (0.6+2.1)/13 = 0.20769…
    erwartet_rel = (6 * 0.1 + 7 * 0.3) / 13
    assert abs(schwelle["schwelle_rel"] - erwartet_rel) < 1e-6
    assert schwelle["n_basis"] == 13
    assert abs(schwelle["schwelle_usd"] - round(erwartet_rel * 1000, 2)) < 0.01


def test_punkt_in_time_ohne_look_ahead():
    """Der erste heiße Montag (Index 13) wird gegen die Schwelle aus den
    vorherigen RUHIGEN Montagen bewertet — nicht durch spätere Tage verwässert."""
    bars = _serie([100.0] * 13 + [300.0] * 1)
    bewertungen = punkte_in_time_bewertungen(bars, k=1.0, fenster=13,
                                             min_vorgaenger=6)
    montage = [b for b in bewertungen if b["wochentag"] == 0]
    letzter = montage[-1]
    assert abs(letzter["schwelle_rel"] - 0.1) < 1e-9   # nur aus den 100ern davor
    assert letzter["bewegung"] is True
