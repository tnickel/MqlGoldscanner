"""Kurs-Kennzahlen — reiner Code, das LLM zitiert sie nur (KiScanner-Regel 1).

Wilder-Glättung für ATR und RSI (Seed = Mittelwert der ersten `periode`
Werte, danach rekursiv (vorheriger·(n−1)+neu)/n).
"""
from __future__ import annotations

from datetime import datetime, timezone


def true_ranges(bars: list[dict]) -> list[float]:
    """TR je Bar (Bar 0 hat keinen Vorgänger und fehlt deshalb)."""
    trs = []
    for vorher, aktuell in zip(bars, bars[1:]):
        pc = vorher["close"]
        trs.append(max(aktuell["high"] - aktuell["low"],
                       abs(aktuell["high"] - pc),
                       abs(aktuell["low"] - pc)))
    return trs


def atr_wilder(bars: list[dict], periode: int = 14) -> float | None:
    trs = true_ranges(bars)
    if len(trs) < periode:
        return None
    atr = sum(trs[:periode]) / periode
    for tr in trs[periode:]:
        atr = (atr * (periode - 1) + tr) / periode
    return atr


def sma(werte: list[float], n: int) -> float | None:
    if not werte:
        return None
    fenster = werte[-n:]
    return sum(fenster) / len(fenster)


def sma_reihe(werte: list[float], n: int) -> list[float | None]:
    reihe: list[float | None] = []
    summe = 0.0
    for i, w in enumerate(werte):
        summe += w
        if i >= n:
            summe -= werte[i - n]
        reihe.append(summe / n if i >= n - 1 else None)
    return reihe


def rsi_wilder(closes: list[float], periode: int = 14) -> float | None:
    if len(closes) < periode + 1:
        return None
    gewinn = verlust = 0.0
    for i in range(1, periode + 1):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gewinn += diff
        else:
            verlust -= diff
    avg_gewinn, avg_verlust = gewinn / periode, verlust / periode
    for i in range(periode + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        avg_gewinn = (avg_gewinn * (periode - 1) + max(diff, 0)) / periode
        avg_verlust = (avg_verlust * (periode - 1) + max(-diff, 0)) / periode
    if avg_verlust == 0:
        return 100.0 if avg_gewinn else 50.0
    return 100.0 - 100.0 / (1.0 + avg_gewinn / avg_verlust)


def _pct_vor(closes: list[float], n: int) -> float | None:
    if len(closes) <= n or closes[-1 - n] == 0:
        return None
    return round((closes[-1] / closes[-1 - n] - 1) * 100, 2)


def kennzahlen_aus_d1(d1: list[dict], h1: list[dict] | None = None) -> dict:
    """Kennzahlenset für Dashboard/Chart-Panel (Keys deutsch, direkt anzeigbar)."""
    if not d1:
        return {"fehler": "Keine D1-Daten."}
    closes = [b["close"] for b in d1]
    letzter = closes[-1]
    bar = d1[-1]
    fenster = closes[-30:] if len(closes) >= 30 else closes

    sma10 = sma(closes, 10)
    sma50 = sma(closes, 50) if len(closes) >= 50 else None
    sma200 = sma(closes, 200) if len(closes) >= 200 else None
    atr_h1 = atr_wilder(h1, 14) if h1 else None
    atr_d1 = atr_wilder(d1, 14)
    tr_heute = true_ranges(d1[-2:])[0] if len(d1) >= 2 else bar["high"] - bar["low"]

    zeit = datetime.fromtimestamp(bar["time"], tz=timezone.utc)
    return {
        "close": round(letzter, 2),
        "veraenderung_heute_pct": _pct_vor(closes, 1),
        "veraenderung_7t_pct": _pct_vor(closes, 7),
        "veraenderung_30t_pct": _pct_vor(closes, 30),
        "distanz_30t_hoch_pct": round((letzter / max(fenster) - 1) * 100, 2) if fenster else None,
        "distanz_30t_tief_pct": round((letzter / min(fenster) - 1) * 100, 2) if fenster else None,
        "tagesrange_pct": round((bar["high"] - bar["low"]) / bar["close"] * 100, 2)
                          if bar["close"] else None,
        "tr_heute": round(tr_heute, 2),
        "atr14_h1": round(atr_h1, 2) if atr_h1 is not None else None,
        "atr14_d1": round(atr_d1, 2) if atr_d1 is not None else None,
        "sma10": round(sma10, 2) if sma10 is not None else None,
        "sma50": round(sma50, 2) if sma50 is not None else None,
        "sma200": round(sma200, 2) if sma200 is not None else None,
        "trend_close_vs_sma10_pct": round((letzter / sma10 - 1) * 100, 2)
                                    if sma10 else None,
        "rsi14_d1": round(rsi_wilder(closes, 14), 1) if rsi_wilder(closes, 14) is not None else None,
        "letzte_bar": zeit.strftime("%a %d.%m.%Y"),
        "bars_d1": len(d1),
    }
