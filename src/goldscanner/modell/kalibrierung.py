# -*- coding: utf-8 -*-
"""Nachkalibrierung (S5): Platt sofort, Isotonic ab ~500 Beobachtungen.

Beide arbeiten auf Roh-Scores eines Modells (z. B. Logit-Scores oder
Wahrscheinlichkeiten) und lernen die Zuordnung Score → kalibrierte
Wahrscheinlichkeit aus Trainingsdaten. Isotonic (PAVA = Pool Adjacent
Violators) ist die flexiblere, nichtparametrische Monoton-Regression —
stabil erst ab ~500 Beobachtungen (Faustregel aus dem Konzept §14),
darunter greift die 2-Parameter-Platt-Skalierung.
"""
from __future__ import annotations

import math


def platt_transform(scores: list[float], p_kalibriert_a: float,
                     p_kalibriert_b: float, score: float) -> float:
    """Platt: p = sigmoid(a·score + b) — Parameter aus dem Movement-Modell
    (har.platt_fitten) oder hier geschätzt."""
    z = p_kalibriert_a * score + p_kalibriert_b
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def isotonic_pava(x: list[float], y: list[float]) -> list[float]:
    """PAVA: monotone (aufsteigende) Fit-Werte zu (x, y)-Paaren.
    Rückgabe in der Original-Reihenfolge der Eingabe."""
    if len(x) != len(y) or not x:
        raise ValueError("isotonic_pava braucht gleich lange, nicht-leere Listen")
    reihenfolge = sorted(range(len(x)), key=lambda i: x[i])
    # Klassisches PAVA über die nach x sortierten y-Werte: [summe, n]-Blöcke
    bloecke: list[list[float]] = []
    for i in reihenfolge:
        bloecke.append([y[i], 1.0])
        while (len(bloecke) >= 2
               and bloecke[-2][0] / bloecke[-2][1] > bloecke[-1][0] / bloecke[-1][1]):
            letzter = bloecke.pop()
            vorletzter = bloecke[-1]
            vorletzter[0] += letzter[0]
            vorletzter[1] += letzter[1]
    sortiert: list[float] = []
    for summe, n in bloecke:
        sortiert.extend([summe / n] * int(n))
    ergebnis = [0.0] * len(x)
    for ziel_pos, wert in zip(reihenfolge, sortiert):
        ergebnis[ziel_pos] = wert
    return ergebnis


class IsotonicModell:
    """Schrittfunktion aus PAVA: predict(score) = Mittelwert des
    zugehörigen Trainings-Score-Buckets (monoton, oberster/unterster Rand
    werden fortgesetzt)."""

    def __init__(self, scores: list[float], ziele: list[float]):
        self.x, self.y = zip(*sorted(zip(scores, ziele))) if scores else ([], [])
        self.fit = isotonic_pava(list(self.x), list(self.y)) if scores else []
        # Aufeinanderfolgende gleiche Fit-Werte zu Stufen zusammenfassen
        self.stufen: list[tuple[float, float]] = []   # (x_grenze, p)
        for xi, pi in zip(self.x, self.fit):
            if not self.stufen or self.stufen[-1][1] != pi:
                self.stufen.append((xi, pi))

    @property
    def n(self) -> int:
        return len(self.x)

    def predict(self, score: float) -> float:
        if not self.stufen:
            return 0.5
        if score <= self.stufen[0][0]:
            return self.stufen[0][1]
        for x_grenze, p in reversed(self.stufen):
            if score >= x_grenze:
                return p
        return self.stufen[-1][1]


def kalibriere(scores: list[float], ziele: list[float]) -> tuple[str, object]:
    """Wählt automatisch: Isotonic ab 500 Beobachtungen, sonst Platt.
    Rückgabe: (methode, anwendbar(score)→kalibrierte Wahrscheinlichkeit)."""
    from . import har
    if len(scores) >= 500:
        modell = IsotonicModell(scores, ziele)
        return "isotonic_pava", modell.predict
    a, b = har.platt_fitten(scores, [int(y) for y in ziele])

    def _platt(score: float, _a=a, _b=b) -> float:
        z = _a * score + _b
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        e = math.exp(z)
        return e / (1.0 + e)

    return "platt", _platt
