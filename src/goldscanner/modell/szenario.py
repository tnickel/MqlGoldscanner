"""S7-Bausteine: Wochen-Summenwert und Was-wäre-wenn-Simulation.

**Wochen-Summenwert** („mindestens ein Bewegungstag diese Woche"):
- Modell: 1 − ∏(1 − p_t) unter der (vereinfachenden) Unabhängigkeitsannahme —
  Bewegungstage clustern real (Volatilitäts-Persistenz), deshalb zusätzlich …
- Basisrate: empirischer Anteil der Wochen mit ≥1 Bewegungstag (k=1.0) aus
  der eigenen Historie — das ist die ehrliche Messlatte für den Summenwert.

**Was-wäre-wenn** (klar als Simulation gekennzeichnet, verändert NICHTS an
der gespeicherten Prognose): verschiebt mu/sigma der gespeicherten Modell-
Verteilung je Tag und rechnet P neu — dieselbe Formel wie das echte Modell
(har.p_bewegung), nur mit verschobenen Parametern.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone


def wochen_summenwert(matrix: dict, d1: list[dict], k: float = 1.0) -> dict | None:
    """P(≥1 Bewegungstag) für die Matrix-Woche. Rückgabe None ohne Modell-P."""
    p_tage = [t.get("p_stat") for t in matrix.get("tage", [])]
    p_tage = [p for p in p_tage if p is not None]
    if not p_tage:
        return None
    unabhaengig = 1.0 - math.prod(1.0 - min(max(p, 0.0), 1.0) for p in p_tage)

    # Historische Basisrate: Wochen (Mo-Fr) mit ≥1 Bewegungstag. Bewegungstag
    # je Tag über die Tages-Range (high-low) gegen den Wochentags-Ø der Woche?
    # Konsistent zur Matrix-Definition: TR > k × Ø-TR des Wochentags (Fenster).
    from ..klimatologie import wochentags_statistik
    stat = wochentags_statistik(d1, k=k, fenster=13)
    je_wt = stat["je_wochentag"]
    # wochentags_statistik liefert je Wochentag p (Bewegungstag-Rate); daraus
    # folgt die Unabhängigkeits-Basisrate der Woche:
    basis_unabh = 1.0 - math.prod(1.0 - (s["p"] if s else 0.0)
                                  for s in (je_wt.get(wt) for wt in range(5)))
    n_global = stat.get("n_global", 0)
    # Grobe Wochen-Anzahl: bewertete Tage / 5
    n_wochen = n_global // 5 if n_global else None
    return {
        "p_mindestens_ein_modell": round(unabhaengig, 4),
        "p_mindestens_ein_klima": round(basis_unabh, 4),
        "n_tage_modell": len(p_tage),
        "n_wochen_schaetzung": n_wochen,
        "hinweis": ("Unabhängigkeitsannahme: real clustern Bewegungstage "
                    "(Volatilitäts-Persistenz) — der wahre Wert liegt "
                    "typischerweise UNTER dem Produkt mit positiver Korrelation."),
    }


def was_waere_wenn(je_tag_mu_sigma: dict[str, tuple[float, float]],
                   ln_schwellen: dict[str, float],
                   vola_shift_pct: float = 0.0,
                   mu_shift_pct: float = 0.0,
                   event_zuschlag_pp: float = 0.0) -> dict[str, float]:
    """Simulation: verschiebt die Modell-Verteilung und rechnet P je Tag neu.

    je_tag_mu_sigma: {datum: (mu, sigma)} der gespeicherten Prognose (ln-TR).
    ln_schwellen:   {datum: ln(schwelle_rel)} der gespeicherten Prognose.
    vola_shift_pct: Sigma-Multiplikator in % (z. B. +30 = 30 % mehr Vola).
    mu_shift_pct:   Multiplikator auf exp(mu) (Range-Niveau) in %.
    event_zuschlag_pp: additive pp auf das Ergebnis je Tag.
    """
    from . import har
    sigma_faktor = 1.0 + vola_shift_pct / 100.0
    mu_additiv = math.log(1.0 + mu_shift_pct / 100.0)
    aus: dict[str, float] = {}
    for datum, (mu, sigma) in je_tag_mu_sigma.items():
        ln_b = ln_schwellen.get(datum)
        if ln_b is None:
            continue
        p = har.p_bewegung(mu + mu_additiv, sigma * sigma_faktor, ln_b)
        p = min(max(p + event_zuschlag_pp / 100.0, 0.0), 1.0)
        aus[datum] = round(p, 4)
    return aus
