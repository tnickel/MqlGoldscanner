# -*- coding: utf-8 -*-
"""Track-Record — Platzhalter bis Stufe 3/6 (Prognosequalität messbar)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from goldscanner.ui_design import page_header

page_header(
    "Track-Record · geplant",
    "Prognosequalität messbar machen",
    "Aktiv, sobald die ersten Prognosen verifiziert sind — Stufe 3 erzeugt die Zahlen, "
    "Stufe 6 die Seite. Grundlage entsteht jetzt: jede Prognose wird as_of-versioniert "
    "gespeichert (kein Look-ahead).",
)

links, rechts = st.columns(2, gap="medium")
with links:
    with st.container(border=True):
        st.subheader("Geplante Kennzahlen", width="content")
        st.markdown(
            "· **Reliability-Diagramm** mit Konsistenzbalken: sagte „70 %“, kam es in "
            "~70 % der Fälle?\n\n"
            "· **Brier-Skill-Score gegen die Klimatologie** (~43 %) über 13/52 Wochen\n\n"
            "· **Richtungstreffer** und **Coverage der Range-Bänder** (Q10–Q90)\n\n"
            "· **LLM-Delta-Nutztwert**: bringt die Abweichung des Analytikers von P_stat "
            "historisch etwas?")
with rechts:
    with st.container(border=True):
        st.subheader("Wichtigste Regel", width="content")
        st.markdown(
            "Jede Prognose muss die **Basisrate ~43 %** schlagen (BSS > 0) — sonst hat "
            "das Agentensystem keinen messbaren Mehrwert gegenüber einer sauberen "
            "Klimatologie. Genau das misst der Entscheidungstest T3 im Stufenplan.")
        st.info("Marktlücke laut Deep Research: Kein Produkt liefert kalibrierte "
                "Bewegungswahrscheinlichkeiten je Wochentag mit Track-Record — genau "
                "das ist das Alleinstellungsmerkmal.")
