# -*- coding: utf-8 -*-
"""Dashboard — Stufe 2: Wochenmatrix (Klimatologie), Schwellen-Tabelle, Status."""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import streamlit as st

from goldscanner import config, secrets_store
from goldscanner.app_state import hole_db
from goldscanner.kennzahlen import kennzahlen_aus_d1
from goldscanner.ui_design import page_header, status_feed, zeige_stepper
from goldscanner.wochenlauf import starten as wochenlauf_starten
from goldscanner.wochenmatrix import baue_matrix

page_header(
    "Stufe 2 · Klimatologie-Matrix",
    "Gold-Bewegungswahrscheinlichkeit je Wochentag",
    "Hauptziel: pro Tag **Wahrscheinlichkeit**, **erwartete Range** und (ab S5) "
    "**Richtung**. Diese Matrix ist rein statistisch — Basisrate je Wochentag mit "
    "Shrinkage, Schwelle B aus den letzten 13 Wochen desselben Wochentags "
    "(point-in-time, kein Look-ahead). Kalibriert wird ab Stufe 3 (BSS gegen die "
    "Basisrate ~43 %).",
)

zeige_stepper([
    {"nr": 1, "title": "Gerüst & Kurse", "status": "complete", "meta": "App · MT5 · GLM"},
    {"nr": 2, "title": "Klimatologie-Matrix", "status": "complete", "meta": "Kalender · Basisrate"},
    {"nr": 3, "title": "Kalibriertes Modell", "status": "pending", "meta": "HAR · Events · iv30"},
    {"nr": 4, "title": "LLM-Erklärungen", "status": "pending", "meta": "Treiber · Begründung · PDF"},
    {"nr": 5, "title": "Richtung & Quant", "status": "pending", "meta": "P(hoch) · COT · FRED"},
    {"nr": 6, "title": "Betrieb & Track-Record", "status": "pending", "meta": "Daemon · BSS · Scout"},
    {"nr": 7, "title": "Ausbau", "status": "pending", "meta": "optional"},
], overall=2 / 7)

settings = config.load_settings()

# ── Wochenlauf ────────────────────────────────────────────────────────────
links, mitte, rechts = st.columns([1, 1, 2.2], vertical_alignment="center")
with links:
    laufen = st.button("Wochenlauf starten", type="primary",
                       icon=":material/rocket_launch:")
with mitte:
    aktualisieren = st.button("Matrix neu bauen", icon=":material/refresh:",
                              help="Ohne neue Abrufe — nur Statistik auf lokalen Daten")
with rechts:
    letzter = hole_db().letzte_schritte(50)
    letzte_matrix = [z for z in letzter if z["lauf"] == "wochenlauf"]
    if letzte_matrix:
        st.caption(f"Letzter Wochenlauf · {letzte_matrix[0]['zeit'][:16].replace('T', ' · ')}")
    else:
        st.caption("Noch kein Wochenlauf — startet Kurse + Kalender + Matrix")

if laufen:
    from goldscanner.ui_design import aktivitaets_banner
    banner = aktivitaets_banner("Wochenlauf: Kurse → Kalender (5 Quellen) → Matrix …")
    protokoll = wochenlauf_starten(hole_db(), settings)
    banner.empty()
    st.session_state["matrix"] = protokoll["matrix_objekt"]
    kal = protokoll["kalender"]["status"]
    fehler = [q for q, s in kal.items() if not s.get("ok")]
    if protokoll["kurse"].get("ok"):
        k_info = (f"{protokoll['kurse']['terminal']} · "
                  + ", ".join(f"{tf}={n}" for tf, n in protokoll["kurse"]["bars"].items()))
    else:
        k_info = "DB-Fallback (" + str(protokoll["kurse"].get("grund", ""))[:60] + ")"
    st.toast(f"Wochenlauf fertig · Kalender: {len(kal) - len(fehler)}/{len(kal)} Quellen"
             + (f" (Fehler: {', '.join(fehler)})" if fehler else ""),
             icon=":material/check_circle:")
    st.caption(f"Kurse: {k_info}")

if aktualisieren:
    st.session_state["matrix"] = baue_matrix(hole_db(), settings)

matrix = st.session_state.get("matrix")
if matrix:
    st.divider()
    basis = matrix["basis"]
    woche_start = datetime.fromisoformat(matrix["woche"])
    st.subheader(f"Wochenmatrix · {matrix['woche']} bis {matrix['bis']}", width="content")
    st.caption(f"Modell **{matrix['modell']}** · Basisrate gesamt "
               f"**{basis['p_global'] * 100:.1f} %** (n={basis['n_global']}, "
               f"{basis['bars_d1']} D1-Bars, Fenster {basis['fenster']} W) · "
               "P = geschätzte Wahrscheinlichkeit eines Bewegungstags "
               "(TR > 1,0× Ø-TR des Wochentags)")

    _WARNFARBEN = {"ruhig": "#38BDF8", "normal": "#94A3B8", "erhöht": "#E8B84B",
                   "hoch": "#FB923C", "extrem": "#F43F5E"}
    spalten = st.columns(5, gap="small")
    for spalte, tag in zip(spalten, matrix["tage"]):
        with spalte:
            with st.container(border=True):
                d = datetime.fromisoformat(tag["datum"])
                st.markdown(f"**{tag['wochentag']}** · {d.strftime('%d.%m.')}")
                p = tag["p"]
                st.metric("P(Bewegung)", "–" if p is None else f"{p * 100:.0f} %",
                          None if tag["delta_zu_basis"] is None
                          else f"{tag['delta_zu_basis'] * 100:+.0f} pp",
                          border=True, label_visibility="collapsed")
                if p is not None:
                    st.progress(min(p, 1.0))
                farbe = _WARNFARBEN.get(tag["warnstufe"], "#94A3B8")
                st.markdown(f'<span style="color:{farbe};font-weight:700">'
                            f'● {tag["warnstufe"].upper()}</span>',
                            unsafe_allow_html=True)
                st.caption(f"Schwelle B: {tag['schwelle_usd']} USD "
                           f"({tag['schwelle_pct']} %)")
                if tag["q10_usd"] is not None:
                    st.caption(f"Range Q10–Q90: {tag['q10_usd']}–{tag['q90_usd']} USD"
                               f" (Q50 {tag['q50_usd']})")
                if tag["top_events"]:
                    for e in tag["top_events"]:
                        sterne = "★" * (e.get("gold_relevanz") or 0)
                        st.caption(f"{e['zeit']} · {e['titel'][:34]} {sterne}")
                    if tag["events_count"] > len(tag["top_events"]):
                        st.caption(f"+{tag['events_count'] - len(tag['top_events'])} weitere")
                else:
                    st.caption("keine Ereignisse verzeichnet")
                st.caption(f"n={tag['n']} · unkalibriert")

    with st.expander("Schwellen-Tabelle — P(TR > k × Ø-TR des Wochentags)"):
        st.dataframe(pd.DataFrame(matrix["schwellen_tabelle"]), hide_index=True,
                     width="stretch")
        st.caption("1,0× = Bewegungstag-Definition · 1,5×/2,0× zeigen das "
                   "Extremrisiko (USGS-Vorbild). n = bewertete Tage je Wochentag "
                   "nach Aufwärmphase.")
else:
    st.info("Noch keine Matrix in dieser Sitzung. **„Wochenlauf starten“** holt Kurse "
            "und Kalender (ForexFactory, BLS, BEA, Fed, Treasury, Regeltermine) und "
            "baut die Wochenmatrix. Alternativ lädt „Matrix neu bauen“ die Statistik "
            "auf bereits gespeicherten Kursen.")

st.divider()

# ── KPI-Zeile ─────────────────────────────────────────────────────────────
symbol = settings.get("mt5_symbol", "XAUUSD")
kennz: dict = {}
quelle = ""
kurse_state = st.session_state.get("kurse")
if kurse_state and kurse_state.get("ok"):
    kennz = kurse_state.get("kennzahlen", {})
    quelle = f"live · {kurse_state.get('terminal', 'MT5')}"
else:
    d1 = hole_db().raten_laden(symbol, "d1")
    if d1:
        kennz = kennzahlen_aus_d1(d1)
        quelle = f"Datenbank · {len(d1)} D1-Bars"

k1, k2, k3, k4, k5 = st.columns(5, gap="small", vertical_alignment="center")
with k1:
    st.metric(f"{symbol} Close", kennz.get("close", "–"),
              None if not kennz else f"{kennz.get('veraenderung_heute_pct', 0):+.2f} %",
              border=True)
with k2:
    st.metric("ATR 14 (D1) · USD", kennz.get("atr14_d1", "–"), border=True)
with k3:
    st.metric("TR heute · USD", kennz.get("tr_heute", "–"), border=True)
with k4:
    st.metric("RSI 14 (D1)", kennz.get("rsi14_d1", "–"), border=True)
with k5:
    st.metric("Kalender-Events", hole_db().events_anzahl(), border=True)
if quelle:
    st.caption(f"Kursgrundlage: {quelle} · Zeitangaben = MT5-Serverszeit")

st.divider()

# ── Status-Spalten ────────────────────────────────────────────────────────
links, rechts = st.columns([1.2, 1], gap="medium")
with links:
    with st.container(border=True):
        st.subheader("Systemstatus", width="content")
        endpunkt = "Coding (Abo)" if settings.get("glm_endpunkt") != "api" else "API (PAYG)"
        st.markdown(
            f"· GLM-Key: **{secrets_store.maskiert('glm_api_key')}** · Endpunkt **{endpunkt}**\n\n"
            f"· MT5: Terminal wird "
            f"{'**selbst gestartet (portabel)**' if settings.get('mt5_start_erlauben') else '**nicht selbst gestartet** (Standard)'}\n\n"
            f"· Actuals: **MT5-Exporter** (mql5/CalendarExport.mq5) primär, Nasdaq-Fallback")
        db = hole_db()
        st.markdown(
            f"· Kurse in DB: **{db.raten_anzahl(symbol, 'd1')}** D1 · "
            f"**{db.raten_anzahl(symbol, 'h1')}** H1\n\n"
            f"· Token-Budget heute: **{db.tokens_heute():,}** / "
            f"**{int(settings.get('llm_token_budget_tag', 2_000_000)):,}**".replace(",", "."))
    with st.container(border=True):
        st.subheader("Letzte Läufe", width="content")
        zeilen = [f"{z['zeit'][:16]} · {z['lauf']} · {z['art']} "
                  + ("✓" if z["ok"] else f"✗ {z['fehler'] or ''}")
                  for z in hole_db().letzte_schritte(6)]
        status_feed(zeilen)
with rechts:
    with st.container(border=True):
        st.subheader("So geht es weiter", width="content")
        st.markdown(
            "**S3 — Prognosemodell**  \n"
            "HAR auf ln(TR), gemessene Event-Multiplikatoren, GVZ/iv30 Expected Move, "
            "Walk-Forward mit Brier-Skill-Score. **Tor T3:** erst wenn BSS > 0 gegen "
            "diese Basisrate stabil ist, folgt die LLM-Schicht.\n\n"
            "**S4 — LLM-Erklärungen**  \n"
            "News-/Community-Destillation, Analytiker im ±10-pp-Band, Treiber-"
            "Wasserfall, Wochen-PDF.\n\n"
            "**S5 — Richtung & Quant-Feeds**  \n"
            "Richtungsmodell P(hoch), COT/GLD/FRED, Intraday-Update.")
    with st.container(border=True):
        st.subheader("Jetzt sinnvoll", width="content")
        st.markdown(
            "1. **mql5/CalendarExport.mq5** einmal im Terminal ausführen → Ist-Werte "
            "(Actuals) fließen in die Tagessicht\n\n"
            "2. **Tagessicht** öffnen: Event-Zeitleiste der Woche\n\n"
            "3. **Quellen** → Launch-Check; **Chart** → Kurse laden")
