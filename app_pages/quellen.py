# -*- coding: utf-8 -*-
"""Quellen — Launch-Check der geplanten Kern-URLs (erster Wächter-Baustein)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import streamlit as st

from goldscanner import config
from goldscanner.app_state import hole_db
from goldscanner.quellen_check import pruefen
from goldscanner.ui_design import aktivitaets_banner, page_header

page_header(
    "Quellen · Launch-Check",
    "Erreichbarkeit der Kern-Quellen",
    "Alle geplanten Datenquellen (Konzept §7, am 23.09.2026 verifiziert) werden einmal "
    "mit dem **ehrlichen User-Agent** abgefragt. Wächter-Prinzip: HTTP 200 allein "
    "beweist nichts — Content-Type und Inhalts-Signatur werden mitgeprüft.",
)

settings = config.load_settings()
st.caption(f"User-Agent: `{config.user_agent(settings.get('kontakt_fuer_useragent', ''))}` — "
           "Kontakt-Adresse in den Einstellungen hinterlegen (höflich, keine Browser-Vortäuschung).")

start = st.button("Launch-Check starten", type="primary", icon=":material/travel_explore:")
if start:
    banner = aktivitaets_banner("Prüfe 16 Quellen sequenziell (0,8 s Abstand) …")
    lauf = hole_db().lauf_starten("quellen_launch_check", "Erreichbarkeit der Kern-Quellen (S1)")
    ergebnisse = pruefen(settings)
    banner.empty()
    ok = sum(1 for e in ergebnisse if e["ok"])
    hole_db().quellen_status_speichern(ergebnisse)
    hole_db().schritt(lauf, "quellen", "launch_check",
                      f"{len(ergebnisse)} Quellen", f"{ok}/{len(ergebnisse)} OK",
                      ok=True)
    hole_db().lauf_beenden(lauf, True)
    st.session_state["quellen_ergebnisse"] = ergebnisse
    st.toast(f"{ok} von {len(ergebnisse)} Quellen OK", icon=":material/check_circle:")

ergebnisse = st.session_state.get("quellen_ergebnisse")
if not ergebnisse:
    st.info("Noch kein Check in dieser Sitzung. **„Launch-Check starten“** klicken — "
            "dauert rund 30 Sekunden (höflicher sequenzieller Abruf).")
    st.stop()

ok = sum(1 for e in ergebnisse if e["ok"])
m1, m2, m3 = st.columns(3, gap="small")
with m1:
    st.metric("Erreichbar + formatplausibel", f"{ok} / {len(ergebnisse)}", border=True)
with m2:
    blockiert = [e for e in ergebnisse if e["status"] in (401, 403, 429)]
    st.metric("Blockiert/Drossel", len(blockiert), border=True)
with m3:
    dauer = sum(e["dauer_ms"] for e in ergebnisse) / 1000
    st.metric("Gesamtdauer", f"{dauer:.1f} s", border=True)

df = pd.DataFrame([{
    "Quelle": e["name"],
    "Kategorie": e["kategorie"],
    "Status": e["status"] or "–",
    "OK": "✓" if e["ok"] else "✗",
    "Typ": (e["content_type"] or "–").split(";")[0],
    "Größe": f"{e['groesse'] / 1024:.0f} KB" if e["groesse"] else "–",
    "Dauer": f"{e['dauer_ms']} ms",
    "Hinweis": e["hinweis"],
} for e in ergebnisse])
st.dataframe(
    df,
    width='stretch',
    hide_index=True,
    column_config={
        "Quelle": st.column_config.TextColumn(width="medium"),
        "Hinweis": st.column_config.TextColumn(width="large"),
    },
)
