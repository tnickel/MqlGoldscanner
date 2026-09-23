# -*- coding: utf-8 -*-
"""Chart — XAUUSD-Tageskerzen mit SMA-Overlays und Kennzahlen-Panel."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from goldscanner import config
from goldscanner.app_state import hole_db
from goldscanner.kennzahlen import sma_reihe
from goldscanner.mt5 import kurse
from goldscanner.ui_design import aktivitaets_banner, page_header

SICHTBARE_D1 = 180

page_header(
    "Kursdaten · MetaTrader",
    "XAUUSD-Tageskerzen mit SMA 10/50/200",
    "Kurse kommen direkt aus deinem MT5-Terminal (offizielles Python-Paket, "
    "**nur lesend**). Standard-Politik: der Scanner startet das Terminal nicht selbst "
    "und beendet nur selbst gestartete Instanzen — dein laufendes MT5 bleibt unberührt.",
)

settings = config.load_settings()
symbol = settings.get("mt5_symbol", "XAUUSD")

links, mitte, rechts = st.columns([1, 1, 2.4], vertical_alignment="center")
with links:
    laden = st.button("Kurse laden (MT5)", type="primary", icon=":material/download:")
with mitte:
    testen = st.button("Nur Verbindung testen", icon=":material/network_check:")
with rechts:
    st.caption(f"Lookback {settings.get('mt5_lookback_tage', 400)} Tage · "
               f"Terminal-Pfad: {settings.get('mt5_terminal_pfad') or 'leer = Attach ans laufende Terminal'}")

if testen:
    banner = aktivitaets_banner("Teste MT5-Verbindung …")
    ergebnis = kurse.verbindung_testen(settings)
    banner.empty()
    if ergebnis["ok"]:
        st.success(ergebnis["grund"])
    else:
        st.error(ergebnis["grund"])
    db = hole_db()
    lauf = db.lauf_starten("mt5_verbindungstest", "Attach-Test aus dem Chart-Bereich")
    db.schritt(lauf, "kurse", "test", "verbindung_testen", ergebnis["grund"],
               ok=ergebnis["ok"], fehler="" if ergebnis["ok"] else ergebnis["grund"])
    db.lauf_beenden(lauf, ergebnis["ok"])

if laden:
    banner = aktivitaets_banner(f"Rufe {symbol} D1/H4/H1 aus MetaTrader ab …")
    ergebnis = kurse.kurse_holen(settings)
    banner.empty()
    db = hole_db()
    lauf = db.lauf_starten("kurse_holen", "Kursabruf D1/H4/H1")
    if not ergebnis["ok"]:
        db.schritt(lauf, "kurse", "abruf", "kurse_holen", "",
                   ok=False, fehler=ergebnis["grund"])
        db.lauf_beenden(lauf, False)
        st.error(ergebnis["grund"])
    else:
        neu = sum(db.raten_speichern(ergebnis["symbol"], tf, bars)
                  for tf, bars in ergebnis["raten"].items())
        st.session_state["kurse"] = ergebnis
        info = (f"{ergebnis['symbol']} · {ergebnis['terminal']} · "
                + ", ".join(f"{tf}={n}" for tf, n in ergebnis["bars"].items())
                + (f" · {neu} neu in DB" if neu else " · DB aktuell"))
        db.schritt(lauf, "kurse", "abruf", "kurse_holen", info, ok=True)
        db.lauf_beenden(lauf, True)
        st.toast("Kurse geladen", icon=":material/check_circle:")

# ── Chart aus Session (frisch) oder DB ─────────────────────────────────────
kurse_ergebnis = st.session_state.get("kurse")
d1: list[dict] = []
if kurse_ergebnis and kurse_ergebnis.get("ok"):
    d1 = kurse_ergebnis["raten"].get("d1", [])
    kennz = kurse_ergebnis.get("kennzahlen", {})
    st.caption(f"Grundlage: live aus {kurse_ergebnis.get('terminal', 'MT5')}")
else:
    d1 = hole_db().raten_laden(symbol, "d1")
    if d1:
        from goldscanner.kennzahlen import kennzahlen_aus_d1
        kennz = kennzahlen_aus_d1(d1)
        st.caption(f"Grundlage: Datenbank · {len(d1)} D1-Bars — „Kurse laden“ für den aktuellen Stand")

if not d1:
    st.info("Noch keine Kursdaten. Oben **„Kurse laden (MT5)“** klicken — das Terminal "
            "sollte dafür laufen (oder Selbststart in den Einstellungen freigeben).")
    st.stop()

fenster = d1[-SICHTBARE_D1:]
datum = [datetime.fromtimestamp(b["time"], tz=timezone.utc).strftime("%d.%m.") for b in fenster]
df = pd.DataFrame(fenster)

fig = go.Figure()
fig.add_trace(go.Candlestick(
    x=list(range(len(fenster))), open=df["open"], high=df["high"],
    low=df["low"], close=df["close"], name=symbol,
    increasing_line_color="#10B981", increasing_fillcolor="#10B981",
    decreasing_line_color="#F43F5E", decreasing_fillcolor="#F43F5E",
))
closes = [b["close"] for b in fenster]
for n, farbe in ((10, "#E8B84B"), (50, "#38BDF8"), (200, "#A855F7")):
    reihe = sma_reihe(closes, n)
    ersichtliche = [(x, y) for x, y in enumerate(reihe) if y is not None]
    if len(ersichtliche) >= 2:
        fig.add_trace(go.Scatter(
            x=[x for x, _ in ersichtliche], y=[y for _, y in ersichtliche],
            mode="lines", name=f"SMA {n}",
            line={"color": farbe, "width": 1.4},
        ))
fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="#0A111E", plot_bgcolor="#0D1524",
    font={"color": "#F1F5F9", "family": "sans-serif"},
    height=560, margin={"l": 10, "r": 10, "t": 30, "b": 10},
    xaxis={"showgrid": False, "tickmode": "array",
           "tickvals": list(range(0, len(fenster), max(1, len(fenster) // 8))),
           "ticktext": [datum[i] for i in range(0, len(fenster), max(1, len(fenster) // 8))]},
    yaxis={"gridcolor": "#273E5B", "gridwidth": 0.6, "title": None},
    legend={"orientation": "h", "y": 1.02, "x": 0},
    showlegend=True,
)
fig.update_xaxes(rangeslider_visible=False)
st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})

# ── Kennzahlen-Panel ───────────────────────────────────────────────────────
st.subheader("Kennzahlen", width="content")
st.caption("Reiner Code — das LLM zitiert sie später nur (Engine rechnet, LLM zitiert). "
           "Zeitangaben = MT5-Serverszeit.")


def metrik(schluessel: str, titel: str, hilfe: str | None = None):
    wert = kennz.get(schluessel)
    anzeige = "–" if wert is None else wert
    st.metric(titel, anzeige, hilfe, border=True)


z1 = st.columns(5, gap="small")
with z1[0]:
    metrik("close", f"{symbol} Close")
with z1[1]:
    metrik("veraenderung_heute_pct", "Δ heute")
with z1[2]:
    metrik("veraenderung_7t_pct", "Δ 7 Tage")
with z1[3]:
    metrik("veraenderung_30t_pct", "Δ 30 Tage")
with z1[4]:
    metrik("tr_heute", "True Range heute")
z2 = st.columns(5, gap="small")
with z2[0]:
    metrik("atr14_d1", "ATR 14 (D1)")
with z2[1]:
    metrik("atr14_h1", "ATR 14 (H1)")
with z2[2]:
    metrik("rsi14_d1", "RSI 14 (D1)")
with z2[3]:
    metrik("sma50", "SMA 50")
with z2[4]:
    metrik("sma200", "SMA 200")
z3 = st.columns(5, gap="small")
with z3[0]:
    metrik("distanz_30t_hoch_pct", "Distanz 30T-Hoch")
with z3[1]:
    metrik("distanz_30t_tief_pct", "Distanz 30T-Tief")
with z3[2]:
    metrik("tagesrange_pct", "Tagesrange %")
with z3[3]:
    metrik("trend_close_vs_sma10_pct", "Trend vs. SMA10")
with z3[4]:
    metrik("bars_d1", "Bars D1")
