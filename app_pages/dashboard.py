# -*- coding: utf-8 -*-
"""Dashboard — Stufen-Fortschritt, KPI-Karten, Systemstatus (Stufe 1)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from goldscanner import config, secrets_store
from goldscanner.app_state import hole_db
from goldscanner.kennzahlen import kennzahlen_aus_d1
from goldscanner.ui_design import page_header, zeige_stepper, status_feed

page_header(
    "Stufe 1 · Gerüst & Kurse",
    "Gold-Bewegungswahrscheinlichkeit je Wochentag",
    "Hauptziel: Für jeden Tag der Woche eine kalibrierte Aussage zu **Wahrscheinlichkeit**, "
    "**erwarteter Range** und **Richtung** — Statistik zuerst, LLM gewichtet erklärt "
    "(&plusmn;10-pp-Band). Aktuell läuft **Stufe 1** (Gerüst &amp; Kurse); die Wochenmatrix "
    "entsteht in Stufe 2 (Klimatologie) und wird in Stufe 3 kalibriert.",
)

zeige_stepper([
    {"nr": 1, "title": "Gerüst & Kurse", "status": "complete", "meta": "App · MT5 · GLM"},
    {"nr": 2, "title": "Klimatologie-Matrix", "status": "pending", "meta": "Kalender · Basisrate ~43 %"},
    {"nr": 3, "title": "Kalibriertes Modell", "status": "pending", "meta": "HAR · Events · iv30"},
    {"nr": 4, "title": "LLM-Erklärungen", "status": "pending", "meta": "Treiber · Begründung · PDF"},
    {"nr": 5, "title": "Richtung & Quant", "status": "pending", "meta": "P(hoch) · COT · FRED"},
    {"nr": 6, "title": "Betrieb & Track-Record", "status": "pending", "meta": "Daemon · BSS · Scout"},
    {"nr": 7, "title": "Ausbau", "status": "pending", "meta": "optional"},
], overall=1 / 7)

st.divider()

# ── KPI-Zeile: Kurse (live aus Session oder DB) + GLM-Status ───────────────
settings = config.load_settings()
symbol = settings.get("mt5_symbol", "XAUUSD")
kennz: dict = {}
quelle = ""

kurse = st.session_state.get("kurse")
if kurse and kurse.get("ok"):
    kennz = kurse.get("kennzahlen", {})
    quelle = f"live · {kurse.get('terminal', 'MT5')}"
else:
    try:
        d1 = hole_db().raten_laden(symbol, "d1")
        if d1:
            kennz = kennzahlen_aus_d1(d1)
            quelle = f"Datenbank · {len(d1)} D1-Bars"
    except Exception:
        kennz = {}

k1, k2, k3, k4, k5 = st.columns(5, gap="small", vertical_alignment="center")
with k1:
    st.metric(f"{symbol} Close", f"{kennz.get('close', '–')}",
              f"{kennz.get('veraenderung_heute_pct', 0):+.2f} %" if kennz else None,
              border=True)
with k2:
    st.metric("ATR 14 (D1) · USD", kennz.get("atr14_d1", "–"), border=True)
with k3:
    st.metric("TR heute · USD", kennz.get("tr_heute", "–"), border=True)
with k4:
    st.metric("RSI 14 (D1)", kennz.get("rsi14_d1", "–"), border=True)
with k5:
    st.metric("Trend vs. SMA10", "–" if kennz.get("trend_close_vs_sma10_pct") is None
              else f"{kennz['trend_close_vs_sma10_pct']:+.2f} %", border=True)
if quelle:
    st.caption(f"Kursgrundlage: {quelle} · Zeitangaben = MT5-Serverszeit")

st.divider()

links, rechts = st.columns([1.2, 1], gap="medium")
with links:
    with st.container(border=True):
        st.subheader("Systemstatus", width="content")
        key_da = bool(secrets_store.get_secret("glm_api_key"))
        endpunkt = "Coding (Abo)" if settings.get("glm_endpunkt") != "api" else "API (PAYG)"
        st.markdown(
            f"· GLM-Key: **{secrets_store.maskiert('glm_api_key')}**\n\n"
            f"· Endpunkt: **{endpunkt}** · Modelle `{settings.get('model_stufe1')}` / "
            f"`{settings.get('model_stufe2')}`\n\n"
            f"· MT5: Standard-Politik = Terminal wird **nicht selbst gestartet**"
            + (" *(Freigabe erteilt)*" if settings.get("mt5_start_erlauben") else "")
            + f"\n\n· Selbststart des Terminals beendet nur der Scanner **selbst gestartete** "
              f"Instanzen — dein laufendes MT5 bleibt am Leben")
        try:
            db = hole_db()
            st.markdown(
                f"· Kurse in DB: **{db.raten_anzahl(symbol, 'd1')}** D1 · "
                f"**{db.raten_anzahl(symbol, 'h4')}** H4 · "
                f"**{db.raten_anzahl(symbol, 'h1')}** H1\n\n"
                f"· Token-Budget heute: **{db.tokens_heute():,}** / "
                f"**{int(settings.get('llm_token_budget_tag', 2_000_000)):,}**".replace(",", "."))
        except Exception:
            st.caption("Datenbank wird beim ersten Zugriff angelegt.")
    with st.container(border=True):
        st.subheader("Letzte Läufe", width="content")
        try:
            zeilen = [f"{z['zeit'][:16]} · {z['lauf']} · {z['art']} "
                      + ("✓" if z["ok"] else f"✗ {z['fehler'] or ''}")
                      for z in hole_db().letzte_schritte(6)]
            status_feed(zeilen)
        except Exception:
            status_feed([])
with rechts:
    with st.container(border=True):
        st.subheader("So geht es weiter", width="content")
        st.markdown(
            "**S2 — Datengrundlage & Klimatologie**  \n"
            "Kalender-Adapter (ForexFactory, BLS/BEA, Fed), regelbasierte Termine, "
            "Snapshot-Archiv — erste Wochenmatrix rein statistisch (Basisrate ~43 %).\n\n"
            "**S3 — Prognosemodell**  \n"
            "HAR auf ln(TR), gemessene Event-Multiplikatoren, GVZ/iv30, Walk-forward mit "
            "Brier-Skill-Score gegen die Klimatologie.\n\n"
            "**S4 — LLM-Schicht**  \n"
            "News-/Community-Destillation, Analytiker im ±10-pp-Band mit Treiber-Wasserfall, "
            "Wochen-PDF.")
    with st.container(border=True):
        st.subheader("Nächste Schritte jetzt", width="content")
        st.markdown(
            "1. **Chart** öffnen → „Kurse laden“ (liest D1/H4/H1 aus deinem MT5)\n\n"
            "2. **Quellen** → Launch-Check über alle 16 Kern-URLs\n\n"
            "3. **Agenten** → GLM-Verbindung testen\n\n"
            "4. **Einstellungen** → Broker-Symbol/Endpunkt prüfen")
