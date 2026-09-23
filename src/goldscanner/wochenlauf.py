# -*- coding: utf-8 -*-
"""Wochenlauf (S2): Kurse aktualisieren → Kalender abrufen (Snapshots) →
Wochenmatrix bauen. Alles wird im Journal protokolliert; jeder Schritt
arbeitet auf lokalen Daten weiter (Resilienz-Prinzip aus dem Konzept §4)."""
from __future__ import annotations

from .adapter import kalender
from .mt5 import kurse
from .wochenmatrix import baue_matrix


def starten(db, settings: dict) -> dict:
    """Läuft synchron (UI zeigt Aktivitäts-Badge). Rückgabe: Gesamtprotokoll."""
    protokoll: dict = {"kurse": {}, "kalender": {}, "matrix": {}}

    # 1) Kurse frisch halten (Fehler tolerieren: DB-Bestand reicht notfalls)
    lauf = db.lauf_starten("wochenlauf", "Kurse + Kalender + Klimatologie-Matrix (S2)")
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

    # 3) Matrix aus lokalen Daten
    matrix = baue_matrix(db, settings)
    protokoll["matrix"] = {"ok": True, "woche": matrix["woche"],
                           "p_global": matrix["basis"]["p_global"]}

    db.schritt(lauf, "wochenlauf", "gesamt",
               "kurse→kalender→matrix",
               f"kurse={'ok' if protokoll['kurse'].get('ok') else 'DB-Fallback'} · "
               f"kalender={'ok' if protokoll['kalender'].get('ok') else 'teilweise'} · "
               f"matrix={matrix['woche']}",
               ok=protokoll["kalender"].get("ok", False))
    db.lauf_beenden(lauf, True)
    protokoll["matrix_objekt"] = matrix
    return protokoll
