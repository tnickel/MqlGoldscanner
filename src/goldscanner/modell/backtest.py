# -*- coding: utf-8 -*-
"""Walk-Forward-Backtest (S3) — Entscheidungstor T3.

Expanding Window: für jeden Testtag t wird NUR mit Zeilen < t trainiert und
bewertet (kein Look-ahead, konzeptionsgemäß chronologisch). Konfigurationen:
  A_klimatologie  — Punkt-in-Time-Wochentags-Basisrate (Referenz)
  B_har           — + HAR-Lags + Wochentags-Dummies
  C_har_events    — + NFP/FOMC/GC-Termine
  D_har_events_iv — + GVZ-implizite Volatilität + ATR-Regime
Tor T3: min. eine Modellkonfiguration erreicht BSS = 1 − Brier/Brier(A) > 0.
"""
from __future__ import annotations

import math

import numpy as np

from . import har
from .features import KONFIGURATIONEN

MIN_TRAIN = 120          # Mindestzeilen vor dem ersten Testtag
KALIB_SPLIT = 0.5        # Platt wird auf der 1. Hälfte der OOS-Paare gefittet


def _klima_p(train: list[dict], wochentag: int, shrinkage: float = 2.0) -> float:
    """Punkt-in-Time-Wochentags-Basisrate aus NUR den Trainingszeilen."""
    gleiche = [z for z in train if z["wochentag"] == wochentag]
    alle_n = len(train)
    alle_treffer = sum(1 for z in train if z["bewegung"])
    p_global = alle_treffer / alle_n if alle_n else 0.5
    if not gleiche:
        return p_global
    alpha = shrinkage * p_global
    beta = shrinkage * (1 - p_global)
    treffer = sum(1 for z in gleiche if z["bewegung"])
    return (treffer + alpha) / (len(gleiche) + alpha + beta)


def _brier(p_liste: list[float], y_liste: list[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(p_liste, y_liste)) / len(p_liste)


def _logloss(p_liste: list[float], y_liste: list[int]) -> float:
    return -sum(y * math.log(p) + (1 - y) * math.log(1 - p)
                for p, y in zip(p_liste, y_liste)) / len(p_liste)


def _reliability(p_liste: list[float], y_liste: list[int]) -> list[dict]:
    bins = []
    for unten in (0.0, 0.2, 0.4, 0.6, 0.8):
        oben = unten + 0.2
        treffer = [(p, y) for p, y in zip(p_liste, y_liste)
                   if unten <= p < oben or (oben == 1.0 and p == 1.0)]
        if treffer:
            bins.append({
                "bin": f"{unten:.1f}–{oben:.1f}",
                "n": len(treffer),
                "p_mittel": round(sum(p for p, _ in treffer) / len(treffer), 3),
                "beobachtet": round(sum(y for _, y in treffer) / len(treffer), 3)})
    return bins


def walk_forward(zeilen: list[dict], refit_jede: int = 5) -> dict:
    """Fährt A/B/C/D expanding-window. Rückgabe: Kennzahlen je Konfiguration."""
    start = MIN_TRAIN
    if len(zeilen) < start + 40:
        return {"ok": False, "grund": f"zu wenig Zeilen ({len(zeilen)})",
                "mindestens": start + 40}

    p_oos: dict[str, list[float]] = {"A_klimatologie": []}
    y_oos: list[int] = []
    letzte_beta: dict[str, object] = {}
    letzte_sigma: dict[str, object] = {}

    for name in KONFIGURATIONEN:
        p_oos[name] = []

    for i in range(start, len(zeilen)):
        train = zeilen[:i]
        test = zeilen[i]
        y_oos.append(1 if test["bewegung"] else 0)
        p_oos["A_klimatologie"].append(_klima_p(train, test["wochentag"]))
        for name, features in KONFIGURATIONEN.items():
            if i % refit_jede == 0 or name not in letzte_beta:
                X, y = har.design_matrix(train, features)
                if len(X) < 30:
                    letzte_beta[name] = None
                    continue
                beta = har.ols_fit(X, y)
                letzte_beta[name] = beta
                letzte_sigma[name] = har.residuen_sigma(X, y, beta)
            beta = letzte_beta.get(name)
            if beta is None:
                p_oos[name].append(p_oos["A_klimatologie"][-1])
                continue
            if any(test.get(f) is None for f in features):
                p_oos[name].append(p_oos["A_klimatologie"][-1])
                continue
            x = np.array([[1.0] + [test[f] for f in features]])
            mu = float((x @ beta).item())
            ln_s = math.log(test["schwelle_rel"])
            p_oos[name].append(har.p_bewegung(mu, float(letzte_sigma[name]), ln_s))

    n = len(y_oos)
    brier_a = _brier(p_oos["A_klimatologie"], y_oos)
    ergebnisse = []
    for name in ["A_klimatologie"] + list(KONFIGURATIONEN):
        p_liste = p_oos[name][:n]
        brier = _brier(p_liste, y_oos)
        eintrag = {
            "konfiguration": name,
            "n": n,
            "brier": round(brier, 4),
            "bss": round(1 - brier / brier_a, 4) if name != "A_klimatologie" else 0.0,
            "logloss": round(_logloss(p_liste, y_oos), 4),
            "reliability": _reliability(p_liste, y_oos),
        }
        # Platt auf 2. Hälfte (Fit auf 1. Hälfte der OOS-Paare)
        mitte = n // 2
        a, b = har.platt_fitten(p_liste[:mitte], y_oos[:mitte])
        p_platt = [har.platt_anwenden(p, a, b) for p in p_liste[mitte:]]
        eintrag["brier_platt_2haelfte"] = round(_brier(p_platt, y_oos[mitte:]), 4)
        roh_2 = _brier(p_liste[mitte:], y_oos[mitte:])
        eintrag["bss_platt_2haelfte"] = round(1 - eintrag["brier_platt_2haelfte"] / roh_2, 4) if roh_2 else None
        ergebnisse.append(eintrag)

    beste = max((e for e in ergebnisse if e["konfiguration"] != "A_klimatologie"),
                key=lambda e: e["bss"], default=None)
    return {
        "ok": True, "n_test": n, "ergebnisse": ergebnisse,
        "brier_klimatologie": round(brier_a, 4),
        "beste_konfiguration": beste["konfiguration"] if beste else None,
        "tor_t3_bestanden": bool(beste and beste["bss"] > 0),
    }
