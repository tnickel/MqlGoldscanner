# -*- coding: utf-8 -*-
"""Tagessicht — Event-Zeitleiste eines Wochentags + Klimatologie-Karte (S2)."""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from goldscanner import config
from goldscanner.adapter.kalender import dedup_ereignisse
from goldscanner.app_state import hole_db
from goldscanner.klimatologie import (WEEKDAY_NAMEN, schwelle_naechster_tag,
                                      wochentags_statistik)
from goldscanner.ui_design import page_header

BERLIN = ZoneInfo("Europe/Berlin")

page_header(
    "Tagessicht",
    "Event-Zeitleiste und Tages-Statistik",
    "Alle Termine des gewählten Wochentags — Wirtschaftsdaten (ForexFactory, BLS, "
    "BEA, Fed), Treasury-Auktionen und regelbasierte Termine (GC FND/LTD/Opex, "
    "Quartalsenden, Feiertage, DST). Uhrzeiten in Europe/Berlin; bei Dubletten "
    "gewinnt die Quelle mit der höchsten Qualität (FF vor BLS/BEA vor Fed).",
)

settings = config.load_settings()
db = hole_db()
symbol = settings.get("mt5_symbol", "XAUUSD")

heute = date.today()
montag = heute - timedelta(days=heute.weekday())

auswahl = st.selectbox(
    "Wochentag",
    list(range(7)),
    index=heute.weekday(),
    format_func=lambda i: (f"{WEEKDAY_NAMEN[i]} · "
                           f"{(montag + timedelta(days=i)).strftime('%d.%m.%Y')}"
                           + (" (heute)" if (montag + timedelta(days=i)) == heute else "")))
tag = montag + timedelta(days=auswahl)

events = dedup_ereignisse(db.events_fuer_zeitraum(tag.isoformat(), tag.isoformat()))

# Session-Lage (S5): Asia-Range + Gap + empirische Revision — nur für HEUTE
if tag == heute:
    from goldscanner.modell import session as session_modul
    from goldscanner.klimatologie import schwelle_naechster_tag
    h1 = db.raten_laden(settings.get("mt5_symbol", "XAUUSD"), "h1")
    d1 = db.raten_laden(settings.get("mt5_symbol", "XAUUSD"), "d1")
    lage = session_modul.asia_range_und_gap(h1, heute.isoformat())
    if lage.get("ok"):
        with st.container(border=True):
            st.subheader("Session-Lage heute (Asia bis 08:00 MEZ)", width="content")
            s1, s2, s3 = st.columns(3, gap="small")
            with s1:
                st.metric("Asia-Range", f"{lage['range_usd']:.1f} USD", border=True)
            with s2:
                st.metric("Letzter Kurs (08:00)",
                          f"{lage['letzter_close']:.1f}", border=True)
            with s3:
                st.metric("Wochenend-Gap",
                          "–" if lage.get("wochend_gap_usd") is None
                          else f"{lage['wochend_gap_usd']:+.1f} USD", border=True)
            schwelle = schwelle_naechster_tag(
                d1, heute.weekday(), float(settings.get("matrix_k", 1.0)),
                int(settings.get("matrix_fenster", 13)))
            if schwelle:
                empirie = session_modul.empirie_h1(h1, d1)
                bedingt = session_modul.bedingte_bewegungs_p(
                    empirie, schwelle["schwelle_usd"], lage["range_usd"])
                if bedingt.get("ok"):
                    delta_pp = ((bedingt["p_bedingt"] - bedingt["p_ohne_bedingung"])
                                * 100 if bedingt.get("p_ohne_bedingung") is not None else None)
                    st.markdown(
                        f"Asia-Range = **{bedingt['asia_anteil_der_schwelle']:.0f} × "
                        f"Schwelle B** ({schwelle['schwelle_usd']:.0f} USD). "
                        f"Historisch endeten Tage mit ähnlicher Asia-Range zu "
                        f"**{bedingt['p_bedingt'] * 100:.0f} %** als Bewegungstag "
                        f"(n={bedingt['n_bucket']} von {bedingt['n_gesamt']} Tagen; "
                        f"ohne Bedingung: {bedingt['p_ohne_bedingung'] * 100:.0f} %"
                        + (f", Delta {delta_pp:+.0f} pp" if delta_pp is not None else "")
                        + ").")
                else:
                    st.caption(f"Schwelle B: {schwelle['schwelle_usd']:.0f} USD — "
                               "für diese Asia-Range gibt es noch zu wenige "
                               "historische Vergleichstage.")
            st.caption("Rein empirisch aus der eigenen H1-Historie (~200 Tage) — "
                       "kein Modell, großes Konfidenzintervall, als Intraday-"
                       "Frühindiktor zu lesen.")

links, rechts = st.columns([1.5, 1], gap="medium")

with links:
    with st.container(border=True):
        st.subheader(f"Ereignisse · {tag.strftime('%A, %d.%m.%Y')}", width="content")
        if not events:
            st.caption("Keine Ereignisse für diesen Tag verzeichnet.")
        hat_actuals = False
        _QUELLFARBEN = {"ff": "#E8B84B", "bls": "#38BDF8", "bea": "#38BDF8",
                        "fed": "#A855F7", "treasury": "#10B981", "regel": "#94A3B8"}
        for e in events:
            zeit = ("ganztag" if not e.get("zeit_utc") else
                    datetime.fromisoformat(e["zeit_utc"]).astimezone(BERLIN).strftime("%H:%M"))
            farbe = _QUELLFARBEN.get(e.get("quelle", ""), "#94A3B8")
            relevanz = e.get("gold_relevanz") or 0
            sterne = f'<span title="Gold-Relevanz {relevanz}/5">{"★" * relevanz}</span>'
            titel = (e["titel"] or "")[:70]
            zeile = (f'<span style="color:{farbe};font-weight:700">'
                     f'{zeit}</span> · {titel} &nbsp;{sterne}'
                     f' <span style="color:#64748B">[{e.get("quelle", "")}]</span>')
            details = []
            for label, feld in (("F", e.get("forecast")), ("P", e.get("previous")),
                                ("A", e.get("actual_latest") or e.get("actual_first"))):
                if feld:
                    details.append(f"{label}: {feld}")
            if details:
                zeile += f' <span style="color:#94A3B8">{" · ".join(details)}</span>'
                if e.get("actual_latest") or e.get("actual_first"):
                    hat_actuals = True
            st.markdown(zeile, unsafe_allow_html=True)
        if not hat_actuals:
            st.info("Noch keine Ist-Werte: einmal **mql5/CalendarExport.mq5** im "
                    "Terminal ausführen (siehe mql5/README) — Actuals werden dann "
                    "hier und für kommende Auswertungen nachgetragen.")

with rechts:
    with st.container(border=True):
        st.subheader("Klimatologie dieses Wochentags", width="content")
        d1 = db.raten_laden(symbol, "d1")
        if not d1:
            st.caption("Keine Kursdaten — zuerst im Chart „Kurse laden“.")
        else:
            fenster = int(settings.get("matrix_fenster", 13))
            wt = tag.weekday()
            stats = wochentags_statistik(d1, k=1.0, fenster=fenster)
            stat = stats["je_wochentag"].get(wt)
            schwelle = schwelle_naechster_tag(d1, wt, 1.0, fenster)
            if stat:
                st.metric("P(Bewegungstag)", f"{stat['p'] * 100:.0f} %",
                          f"{(stat['p'] - stats['p_global']) * 100:+.1f} pp vs. Gesamt",
                          border=True)
                st.caption(f"roh {stat['p_roh'] * 100:.0f} % · n={stat['n']} bewertete "
                           f"{WEEKDAY_NAMEN[wt]}e (Shrinkage zur Gesamtrate)")
            if schwelle:
                st.metric("Schwelle B", f"{schwelle['schwelle_usd']} USD",
                          f"{schwelle['schwelle_pct']} % vom Close "
                          f"{schwelle['close_referenz']}", border=True)
                st.caption(f"Basis: letzte {schwelle['n_basis']} {WEEKDAY_NAMEN[wt]}e "
                           "× 1,0 (point-in-time)")
            if stat and schwelle:
                close = schwelle["close_referenz"]
                st.caption(f"Typische Range (relativ → USD): Q10 "
                           f"{stat['q10_tr_rel'] * close:.0f} $ · Median "
                           f"{stat['median_tr_rel'] * close:.0f} $ · Q90 "
                           f"{stat['q90_tr_rel'] * close:.0f} $")

    with st.container(border=True):
        st.subheader("Lesart", width="content")
        st.caption(
            "Bewegungstag = True Range > 1,0 × Ø-TR desselben Wochentags der "
            "letzten 13 Wochen. Die Wahrscheinlichkeit ist die historische Rate "
            "dieses Wochentags (unkalibriert) — Hochrechnung ab Stufe 3 durch das "
            "HAR-Modell mit Events und impliziter Volatilität.")
