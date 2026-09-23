# -*- coding: utf-8 -*-
"""Richtungsmodell (S5): P(Close > Vortag) — eigenes Kalibrierziel.

Logistische Regression (Newton-Raphson, numpy) auf strikt point-in-time-
Features (alles ≤ t−1; FRED konservativ ≤ t−2 wegen Tagesverzugs, COT erst
ab Stichtag+4 wegen Freitag-Veröffentlichung — Konzept §7.4):

  R0  Baseline: konstante Ø-Aufwärtswahrscheinlichkeit (Abnahmemesslatte)
  R1  + Trend:   SMA20-Abstand, 5-Tage-Momentum, RSI14
  R2  + Makro:   ΔRealzins 5T, ΔDollar 5T, GVZ-Level
  R3  + Positionierung: COT-Netto-Z-Score (3J), GLD-Bestands-Δ 5T

Walk-Forward expanding (Refit alle 5 Tage) über identische Testtage
(Complete-Case — nur Tage, an denen ALLE Features existieren). Tor T5:
mindestens eine R-Konfiguration muss BSS > 0 gegen R0 erreichen.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import numpy as np

from . import kalibrierung as kal_modul

MIN_TRAIN = 250
REFIT_JEDE = 5

TREND = ("sma20_dist", "mom5", "rsi14_s")
MAKRO = ("d_realzins5", "d_dollar5", "gvz_level")
POSITION = ("cot_z", "gld_delta5_pct")
KONFIGURATIONEN: dict[str, tuple[str, ...]] = {
    "R1_trend": TREND,
    "R2_makro": TREND + MAKRO,
    "R3_position": TREND + MAKRO + POSITION,
}


# ── Feature-Bau ─────────────────────────────────────────────────────────────

def _sma_reihe(closes: list[float], n: int) -> list[float | None]:
    aus: list[float | None] = []
    summe = 0.0
    for i, c in enumerate(closes):
        summe += c
        if i >= n:
            summe -= closes[i - n]
        aus.append(summe / n if i >= n - 1 else None)
    return aus


def _rsi_reihe(closes: list[float], n: int = 14) -> list[float | None]:
    aus: list[float | None] = [None] * len(closes)
    auf = ab = 0.0
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gewinn = max(delta, 0.0)
        verlust = max(-delta, 0.0)
        if i <= n:
            auf += gewinn
            ab += verlust
            if i == n:
                auf /= n
                ab /= n
                aus[i] = 100.0 if ab == 0 else 100.0 - 100.0 / (1.0 + auf / ab)
        else:
            auf = (auf * (n - 1) + gewinn) / n
            ab = (ab * (n - 1) + verlust) / n
            aus[i] = 100.0 if ab == 0 else 100.0 - 100.0 / (1.0 + auf / ab)
    return aus


def _serie_wert_vor(serie: dict[str, float], datum: str, abstand: int = 1) -> float | None:
    """Letzter Serienwert mit datum ≤ (datum − abstand Kalendertage).
    FRED: abstand=2 (Tagesverzug, konservativ); GVZ etc.: abstand=1."""
    grenze = (date.fromisoformat(datum) - timedelta(days=abstand)).isoformat()
    bester_tag = None
    for tag in serie:
        if tag <= grenze and (bester_tag is None or tag > bester_tag):
            bester_tag = tag
    return serie.get(bester_tag) if bester_tag else None


def _delta_n(serie: dict[str, float], datum: str, n: int, abstand: int = 1) -> float | None:
    """wert(datum) − wert(n Beobachtungen früher) — Beobachtungen = sortierte
    Serientage vor dem Grenzdatum."""
    grenze = (date.fromisoformat(datum) - timedelta(days=abstand)).isoformat()
    vergangene = sorted(t for t in serie if t <= grenze)
    if len(vergangene) < n + 1:
        return None
    return serie[vergangene[-1]] - serie[vergangene[-1 - n]]


def _cot_z(netto: dict[str, float], datum: str, fenster_jahre: int = 3) -> float | None:
    """Z-Score der letzten VERÖFFENTLICHTEN COT-Position vs. rollierendem
    3-Jahres-Fenster (nur Stichtage ≤ datum−4 — kein Look-ahead)."""
    from ..adapter.quant import cot_wert_vor
    wert = cot_wert_vor(netto, datum)
    if wert is None:
        return None
    grenze = (date.fromisoformat(datum) - timedelta(days=4)).isoformat()
    stichtage = sorted(t for t in netto
                       if t <= grenze)[-fenster_jahre * 52:]
    if len(stichtage) < 52:
        return None
    werte = [netto[t] for t in stichtage]
    mittel = float(np.mean(werte))
    std = float(np.std(werte, ddof=1))
    return (wert - mittel) / std if std > 1e-9 else 0.0


def tages_zeilen(d1: list[dict], db) -> list[dict]:
    """Zeilen je Tag t: y = 1[close_t > close_{t−1}] und Features ≤ t−1."""
    closes = [b["close"] for b in d1]
    sma20 = _sma_reihe(closes, 20)
    rsi = _rsi_reihe(closes)
    gvz = db.quant_laden("gvz")
    realzins = db.quant_laden("fred_dfii10")
    dollar = db.quant_laden("fred_dtwexbgs")
    cot = db.quant_laden("cot_mm_netto")
    gld = db.quant_laden("gld_tonnen")

    zeilen: list[dict] = []
    for i in range(26, len(d1)):                      # SMA20+RSI14+5er-Lags
        t_iso = datetime.fromtimestamp(d1[i]["time"], tz=timezone.utc).date().isoformat()
        vortag = datetime.fromtimestamp(d1[i - 1]["time"], tz=timezone.utc).date().isoformat()
        if None in (sma20[i - 1], rsi[i - 1]) or i < 6:
            continue
        zeile: dict = {
            "datum": t_iso, "wochentag": date.fromisoformat(t_iso).weekday(),
            "y": 1.0 if closes[i] > closes[i - 1] else 0.0,
            "sma20_dist": closes[i - 1] / sma20[i - 1] - 1.0,
            "mom5": closes[i - 1] / closes[i - 6] - 1.0,
            "rsi14_s": (rsi[i - 1] - 50.0) / 50.0,
        }
        rv = _serie_wert_vor(realzins, vortag, abstand=2)
        rv_alt = _delta_n(realzins, vortag, 5, abstand=2)
        dl = _serie_wert_vor(dollar, vortag, abstand=2)
        dl_alt = _delta_n(dollar, vortag, 5, abstand=2)
        gv = _serie_wert_vor(gvz, vortag, abstand=1)
        cot_z = _cot_z(cot, vortag)
        gld_wert = _serie_wert_vor(gld, vortag, abstand=1)
        gld_alt = None
        if gld_wert is not None:
            delta = _delta_n(gld, vortag, 5, abstand=1)
            gld_alt = delta / gld_wert * 100.0 if delta is not None else None
        zeile["d_realzins5"] = rv_alt if (rv is not None and rv_alt is not None) else None
        zeile["d_dollar5"] = dl_alt if (dl is not None and dl_alt is not None) else None
        zeile["gvz_level"] = (gv / 20.0) if gv is not None else None
        zeile["cot_z"] = cot_z
        zeile["gld_delta5_pct"] = gld_alt
        zeilen.append(zeile)
    return zeilen


# ── Logit (Newton-Raphson mit Ridge) ───────────────────────────────────────

def _sigmoid(z: np.ndarray) -> np.ndarray:
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    e = np.exp(z[~pos])
    out[~pos] = e / (1.0 + e)
    return out


def logit_fit(X: np.ndarray, y: np.ndarray, ridge: float = 1e-4,
              max_iter: int = 60) -> np.ndarray:
    """Standardisiert (ohne Intercept) + Newton-Raphson mit Ridge-Term."""
    n, k = X.shape
    mittel = X[:, 1:].mean(axis=0) if k > 1 else np.zeros(0)
    std = X[:, 1:].std(axis=0) if k > 1 else np.zeros(0)
    std = np.where(std < 1e-9, 1.0, std)
    Xs = X.copy()
    if k > 1:
        Xs[:, 1:] = (X[:, 1:] - mittel) / std
    beta = np.zeros(k)
    strafe = np.eye(k) * ridge
    strafe[0, 0] = 0.0                       # Intercept nicht bestrafen
    for _ in range(max_iter):
        p = np.clip(_sigmoid(Xs @ beta), 1e-6, 1 - 1e-6)
        w = p * (1.0 - p)
        grad = Xs.T @ (y - p)
        hesse = Xs.T @ (Xs * w[:, None]) + strafe
        try:
            delta = np.linalg.solve(hesse, grad)
        except np.linalg.LinAlgError:
            delta = np.linalg.lstsq(hesse, grad, rcond=None)[0]
        delta = np.clip(delta, -5.0, 5.0)
        beta += delta
        if float(np.max(np.abs(delta))) < 1e-8:
            break
    return beta, (mittel, std)


def logit_predict(X: np.ndarray, beta: np.ndarray, standard: tuple) -> np.ndarray:
    mittel, std = standard
    Xs = X.copy()
    if X.shape[1] > 1:
        Xs[:, 1:] = (X[:, 1:] - mittel) / std
    return np.clip(_sigmoid(Xs @ beta), 1e-6, 1 - 1e-6)


def _design(zeilen: list[dict], features: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Design-Matrix: Intercept + WD-Dummies (Di–Fr) + Features."""
    spalten: list[list[float]] = [[1.0] * len(zeilen),
                                 [1.0 if z["wochentag"] == 1 else 0.0 for z in zeilen],
                                 [1.0 if z["wochentag"] == 2 else 0.0 for z in zeilen],
                                 [1.0 if z["wochentag"] == 3 else 0.0 for z in zeilen],
                                 [1.0 if z["wochentag"] == 4 else 0.0 for z in zeilen]]
    for f in features:
        spalten.append([float(z[f]) for z in zeilen])
    return np.array(spalten).T, np.array([z.get("y", 0.0) for z in zeilen])


# ── Walk-Forward + Ablation ────────────────────────────────────────────────

def walk_forward(zeilen: list[dict]) -> dict:
    """Complete-Case (alle Features vorhanden), expanding, Refit alle 5.
    Rückgabe: {baseline_brier, ergebnisse: [{konfiguration, brier, bss, ...}],
    tor_t5_bestanden, base_rate, n_test, oos: {konf: [(p, y), ...]}}."""
    voll = [z for z in zeilen
            if all(z.get(f) is not None for f in TREND + MAKRO + POSITION)]
    if len(voll) < MIN_TRAIN + 60:
        return {"tor_t5_bestanden": False, "grund": "zu wenige vollständige Tage",
                "n_voll": len(voll)}
    base_rate = float(np.mean([z["y"] for z in voll]))

    oos: dict[str, list[tuple[float, float]]] = {"R0_baseline": []}
    for konf in KONFIGURATIONEN:
        oos[konf] = []

    for start in range(MIN_TRAIN, len(voll), REFIT_JEDE):
        train = voll[:start]
        tests = voll[start:start + REFIT_JEDE]
        y_train = np.array([z["y"] for z in train])
        p_base = float(np.mean(y_train))
        for z in tests:
            oos["R0_baseline"].append((p_base, z["y"]))
        for konf, features in KONFIGURATIONEN.items():
            X_tr, y_tr = _design(train, features)
            beta, standard = logit_fit(X_tr, y_tr)
            for z in tests:
                X_einzeln, _ = _design([z], features)
                p = float(logit_predict(X_einzeln, beta, standard)[0])
                oos[konf].append((p, z["y"]))

    def _brier(paare: list[tuple[float, float]]) -> float:
        return float(np.mean([(p - y) ** 2 for p, y in paare]))

    brier_base = _brier(oos["R0_baseline"])
    ergebnisse = []
    for konf in KONFIGURATIONEN:
        b = _brier(oos[konf])
        ergebnisse.append({"konfiguration": konf, "n": len(oos[konf]),
                           "brier": b, "bss": 1.0 - b / brier_base if brier_base else 0.0})
    beste = max(ergebnisse, key=lambda e: e["bss"])
    tor = bool(beste["bss"] > 0.0 and beste["brier"] < brier_base)

    # Nachkalibrierung der besten Konfiguration: 1. OOS-Hälfte fitten,
    # 2. Hälfte bewerten (ehrlich, keine In-Sample-Schönung)
    kal_brier = kal_methode = None
    paare = oos[beste["konfiguration"]]
    if len(paare) >= 120:
        halb = len(paare) // 2
        scores = [math.log(p / (1 - p)) for p, _ in paare[:halb]]
        ziele = [y for _, y in paare[:halb]]
        kal_methode, anwenden = kal_modul.kalibriere(scores, ziele)
        kal_brier = _brier([(anwenden(math.log(p / (1 - p))), y)
                            for p, y in paare[halb:]])

    return {
        "base_rate": base_rate, "brier_baseline": brier_base,
        "ergebnisse": ergebnisse, "beste_konfiguration": beste["konfiguration"],
        "bss": beste["bss"], "tor_t5_bestanden": tor,
        "n_test": len(oos["R0_baseline"]), "n_vollstaendig": len(voll),
        "kalibrierung": {"methode": kal_methode, "brier_2haelfte": kal_brier},
    }


# ── Wochen-Prognose (Richtung je Wochentag) ────────────────────────────────

def _aktuelle_features(d1: list[dict], db) -> dict | None:
    """Feature-Stand von GESTERN (= letzte vollständige Information)."""
    closes = [b["close"] for b in d1]
    sma20 = _sma_reihe(closes, 20)
    rsi = _rsi_reihe(closes)
    i = len(d1) - 1
    if sma20[i - 1] is None or rsi[i - 1] is None or i < 6:
        return None
    vortag = datetime.fromtimestamp(d1[i]["time"], tz=timezone.utc).date().isoformat()
    gvz = db.quant_laden("gvz")
    realzins = db.quant_laden("fred_dfii10")
    dollar = db.quant_laden("fred_dtwexbgs")
    cot = db.quant_laden("cot_mm_netto")
    gld = db.quant_laden("gld_tonnen")
    rv = _serie_wert_vor(realzins, vortag, abstand=2)
    dl = _serie_wert_vor(dollar, vortag, abstand=2)
    gv = _serie_wert_vor(gvz, vortag, abstand=1)
    gld_wert = _serie_wert_vor(gld, vortag, abstand=1)
    delta_gld = _delta_n(gld, vortag, 5, abstand=1) if gld_wert is not None else None
    return {
        "sma20_dist": closes[i - 1] / sma20[i - 1] - 1.0,
        "mom5": closes[i - 1] / closes[i - 6] - 1.0,
        "rsi14_s": (rsi[i - 1] - 50.0) / 50.0,
        "d_realzins5": _delta_n(realzins, vortag, 5, abstand=2),
        "d_dollar5": _delta_n(dollar, vortag, 5, abstand=2),
        "gvz_level": (gv / 20.0) if gv is not None else None,
        "cot_z": _cot_z(cot, vortag),
        "gld_delta5_pct": (delta_gld / gld_wert * 100.0
                           if (delta_gld is not None and gld_wert) else None),
    }


def richtungs_symbol(p_hoch: float, base_rate: float) -> str:
    delta = p_hoch - base_rate
    if delta >= 0.12:
        return "▲▲"
    if delta >= 0.05:
        return "▲"
    if delta > -0.05:
        return "▬"
    if delta > -0.12:
        return "▼"
    return "▼▼"


def wochen_prognose(db, d1: list[dict], zieltage: list[str]) -> dict | None:
    """P(hoch) je Zieltag: beste Konfiguration auf ALLEN vollständigen Tagen
    gefittet, Features = aktueller Stand, WD-Dummies je Zieltag."""
    zeilen = [z for z in tages_zeilen(d1, db)
              if all(z.get(f) is not None for f in TREND + MAKRO + POSITION)]
    if len(zeilen) < MIN_TRAIN:
        return None
    ergebnis = walk_forward(tages_zeilen(d1, db))
    beste = ergebnis.get("beste_konfiguration")
    if not beste:
        return None
    features = KONFIGURATIONEN[beste]
    X, y = _design(zeilen, features)
    beta, standard = logit_fit(X, y)
    aktuell = _aktuelle_features(d1, db)
    if not aktuell or any(aktuell.get(f) is None for f in features):
        return None
    base = ergebnis["base_rate"]
    je_tag = {}
    for datum in zieltage:
        wt = date.fromisoformat(datum).weekday()
        if wt > 4:
            continue
        zeile = {"wochentag": wt, **aktuell}
        X_e, _ = _design([zeile], features)
        p = float(logit_predict(X_e, beta, standard)[0])
        je_tag[datum] = {"p_hoch": p, "symbol": richtungs_symbol(p, base)}
    return {"konfiguration": beste, "base_rate": base, "je_tag": je_tag,
            "backtest": {k: ergebnis[k] for k in
                         ("brier_baseline", "ergebnisse", "bss",
                          "tor_t5_bestanden", "n_test", "kalibrierung",
                          "n_vollstaendig")},
            "features_aktuell": aktuell}
