# -*- coding: utf-8 -*-
"""Lauf-Zustand für den Live-Stepper (S: Wochenlauf im Hintergrund-Thread).

Streamlit führt Seitenskripte bei jedem Rerun neu aus — module-Level-Dicts
in Seiten fielen also jedes Mal zurück. Dieses importierte Modul bleibt
dank Modul-Cache über Reruns hinweg bestehen und ist die eine,
prozessweite Wahrheit darüber, was der gerade laufende Wochenlauf tut.

Der Worker-Thread schreibt (mit Lock), das Dashboard-Fragment liest.
Einfache Zuweisungen auf ein dict sind unter CPython/GIL ohnehin atomar —
das Lock ist Disziplin statt Notwendigkeit.
"""
from __future__ import annotations

import threading
from datetime import datetime

_zustand: dict = {
    "aktiv": False,
    "station": None,        # Schlüssel der laufenden Station (z. B. "matrix")
    "stationen": [],        # Reihenfolge für die Anzeige
    "meldungen": [],        # Live-Zeilen für den Feed (neueste zuletzt)
    "fertig": False,
    "fehler": None,         # Fehlertext, falls der Lauf crashte
    "protokoll": None,      # Rückgabe von wochenlauf.starten
    "start_zeit": None,
}
_lock = threading.Lock()
_MAX_MELDUNGEN = 30


def zuruecksetzen(stationen: list[str]) -> None:
    with _lock:
        _zustand.update(aktiv=True, station=None, stationen=list(stationen),
                        meldungen=[], fertig=False, fehler=None,
                        protokoll=None,
                        start_zeit=datetime.now().isoformat(timespec="seconds"))


def station_setzen(schluessel: str, text: str | None = None) -> None:
    with _lock:
        if _zustand["aktiv"]:
            _zustand["station"] = schluessel
            if text:
                _zustand["meldungen"] = (_zustand["meldungen"] + [text]
                                         )[-_MAX_MELDUNGEN:]


def beenden(protokoll: dict | None = None, fehler: str | None = None) -> None:
    with _lock:
        _zustand.update(aktiv=False, fertig=True, protokoll=protokoll,
                        fehler=fehler)


def lesen() -> dict:
    with _lock:
        return dict(_zustand)


def laeuft() -> bool:
    with _lock:
        return bool(_zustand["aktiv"])
