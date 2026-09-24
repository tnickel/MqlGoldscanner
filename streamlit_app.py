"""MqlGoldscanner — Streamlit-App (Stufe 1: Gerüst & Kurse).

Einstiegspunkt: Navigation + globaler Status. Business-Logik liegt in
src/goldscanner/ — die Seiten in app_pages/ sind dünn (KiScanner-Muster).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st  # noqa: E402

from goldscanner import config, secrets_store  # noqa: E402
from goldscanner.betrieb import daemon  # noqa: E402
from goldscanner.ui_design import apply_theme  # noqa: E402

st.set_page_config(
    page_title="MqlGoldscanner",
    page_icon=":material/monitoring:",
    layout="wide",
)
apply_theme()

from goldscanner.app_state import hole_db  # noqa: E402


# ------------------------------------------------- REST (S7, nur lesen)
@st.cache_resource(show_spinner=False)
def _rest_server():
    """Schreibgeschütztes localhost-REST — einmal je Prozess (wie KiScanner)."""
    try:
        from goldscanner import rest_api
        return rest_api.start_background()
    except Exception:
        return None


rest_server = _rest_server()


# ------------------------------------------------------------------ Sidebar
settings = config.load_settings()
with st.sidebar:
    with st.container(key="sidebar_brand", gap="xsmall"):
        st.caption("GOLD MARKET RESEARCH · FORENSIC SCANNER")
        st.markdown(
            '<span style="font-size:1.6rem;font-weight:900;'
            'color:#F5D67B;letter-spacing:.4px;display:block;'
            'line-height:1.1">MqlGoldscanner</span>',
            unsafe_allow_html=True)
        st.caption("Wahrscheinlichkeit vor Richtung")
    with st.container(border=True):
        st.markdown("**Systemstatus**")
        key_da = bool(secrets_store.get_secret("glm_api_key"))
        st.badge("KI bereit" if key_da else "GLM-Key fehlt",
                 color="green" if key_da else "orange", icon=":material/psychology:")
        st.badge(f"Symbol {settings.get('mt5_symbol', 'XAUUSD')}",
                 color="blue", icon=":material/monitoring:")
        endpunkt = "Coding (Abo)" if settings.get("glm_endpunkt") != "api" else "API (PAYG)"
        st.badge(f"GLM {endpunkt}", color="gray", icon=":material/cable:")
        if rest_server is not None:
            st.badge(f"REST :{rest_server.port}", color="green",
                     icon=":material/cable:")
        elif int(settings.get("rest_api_port", 8606)) > 0:
            st.badge("REST-Port belegt", color="orange", icon=":material/cable:")
        try:
            db = hole_db()
            heute = db.tokens_heute()
            st.caption(f"Token-Budget heute · {heute:,} / "
                       f"{int(settings.get('llm_token_budget_tag', 2_000_000)):,}".replace(",", "."))
            letzter_check = db.letzte_schritte(1)
            if letzter_check:
                von = letzter_check[0]["zeit"][:16].split("T")
                st.caption(f"Letzter Lauf · {von[0].replace('-', '.')}, {von[1]} "
                           f"({letzter_check[0]['lauf']})")
        except Exception:
            st.caption("Datenbank wird beim ersten Zugriff angelegt.")
    with st.container(border=True):
        st.caption("GRUNDPRINZIP")
        st.markdown("**Engine rechnet · LLM zitiert**  \nJede Prognose muss die "
                    "**Basisrate ~43 %** schlagen")
        st.caption("Bewegungstag: TR > 1,0× Ø-TR des Wochentags (13 Wochen)")

# --------------------------------------------------------------- Navigation
# Automatik-Status live: Daemon läuft → grün "ok", sonst rot "aus".
daemon_aktiv = False
try:
    daemon_aktiv = daemon.laeuft()
except Exception:
    pass
automatik_titel = ("Automatik · ok 🟢" if daemon_aktiv
                   else "Automatik · aus 🔴")

seiten = {
    "Arbeitsbereich": [
        st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/dashboard:"),
        st.Page("app_pages/tagesicht.py", title="Tagessicht", icon=":material/event:"),
        st.Page("app_pages/chart.py", title="Chart", icon=":material/candlestick_chart:"),
        st.Page("app_pages/quellen.py", title="Quellen", icon=":material/rss_feed:"),
        st.Page("app_pages/agenten.py", title="Agenten", icon=":material/tune:"),
        st.Page("app_pages/journal.py", title="Journal", icon=":material/history:"),
        st.Page("app_pages/track_record.py", title="Track-Record", icon=":material/verified:"),
    ],
    "Konfiguration": [
        st.Page("app_pages/automatik.py", title=automatik_titel, icon=":material/schedule:"),
        st.Page("app_pages/einstellungen.py", title="Einstellungen", icon=":material/settings:"),
    ],
}
st.navigation(seiten, position="sidebar").run()
