# -*- coding: utf-8 -*-
"""Journal — Audit-Protokoll mit vollständigen Prompts und Antworten."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import streamlit as st

from goldscanner.app_state import hole_db
from goldscanner.ui_design import page_header

page_header(
    "Journal",
    "Lauf- und Schritt-Protokoll",
    "Jeder Lauf mit VOLLSTÄNDIGEN Prompts und Antworten — Audit statt Trockenmodus "
    "(KiScanner-Prinzip). Grundlage für Backtests ohne Look-ahead.",
)

schritte = hole_db().letzte_schritte(50)
if not schritte:
    st.info("Noch keine Läufe. Starte einen Kursabruf, einen Quellen-Check oder den "
            "GLM-Ping — alles landet hier.")
    st.stop()

df = pd.DataFrame([{
    "Zeit": z["zeit"][:19],
    "Lauf": z["lauf"] or f"#{z['lauf_id']}",
    "Agent": z["agent"] or "",
    "Art": z["art"] or "",
    "Modell": z["modell"] or "",
    "Tokens": z["tokens"] if z["tokens"] is not None else "",
    "Dauer s": z["dauer_s"] if z["dauer_s"] is not None else "",
    "OK": "✓" if z["ok"] else "✗",
    "Fehler": z["fehler"] or "",
} for z in schritte])
st.dataframe(df, width='stretch', hide_index=True,
             column_config={"Fehler": st.column_config.TextColumn(width="large")})

st.subheader("Detail", width="content")
auswahl = st.selectbox(
    "Schritt wählen",
    range(len(schritte)),
    format_func=lambda i: f"{schritte[i]['zeit'][:19]} · {schritte[i]['lauf']} · "
                          f"{schritte[i]['agent']} · {schritte[i]['art']} "
                          f"({'✓' if schritte[i]['ok'] else '✗'})")
z = schritte[auswahl]
c1, c2 = st.columns(2, gap="medium")
with c1:
    st.caption("Prompt")
    st.code(z["prompt"] or "(leer)", language=None)
with c2:
    st.caption("Antwort")
    st.code(z["antwort"] or "(leer)", language=None)
if z["fehler"]:
    st.error(z["fehler"])
