# -*- coding: utf-8 -*-
"""Knoten-Detail-Popup: Klick im Baum setzt ?knoten=<id>, das Dashboard
öffnet diesen Dialog mit Erklärung + grafischen Live-Daten aus der DB.
(Wird von dashboard.py per exec/import eingebunden; liegt in app_pages,
weil es Streamlit-UI baut.)"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from goldscanner.adapter.kalender import dedup_ereignisse
from goldscanner.app_state import hole_db
from goldscanner.help_content import KNOTEN_INFO


def _knoten_quellen(knoten: str) -> list[tuple[str, str, str]]:
    """(Label, URL oder "", Hinweis) je Knoten — URLs direkt aus den
    Adapter-Modulen gezogen, damit sie mit dem Code identisch bleiben."""
    from goldscanner.adapter import kalender as _kal
    from goldscanner.adapter import news as _news
    from goldscanner.adapter import quant as _quant
    from goldscanner.modell.quant_feeds import GLD_OPTIONS_URL, GVZ_URL
    from goldscanner import config as _cfg

    namen_kal = {"ff": "ForexFactory (diese Woche)",
                 "bls": "US-Arbeitsamt BLS (Kalender)",
                 "bea": "BEA Wirtschaftsanalyse (Kalender)",
                 "fed": "Federal Reserve (Termin-JSON)",
                 "treasury": "US-Finanzministerium TreasuryDirect"}
    if knoten == "kurse":
        return [("", "", "MetaTrader-5-Terminal des Brokers (Tickmill) — "
                         "Symbol " + (_cfg.load_settings().get("mt5_symbol")
                                      or "XAUUSD")
                         + "; nur lesender Zugriff per Whitelist"),
                ("MetaQuotes", "https://www.metaquotes.net/en/terminals",
                 "Terminal-Hersteller; Kursdaten stammen vom Broker-Feed")]
    if knoten == "kalender":
        return [(namen_kal.get(qid, qid), url, "Abruf je Wochenlauf, Hash-archiviert")
                for qid, url, _a, _p in _kal._QUELLEN] + [
                ("", "", "Regeltermine (Gold-FND/LTD, Opex, Feiertage, DST) "
                         "werden lokal berechnet — keine URL")]
    if knoten == "gvz":
        zeilen = [("Cboe GVZ-Historie", GVZ_URL,
                   "implizite 30-Tage-Gold-Volatilität aus Optionen"),
                  ("GLD-Options-JSON (iv30)", GLD_OPTIONS_URL,
                   "verzögerte Optionskette, Expected-Move-Prüfung")]
        for kuerzel, serie in _quant.FRED_SERIEN.items():
            zeilen.append((f"FRED {serie}", f"https://fred.stlouisfed.org/series/{serie}",
                           kuerzel))
        zeilen += [
            ("CFTC Commitments of Traders (Gold 088691)",
             f"https://publicreporting.cftc.gov/resource/{_quant.COT_DATASET}"
             "?cftc_contract_market_code=088691",
             "Fonds-Positionen, 4 Tage nach Stichtag"),
            ("SPDR GLD Bestände (Tonnen)", _quant.GLD_URL,
             "XLSX-Archiv, ToS: private Nutzung")]
        return zeilen
    if knoten == "news":
        return [(qid, url, "RSS-Feed") for qid, url in _news.QUELLEN]
    if knoten == "community":
        return [
            ("TradingView Ideen (OANDA:XAUUSD)",
             "https://www.tradingview.com/feed/?symbol=OANDA:XAUUSD",
             "30 Ideen; Long/Short + Kursmarken — ToS: privat/Anzeige"),
            ("FXStreet Analysen", "https://www.fxstreet.com/rss/analysis", "RSS"),
            ("FXEmpire Prognosen",
             "https://www.fxempire.com/api/v1/en/articles/rss/forecasts", "RSS"),
            ("Kitco Weekly Gold Survey",
             "https://www.kitco.com/news/category/weekly-gold-survey",
             "Best-Effort (HTML ohne RSS)")]
    if knoten in ("news_distill", "comm_destill", "fusion"):
        return [
            ("GLM-API (Z.ai)", _cfg.glm_base_url(_cfg.load_settings()) + "/chat/completions",
             ("glm-5.3-flash (Destillation)" if knoten != "fusion"
              else "glm-5.3 (Analytiker)") + " — vollständige Prompte/Antworten "
             "im Journal (Seite Journal)"),
            ("Z.ai API-Dokumentation", "https://api.z.ai", "Endpunkt umschaltbar: "
             "Abo (Coding) / Pay-as-you-go")]
    if knoten == "statistik":
        return [
            ("", "", "Eigenberechnung aus den lokalen Kursen — keine externe "
                     "Quelle (Engine rechnet, LLM zitiert)"),
            ("Corsi/Andersen (HAR-Grundlage)",
             "https://doi.org/10.2139/ssrn.1010579",
             "„Realized Volatility Almost Everything“ (2003/2009)"),
            ("CBOE GVZ (Feature)", GVZ_URL, "eins der Modell-Merkmale")]
    if knoten == "matrix":
        return [("", "", "Interne Berechnung — jede Version as_of archiviert; "
                         "lesbar über REST 127.0.0.1:8606/matrix")]
    if knoten == "pdf":
        return [("", "", "reportlab-generiert aus der Matrix; Dateien in "
                         "data/reports/ (Download-Buttons oben)")]
    if knoten == "export":
        return [("", "", "CSV: data/exports/goldscanner_prognose.csv + "
                         "MT5-Common-Files (identisch)")]
    return []


@st.dialog("Knoten-Details", width="large")
def knoten_dialog(knoten: str, settings: dict) -> None:
    titel, text = KNOTEN_INFO[knoten]
    st.subheader(titel)
    st.markdown(text)
    st.divider()
    try:
        _live_daten(knoten, settings)
    except Exception as exc:
        st.caption(f"(Live-Daten gerade nicht verfügbar: {type(exc).__name__})")
    quellen = _knoten_quellen(knoten)
    if quellen:
        st.divider()
        st.markdown("**Quellen — woher das kommt**")
        for label, url, hinweis in quellen:
            link = (f"[{label}]({url})" if url and label
                    else (label or hinweis or ""))
            st.markdown(f"· {link}"
                        + (f" — {hinweis}" if url and label and hinweis else
                           (" — " + hinweis if not label and hinweis else "")))
    if st.button("Schließen", icon=":material/close:", type="primary"):
        st.query_params.pop("knoten", None)
        st.rerun()


def _live_daten(knoten: str, settings: dict) -> None:
    db = hole_db()
    symbol = settings.get("mt5_symbol", "XAUUSD")
    matrix = st.session_state.get("matrix") or {}

    if knoten == "kurse":
        c1, c2, c3 = st.columns(3)
        c1.metric("D1-Bars", f"{db.raten_anzahl(symbol, 'd1'):,}".replace(",", "."))
        c2.metric("H4-Bars", f"{db.raten_anzahl(symbol, 'h4'):,}".replace(",", "."))
        c3.metric("H1-Bars", f"{db.raten_anzahl(symbol, 'h1'):,}".replace(",", "."))

    elif knoten == "kalender":
        st.metric("Termine in DB", f"{db.events_anzahl():,}".replace(",", "."))
        events = dedup_ereignisse(db.events_fuer_zeitraum(
            date.today().isoformat(),
            (date.today() + timedelta(days=7)).isoformat()))[:8]
        if events:
            st.dataframe(pd.DataFrame([{
                "Datum": e["datum"],
                "Zeit": (e.get("zeit_utc") or "")[:16] or "ganztag",
                "Termin": e["titel"][:48], "Klasse": e.get("klasse"),
                "★": e.get("gold_relevanz")} for e in events]),
                hide_index=True, width="stretch")

    elif knoten == "gvz":
        ml = matrix.get("marktlage") or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("GVZ (Options-Vola)", ml.get("gvz_level") or "–")
        c2.metric("Δ Realzins 5T (pp)", ml.get("d_realzins5_pp") or "–")
        c3.metric("Δ Dollar 5T (%)", ml.get("d_dollar5_pct") or "–")
        c4.metric("VIX", ml.get("vix") or "–")
        c5, c6 = st.columns(2)
        c5.metric("COT Fonds-Netto",
                  f"{(ml.get('cot_netto') or 0) / 1000:.0f}k "
                  f"(P{ml.get('cot_perzentil') or '?'})")
        c6.metric("GLD-Bestand Δ5T (%)", ml.get("gld_delta5_pct") or "–")
        for f in (ml.get("flags") or []):
            st.markdown(f"· {f}")

    elif knoten == "news":
        c1, c2 = st.columns(2)
        c1.metric("Artikel in DB", f"{db.news_anzahl():,}".replace(",", "."))
        c2.metric("noch unbearbeitet",
                  f"{db.news_anzahl(offen=True):,}".replace(",", "."))
        letzte = [z for z in db.letzte_schritte(400)
                  if z["agent"] == "news_destillation" and z["ok"]]
        if letzte:
            try:
                daten = json.loads(letzte[0]["antwort"])
                st.markdown(f"**Letztes Destillat** ({letzte[0]['zeit'][:16]}): "
                            f"{daten.get('erkenntnis', '')}")
                st.dataframe(pd.DataFrame([{
                    "Treiber": tr.get("name"), "Richtung": tr.get("richtung"),
                    "Konfidenz": tr.get("konfidenz"),
                    "Beleg": (tr.get("beleg_url") or "")[:60]}
                    for tr in daten.get("treiber", [])]),
                    hide_index=True, width="stretch")
            except (ValueError, KeyError, TypeError):
                pass

    elif knoten in ("news_distill", "comm_distill"):
        agent = ("news_destillation" if knoten == "news_distill"
                 else "community_destillation")
        zeilen = [z for z in db.letzte_schritte(400)
                  if z["agent"] == agent and z["ok"]]
        if zeilen:
            z = zeilen[0]
            st.caption(f"Letzter Aufruf {z['zeit'][:19]} · Modell {z['modell']} · "
                       f"{z['tokens']:,} Token".replace(",", "."))
            try:
                daten = json.loads(z["antwort"])
                if knoten == "comm_distill":
                    for k in ("konsens_richtung", "einigkeit",
                              "volatilitaet_effekt"):
                        st.markdown(f"· **{k}:** {daten.get(k)}")
                    st.markdown(daten.get("erklaerung", ""))
                else:
                    st.dataframe(pd.DataFrame([{
                        "Treiber": tr.get("name"),
                        "Richtung": tr.get("richtung"),
                        "Horizont": tr.get("horizont"),
                        "Erklärung": (tr.get("erklaerung") or "")[:70]}
                        for tr in daten.get("treiber", [])]),
                        hide_index=True, width="stretch")
            except (ValueError, KeyError, TypeError):
                st.code((z["antwort"] or "")[:800], language=None)
        else:
            st.caption("Noch kein Aufruf im Journal.")

    elif knoten == "fusion":
        fusion = db.fusion_letzte()
        if fusion:
            daten = json.loads(fusion["inhalt"])
            st.caption(f"as_of {fusion['as_of'][:19]} · Modell {fusion['modell']} · "
                       f"Band ±{fusion['band_pp']:.0f} pp · Δmax "
                       f"{fusion['delta_max_pp']} pp · "
                       f"{fusion['verstoesse']} Verstoß/Verstöße")
            st.markdown(daten.get("zusammenfassung", ""))
            st.dataframe(pd.DataFrame([{
                "Tag": t.get("datum"),
                "P_finale": f"{t.get('p_finale_pct')} %",
                "Basis": f"{t.get('basis_pct')} %",
                "Δ pp": t.get("abweichung_pp"),
                "Richtung": t.get("richtung"),
                "Konfidenz": t.get("konfidenz")}
                for t in daten.get("tage", [])]),
                hide_index=True, width="stretch")
        else:
            st.caption("Noch keine Fusion gespeichert.")

    elif knoten in ("statistik", "matrix"):
        info = matrix.get("modell_info") or {}
        if info:
            c1, c2, c3 = st.columns(3)
            c1.metric("Modell", matrix.get("modell", "–"))
            c2.metric("BSS (Tor T3)", f"{info.get('bss', 0):+.3f}")
            c3.metric("Testtage", info.get("n_test"))
        tage = matrix.get("tage") or []
        if tage:
            fusion_je_tag = {f.get("datum"): f for f in
                             (matrix.get("llm") or {}).get("tage", [])}
            st.dataframe(pd.DataFrame([{
                "Tag": t["wochentag"],
                "P_finale": (f"{fusion_je_tag.get(t['datum'], {}).get('p_finale_pct')} %"
                             if fusion_je_tag.get(t["datum"]) else "–"),
                "P_stat": f"{round((t.get('p_stat') or t.get('p') or 0) * 100)} %",
                "Klima": f"{round((t.get('p_klima') or 0) * 100)} %",
                "Warnstufe": t.get("warnstufe"),
                "Schwelle $": t.get("schwelle_usd"),
                "Q10–Q90": (f"{t.get('q10_usd')}–{t.get('q90_usd')}"
                            if t.get("q10_usd") else "–")} for t in tage]),
                hide_index=True, width="stretch")

    elif knoten == "pdf":
        from goldscanner import config as _cfg
        pdfs = sorted(_cfg.REPORTS_DIR.glob("*.pdf"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        if not pdfs:
            st.info("Noch kein PDF erzeugt — der nächste Wochenlauf legt es "
                    "nach data/reports/.")
        for pfad in pdfs[:4]:
            c_dl, c_info = st.columns([1, 3])
            with c_dl:
                st.download_button("Download", pfad.read_bytes(),
                                   file_name=pfad.name, mime="application/pdf",
                                   key=f"pdf_dl_{pfad.name}")
            with c_info:
                st.caption(f"{pfad.name} · {pfad.stat().st_size / 1024:.0f} KB")
        if pdfs:
            with st.expander("Vorschau (neuestes PDF direkt im Fenster)",
                             expanded=True):
                # Chrome blockiert eingebettete PDFs aus data:-URLs — die
                # Seiten werden deshalb mit PyMuPDF zu Bildern gerendert
                # (immer lesbar, offline, kein Plugin nötig).
                import fitz
                doc = fitz.open(pdfs[0])
                for i, seite in enumerate(doc):
                    pix = seite.get_pixmap(dpi=110)
                    st.image(pix.tobytes("png"),
                             caption=f"{pdfs[0].name} · Seite {i + 1} von {len(doc)}",
                             use_container_width=True)
                doc.close()

    elif knoten == "export":
        from goldscanner import config as _cfg
        csv_pfad = _cfg.DATA_DIR / "exports" / "goldscanner_prognose.csv"
        if csv_pfad.exists():
            st.caption(f"Datei: `{csv_pfad}` (identische Kopie liegt in den "
                       "MT5 Common-Files)")
            st.code(csv_pfad.read_text(encoding="utf-8")[:1500], language=None)
        else:
            st.info("Noch kein Export — der nächste Wochenlauf schreibt ihn.")
