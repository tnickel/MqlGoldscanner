# -*- coding: utf-8 -*-
"""Agenten — GLM-Zugang testen, Budget, geplante Rollen."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import streamlit as st

from goldscanner import config, secrets_store
from goldscanner.app_state import hole_db
from goldscanner.llm.client import (GlmClient, LlmBudgetError, LlmError,
                                    LlmIncompleteResponseError, LlmNoBalanceError)
from goldscanner.ui_design import aktivitaets_banner, page_header

page_header(
    "Agenten",
    "GLM-Zugang und geplante Rollen",
    "Die Agenten-Rollen gehen ab Stufe 2/3 an den Start. Hier kannst du den LLM-Zugang "
    "testen und das Tagesbudget beobachten — jedes Token wird in der Datenbank gebucht.",
)

settings = config.load_settings()
db = hole_db()

links, rechts = st.columns([1.1, 1], gap="medium")
with links:
    with st.container(border=True):
        st.subheader("GLM-Zugang (Z.ai)", width="content")
        endpunkt = "Coding-Endpunkt (Abo)" if settings.get("glm_endpunkt") != "api" \
            else "Standard-Endpunkt (PAYG)"
        st.markdown(
            f"· API-Key: **{secrets_store.maskiert('glm_api_key')}**\n\n"
            f"· Endpunkt: **{endpunkt}**  \n"
            f"`{config.glm_base_url(settings)}`\n\n"
            f"· Stufe 1 (Destillation): `{settings.get('model_stufe1')}`  \n"
            f"· Stufe 2 (Analytiker): `{settings.get('model_stufe2')}`")
        if st.button("GLM-Verbindung testen", type="primary", icon=":material/psychology:"):
            banner = aktivitaets_banner("GLM-Ping läuft (Reasoning-Tokens inklusive) …")
            lauf = db.lauf_starten("glm_ping", "GLM-Verbindungstest")
            try:
                client = GlmClient(settings.get("model_stufe1"), settings.get("model_stufe2"),
                                   max_total_tokens=int(settings.get("llm_max_total_tokens", 5_000_000)),
                                   timeout=60, base_url=config.glm_base_url(settings), db=db)
                ergebnis = client.test_connection()
                banner.empty()
                st.success(f"OK — Antwort: „{ergebnis['antwort']}“ · "
                           f"{ergebnis['usage']['total_tokens']} Tokens")
                db.schritt(lauf, "glm", "ping", "Antworte mit genau einem Wort: Test",
                           ergebnis["antwort"], modell=settings.get("model_stufe1", ""),
                           tokens=ergebnis["usage"]["total_tokens"], ok=True)
                db.lauf_beenden(lauf, True)
            except LlmNoBalanceError as e:
                banner.empty()
                st.error(str(e))
                db.schritt(lauf, "glm", "ping", ok=False, fehler=str(e))
                db.lauf_beenden(lauf, False)
            except LlmBudgetError as e:
                banner.empty()
                st.warning(str(e))
                db.schritt(lauf, "glm", "ping", ok=False, fehler=str(e))
                db.lauf_beenden(lauf, False)
            except (LlmIncompleteResponseError, LlmError) as e:
                banner.empty()
                st.error(str(e))
                db.schritt(lauf, "glm", "ping", ok=False, fehler=str(e))
                db.lauf_beenden(lauf, False)
    with st.container(border=True):
        heute = db.tokens_heute()
        max_tag = int(settings.get("llm_token_budget_tag", 2_000_000))
        st.metric("Token-Budget heute", f"{heute:,} / {max_tag:,}".replace(",", "."),
                  border=True)
        st.caption("Unvollständige Antworten zählen mit (KiScanner-Regel). "
                   "Limit in den Einstellungen anpassbar.")

with rechts:
    with st.container(border=True):
        st.subheader("Geplante Rollen (Konzept §5)", width="content")
        rollen = pd.DataFrame([
            {"Stufe": "S2", "Rolle": "Kalender-Adapter + Regeltermine", "Aufgabe": "FF/BLS/BEA/Fed/Treasury, FND/LTD/Opex berechnet"},
            {"Stufe": "S2", "Rolle": "Klimatologie-Statistik", "Aufgabe": "Basisrate je Wochentag, Schwelle B, Quantile"},
            {"Stufe": "S3", "Rolle": "HAR-Modell + Event-Multiplikatoren", "Aufgabe": "P(TR>B), gemessene Event-Wirkung"},
            {"Stufe": "S3", "Rolle": "Vola-/Options-Agent", "Aufgabe": "GVZ/iv30 → implizite Range vs. Schwelle"},
            {"Stufe": "S4", "Rolle": "News-/Community-Destillation", "Aufgabe": "Treiber mit Stimmung, Level-Cluster"},
            {"Stufe": "S4", "Rolle": "Analytiker (Fusion)", "Aufgabe": "±10-pp-Band um P_stat, Treiber-Wasserfall"},
            {"Stufe": "S5", "Rolle": "Richtungsmodell", "Aufgabe": "P(Close > Vortag), eigenkalibriert"},
            {"Stufe": "S5", "Rolle": "Makro-/Regime + Positionierung", "Aufgabe": "Realzins, Dollar, COT, GLD-Flows"},
            {"Stufe": "S6", "Rolle": "Verifikation + Dirigent + Scout", "Aufgabe": "BSS/Reliability, Orchestrrierung, neue Quellen"},
        ])
        st.dataframe(rollen, width='stretch', hide_index=True,
                     column_config={"Aufgabe": st.column_config.TextColumn(width="large")})
