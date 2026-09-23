# -*- coding: utf-8 -*-
"""Wochenmatrix (S2 Klimatologie + S3 Prognosemodell).

Je Wochentag (Mo–Fr): Klimatologie-P (unkalibrierte Basisrate) UND — wenn
Tor T3 bestanden ist — P_stat aus dem HAR-Modell (HAR-Lags + Events + GVZ),
Range-Band aus der Modellverteilung, Top-Events, Warnstufe.
Jede Matrix wird as_of-versioniert in prognose_versionen gespeichert.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .adapter.kalender import dedup_ereignisse
from .klimatologie import (WEEKDAY_NAMEN, schwelle_naechster_tag, warnstufe,
                           wochentags_statistik)
from .modell import backtest as backtest_modul
from .modell import har
from .modell.event_multiplikatoren import multiplikatoren
from .modell.features import KONFIGURATIONEN, tages_zeilen
from .modell.quant_feeds import gvz_vor
from .modell import richtung as richtung_modul

BERLIN = ZoneInfo("Europe/Berlin")

KLASSEN_FUER_MATRIX = (1.0, 1.5, 2.0)   # Schwellen-Tabelle P(TR > k×Ø)


def montag_von(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _berlin_zeit(zeit_utc: str | None) -> str:
    if not zeit_utc:
        return "ganztag"
    dt = datetime.fromisoformat(zeit_utc).astimezone(BERLIN)
    return dt.strftime("%H:%M")


def _event_flags(db, datum: str) -> dict[str, float]:
    events = dedup_ereignisse(db.events_fuer_zeitraum(datum, datum))
    return {
        "nfp": float(any(e.get("klasse") == "nfp" for e in events)),
        "fomc": float(any(e.get("klasse") == "fomc" for e in events)),
        "gold_termin": float(any((e.get("klasse") or "").startswith("gold_")
                                 for e in events)),
    }


def _modell_sektion(db, settings: dict, d1: list[dict], ziele_schwellen: dict) -> dict | None:
    """Backtest fahren (Tor T3), beste Konfiguration auf allen Daten fitten,
    Fünf-Tage-Prognose je Zieltag. Rückgabe None, wenn keine Nutzdaten."""
    fenster = int(settings.get("matrix_fenster", 13))
    zeilen = tages_zeilen(d1, db, k=float(settings.get("matrix_k", 1.0)), fenster=fenster)
    if len(zeilen) < 160:
        return None
    ergebnis = backtest_modul.walk_forward(zeilen)
    beste_name = ergebnis.get("beste_konfiguration")
    if not beste_name:
        return None

    features = KONFIGURATIONEN[beste_name]
    X, y = har.design_matrix(zeilen, features)
    beta = har.ols_fit(X, y)
    sigma = har.residuen_sigma(X, y, beta)

    iv_tag = datetime.fromtimestamp(d1[-1]["time"], tz=timezone.utc).date()
    iv_daily = None
    gvz = gvz_vor(db, (iv_tag + timedelta(days=1)).isoformat())
    if gvz is not None:
        iv_daily = gvz / 100.0 / 252 ** 0.5

    ziele = [{
        "datum": datum, "wochentag": wt,
        "ln_schwelle": math.log(s["schwelle_rel"]),
        "sigma": sigma,
        "events": _event_flags(db, datum),
        "iv_daily": iv_daily,
    } for datum, (wt, s) in ziele_schwellen.items() if s]
    if not ziele:
        return None
    prognosen = har.mehr_tages(zeilen, features, beta, ziele)
    je_tag = {}
    for p in prognosen:
        je_tag[p["datum"]] = {
            "mu": p["mu"],
            "sigma": sigma,
            "quantile": har.quantile_range(p["mu"], sigma),
            "p_stat": har.p_bewegung(p["mu"], sigma, next(
                z["ln_schwelle"] for z in ziele if z["datum"] == p["datum"])),
        }
    beste_zeile = next(e for e in ergebnis["ergebnisse"]
                       if e["konfiguration"] == beste_name)
    return {
        "konfiguration": beste_name,
        "tor_t3_bestanden": ergebnis["tor_t3_bestanden"],
        "bss": beste_zeile["bss"],
        "brier": beste_zeile["brier"],
        "brier_klimatologie": ergebnis["brier_klimatologie"],
        "n_test": ergebnis["n_test"],
        "backtest_ergebnisse": [
            {k: e[k] for k in ("konfiguration", "n", "brier", "bss", "logloss",
                               "bss_platt_2haelfte")}
            for e in ergebnis["ergebnisse"]],
        "multiplikatoren": multiplikatoren(zeilen),
        "je_tag": je_tag,
        "n_zeilen": len(zeilen),
    }


def _marktlage(db, d1: list[dict]) -> dict:
    """Aktueller Makro-/Positionierungs-Schnappschuss für die UI (S5)."""
    from .modell.richtung import _aktuelle_features
    feats = _aktuelle_features(d1, db) or {}
    cot = db.quant_laden("cot_mm_netto")
    cot_wert = cot_perzentil = None
    if cot:
        letzter_stichtag = max(cot)
        cot_wert = cot[letzter_stichtag]
        werte = sorted(cot.values())
        cot_perzentil = round(100.0 * sum(1 for w in werte if w <= cot_wert)
                              / len(werte), 1)
    vix = db.quant_laden("fred_vixcls")
    vix_aktuell = vix.get(max(vix)) if vix else None
    flags: list[str] = []
    if cot_perzentil is not None and cot_perzentil >= 90:
        flags.append("COT-Crowding: Managed Money extrem long (Historien-"
                     f"Perzentil {cot_perzentil:.0f} %) — anfällig für "
                     "Long-Liquidation")
    if cot_perzentil is not None and cot_perzentil <= 10:
        flags.append(f"COT-Extrem kurz (Perzentil {cot_perzentil:.0f} %) — "
                     "historisch Kontra-Boden")
    if feats.get("gld_delta5_pct") is not None:
        if feats["gld_delta5_pct"] >= 1.0:
            flags.append(f"ETF-Zuflüsse stark ({feats['gld_delta5_pct']:+.1f} % "
                         "GLD-Bestand 5T)")
        elif feats["gld_delta5_pct"] <= -1.0:
            flags.append(f"ETF-Abflüsse ({feats['gld_delta5_pct']:+.1f} % "
                         "GLD-Bestand 5T)")
    if feats.get("d_realzins5") is not None:
        if feats["d_realzins5"] <= -0.10:
            flags.append(f"Realzins 5T {feats['d_realzins5']:+.2f} pp — "
                         "goldfreundlich")
        elif feats["d_realzins5"] >= 0.10:
            flags.append(f"Realzins 5T {feats['d_realzins5']:+.2f} pp — "
                         "goldbelastend")
    if feats.get("d_dollar5") is not None:
        if feats["d_dollar5"] <= -0.5:
            flags.append(f"Dollar 5T {feats['d_dollar5']:+.2f} % — "
                         "goldfreundlich")
        elif feats["d_dollar5"] >= 0.5:
            flags.append(f"Dollar 5T {feats['d_dollar5']:+.2f} % — "
                         "goldbelastend")
    return {
        "d_realzins5_pp": feats.get("d_realzins5"),
        "d_dollar5_pct": feats.get("d_dollar5"),
        "gvz_level": feats.get("gvz_level"),
        "vix": vix_aktuell,
        "cot_netto": cot_wert,
        "cot_stichtag": max(cot) if cot else None,
        "cot_perzentil": cot_perzentil,
        "gld_delta5_pct": feats.get("gld_delta5_pct"),
        "flags": flags,
    }


def baue_matrix(db, settings: dict, basis: date | None = None) -> dict:
    symbol = settings.get("mt5_symbol", "XAUUSD")
    fenster = int(settings.get("matrix_fenster", 13))
    k = float(settings.get("matrix_k", 1.0))
    d1 = db.raten_laden(symbol, "d1")

    statistiken = {kk: wochentags_statistik(d1, k=kk, fenster=fenster)
                   for kk in KLASSEN_FUER_MATRIX}
    basis_stat = statistiken[1.0]
    p_global = basis_stat["p_global"]

    montag = montag_von(basis or date.today())

    # Schwellen je Zieltag (für Modell + Anzeige)
    ziele_schwellen: dict[str, tuple[int, dict | None]] = {}
    schwellen: dict[str, dict | None] = {}
    for i in range(5):
        d = montag + timedelta(days=i)
        s = schwelle_naechster_tag(d1, d.weekday(), k, fenster)
        schwellen[d.isoformat()] = s
        ziele_schwellen[d.isoformat()] = (d.weekday(), s)

    modell = _modell_sektion(db, settings, d1, ziele_schwellen)

    # Richtung (S5): P(hoch) je Zieltag + Backtest/Tor T5 — Fehler tolerieren
    richtung: dict | None = None
    try:
        richtung = richtung_modul.wochen_prognose(
            db, d1, list(ziele_schwellen.keys()))
    except Exception:
        richtung = None
    if richtung and richtung.get("backtest"):
        bt = richtung["backtest"]
        kal = bt.get("kalibrierung") or {}
        db.kalibrierung_speichern(
            "richtung", richtung["konfiguration"], kal.get("methode") or "keine",
            json.dumps({"bss": bt.get("bss"), "kal_brier_2haelfte":
                        kal.get("brier_2haelfte")}, ensure_ascii=False),
            n_train=int(bt.get("n_vollstaendig", 0)) - int(bt.get("n_test", 0)),
            n_test=int(bt.get("n_test", 0)),
            brier=next((e["brier"] for e in bt.get("ergebnisse", [])
                        if e["konfiguration"] == richtung["konfiguration"]), None),
            brier_baseline=bt.get("brier_baseline"),
            bss=bt.get("bss"),
            meta=f"tor_t5={'bestanden' if bt.get('tor_t5_bestanden') else 'nicht bestanden'}")

    tage: list[dict] = []
    for i in range(5):
        d = montag + timedelta(days=i)
        iso = d.isoformat()
        wt = d.weekday()
        events = dedup_ereignisse(db.events_fuer_zeitraum(iso, iso))
        top = sorted(events, key=lambda e: (-(e.get("gold_relevanz") or 0),
                                            -(e.get("wichtigkeit") or 0)))[:4]
        stat = basis_stat["je_wochentag"].get(wt)
        schwelle = schwellen[iso]
        close = schwelle["close_referenz"] if schwelle else None

        p_klima = stat["p"] if stat else None
        p_stat = None
        q10 = q50 = q90 = None
        if modell and iso in modell["je_tag"]:
            p_stat = min(max(modell["je_tag"][iso]["p_stat"], 0.0), 1.0)
            if close:
                quan = modell["je_tag"][iso]["quantile"]
                q10 = round(quan["q10"] * close, 1)
                q50 = round(quan["q50"] * close, 1)
                q90 = round(quan["q90"] * close, 1)
        tage.append({
            "datum": iso,
            "wochentag": WEEKDAY_NAMEN[wt],
            "p": p_klima,
            "p_klima": p_klima,
            "p_stat": p_stat,
            "p_roh": stat["p_roh"] if stat else None,
            "n": stat["n"] if stat else 0,
            "delta_zu_basis": round(p_klima - p_global, 4) if p_klima is not None else None,
            "warnstufe": warnstufe(p_stat if p_stat is not None else (p_klima or 0.5))
                         if (p_stat is not None or p_klima is not None) else "–",
            "schwelle_usd": schwelle["schwelle_usd"] if schwelle else None,
            "schwelle_pct": schwelle["schwelle_pct"] if schwelle else None,
            # Range-Band: Modellverteilung, sonst empirische Klima-Quantile
            "q10_usd": q10 if q10 is not None else
                       (round(stat["q10_tr_rel"] * close, 1) if stat and close else None),
            "q50_usd": q50 if q50 is not None else
                       (round(stat["median_tr_rel"] * close, 1) if stat and close else None),
            "q90_usd": q90 if q90 is not None else
                       (round(stat["q90_tr_rel"] * close, 1) if stat and close else None),
            "events_count": len(events),
            "top_events": [{
                "zeit": _berlin_zeit(e["zeit_utc"]),
                "titel": e["titel"],
                "gold_relevanz": e.get("gold_relevanz"),
                "klasse": e.get("klasse"),
                "forecast": e.get("forecast"),
                "previous": e.get("previous"),
                "actual": e.get("actual_latest") or e.get("actual_first"),
            } for e in top],
            "richtung": (richtung["je_tag"].get(iso) if richtung else None),
        })

    # Schwellen-Tabelle: P(TR > 1,0×/1,5×/2,0× Ø-TR) je Wochentag
    schwellen_tabelle = []
    for wt in range(5):
        zeile = {"Wochentag": WEEKDAY_NAMEN[wt]}
        for kk in KLASSEN_FUER_MATRIX:
            stat = statistiken[kk]["je_wochentag"].get(wt)
            zeile[f"P(>{kk:.1f}×)"] = f"{stat['p'] * 100:.0f} %" if stat else "–"
        stat1 = statistiken[1.0]["je_wochentag"].get(wt)
        zeile["n"] = stat1["n"] if stat1 else 0
        zeile["Median TR"] = f"{stat1['median_tr_rel'] * 100:.2f} %" if stat1 else "–"
        schwellen_tabelle.append(zeile)

    matrix = {
        "woche": montag.isoformat(),
        "bis": (montag + timedelta(days=4)).isoformat(),
        "modell": (f"har_{modell['konfiguration']} (BSS {modell['bss']:+.3f})"
                   if modell and modell["tor_t3_bestanden"]
                   else "klimatologie_v1 (unkalibriert)"),
        "modell_info": modell,
        "erzeugt_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "basis": {
            "symbol": symbol, "bars_d1": len(d1), "fenster": fenster,
            "p_global": p_global, "n_global": basis_stat["n_global"],
        },
        "tage": tage,
        "schwellen_tabelle": schwellen_tabelle,
        "richtung": richtung,
        "marktlage": _marktlage(db, d1),
    }
    db.prognose_speichern(matrix["woche"], matrix["modell"],
                          json.dumps(matrix, ensure_ascii=False))
    return matrix
