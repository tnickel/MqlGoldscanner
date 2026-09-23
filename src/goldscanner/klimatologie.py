"""Klimatologie — die statistische Basisrate der Wochenmatrix (S2).

Definition (Konzept §2): Bewegungstag = True Range > k × Ø-True-Range desselben
Wochentags der vorherigen `fenster` Wochen (Default k=1,0, 13 Wochen) —
STRIKT point-in-time: für jeden historischen Tag wird die Schwelle nur aus
Daten VOR diesem Tag gebildet (kein Look-ahead, Grundlage für spätere
Walk-forward-Verifikation).

Lange Historien werden über die RELATIVE True Range (TR/Close) vergleichbar
gehalten — der Goldpreis hat sich seit 2022 mehr als verdoppelt.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone

WEEKDAY_NAMEN = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
                 "Samstag", "Sonntag"]

# 5-stufige Warnskala zentriert um die Basisrate (~43 % = „normal")
_WARNSTUFEN = [(0.33, "ruhig"), (0.45, "normal"), (0.55, "erhöht"), (0.65, "hoch")]
WARNSTUFE_EXTREM = "extrem"


def warnstufe(p: float) -> str:
    for grenze, name in _WARNSTUFEN:
        if p < grenze:
            return name
    return WARNSTUFE_EXTREM


def quantil(werte: list[float], q: float) -> float:
    """Empirisches Quantil mit linearer Interpolation (0..1)."""
    if not werte:
        return float("nan")
    sortiert = sorted(werte)
    if len(sortiert) == 1:
        return sortiert[0]
    pos = q * (len(sortiert) - 1)
    unten = int(pos)
    oben = min(unten + 1, len(sortiert) - 1)
    anteil = pos - unten
    return sortiert[unten] * (1 - anteil) + sortiert[oben] * anteil


def _wochentag(bar: dict) -> int:
    return datetime.fromtimestamp(bar["time"], tz=timezone.utc).weekday()


def punkte_in_time_bewertungen(d1: list[dict], k: float = 1.0, fenster: int = 13,
                               min_vorgaenger: int = 6) -> list[dict]:
    """Bewertet jeden Bar gegen seine point-in-time-Schwelle.

    d1: aufsteigend nach time. Rückgabe je Bar (ab Bewertung):
    {time, wochentag, tr, tr_rel, schwelle, schwelle_rel, bewegung}.
    Bars mit weniger als `min_vorgaenger` Vorgängern desselben Wochentags
    bleiben unbewertet (Aufwärmphase) und fehlen in der Liste.
    """
    bewertungen: list[dict] = []
    vorgaenger: dict[int, deque] = defaultdict(lambda: deque(maxlen=fenster))
    letzter_close: float | None = None
    for bar in d1:
        if letzter_close is not None:
            tr = max(bar["high"] - bar["low"],
                     abs(bar["high"] - letzter_close),
                     abs(bar["low"] - letzter_close))
            tr_rel = tr / bar["close"] if bar["close"] else 0.0
            wt = _wochentag(bar)
            hist = vorgaenger[wt]
            if len(hist) >= min_vorgaenger:
                schwelle_rel = k * (sum(hist) / len(hist))
                bewertungen.append({
                    "time": bar["time"], "wochentag": wt,
                    "tr": tr, "tr_rel": tr_rel,
                    "schwelle": schwelle_rel * bar["close"] if bar["close"] else 0.0,
                    "schwelle_rel": schwelle_rel,
                    "bewegung": tr_rel > schwelle_rel,
                })
            hist.append(tr_rel)
        letzter_close = bar["close"]
    return bewertungen


def wochentags_statistik(d1: list[dict], k: float = 1.0, fenster: int = 13,
                         shrinkage_staerke: float = 2.0) -> dict:
    """Je Wochentag: Basisrate (roh und geschrumpft Richtung GesamtRate),
    Beobachtungszahl und relative TR-Quantile (Q10/50/90).

    Shrinkage: p = (treffer + γ·p_global) / (n + γ) — zieht dünne Wochentage
    Richtung Gesamt-Basisrate statt blind gegen 50 %.
    """
    bewertungen = punkte_in_time_bewertungen(d1, k=k, fenster=fenster)
    gesamt_n = len(bewertungen)
    gesamt_treffer = sum(1 for b in bewertungen if b["bewegung"])
    p_global = gesamt_treffer / gesamt_n if gesamt_n else 0.5

    je_tag: dict[int, dict] = {}
    rels: dict[int, list[float]] = defaultdict(list)
    treffer: dict[int, int] = defaultdict(int)
    anzahlen: dict[int, int] = defaultdict(int)
    for b in bewertungen:
        rels[b["wochentag"]].append(b["tr_rel"])
        anzahlen[b["wochentag"]] += 1
        if b["bewegung"]:
            treffer[b["wochentag"]] += 1

    for wt in sorted(anzahlen):
        n = anzahlen[wt]
        p_roh = treffer[wt] / n
        alpha = shrinkage_staerke * p_global
        beta = shrinkage_staerke * (1 - p_global)
        je_tag[wt] = {
            "n": n,
            "treffer": treffer[wt],
            "p_roh": round(p_roh, 4),
            "p": round((treffer[wt] + alpha) / (n + alpha + beta), 4),
            "median_tr_rel": round(quantil(rels[wt], 0.5), 6),
            "q10_tr_rel": round(quantil(rels[wt], 0.10), 6),
            "q90_tr_rel": round(quantil(rels[wt], 0.90), 6),
        }
    return {
        "p_global": round(p_global, 4),
        "n_global": gesamt_n,
        "fenster": fenster,
        "k": k,
        "je_wochentag": je_tag,
    }


def schwelle_naechster_tag(d1: list[dict], wochentag: int, k: float = 1.0,
                           fenster: int = 13) -> dict | None:
    """Schwelle B für den NÄCHSTEN Tag mit Wochentag `wochentag`: Mittel der
    letzten `fenster` relativen TRs dieses Wochentags × k, in USD am letzten
    Close (regime-robust: Schätzung relativ, Ausgabe absolut)."""
    hist: deque = deque(maxlen=fenster)
    letzter_close: float | None = None
    vorgaenger_close: float | None = None
    for bar in d1:
        if vorgaenger_close is not None and bar["close"]:
            tr = max(bar["high"] - bar["low"],
                     abs(bar["high"] - vorgaenger_close),
                     abs(bar["low"] - vorgaenger_close))
            if _wochentag(bar) == wochentag:
                hist.append(tr / bar["close"])
        vorgaenger_close = bar["close"]
        letzter_close = bar["close"]
    if not hist or not letzter_close:
        return None
    schwelle_rel = k * (sum(hist) / len(hist))
    return {"k": k, "fenster": fenster, "n_basis": len(hist),
            "schwelle_rel": round(schwelle_rel, 6),
            "schwelle_usd": round(schwelle_rel * letzter_close, 2),
            "close_referenz": round(letzter_close, 2),
            "schwelle_pct": round(schwelle_rel * 100, 2)}
