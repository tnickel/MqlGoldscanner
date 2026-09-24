"""Track-Record (S6): Prognosequalität messbar — Prognose vs. Realität.

Datenbasis: verifikationen-Tabelle (der Verifikations-Agent vergleicht je
vergangenem Tag die point-in-time-Prognose mit der echten Kerze). Die Seite
füllt sich automatisch — jede Woche wächst n.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from goldscanner import config
from goldscanner.app_state import hole_db
from goldscanner.betrieb import daemon, verifikation
from goldscanner.betrieb.auswertung import laeuft as auswertung_laeuft
from goldscanner.ui_design import page_header, qualitaets_farbe, status_feed

page_header(
    "Track-Record",
    "Prognosequalität — Prognose vs. eingetretene Realität",
    "Jeder vergangene Tag wird gegen die Prognose geprüft, die **zum damaligen "
    "Zeitpunkt galt** (point-in-time aus den as_of-versionierten Matrizen — kein "
    "Look-ahead auch in der Auswertung). Bewegungstag = TR > Schwelle B der "
    "damaligen Prognose; Richtung = Close > Vortag; Range-Coverage = TR "
    "innerhalb Q10–Q90. Samstags 09:00 entstehen daraus der **Prognose-Score "
    "0-100** je Woche und ein KI-Review, dessen Lessons in den Sonntagslauf "
    "zurückfließen.",
)

settings = config.load_settings()
db = hole_db()

oben, unten = st.columns([1, 1], gap="medium", vertical_alignment="center")
with oben:
    if st.button("Verifikation + Wochen-Auswertung", type="primary",
                 icon=":material/fact_check:"):
        prot = verifikation.nachziehen(db, settings)
        aus = auswertung_laeuft(db, settings)
        score_txt = (f" · Score {aus['score_letzte']}/100"
                     if aus.get("score_letzte") is not None else "")
        st.toast(f"{prot.get('neu', 0)} Tage verifiziert{score_txt} "
                 f"({prot.get('ohne_prognose', 0)} ohne passende Prognose)",
                 icon=":material/check_circle:")
        st.rerun()
with unten:
    st.caption("Bewertet werden Tage mit vollständiger Kerze (heute selbst erst "
               "morgen). Ohne gespeicherte Prognose (z. B. vor dem ersten "
               "Wochenlauf) wird ein Tag übersprungen. Der Knopf macht exakt "
               "das, was der Daemon samstags 09:00 automatisch tut.")

zeilen = db.verifikationen()
kz = verifikation.kennzahlen(zeilen)

if not zeilen:
    st.info("Noch keine verifizierten Tage. **„Verifikation jetzt nachziehen“** "
            "wertet alle vergangenen Tage aus, für die eine gespeicherte "
            "Prognose existiert (seit dem ersten Wochenlauf — Bewertungen "
            "entstehen immer erst einen Tag später, wenn die Kerze vollständig "
            "ist). Der Daemon macht das künftig automatisch Samstags 09:00.")

st.subheader(f"{kz['n_tage']} verifizierte Tage", width="content")

k1, k2, k3, k4, k5 = st.columns(5, gap="small")
with k1:
    st.metric("Brier P_stat", f"{kz['brier_stat']:.4f}" if kz["brier_stat"] is not None else "–",
              border=True)
with k2:
    st.metric("BSS vs. Klima",
              f"{kz['bss']:+.3f}" if kz["bss"] is not None else "–",
              help="> 0 = besser als die Wochentags-Klimatologie (Tor-T3-Kriterium, "
                   "jetzt live gemessen statt nur im Backtest)",
              border=True)
with k3:
    delta = kz["llm_delta_nutzt"]
    st.metric("LLM-Delta-Nutzt (Tor T4)",
              "–" if delta is None else f"{delta * 100:+.2f} pp Brier",
              help="Positiv = die KI-Anpassung (P_finale) lag näher an der Realität "
                   "als P_stat. Über viele Wochen die Basis für die Tor-T4-Entscheidung: "
                   "dauerhaft ≤ 0 → Band in den Einstellungen auf 0 setzen.",
              border=True)
with k4:
    st.metric("Richtungstreffer",
              "–" if kz["richtungstreffer"] is None
              else f"{kz['richtungstreffer'] * 100:.0f} % (n={kz['n_richtung']})",
              help="P(hoch) ≥ 50 % vs. Close > Vortag. Zur Erinnerung (Tor T5): "
                   "die Richtung ist NICHT als besser als Zufall verifiziert.",
              border=True)
with k5:
    st.metric("Range-Coverage Q10–Q90",
              "–" if kz["range_coverage"] is None
              else f"{kz['range_coverage'] * 100:.0f} % (n={kz['n_band']})",
              help="Anteil der Tage, deren echte TR im prognostizierten Band "
                   "lag — idealerweise ~80 %.",
              border=True)

# ── Prognose-Score 0-100 (Samstags-Auswertung) ─────────────────────────────
st.divider()
st.subheader("Prognose-Score 0-100", width="content")
berichte = db.wochenberichte()
if not berichte:
    st.info("Noch kein Wochen-Score. Er entsteht automatisch mit der ersten "
            "vollständig verifizierten Woche — Samstags 09:00 im Daemon oder "
            "per Knopf oben. Grundlage ist je Tag eine Note aus Bewegung "
            "(40 P.), Richtung (40 P.) und Range-Band (20 P.); der Wochen-"
            "Score ist der Durchschnitt der Tagesnoten.")
else:
    letzte = db.wochenbericht(berichte[-1]["woche"]) or {}
    score = letzte.get("score")
    n_tage = letzte.get("n_tage", 0)
    tage_wort = "Tag" if n_tage == 1 else "Tage"
    wochen_label = (f"Woche {letzte['woche'][8:]}.–"
                    f"{int(letzte['woche'][8:]) + 4:02d}.{letzte['woche'][5:7]}")
    st.caption("Tagesnote je Tag aus Bewegung (40 P.) · Richtung (40 P.) · "
               "Band (20 P.) — fehlende Bausteine werden wegnormiert. "
               "Wochen-Score = Ø der Tagesnoten. ~50 entspricht Münzwurf-"
               "Niveau, deutlich darüber liefert das System echten Mehrwert.")

    kopf_links, kopf_rechts = st.columns([1, 2.2], gap="large",
                                         vertical_alignment="center")
    with kopf_links:
        trend_html = ""
        if len(berichte) > 1:
            diff = score - berichte[-2]["score"]
            pfeil = "▲" if diff >= 0 else "▼"
            trend_html = (f'<span style="color:{qualitaets_farbe(50 + diff)};'
                          f'font-weight:700">{pfeil} {abs(diff)} zur Vorwoche'
                          f'</span>')
        st.markdown(
            f'<div style="line-height:1.05"><span style="font-size:3.2rem;'
            f'font-weight:800;color:{qualitaets_farbe(score)}">{score}</span>'
            f'<span style="font-size:1.4rem;color:#7C8DA6">/100</span></div>'
            f'<div style="color:#94A3B8;font-size:.85rem;margin-top:.2rem">'
            f'{wochen_label} · {n_tage} {tage_wort}'
            + (f' · {trend_html}' if trend_html else "") + "</div>",
            unsafe_allow_html=True)
    with kopf_rechts:
        ts = letzte.get("teilscores") or {}
        t1, t2, t3 = st.columns(3, gap="small")
        with t1:
            st.metric("Bewegung", f"{ts.get('bewegung') if ts.get('bewegung') is not None else '–'} / 100",
                      border=True, help="Waren die Bewegungstag-Wahrscheinlichkeiten richtig? "
                                        "Bewertet auf der höchsten Ebene, die zur Prognosezeit "
                                        "galt (KI-Fusion → Statistik → Klimatologie).")
        with t2:
            st.metric("Richtung", f"{ts.get('richtung') if ts.get('richtung') is not None else '–'} / 100",
                      border=True, help="P(hoch) vs. tatsächlich Close höher als Vortag.")
        with t3:
            st.metric("Band", f"{ts.get('band') if ts.get('band') is not None else '–'} / 100",
                      border=True, help="Lag die echte Tagesrange in Q10–Q90 der Prognose?")

    chart_links, chart_rechts = st.columns([1, 1], gap="large")
    with chart_links:
        st.markdown("**Wochen-Score im Zeitverlauf**")
        fig_w = go.Figure()
        fig_w.add_trace(go.Bar(
            x=[f"{int(b['woche'][8:]):02d}.{b['woche'][5:7]}" for b in berichte],
            y=[b["score"] for b in berichte],
            marker_color=[qualitaets_farbe(b["score"]) for b in berichte],
            marker_line=dict(color="#0B1220", width=1),
            text=[b["score"] for b in berichte], textposition="outside",
            customdata=[[b["n_tage"], b["woche"]] for b in berichte],
            hovertemplate="%{customdata[1]} · %{y}/100 · %{customdata[0]} Tage"
                          "<extra></extra>"))
        if len(berichte) > 1:
            mittel = sum(b["score"] for b in berichte) / len(berichte)
            fig_w.add_hline(y=mittel, line=dict(color="#94A3B8", dash="dash"),
                            annotation_text=f"Ø {mittel:.0f}",
                            annotation_font_color="#94A3B8")
        fig_w.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", height=300, showlegend=False,
            margin=dict(t=10, b=0),
            yaxis=dict(range=[0, 108], gridcolor="#273E5B", title="Score"),
            xaxis=dict(gridcolor="#273E5B"))
        st.plotly_chart(fig_w, use_container_width=True)
    with chart_rechts:
        st.markdown(f"**Tagesnoten der letzten Woche** ({wochen_label})")
        tage_lw = letzte.get("tagesnoten") or []
        fig_t = go.Figure()
        if tage_lw:
            fig_t.add_trace(go.Bar(
                x=[t["wochentag"][:2] for t in tage_lw],
                y=[t["note"] for t in tage_lw],
                marker_color=[qualitaets_farbe(t["note"]) for t in tage_lw],
                marker_line=dict(color="#0B1220", width=1),
                text=[t["note"] for t in tage_lw], textposition="outside",
                customdata=[[t["datum"],
                             t.get("tr_usd"), t.get("schwelle_usd"),
                             t["note"]] for t in tage_lw],
                hovertemplate=("%{customdata[0]} · Note %{customdata[3]}/100 · "
                               "TR %{customdata[1]:.0f} USD "
                               "(Schwelle %{customdata[2]:.0f})"
                               "<extra></extra>")))
        fig_t.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", height=300, showlegend=False,
            margin=dict(t=10, b=0),
            yaxis=dict(range=[0, 108], gridcolor="#273E5B", title="Note"),
            xaxis=dict(gridcolor="#273E5B"))
        st.plotly_chart(fig_t, use_container_width=True)

    # KI-Review: Fazit + Lessons der letzten Woche, ältere im Expander
    stimmung_farbe = {"gut": "#10B981", "durchschnittlich": "#E8B84B",
                      "schwach": "#F43F5E"}
    if letzte.get("fazit"):
        with st.container(border=True):
            k1r, k2r = st.columns([3, 1], gap="small",
                                  vertical_alignment="center")
            with k2r:
                st.markdown(
                    f'<div style="text-align:right"><span style="color:'
                    f'{stimmung_farbe.get(letzte.get("stimmung"), "#94A3B8")};'
                    f'font-weight:700">● {letzte.get("stimmung", "?")}</span>'
                    f'<div style="color:#7C8DA6;font-size:.75rem">KI-Review '
                    + (f'{letzte["as_of_review"][:10]}' if letzte.get("as_of_review") else "")
                    + "</div></div>", unsafe_allow_html=True)
            with k1r:
                st.markdown("**KI-Fazit zur Woche** — was das Review sagt:")
                st.markdown(letzte["fazit"])
            lessons = letzte.get("lessons") or []
            if lessons:
                st.markdown("**Lessons für die nächste Prognose** "
                            "(fließen in die Sonntags-Fusion ein):")
                for lesson in lessons:
                    st.markdown(f"- {lesson}")
    else:
        st.caption("KI-Review steht für diese Woche noch aus — es entsteht "
                   "automatisch samstags bzw. per Knopf oben, sobald ein "
                   "GLM-Key gesetzt ist. Der Score selbst ist bereits "
                   "vollständig (reine Formel, kein LLM nötig).")
    alte = [b for b in berichte[:-1] if b.get("fazit")]
    if alte:
        with st.expander(f"Frühere KI-Reviews ({len(alte)})", expanded=False):
            alte.sort(key=lambda b: b["woche"], reverse=True)
            for b in alte:
                st.markdown(f"**{b['woche']}** · Score {b['score']}/100 · "
                            f"● {b.get('stimmung', '?')}")
                st.caption(b["fazit"])

links, rechts = st.columns([1, 1], gap="large")
with links:
    st.markdown("**Reliability-Diagramm** (P_finale): sagte „X %“, kam es in "
                "~X % der Fälle?")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1], mode="lines", name="ideal",
        line=dict(color="#94A3B8", dash="dash")))
    if kz["reliability"]:
        fig.add_trace(go.Scatter(
            x=[b["p_gesagt"] for b in kz["reliability"]],
            y=[b["treffer_rate"] for b in kz["reliability"]],
            mode="markers+lines", name="beobachtet",
            marker=dict(size=[6 + min(b["n"], 20) for b in kz["reliability"]],
                        color="#E8B84B", line=dict(color="#F5D67B", width=1)),
            text=[f"n={b['n']}" for b in kz["reliability"]]))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", height=320, showlegend=True,
        xaxis=dict(title="gesagte Wahrscheinlichkeit", range=[0, 1],
                   tickformat=".0%", gridcolor="#273E5B"),
        yaxis=dict(title="beobachtete Rate", range=[0, 1],
                   tickformat=".0%", gridcolor="#273E5B"))
    st.plotly_chart(fig, use_container_width=True)
    if kz["reliability"]:
        st.caption("Punktgröße ∝ Besetzung je Bin. Mit kleinen n sind die Bins "
                   "noch breit — die Aussage schärft sich über die Wochen.")
with rechts:
    st.markdown("**Brier je Prognose-Ebene** — das Tor-T4-Fenster:")
    tabelle = pd.DataFrame([
        {"Ebene": "Klimatologie (Basisrate)", "Brier": kz["brier_klima"],
         "n": kz["n_bewegung"]},
        {"Ebene": "P_stat (HAR-Modell)", "Brier": kz["brier_stat"],
         "n": kz["n_bewegung"]},
        {"Ebene": "P_finale (KI-Fusion)", "Brier": kz["brier_finale"],
         "n": kz["n_bewegung"]},
    ])
    st.dataframe(tabelle, hide_index=True, width="stretch")
    st.caption("LLM-Delta-Nutzt = Brier(P_stat) − Brier(P_finale). Positiv = "
               "die KI-Anpassung hat geholfen. Die fusionen-Tabelle speichert "
               "jede Fusion as_of — damit ist der Vergleich fair (gleiche Tage, "
               "verschiedene Prognose-Ebenen).")

with st.expander("Alle verifizierten Tage (Rohdaten)", expanded=False):
    df = pd.DataFrame(zeilen)
    if df.empty:
        st.caption("Noch nichts — füllt sich automatisch ab dem ersten "
                   "bewertbaren Tag.")
    else:
        anzeige = df[["datum", "woche", "p_klima", "p_stat", "p_finale",
                      "eingetreten", "tr_usd", "schwelle_usd", "q10_usd",
                      "q90_usd", "in_band", "richtung_p_hoch",
                      "richtung_eingetreten"]].copy()
        for spalte in ("p_klima", "p_stat", "p_finale", "richtung_p_hoch"):
            anzeige[spalte] = (anzeige[spalte].astype(float) * 100).round(0)
            anzeige = anzeige.rename(columns={spalte: f"{spalte} (%)"})
        anzeige["eingetreten"] = anzeige["eingetreten"].map(
            {1: "⚡", 0: "·", None: "–"})
        anzeige["richtung_eingetreten"] = anzeige["richtung_eingetreten"].map(
            {1: "▲", 0: "▼"})
        st.dataframe(anzeige.sort_values("datum", ascending=False),
                     hide_index=True, width="stretch")

st.divider()

# ── Daemon-Steuerung (Betrieb) ────────────────────────────────────────────
st.subheader("Daemon — läuft von selbst", width="content")
stat = daemon.status()
d1, d2, d3 = st.columns([1.2, 1, 2], gap="small", vertical_alignment="center")
with d1:
    if stat["laeuft"]:
        alter = stat["herzschlag_alt_s"]
        herzbild = (f"● aktiv · Herzschlag vor "
                    f"{alter:.0f} s" if alter is not None else "● aktiv")
        st.markdown(f'<span style="color:#10B981;font-weight:700">{herzbild}</span>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<span style="color:#FB923C;font-weight:700">○ gestoppt</span>',
                    unsafe_allow_html=True)
with d2:
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Starten", icon=":material/play_arrow:",
                     disabled=stat["laeuft"], type="primary"):
            if daemon.starte_detached():
                st.toast("Daemon gestartet (unabhängiger Prozess)",
                         icon=":material/check_circle:")
                st.rerun()
    with col_b:
        if st.button("Stoppen", icon=":material/stop_circle:",
                     disabled=not stat["laeuft"]):
            daemon.stoppe()
            st.toast("Stopp-Signal gesetzt — Daemon beendet sich sauber (≤30 s)",
                     icon=":material/check_circle:")
            st.rerun()
with d3:
    st.caption("Zeitplan: Tageslauf 06:30 · Scout So 17:00 · Wochenlauf So 18:00 "
               "· Verifikation + Auswertung Sa 09:00. Der Daemon überlebt das "
               "Schließen der UI und schützt Läufe mit Locks gegen "
               "Doppelausführung.")

with st.container(border=True):
    st.markdown("**Letzte Daemon-Meldungen**")
    feed = [f"{z['zeit'][:16]} · {z['job']} · {'✓' if z['ok'] else '✗'} "
            + (z["info"] or "")[:80] for z in stat["zeilen"]]
    status_feed(feed or ["noch keine Meldungen"])
