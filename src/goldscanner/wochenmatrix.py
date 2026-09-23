# -*- coding: utf-8 -*-
"""Wochenmatrix v2 im Statistik-Modus (S2) — das erste echte Kernprodukt:

Je Wochentag (Mo–Fr): Klimatologie-Wahrscheinlichkeit P(Bewegungstag) mit
Shrinkage, Schwelle B in USD/%, Range-Band Q10–Q90, Top-Events (Kalender +
Regeltermine) und 5-stufige Warnstufe. Bewusst mit Vermerk „unkalibriert" —
Kalibrierung/Modell kommt in S3 (BSS gegen genau diese Basisrate).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .adapter.kalender import dedup_ereignisse
from .klimatologie import (WEEKDAY_NAMEN, schwelle_naechster_tag, warnstufe,
                           wochentags_statistik)

BERLIN = ZoneInfo("Europe/Berlin")

KLASSEN_FUER_MATRIX = (1.0, 1.5, 2.0)   # Schwellen-Tabelle P(TR > k×Ø)


def montag_von(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _berlin_zeit(zeit_utc: str | None) -> str:
    if not zeit_utc:
        return "ganztag"
    dt = datetime.fromisoformat(zeit_utc).astimezone(BERLIN)
    return dt.strftime("%H:%M")


def baue_matrix(db, settings: dict, basis: date | None = None) -> dict:
    symbol = settings.get("mt5_symbol", "XAUUSD")
    fenster = int(settings.get("matrix_fenster", 13))
    d1 = db.raten_laden(symbol, "d1")

    statistiken = {k: wochentags_statistik(d1, k=k, fenster=fenster)
                   for k in KLASSEN_FUER_MATRIX}
    basis_stat = statistiken[1.0]
    p_global = basis_stat["p_global"]

    montag = montag_von(basis or date.today())
    tage: list[dict] = []
    for i in range(5):
        d = montag + timedelta(days=i)
        wt = d.weekday()
        events = dedup_ereignisse(db.events_fuer_zeitraum(d.isoformat(), d.isoformat()))
        top = sorted(events, key=lambda e: (-(e.get("gold_relevanz") or 0),
                                            -(e.get("wichtigkeit") or 0)))[:4]
        stat = basis_stat["je_wochentag"].get(wt)
        schwelle = schwelle_naechster_tag(d1, wt, 1.0, fenster)
        close = schwelle["close_referenz"] if schwelle else None

        p = stat["p"] if stat else None
        tage.append({
            "datum": d.isoformat(),
            "wochentag": WEEKDAY_NAMEN[wt],
            "p": p,
            "p_roh": stat["p_roh"] if stat else None,
            "n": stat["n"] if stat else 0,
            "delta_zu_basis": round(p - p_global, 4) if p is not None else None,
            "warnstufe": warnstufe(p) if p is not None else "–",
            "schwelle_usd": schwelle["schwelle_usd"] if schwelle else None,
            "schwelle_pct": schwelle["schwelle_pct"] if schwelle else None,
            "q10_usd": round(stat["q10_tr_rel"] * close, 1) if stat and close else None,
            "q50_usd": round(stat["median_tr_rel"] * close, 1) if stat and close else None,
            "q90_usd": round(stat["q90_tr_rel"] * close, 1) if stat and close else None,
            "events_count": len(events),
            "top_events": [{
                "zeit": _berlin_zeit(e["zeit_utc"]),
                "titel": e["titel"],
                "gold_relevanz": e.get("gold_relevanz"),
                "klasse": e.get("klasse"),
                "forecast": e.get("forecast"),
                "previous": e.get("previous"),
                "actual": e.get("actual_latest") or e.get("actual_first"),
            } for e in top],
        })

    # Schwellen-Tabelle: P(TR > 1,0×/1,5×/2,0× Ø-TR) je Wochentag
    schwellen_tabelle = []
    for wt in range(5):
        zeile = {"Wochentag": WEEKDAY_NAMEN[wt]}
        for k in KLASSEN_FUER_MATRIX:
            stat = statistiken[k]["je_wochentag"].get(wt)
            zeile[f"Jahr P(>{k:.1f}×)"] = (f"{stat['p'] * 100:.0f} %"
                                           if stat else "–")
        stat1 = statistiken[1.0]["je_wochentag"].get(wt)
        zeile["n"] = stat1["n"] if stat1 else 0
        zeile["Median TR"] = (f"{stat1['median_tr_rel'] * 100:.2f} %"
                              if stat1 else "–")
        schwellen_tabelle.append(zeile)

    matrix = {
        "woche": montag.isoformat(),
        "bis": (montag + timedelta(days=4)).isoformat(),
        "modell": "klimatologie_v1 (unkalibriert)",
        "erzeugt_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "basis": {
            "symbol": symbol, "bars_d1": len(d1), "fenster": fenster,
            "p_global": p_global, "n_global": basis_stat["n_global"],
        },
        "tage": tage,
        "schwellen_tabelle": schwellen_tabelle,
    }
    db.prognose_speichern(matrix["woche"], matrix["modell"],
                          json.dumps(matrix, ensure_ascii=False))
    return matrix
