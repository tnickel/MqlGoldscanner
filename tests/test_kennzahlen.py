"""Ankertests für Kennzahlen — handgerechnete Werte (portiert aus dem
Java-Prototyp, dort bereits grün)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from goldscanner.kennzahlen import (atr_wilder, kennzahlen_aus_d1, rsi_wilder,
                                    sma, sma_reihe, true_ranges)


def _bar(open_, high, low, close):
    return {"time": 0, "open": open_, "high": high, "low": low,
            "close": close, "volumen": 0}


def test_true_range_handgerechnet():
    vorher = _bar(100, 110, 90, 105)
    heute = _bar(105, 120, 95, 110)
    # max(H-L=25, |H-PrevC|=15, |L-PrevC|=10) = 25
    assert heute and true_ranges([vorher, heute]) == [25.0]


def test_atr_konstante_range():
    balken = [_bar(100, 110, 100, 100) for _ in range(15)]   # jede TR = 10
    assert atr_wilder(balken, 14) == 10.0


def test_atr_schock_am_ende():
    balken = [_bar(100, 110, 100, 100) for _ in range(14)] + [_bar(100, 130, 100, 100)]
    assert abs(atr_wilder(balken, 14) - 160.0 / 14.0) < 1e-9   # Wilder: (10·13+30)/14


def test_atr_zu_wenig_bars():
    assert atr_wilder([_bar(1, 2, 1, 1)], 14) is None


def test_sma_anker():
    werte = [float(i) for i in range(1, 11)]
    assert sma(werte, 10) == 5.5
    assert sma(werte, 1) == 10.0
    reihe = sma_reihe(werte, 3)
    assert reihe[0] is None and reihe[1] is None
    assert reihe[2] == 2.0        # (1+2+3)/3
    assert reihe[9] == 9.0        # (8+9+10)/3


def test_rsi_grenzfaelle():
    steigend = [100.0 + i for i in range(15)]
    fallend = [200.0 - i for i in range(15)]
    assert rsi_wilder(steigend, 14) == 100.0
    assert rsi_wilder(fallend, 14) == 0.0
    wechsel = [100.0]
    for i in range(14):   # 7× +1 und 7× −1 → RSI 50
        wechsel.append(wechsel[-1] + (1 if i % 2 == 0 else -1))
    assert abs(rsi_wilder(wechsel, 14) - 50.0) < 1e-9
    assert rsi_wilder(wechsel[:10], 14) is None


def test_kennzahlen_set_vollstaendig():
    d1 = []
    t = 1_700_000_000
    for i in range(60):
        basis = 2000 + 10 * i
        d1.append({"time": t + i * 86400, "open": basis, "high": basis + 15,
                   "low": basis - 10, "close": basis + 5, "volumen": 100})
    k = kennzahlen_aus_d1(d1, d1)
    assert k["close"] == 2000 + 10 * 59 + 5
    assert "atr14_d1" in k and "rsi14_d1" in k and "sma50" in k
    assert k["sma200"] is None          # nur 60 Bars
    assert isinstance(k["veraenderung_7t_pct"], float)
