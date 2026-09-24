"""Automatik: was das System von selbst tut — und wann.

Der Daemon führt alle automatischen Läufe aus; hier sind Wochentag und
Uhrzeit je Job einstellbar (sichtbar ist zusätzlich der Daemon-Zustand).
Änderungen greifen im nächsten Daemon-Loop (≤ 30 s), ein Neustart ist
nicht nötig.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from goldscanner import config
from goldscanner.betrieb import daemon
from goldscanner.ui_design import page_header

page_header(
    "Automatik",
    "Was das System von selbst tut — und wann",
    "Der Daemon führt alle automatischen Läufe aus (Status unten). "
    "Wochentage und Uhrzeiten stellst du hier ein — der Daemon übernimmt "
    "Änderungen von selbst innerhalb von 30 Sekunden, ein Neustart ist "
    "nicht nötig.",
)

settings = config.load_settings()

WOCHENTAGE = list(daemon.WOCHENTAGE)          # Montag..Sonntag


def _job_zeit(key_zeit: str, default: str):
    roh = str(settings.get(key_zeit, default))
    try:
        stunde, minute = (int(t) for t in roh.strip().split(":")[:2])
        return datetime.now().replace(hour=stunde, minute=minute,
                                      second=0, microsecond=0).time()
    except (ValueError, IndexError):
        return datetime.now().replace(hour=6, minute=30, second=0,
                                      microsecond=0).time()


# ── Daemon-Status ─────────────────────────────────────────────────────────
st.subheader("Daemon", width="content")
stat = daemon.status()
d1, d2 = st.columns([2, 1], gap="small", vertical_alignment="center")
with d1:
    if stat["laeuft"]:
        alter = stat["herzschlag_alt_s"]
        st.markdown(
            '<span style="color:#10B981;font-weight:700">● läuft'
            + (f" · Herzschlag vor {alter:.0f} s" if alter is not None else "")
            + "</span>", unsafe_allow_html=True)
    else:
        st.markdown('<span style="color:#FB923C;font-weight:700">○ '
                    "gestoppt — ohne Daemon läuft nichts von selbst"
                    "</span>", unsafe_allow_html=True)
with d2:
    if st.button("Daemon starten", icon=":material/play_arrow:",
                 disabled=stat["laeuft"], type="primary"):
        daemon.starte_detached()
        st.toast("Daemon gestartet (unabhängiger Prozess)",
                 icon=":material/check_circle:")
        st.rerun()
    if st.button("Daemon stoppen", icon=":material/stop_circle:",
                 disabled=not stat["laeuft"]):
        daemon.stoppe()
        st.toast("Stopp-Signal gesetzt — Daemon beendet sich (≤30 s)",
                 icon=":material/check_circle:")
        st.rerun()

# ── Zeitplan ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("Zeitplan", width="content")
st.caption("Tageslauf läuft täglich; alle anderen Jobs an einem frei "
           "wählbaren Wochentag. Empfehlung: den Wochenlauf auf den "
           "Sonntag legen, NACHdem die Samstags-Auswertung der Vorwoche "
           "gelaufen ist.")

jobs = [
    ("Tageslauf (täglich)", None, "daemon_tageslauf_zeit", "06:30",
     "Kurse, Kalender, Actuals nachziehen"),
    ("Scout (Quellen-Vorschläge)", "daemon_scout_tag", "daemon_scout_zeit",
     "Sonntag 17:00",
     "Schlägt neue Nachrichten-Quellen vor"),
    ("Wochenlauf (Prognose + KI)", "daemon_wochenlauf_tag",
     "daemon_wochenlauf_zeit", "Sonntag 18:00",
     "Komplette Wochenvorhersage inkl. KI-Fusion, PDF, MT5-Export"),
    ("Verifikation + Auswertung", "daemon_verifikation_tag",
     "daemon_verifikation_zeit", "Samstag 09:00",
     "Prognose vs. Realität, Prognose-Score 0-100, KI-Review"),
]
aenderungen: dict = {}
with st.container(border=True):
    for titel, key_tag, key_zeit, default, beschreibung in jobs:
        c1, c2, c3 = st.columns([2.2, 1, 1], gap="small",
                                vertical_alignment="center")
        with c1:
            st.markdown(f"**{titel}**")
            st.caption(beschreibung)
        with c2:
            if key_tag is not None:
                alter_tag = str(settings.get(key_tag, default.split()[0]))
                neuer_tag = st.selectbox("Tag", WOCHENTAGE,
                                         index=WOCHENTAGE.index(
                                             alter_tag if alter_tag in
                                             WOCHENTAGE else 0),
                                         key=f"tag_{key_tag}",
                                         label_visibility="collapsed")
                if neuer_tag != alter_tag:
                    aenderungen[key_tag] = neuer_tag
            else:
                st.markdown("jeden Tag")
        with c3:
            neue_zeit = st.time_input("Uhrzeit",
                                      value=_job_zeit(key_zeit, default),
                                      key=f"zeit_{key_zeit}",
                                      label_visibility="collapsed",
                                      step=timedelta(minutes=15))
            zeile = f"{neue_zeit.hour:02d}:{neue_zeit.minute:02d}"
            if zeile != str(settings.get(key_zeit, default)):
                aenderungen[key_zeit] = zeile

if aenderungen:
    if st.button("Zeitplan speichern", type="primary",
                 icon=":material/save:",
                 help="Der Daemon übernimmt die Änderung im nächsten "
                      "Schleifendurchlauf (≤ 30 s)."):
        config.save_settings({**settings, **aenderungen})
        st.toast("Zeitplan gespeichert — Daemon übernimmt automatisch",
                 icon=":material/check_circle:")
        st.rerun()
    st.info("Ungespeicherte Änderungen: " + ", ".join(
        f"{k} = {v}" for k, v in aenderungen.items()))

# ── Letzte Ausführungen ───────────────────────────────────────────────────
st.divider()
st.subheader("Letzte Daemon-Läufe", width="content")
if stat["zeilen"]:
    for z in stat["zeilen"][:8]:
        st.markdown(f"{z['zeit'][:16]} · {z['job']} · "
                    f"{'✓ ' if z['ok'] else '✗ '}{z['info'] or ''}")
else:
    st.caption("Noch keine Läufe.")
