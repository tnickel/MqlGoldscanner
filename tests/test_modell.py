# -*- coding: utf-8 -*-
"""Ankertests für den S3-Prognosekern: HAR-Parameter-Recovery, Brier/BSS,
Platt-Skalierung, Punkt-in-Time-Disziplin, GVZ-Parser."""
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from goldscanner.modell import har
from goldscanner.modell.backtest import _brier, _klima_p, _reliability, walk_forward
from goldscanner.modell.features import nfp_proxy_datum
from goldscanner.modell.quant_feeds import parse_gvz_csv

_START = datetime(2024, 1, 1, tzinfo=timezone.utc)   # Montag


# ── HAR-Parameter-Recovery auf bekannter AR-Struktur ────────────────────

def test_har_parameter_recovery():
    """y_t = 0.3·y_{t-1} + 0.7·ε mit ε~N(0, 0.05): OLS mit Lag-Feature soll
    den Koeffizienten grob wiederfinden."""
    rng = np.random.default_rng(42)
    n = 5000
    epsilon = rng.normal(0, 0.05, n)
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.3 * y[t - 1] + epsilon[t]
    X = np.column_stack([np.ones(n - 1), y[:-1]])
    beta = har.ols_fit(X, y[1:])
    assert abs(beta[0]) < 0.01            # kein Achsen-Abschnitt im Prozess
    assert abs(beta[1] - 0.3) < 0.05      # AR-Koeffizient wiedergefunden


def test_p_bewegung_grenzfaelle():
    # Schwelle weit über μ ⇒ P am Clip-Floor; weit unter ⇒ am Ceiling; μ ⇒ 0.5
    assert har.p_bewegung(0.0, 0.2, 2.0) <= 1e-6
    assert har.p_bewegung(0.0, 0.2, -2.0) >= 1 - 1e-6
    assert abs(har.p_bewegung(0.0, 0.3, 0.0) - 0.5) < 1e-9
    assert har.phi_standard(0.0) == 0.5


def test_quantile_range_symmetrie():
    q = har.quantile_range(mu=math.log(0.02), sigma=0.3)
    verhaeltnis_oben = q["q90"] / q["q50"]
    verhaeltnis_unten = q["q50"] / q["q10"]
    assert abs(verhaeltnis_oben - verhaeltnis_unten) < 1e-9   # log-symmetrisch


# ── Brier/BSS/Reliability/Klimatologie ──────────────────────────────────

def test_brier_und_reliability_anker():
    p = [0.8, 0.2, 0.6, 0.4]
    y = [1, 0, 1, 0]
    assert _brier(p, y) == pytest.approx((0.04 + 0.04 + 0.16 + 0.16) / 4)
    rel = _reliability([0.25, 0.25, 0.25, 0.75], [1, 0, 0, 1])
    by_bin = {r["bin"]: r for r in rel}
    assert by_bin["0.2–0.4"]["n"] == 3
    assert by_bin["0.2–0.4"]["p_mittel"] == pytest.approx(0.25, abs=0.001)
    assert by_bin["0.2–0.4"]["beobachtet"] == pytest.approx(1 / 3, abs=0.001)


def test_klima_p_wertanker_nur_trainingszeilen():
    """Handgerechneter Wert: 100 Montage (50 Bewegungstage) + 50 Dienstage
    (0). Global p = 50/150; Shrinkage γ=2 Richtung Globalrate."""
    train = ([{"wochentag": 0, "bewegung": True},
              {"wochentag": 0, "bewegung": False}] * 50
             + [{"wochentag": 1, "bewegung": False}] * 50)
    p_global = 50 / 150
    alpha, beta = 2 * p_global, 2 * (1 - p_global)
    erwartet = (50 + alpha) / (100 + alpha + beta)
    assert _klima_p(train, 0) == pytest.approx(erwartet)
    # und die Regel „nur Wochentags-Zeilen zählen":
    assert _klima_p(train, 1) == pytest.approx((0 + alpha) / (50 + alpha + beta))


# ── Platt ────────────────────────────────────────────────────────────────

def test_platt_kalibriert_uebertriebene_sicherheit():
    """Konstant p=0.9, aber nur 50 % treffen ein → Platt zieht Richtung 0.5."""
    p_oos = [0.9] * 80
    y_oos = [1, 0] * 40
    a, b = har.platt_fitten(p_oos, y_oos)
    assert har.platt_anwenden(0.9, a, b) < 0.65


def test_platt_gute_kalibrierung_fast_unveraendert():
    """Konstant p=0.7 mit 70 %-Treffern → Platt bleibt nahe 0.7."""
    p_oos = [0.7] * 100
    y_oos = [1] * 70 + [0] * 30
    a, b = har.platt_fitten(p_oos, y_oos)
    assert 0.55 < har.platt_anwenden(0.7, a, b) < 0.85


# ── NFP-Proxy & GVZ-Parser ───────────────────────────────────────────────

def test_nfp_proxy_erster_freitag():
    assert nfp_proxy_datum(2026, 10) == date(2026, 10, 2)   # Fr
    assert nfp_proxy_datum(2026, 1) == date(2026, 1, 2)     # Fr
    assert nfp_proxy_datum(2024, 3) == date(2024, 3, 1)     # Fr


def test_gvz_parser():
    """Echtes Cboe-Format: DATE,GVZ (2 Spalten) — letzte Spalte gewinnt."""
    csv_text = ("DATE,GVZ\n"
                "09/22/2026,23.590000\n"
                "Müll,\n"
                "09/21/2026,23.310000\n")
    serie = parse_gvz_csv(csv_text)
    assert serie == {"2026-09-22": 23.59, "2026-09-21": 23.31}


# ── Walk-Forward auf synthetischen Zeilen ────────────────────────────────

def _synthetische_zeilen(n=400, seed=7):
    """Volatilitäts-Clustering: ln TR folgt AR(1) — Informationen, die NUR
    der HAR-Lag kennt (die Wochentags-Klimatologie A sieht sie nicht)."""
    rng = np.random.default_rng(seed)
    basis = math.log(0.012)
    ln_tr = basis
    history: list[float] = []
    zeilen = []
    wt, tage = 0, 0
    while len(zeilen) < n:
        tage += 1
        wt = (wt + 1) % 5
        ln_tr = 0.5 * ln_tr + 0.5 * basis + float(rng.normal(0, 0.30))
        tr_rel = math.exp(ln_tr)
        if len(history) >= 22:
            lag1 = history[-1]
            mean5 = math.log(sum(math.exp(h) for h in history[-5:]) / 5)
            mean22 = math.log(sum(math.exp(h) for h in history[-22:]) / 22)
            zeilen.append({
                "datum": (date(2022, 1, 3) + timedelta(days=tage)).isoformat(),
                "wochentag": wt,
                "y": ln_tr, "tr_rel": tr_rel,
                "schwelle_rel": 0.012,
                "bewegung": tr_rel > 0.012,
                "ln_lag1": lag1, "ln_mean5": mean5, "ln_mean22": mean22,
                "wd_di": float(wt == 1), "wd_mi": float(wt == 2),
                "wd_do": float(wt == 3), "wd_fr": float(wt == 4),
                "nfp": 0.0, "fomc": 0.0, "gold_termin": 0.0,
                "iv_daily": 0.012 / 2, "regime": lag1 - mean22,
            })
        history.append(ln_tr)
    return zeilen


def test_walk_forward_findet_clustering_signal():
    """AR(1)-Clustering → B_har muss die Wochentags-Klimatologie schlagen."""
    ergebnis = walk_forward(_synthetische_zeilen())
    assert ergebnis["ok"]
    b_har = next(e for e in ergebnis["ergebnisse"]
                 if e["konfiguration"] == "B_har")
    assert b_har["bss"] > 0.02      # echter Informationsgewinn über A hinaus


def test_walk_forward_zu_wenig_zeilen():
    assert not walk_forward(_synthetische_zeilen(50))["ok"]

