# -*- coding: utf-8 -*-
"""Wochenlauf (S2): Kurse aktualisieren → Kalender abrufen (Snapshots) →
Wochenmatrix bauen. Alles wird im Journal protokolliert; jeder Schritt
arbeitet auf lokalen Daten weiter (Resilienz-Prinzip aus dem Konzept §4)."""
from __future__ import annotations

from .adapter import kalender
from .modell.quant_feeds import gvz_aktualisieren
from .mt5 import kurse
from .wochenmatrix import baue_matrix


def starten(db, settings: dict) -> dict:
    """Läuft synchron (UI zeigt Aktivitäts-Badge). Rückgabe: Gesamtprotokoll."""
    protokoll: dict = {"kurse": {}, "kalender": {}, "gvz": {}, "matrix": {}}

    # 1) Kurse frisch halten (Fehler tolerieren: DB-Bestand reicht notfalls)
    lauf = db.lauf_starten("wochenlauf",
                           "Kurse + Kalender + GVZ + Klimatologie/HAR-Matrix (S2/S3)")
    try:
        ergebnis = kurse.kurse_holen(settings)
        if ergebnis.get("ok"):
            neu = sum(db.raten_speichern(ergebnis["symbol"], tf, bars)
                      for tf, bars in ergebnis["raten"].items())
            protokoll["kurse"] = {"ok": True, "terminal": ergebnis["terminal"],
                                  "bars": ergebnis["bars"], "neu": neu}
        else:
            protokoll["kurse"] = {"ok": False, "grund": ergebnis.get("grund")}
    except Exception as exc:
        protokoll["kurse"] = {"ok": False, "grund": f"{type(exc).__name__}: {exc}"}

    # 2) Kalender-Adapter (jede Quelle einzeln fehler-tolerant)
    protokoll["kalender"] = kalender.wochenabruf(db, settings)

    # 3) GVZ-Historie (implizite Volatilität) — Fehler tolerieren
    try:
        protokoll["gvz"] = gvz_aktualisieren(db, settings)
    except Exception as exc:
        protokoll["gvz"] = {"ok": False, "grund": f"{type(exc).__name__}: {exc}"}

    # 4) Matrix aus lokalen Daten (Klimatologie + HAR-Modell + Tor-T3-Backtest)
    matrix = baue_matrix(db, settings)
    protokoll["matrix"] = {"ok": True, "woche": matrix["woche"],
                           "modell": matrix["modell"]}

    db.schritt(lauf, "wochenlauf", "gesamt",
               "kurse→kalender→gvz→matrix",
               f"kurse={'ok' if protokoll['kurse'].get('ok') else 'DB-Fallback'} · "
               f"kalender={'ok' if protokoll['kalender'].get('ok') else 'teilweise'} · "
               f"gvz={'ok' if protokoll['gvz'].get('ok') else 'fehlt'} · "
               f"matrix={matrix['modell']}",
               ok=protokoll["kalender"].get("ok", False))
    db.lauf_beenden(lauf, True)
    protokoll["matrix_objekt"] = matrix
    return protokoll
