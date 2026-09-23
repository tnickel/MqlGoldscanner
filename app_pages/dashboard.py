"""Dashboard — Stufe 2: Wochenmatrix (Klimatologie), Schwellen-Tabelle, Status."""
from __future__ import annotations

import json
import math
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

# Letzte gespeicherte Matrix früh ziehen (bevor Stepper/Kopf sie brauchen)
if "matrix" not in st.session_state:
    letzte_frueh = hole_db().prognose_letzte()
    if letzte_frueh:
        try:
            st.session_state["matrix"] = json.loads(letzte_frueh["inhalt"])
        except (json.JSONDecodeError, TypeError):
            pass

page_header(
    "Stufe 2–5 · Statistik + Modell + KI-Erklärung + Richtung",
    "Gold-Bewegungswahrscheinlichkeit je Wochentag",
    "Hauptziel: pro Tag **Wahrscheinlichkeit**, **erwartete Range** und "
    "**Richtung** (P(hoch)). Die Matrix zeigt P_stat aus dem HAR-Modell (HAR-Lags "
    "+ Events + GVZ) neben der Klimatologie-Basisrate; der Analytiker-Agent "
    "verschiebt P im engeren Band (±{band} pp) nur mit Begründung. Tor T3: nur "
    "Modelle mit BSS > 0 gegen die Basisrate kommen auf die Matrix.".format(
        band=int(config.load_settings().get("llm_band_pp", 10))),
)

_matrix_state = st.session_state.get("matrix") or {}
_llm_ok = bool(_matrix_state.get("llm", {}).get("ok"))
_t5_ok = bool((_matrix_state.get("richtung") or {}).get("backtest", {})
              .get("tor_t5_bestanden"))
zeige_stepper([
    {"nr": 1, "title": "Gerüst & Kurse", "status": "complete", "meta": "App · MT5 · GLM"},
    {"nr": 2, "title": "Klimatologie-Matrix", "status": "complete", "meta": "Kalender · Basisrate"},
    {"nr": 3, "title": "Kalibriertes Modell", "status": "complete" if
        _matrix_state.get("modell_info", {}).get("tor_t3_bestanden")
        else "pending", "meta": "HAR · Events · GVZ"},
    {"nr": 4, "title": "LLM-Erklärungen", "status": "complete" if _llm_ok else "pending",
     "meta": "Treiber · Begründung · PDF"},
    {"nr": 5, "title": "Richtung & Quant", "status": "complete" if _t5_ok else "pending",
     "meta": "P(hoch) · COT · FRED"},
    {"nr": 6, "title": "Betrieb & Track-Record", "status": "pending", "meta": "Daemon · BSS · Scout"},
    {"nr": 7, "title": "Ausbau", "status": "pending", "meta": "optional"},
], overall=(5 if _t5_ok else (4 if _llm_ok else 3)) / 7)

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
    banner = aktivitaets_banner(
        "Wochenlauf: Kurse → Kalender → GVZ → Matrix → News → KI-Fusion …")
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
    llm = protokoll.get("llm", {})
    llm_info = ""
    if llm.get("ok"):
        fusion = llm.get("fusion", {})
        llm_info = (f" · KI-Fusion ok (Δmax {fusion.get('delta_max_pp', 0):.0f} pp, "
                    f"{llm.get('tokens', 0):,} Token)".replace(",", "."))
        if protokoll.get("pdf", {}).get("ok"):
            llm_info += " · PDF erzeugt"
    else:
        llm_info = " · KI-Fusion aus (" + str(llm.get("grund", ""))[:60] + ")"
    st.toast(f"Wochenlauf fertig · Kalender: {len(kal) - len(fehler)}/{len(kal)} Quellen"
             + (f" (Fehler: {', '.join(fehler)})" if fehler else ""),
             icon=":material/check_circle:")
    st.caption(f"Kurse: {k_info}{llm_info}")

if aktualisieren:
    alte = st.session_state.get("matrix") or {}
    neue = baue_matrix(hole_db(), settings)
    # Die KI-Fusion der alten Version bleibt sichtbar, bis der nächste
    # Wochenlauf eine neue erzeugt — „neu bauen" ist ja nur Statistik.
    for feld in ("llm", "protokoll_llm"):
        if alte.get(feld) and feld not in neue:
            neue[feld] = alte[feld]
    st.session_state["matrix"] = neue

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
    _RICHTUNGS_ICON = {"hoch": "▲", "runter": "▼", "neutral": "▬"}
    modell_info = matrix.get("modell_info") or {}
    llm_sektion = matrix.get("llm") or {}
    fusion_je_tag = {t["datum"]: t for t in llm_sektion.get("tage", [])}
    spalten = st.columns(5, gap="small")
    for spalte, tag in zip(spalten, matrix["tage"]):
        with spalte:
            with st.container(border=True):
                d = datetime.fromisoformat(tag["datum"])
                st.markdown(f"**{tag['wochentag']}** · {d.strftime('%d.%m.')}")
                f = fusion_je_tag.get(tag["datum"])
                p = tag["p_stat"] if tag.get("p_stat") is not None else tag["p"]
                p_klima = tag.get("p_klima")
                delta = (p - p_klima) if (p is not None and p_klima is not None) else None
                if f:
                    p_anzeige = f["p_finale_pct"] / 100.0
                    st.metric("P(Bewegung)", f"{p_anzeige * 100:.0f} %",
                              f"{f['abweichung_pp']:+.0f} pp KI-Anpassung",
                              border=True, label_visibility="collapsed")
                else:
                    st.metric("P(Bewegung)", "–" if p is None else f"{p * 100:.0f} %",
                              None if delta is None else f"{delta * 100:+.0f} pp vs. Klima",
                              border=True, label_visibility="collapsed")
                if p is not None or f:
                    st.progress(min(p_anzeige if f else (p or 0.0), 1.0))
                if f:
                    st.caption(f"Modell: {f['basis_pct']:.0f} % · "
                               f"{_RICHTUNGS_ICON.get(f['richtung'], '▬')} "
                               f"{f['richtung']} ({f['konfidenz']})")
                elif p_klima is not None and p is not None:
                    st.caption(f"Klimatologie: {p_klima * 100:.0f} %"
                               + (" · Modell" if tag.get("p_stat") is not None else ""))
                farbe = _WARNFARBEN.get(tag["warnstufe"], "#94A3B8")
                st.markdown(f'<span style="color:{farbe};font-weight:700">'
                            f'● {tag["warnstufe"].upper()}</span>',
                            unsafe_allow_html=True)
                r = tag.get("richtung")
                if r:
                    r_farbe = "#34D399" if r["symbol"].startswith("▲") else (
                        "#FB7185" if r["symbol"].startswith("▼") else "#94A3B8")
                    st.markdown(
                        f'Richtung <span style="color:{r_farbe};font-weight:800">'
                        f'{r["symbol"]}</span> · P(hoch) {r["p_hoch"] * 100:.0f} %',
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

    if modell_info:
        with st.expander(f"Backtest · Tor T3 — {
            'BESTANDEN' if modell_info['tor_t3_bestanden'] else 'NICHT bestanden'} "
                         f"(BSS {modell_info['bss']:+.3f}, n={modell_info['n_test']})"):
            if modell_info["tor_t3_bestanden"]:
                st.success(f"**Tor T3 bestanden:** Konfiguration "
                           f"`{modell_info['konfiguration']}` schlägt die Klimatologie im "
                           f"Walk-Forward (BSS {modell_info['bss']:+.3f} = "
                           f"{modell_info['bss'] * 100:.1f} % weniger Brier-Fehler). "
                           "Die Matrix zeigt P_stat aus dem Modell.")
            else:
                st.warning("**Tor T3 nicht bestanden:** Keine Konfiguration schlägt die "
                           "Klimatologie stabil — die Matrix bleibt auf der Basisrate "
                           "(ehrlich statt Rauschen zu erklären). Features iterieren "
                           "(mehr Historie, echte Event-Historie über CalendarExport.mq5).")
            bt = pd.DataFrame(modell_info["backtest_ergebnisse"]).rename(columns={
                "konfiguration": "Konfiguration", "n": "n Test",
                "brier": "Brier", "bss": "BSS vs. Klima", "logloss": "Log-Loss",
                "bss_platt_2haelfte": "BSS (Platt, 2. Hälfte)"})
            st.dataframe(bt, hide_index=True, width="stretch")
            st.caption("Walk-Forward expanding window: Training nur mit Tagen VOR dem "
                       "Testtag. A = Klimatologie (Referenz), B = +HAR, C = +Events, "
                       "D = +GVZ. Platt = Nachkalibrierung auf der 1. OOS-Hälfte, "
                       "bewertet auf der 2.")
            mult = pd.DataFrame(modell_info["multiplikatoren"]).rename(columns={
                "event": "Event", "n": "n", "multiplikator": "Ø-TR-Multiplikator",
                "p_bewegung_event": "P(Bewegung|Event)", "p_bewegung_normal":
                "P(Bewegung|normal)", "lift_pp": "Lift (pp)"})
            if not mult.empty:
                st.markdown("**Gemessene Event-Multiplikatoren** (historisch, "
                            "NFP = erster-Freitag-Proxy, FOMC aus Fed-Historie):")
                st.dataframe(mult, hide_index=True, width="stretch")

    richtung_sek = matrix.get("richtung")
    marktlage = matrix.get("marktlage") or {}
    if richtung_sek:
        bt = richtung_sek.get("backtest") or {}
        with st.expander(
                f"Richtung & Marktlage (Stufe 5) — P(hoch) je Tag · Tor T5 "
                f"{'BESTANDEN' if bt.get('tor_t5_bestanden') else 'offen/nicht bestanden'}"):
            if bt.get("tor_t5_bestanden"):
                st.success(f"**Tor T5:** Konfiguration `{richtung_sek['konfiguration']}` "
                           f"schlägt die Ø-Aufwärtswahrscheinlichkeit im Walk-Forward "
                           f"(BSS {bt.get('bss', 0):+.3f}, n={bt.get('n_test')} Testtage).")
            else:
                st.warning("**Tor T5 nicht bestanden:** Das Richtungsmodell schlägt die "
                           "Baseline nicht — die Richtungs-Symbole bleiben mit Vorsicht "
                           "zu lesen (qualitative Einschätzung, klar gekennzeichnet).")
            ab = pd.DataFrame(bt.get("ergebnisse", [])).rename(columns={
                "konfiguration": "Konfiguration", "n": "n Test", "brier": "Brier",
                "bss": "BSS vs. Ø-Rate"})
            if not ab.empty:
                st.markdown(f"Baseline (immer Ø-Aufwärtswahrscheinlichkeit "
                            f"{richtung_sek.get('base_rate', 0) * 100:.1f} %): "
                            f"Brier **{bt.get('brier_baseline', 0):.4f}**")
                st.dataframe(ab, hide_index=True, width="stretch")
                st.caption("Ablation auf identischen Testtagen (complete-case): "
                           "R1 Trend → R2 +Makro (Realzins/Dollar/GVZ) → "
                           "R3 +Positionierung (COT/GLD). Nachkalibrierung: "
                           f"{(bt.get('kalibrierung') or {}).get('methode')} "
                           "(1. OOS-Hälfte gefittet, 2. bewertet: Brier "
                           f"{(bt.get('kalibrierung') or {}).get('brier_2haelfte')}). "
                           "FRED-Daten konservativ mit t−2 genutzt, COT erst ab "
                           "Stichtag+4 (Veröffentlichungsverzug) — kein Look-ahead.")
            if marktlage:
                m1, m2, m3, m4 = st.columns(4, gap="small")
                with m1:
                    st.metric("Δ Realzins 5T (pp)",
                              "–" if marktlage.get("d_realzins5_pp") is None
                              else f"{marktlage['d_realzins5_pp']:+.2f}", border=True)
                with m2:
                    st.metric("Δ Dollar 5T (%)",
                              "–" if marktlage.get("d_dollar5_pct") is None
                              else f"{marktlage['d_dollar5_pct']:+.2f}", border=True)
                with m3:
                    st.metric("COT MM Netto",
                              "–" if marktlage.get("cot_netto") is None
                              else f"{marktlage['cot_netto'] / 1000:.0f}k "
                                    f"(P{marktlage.get('cot_perzentil'):.0f})",
                              border=True)
                with m4:
                    st.metric("GLD-Bestand Δ5T (%)",
                              "–" if marktlage.get("gld_delta5_pct") is None
                              else f"{marktlage['gld_delta5_pct']:+.2f}", border=True)
                if marktlage.get("flags"):
                    st.markdown("**Marktlage-Signale:**")
                    for f in marktlage["flags"]:
                        st.markdown(f"· {f}")

    # ── S7: Wochen-Summenwert + Was-wäre-wenn ──────────────────────────
    woche_summe = matrix.get("wochen_summe")
    modell_info_s7 = matrix.get("modell_info") or {}
    je_tag_verteilung = (modell_info_s7.get("je_tag") or {})
    if woche_summe:
        with st.expander(f"Wochen-Summenwert — P(mindestens 1 Bewegungstag) "
                         f"**{woche_summe['p_mindestens_ein_modell'] * 100:.0f} %** "
                         f"(Klima {woche_summe['p_mindestens_ein_klima'] * 100:.0f} %)"):
            st.caption(woche_summe.get("hinweis", ""))
    if je_tag_verteilung:
        with st.expander("Was-wäre-wenn — Simulation (verändert keine "
                         "gespeicherte Prognose)", expanded=False):
            c1, c2, c3 = st.columns(3, gap="small")
            with c1:
                vola = st.slider("Volatilität", -50, 100, 0, 5,
                                 format="%+d %%", key="s7_vola",
                                 help="Sigma der Modell-Verteilung verschieben")
            with c2:
                mu_shift = st.slider("Range-Niveau", -50, 100, 0, 5,
                                     format="%+d %%", key="s7_mu",
                                     help="Erwartete Tagesrange verschieben")
            with c3:
                zuschlag = st.slider("Event-Zuschlag", -20, 20, 0, 1,
                                     format="%+d pp", key="s7_event",
                                     help="Additiv auf das Ergebnis je Tag")
            if vola or mu_shift or zuschlag:
                from goldscanner.modell.szenario import was_waere_wenn
                mu_sigma = {d: (v["mu"], v["sigma"])
                            for d, v in je_tag_verteilung.items()}
                ln_schwellen = {t["datum"]: math.log(t["schwelle_pct"])
                                for t in matrix["tage"] if t.get("schwelle_pct")}
                simuliert = was_waere_wenn(mu_sigma, ln_schwellen,
                                           vola_shift_pct=vola,
                                           mu_shift_pct=mu_shift,
                                           event_zuschlag_pp=zuschlag)
                spalten_sim = st.columns(5, gap="small")
                for spalte, t in zip(spalten_sim, matrix["tage"]):
                    with spalte:
                        p_sim = simuliert.get(t["datum"])
                        basis = (t.get("p_stat") or 0) * 100
                        delta_pp = (p_sim * 100 - basis) if p_sim is not None else 0
                        st.metric(t["wochentag"][:2],
                                  f"{p_sim * 100:.0f} %" if p_sim is not None else "–",
                                  f"{delta_pp:+.0f} pp", border=True)
                st.caption("⚠️ **Simulation** — dieselbe Rechenformel wie das echte "
                           "Modell, aber mit von Hand verschobenen Parametern. Nicht "
                           "gespeichert, nicht exportiert, nicht in der Verifikation.")
            else:
                st.caption("Slider bewegen, um Szenario-Wirkungen auf P je Tag zu "
                           "sehen (alles bei 0 = Prognose unverändert).")

    if llm_sektion.get("ok"):
        band = llm_sektion.get("band_pp", 10)
        with st.expander(
                f"KI-Analyse (Stufe 4) — Analytiker-Fusion im ±{band:.0f}-pp-Band · "
                f"Δmax {llm_sektion.get('delta_max_pp', 0):.0f} pp", expanded=True):
            if llm_sektion.get("zusammenfassung"):
                st.markdown(llm_sektion["zusammenfassung"])
            fusion_je_tag_llm = {t["datum"]: t for t in llm_sektion.get("tage", [])}
            for t_matrix in matrix["tage"]:
                f = fusion_je_tag_llm.get(t_matrix["datum"])
                if not f:
                    continue
                st.markdown(f"**{t_matrix['wochentag']} {t_matrix['datum']}** — "
                            f"P_finale **{f['p_finale_pct']:.0f} %** "
                            f"(Modell {f['basis_pct']:.0f} %, "
                            f"Δ {f['abweichung_pp']:+.1f} pp, "
                            f"{_RICHTUNGS_ICON.get(f['richtung'], '▬')} {f['richtung']})")
                if f.get("begruendung"):
                    st.caption(f["begruendung"])
                if f.get("treiber"):
                    balken = []
                    for tr in f["treiber"]:
                        breite = min(abs(tr["einfluss_pp"]) / max(band, 1.0), 1.0) * 100
                        farbe = {"auf": "#E8B84B", "ab": "#F43F5E"}.get(
                            tr["richtung"], "#94A3B8")
                        balken.append(
                            f'<div class="gld-wasserfall">'
                            f'<span class="gld-wf-name">{tr["name"][:44]}</span>'
                            f'<span class="gld-wf-balken"><i style="width:{breite:.0f}%;'
                            f'background:{farbe}"></i></span>'
                            f'<span class="gld-wf-wert">{tr["einfluss_pp"]:+.1f} pp</span>'
                            f'</div>')
                    st.html('<div class="gld-wasserfall-liste">'
                            + "".join(balken) + "</div>")
            if llm_sektion.get("verstoesse"):
                st.warning(f"**{len(llm_sektion['verstoesse'])} Band-Verstoß/Verstöße** "
                           "vom System abgewiesen (Tag fiel auf die Modellwahrscheinlichkeit): "
                           + "; ".join(llm_sektion["verstoesse"][:4]))
            else:
                st.caption("Band-Disziplin eingehalten — keine Abweisungen.")
            if llm_sektion.get("risiken"):
                st.markdown("**Risiken:** " + " · ".join(llm_sektion["risiken"]))
            if llm_sektion.get("kontra_hinweis"):
                st.caption(f"Kontra-Hinweis: {llm_sektion['kontra_hinweis']}")
            pdf_pfad = (config.REPORTS_DIR /
                        f"wochenbericht_{matrix['woche']}.pdf")
            if pdf_pfad.exists():
                with open(pdf_pfad, "rb") as fh:
                    st.download_button(
                        "Wochenbericht als PDF", fh.read(),
                        file_name=pdf_pfad.name, mime="application/pdf",
                        icon=":material/picture_as_pdf:")
    elif matrix.get("protokoll_llm") is not None and not matrix["protokoll_llm"].get("llm_ok"):
        with st.expander("KI-Analyse (Stufe 4) — nicht verfügbar"):
            st.info("Die LLM-Fusion lief beim letzten Wochenlauf nicht mit "
                    "(kein GLM-Key, Budget erschöpft oder wiederholte ungültige "
                    "Antworten). Die Matrix bleibt rein statistisch — sie lügt "
                    "nie, sie schweigt nur. **„Wochenlauf starten“** erneut "
                    "ausführen, sobald der Grund behoben ist.")
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
    db_fuer_postfach = hole_db()
    offene_meldungen = db_fuer_postfach.meldungen(nur_offene=True)
    if offene_meldungen:
        with st.container(border=True):
            st.subheader(f"Postfach · {len(offene_meldungen)} neu", width="content")
            for m in offene_meldungen[:5]:
                st.markdown(f"· **{m['zeit'][:16].replace('T', ' ')}** — {m['text']}")
            if st.button("Alle als gelesen markieren", icon=":material/done_all:"):
                for m in offene_meldungen:
                    db_fuer_postfach.meldung_gelesen_markieren(m["id"])
                st.rerun()
    with st.container(border=True):
        st.subheader("So geht es weiter", width="content")
        st.markdown(
            "**S6 — Betrieb & Selbstverbesserung**  \n"
            "Daemon, Track-Record, URL-Scout, MT5-Export der Prognosen.\n\n"
            "**Tor T4/T5 im Track-Record:** Nach einigen Wochen wird gemessen, ob "
            "das LLM-Delta und die Quant-Feeds historisch Mehrwert bringen — "
            "sonst Band straffen bzw. Feeds kürzen.")
    with st.container(border=True):
        st.subheader("Jetzt sinnvoll", width="content")
        st.markdown(
            "1. **mql5/CalendarExport.mq5** einmal im Terminal ausführen → Ist-Werte "
            "(Actuals) fließen in die Tagessicht\n\n"
            "2. **Tagessicht** öffnen: Event-Zeitleiste der Woche\n\n"
            "3. **Quellen** → Launch-Check; **Chart** → Kurse laden")
