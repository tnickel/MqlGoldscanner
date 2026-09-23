# -*- coding: utf-8 -*-
"""Tagessicht — Platzhalter bis Stufe 2/3 (Event-Zeitleiste, Treiber)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from goldscanner.ui_design import page_header

page_header(
    "Tagessicht · geplant",
    "Detailansicht eines Wochentags",
    "Aktiv ab Stufe 2/3, sobald Kalender-Adapter und Prognosemodell laufen.",
)

links, rechts = st.columns(2, gap="medium")
with links:
    with st.container(border=True):
        st.subheader("Geplant (Konzept §6/§9)", width="content")
        st.markdown(
            "· **Zeitleiste der Events** mit Uhrzeiten (Europe/Berlin), High-Impact "
            "markiert, Actual vs. Forecast mit Surprise (MT5-Kalender-Exporter, S2)\n\n"
            "· **Treiber-Karten**: News-Stimmung, Chart-Lage, Positionierung, "
            "implizite Volatilität\n\n"
            "· **Ampel-Matrix der Faktoren** mit Berechnungstext im Tooltip "
            "(wie der KiScanner)\n\n"
            "· **Intraday-Update ab S5**: Asia-Range um 08:00 MEZ aktualisiert die "
            "Tages-Prognose")
with rechts:
    with st.container(border=True):
        st.subheader("Vorbereitung läuft", width="content")
        st.markdown(
            "Die Event-Quellen sind bereits im **Quellen-Launch-Check** verankert — "
            "der Check zeigt live, ob ForexFactory, BLS/BEA, Fed und TreasuryDirect "
            "aus deinem Netz erreichbar und formatplausibel sind.")
        st.info("Wochenmatrix (S2) und kalibrierte Prognose (S3) bauen auf genau diesen "
                "Adaptern auf — nichts davon wird doppelt gebaut.")
