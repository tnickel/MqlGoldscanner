# -*- coding: utf-8 -*-
"""Einstellungen — MT5/GLM/Netz (Vorbild: KiScanner admin.py, Stufe-1-Umfang)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from goldscanner import config, secrets_store
from goldscanner.app_state import hole_db
from goldscanner.mt5 import kurse
from goldscanner.ui_design import aktivitaets_banner, page_header

page_header(
    "Einstellungen",
    "MetaTrader · GLM · Netz",
    "Alle Werte landen in `config/app_settings.json` · der GLM-Key in "
    "`config/secrets.local.json` (per .gitignore ausgeschlossen, niemals committen).",
)

settings = config.load_settings()

links, rechts = st.columns(2, gap="medium")
with links:
    with st.container(border=True):
        st.subheader("MetaTrader & Markt", width="content")
        symbol = st.text_input("Broker-Symbol (Suffix beachten)", value=settings.get("mt5_symbol", "XAUUSD"),
                               help="z. B. XAUUSD, XAUUSD.m, XAUUSD.x — beim Broker nachsehen")
        terminal_pfad = st.text_input(
            "Terminal-Pfad (terminal64.exe)", value=settings.get("mt5_terminal_pfad", ""),
            help="Leer lassen = Attach ans laufende Terminal (empfohlen, wenn MT5 ohnehin läuft)")
        start_erlauben = st.checkbox(
            "Terminal darf portabel gestartet werden, wenn es nicht läuft",
            value=bool(settings.get("mt5_start_erlauben")),
            help="Standard-Politik: aus. Selbst gestartete Instanzen werden nach dem Lauf beendet.")
        lookback = st.number_input("Lookback (Handelstage D1)", min_value=60, max_value=2000,
                                   value=int(settings.get("mt5_lookback_tage", 400)), step=50)
        zeitzone = st.selectbox("Zeitzone der Anzeige", ["Europe/Berlin", "UTC", "America/New_York"],
                                index=["Europe/Berlin", "UTC", "America/New_York"].index(
                                    settings.get("zeitzone", "Europe/Berlin")))
        if st.button("MT5-Verbindung testen", icon=":material/network_check:"):
            probe = {"mt5_symbol": symbol, "mt5_terminal_pfad": terminal_pfad,
                     "mt5_start_erlauben": start_erlauben}
            banner = aktivitaets_banner("Teste MT5-Verbindung (liest EINE Kerze) …")
            ergebnis = kurse.verbindung_testen(probe)
            banner.empty()
            (st.success if ergebnis["ok"] else st.error)(ergebnis["grund"])

with rechts:
    with st.container(border=True):
        st.subheader("GLM (Z.ai)", width="content")
        endpunkt = st.radio("Endpunkt", ["coding", "api"], index=0 if settings.get("glm_endpunkt") != "api" else 1,
                            format_func=lambda x: "coding — Abo (GLM Coding Plan)" if x == "coding"
                            else "api — Pay-as-you-go",
                            help="Falscher Endpunkt für deinen Key-Typ ⇒ Fehler 1113 (Insufficient balance)")
        model_stufe1 = st.text_input("Modell Stufe 1 (Destillation)", value=settings.get("model_stufe1"))
        model_stufe2 = st.text_input("Modell Stufe 2 (Analytiker)", value=settings.get("model_stufe2"))
        budget_lauf = st.number_input("Token-Budget je Lauf", min_value=100_000,
                                      value=int(settings.get("llm_max_total_tokens", 5_000_000)),
                                      step=500_000)
        budget_tag = st.number_input("Token-Budget je Tag", min_value=100_000,
                                     value=int(settings.get("llm_token_budget_tag", 2_000_000)),
                                     step=100_000)
        timeout = st.number_input("Timeout (Sekunden)", min_value=30,
                                  value=int(settings.get("llm_timeout_s", 300)), step=30)
        st.caption("**Analytiker-Disziplin (S4)** — das LLM verschiebt die "
                   "Modellwahrscheinlichkeit nur in diesem Band:")
        band_pp = st.slider("Band um P_stat (Prozentpunkte)", min_value=0, max_value=30,
                            value=int(settings.get("llm_band_pp", 10)), step=1,
                            help="0 = LLM darf nichts verschieben (nur erklären). "
                                 "Verstöße gegen das Band werden automatisch abgewiesen.")
        melde_schwelle = st.slider("Meldung bei Prognoseänderung (pp)", min_value=2,
                                   max_value=30,
                                   value=int(settings.get("llm_melde_schwelle_pp", 10)),
                                   step=1,
                                   help="Ändert sich P_finale eines Tages zwischen zwei "
                                        "Läufen um mindestens diesen Wert, landet eine "
                                        "Meldung im Postfach.")
        news_fenster = st.number_input("News-Fenster (Tage)", min_value=2, max_value=21,
                                       value=int(settings.get("news_fenster_tage", 7)),
                                       step=1,
                                       help="Ältere RSS-Items werden ignoriert.")
        st.caption("**Ausbau (S7)** — schreibgeschütztes REST für andere Tools "
                   "(localhost only):")
        rest_port = st.number_input("REST-Port (0 = aus)", min_value=0, max_value=65535,
                                    value=int(settings.get("rest_api_port", 8606)),
                                    step=1,
                                    help="Endpunkte: /status · /matrix · /prognose.csv · "
                                         "/health. Bindet nur an 127.0.0.1. Änderung "
                                         "wirkt nach App-Neustart.")
    with st.container(border=True):
        st.subheader("Netz & Höflichkeit", width="content")
        kontakt = st.text_input("Kontakt-Adresse im User-Agent (empfohlen)",
                                value=settings.get("kontakt_fuer_useragent", ""),
                                help="Ehrlicher UA statt Browser-Vortäuschung — BLS sperrt "
                                     "den User-Agent OHNE Kontakt-Adresse (403); mit Angabe "
                                     "funktioniert die Quelle.")
        st.caption(f"Aktuell: `{config.user_agent(kontakt)}`")
        neuer_key = st.text_input("GLM-API-Key setzen (leer = unverändert)", type="password")
        if st.button("Key in secrets.local.json speichern", icon=":material/key:"):
            if neuer_key.strip():
                secrets_store.set_secret("glm_api_key", neuer_key.strip())
                st.toast("Key gespeichert", icon=":material/key:")
                st.rerun()
            else:
                st.warning("Feld ist leer — es wird nichts überschrieben.")

st.divider()
if st.button("Alle Einstellungen speichern", type="primary", icon=":material/save:"):
    config.save_settings({
        **settings,
        "mt5_symbol": symbol.strip() or "XAUUSD",
        "mt5_terminal_pfad": terminal_pfad.strip(),
        "mt5_start_erlauben": start_erlauben,
        "mt5_lookback_tage": int(lookback),
        "zeitzone": zeitzone,
        "glm_endpunkt": endpunkt,
        "model_stufe1": model_stufe1.strip(),
        "model_stufe2": model_stufe2.strip(),
        "llm_max_total_tokens": int(budget_lauf),
        "llm_token_budget_tag": int(budget_tag),
        "llm_timeout_s": int(timeout),
        "llm_band_pp": float(band_pp),
        "llm_melde_schwelle_pp": float(melde_schwelle),
        "news_fenster_tage": int(news_fenster),
        "rest_api_port": int(rest_port),
        "kontakt_fuer_useragent": kontakt.strip(),
    })
    st.toast("Gespeichert — Sidebar-Status aktualisiert sich beim nächsten Klick.",
             icon=":material/check_circle:")
