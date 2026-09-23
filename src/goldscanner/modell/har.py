"""HAR-Kern (S3): OLS auf ln(TR_rel), Normal-CDF-Wahrscheinlichkeit,
rekursive Mehr-Tages-Prognose für die Wochenmatrix und Platt-Skalierung.

P(TR > B) = 1 − Φ((ln B − μ̂)/σ̂) mit μ̂ = X·β (Konzept §3.1).
"""
from __future__ import annotations

import math

import numpy as np


def phi_standard(z: float) -> float:
    """Standardnormal-Verteilungsfunktion (für Tests auch einzeln nutzbar)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def design_matrix(zeilen: list[dict], features: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """X mit Achsenabschnitt + y; Zeilen mit fehlenden Features werden verworfen."""
    nutzbar = [z for z in zeilen if all(z.get(f) is not None for f in features)]
    X = np.array([[1.0] + [z[f] for f in features] for z in nutzbar])
    y = np.array([z["y"] for z in nutzbar])
    return X, y


def ols_fit(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(X, y, rcond=None)[0]


def residuen_sigma(X: np.ndarray, y: np.ndarray, beta: np.ndarray) -> float:
    residuen = y - X @ beta
    return float(np.std(residuen, ddof=1)) if len(residuen) > 2 else 0.01


def p_bewegung(mu: float, sigma: float, ln_schwelle: float) -> float:
    """P(TR > Schwelle) unter Lognormal-Approximation von TR_rel."""
    if sigma <= 0:
        return 1.0 if mu > ln_schwelle else 0.0
    z = (ln_schwelle - mu) / sigma
    p = 1.0 - phi_standard(z)
    return min(max(p, 1e-6), 1 - 1e-6)


def quantile_range(mu: float, sigma: float) -> dict[str, float]:
    """Q10/Q50/Q90 der relativen TR als Faktoren (× Close = USD)."""
    return {"q10": math.exp(mu - 1.2816 * sigma),
            "q50": math.exp(mu),
            "q90": math.exp(mu + 1.2816 * sigma)}


# ── Mehr-Tages-Prognose (rekursiv, für die Wochenmatrix) ─────────────────

def mehr_tages(zeilen: list[dict], features: list[str], beta: np.ndarray,
               ziele: list[dict]) -> list[dict]:
    """Prognose für kommende Tage. `ziele`: [{datum, wochentag, events{...}, iv_daily}]
    je Ziel: μ̂_h, P(TR>B) mit übergebener ln-Schwelle und σ̂, Quantil-Faktoren.
    Rekursion: ln_lag1 ← Prognose des Vortags; mean5/mean22 rollen mit Prognosen."""
    nutzbar = [z for z in zeilen if all(z.get(f) is not None for f in features)]
    if not nutzbar:
        raise ValueError("keine nutzbaren Zeilen")
    history = [z["y"] for z in nutzbar]
    ergebnisse = []
    for ziel in ziele:
        ln_lag1 = history[-1]
        mean5 = sum(history[-5:]) / len(history[-5:])
        mean22 = sum(history[-22:]) / len(history[-22:])
        werte = {
            "ln_lag1": ln_lag1, "ln_mean5": mean5, "ln_mean22": mean22,
            "wd_di": float(ziel["wochentag"] == 1), "wd_mi": float(ziel["wochentag"] == 2),
            "wd_do": float(ziel["wochentag"] == 3), "wd_fr": float(ziel["wochentag"] == 4),
            "nfp": ziel["events"].get("nfp", 0.0), "fomc": ziel["events"].get("fomc", 0.0),
            "gold_termin": ziel["events"].get("gold_termin", 0.0),
            "iv_daily": ziel.get("iv_daily") if ziel.get("iv_daily") is not None else 0.0,
            "regime": ln_lag1 - mean22,
        }
        x = np.array([1.0] + [werte[f] for f in features])
        mu = float(x @ beta)
        history.append(mu)
        ergebnisse.append({
            "datum": ziel["datum"], "wochentag": ziel["wochentag"],
            "mu": mu, **{k: v for k, v in ziel.items() if k not in ("events",)},
            "quantile": quantile_range(mu, ziel["sigma"]),
        })
    return ergebnisse


# ── Platt-Skalierung (Nachkalibrierung auf OOS-Vorhersagen) ──────────────

def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z: float) -> float:
    """Numerisch stabile Sigmoid (math.exp überläuft bei |z| > ~709)."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def platt_fitten(p_oos: list[float], y_oos: list[int]) -> tuple[float, float]:
    """IRLS für P(y=1) = sigmoid(a·logit(p)+b). Rückgabe (a, b).
    Sonderfall konstantes p (Varianz 0): nur b ist identifizierbar →
    geschlossene Lösung, statt das singuläre 2D-Problem zu lösen.
    Newton-Schritte auf ±2 geclippt: bei perfekt trennbaren Daten divergiert
    IRLS sonst (Separations-Problem) — der Clip hält (a, b) endlich."""
    x = np.array([[_logit(p)] for p in p_oos])
    y = np.array([float(v) for v in y_oos])
    if float(np.var(x)) < 1e-12:
        rate = min(max(float(np.mean(y)), 1e-6), 1 - 1e-6)
        return 1.0, math.log(rate / (1 - rate)) - float(x[0].item())
    a, b = 1.0, 0.0
    for _ in range(50):
        z = a * x[:, 0] + b
        pr = np.array([_sigmoid(v) for v in z])
        w = np.maximum(pr * (1 - pr), 1e-9)
        gradient_b = np.sum(pr - y)
        gradient_a = np.sum((pr - y) * x[:, 0])
        hesse = np.array([[np.sum(w * x[:, 0] ** 2), np.sum(w * x[:, 0])],
                          [np.sum(w * x[:, 0]), np.sum(w)]])
        delta = np.linalg.solve(hesse + np.eye(2) * 1e-9,
                                -np.array([gradient_a, gradient_b]))
        delta = np.clip(delta, -2.0, 2.0)
        a, b = a + delta[0], b + delta[1]
        if abs(delta[0]) < 1e-9 and abs(delta[1]) < 1e-9:
            break
    return float(a), float(b)


def platt_anwenden(p: float, a: float, b: float) -> float:
    return min(max(_sigmoid(a * _logit(p) + b), 1e-6), 1 - 1e-6)
