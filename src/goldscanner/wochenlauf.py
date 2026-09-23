"""Wochenlauf (S2–S4): Kurse → Kalender → GVZ → Matrix (Klima+HAR) →
News → Community → LLM-Fusion → Wochen-PDF.

Alles wird im Journal protokolliert; jeder Schritt arbeitet auf lokalen
Daten weiter (Resilienz-Prinzip aus dem Konzept §4). Die LLM-Schritte
sind optional: Ohne GLM-Key bzw. bei erschöpftem Budget läuft die Matrix
weiter rein statistisch — nie halbe LLM-Ergebnisse.
"""
from __future__ import annotations

import json

from . import config, secrets_store
from .adapter import community as community_adapter
from .adapter import kalender
from .adapter import news as news_adapter
from .adapter import quant as quant_adapter
from .agenten import analytiker, destillation
from .bericht import pdf as pdf_bericht
from .betrieb import mt5_export
from .llm.client import GlmClient
from .modell.quant_feeds import gvz_aktualisieren
from .mt5 import kurse
from .wochenmatrix import baue_matrix


def _client_bauen(settings: dict, db) -> GlmClient | None:
    """Client nur mit Key; Endpunkt/Modelle aus den Einstellungen."""
    if not secrets_store.get_secret("glm_api_key"):
        return None
    return GlmClient(
        model_stufe1=settings.get("model_stufe1", config.MODEL_STUFE1),
        model_stufe2=settings.get("model_stufe2", config.MODEL_STUFE2),
        max_total_tokens=int(settings.get("llm_max_total_tokens", 5_000_000)),
        timeout=int(settings.get("llm_timeout_s", 300)),
        base_url=config.glm_base_url(settings), db=db)


def starten(db, settings: dict, fortschritt=None) -> dict:
    """Läuft synchron (UI zeigt Aktivitäts-Badge). Rückgabe: Gesamtprotokoll.

    Ein lauf_lock verhindert Doppel-Läufe zwischen GUI-Button und Daemon
    (gleicher Lockname wie im Daemon: job_wochenlauf).

    fortschritt: optionaler Callback fortschritt(station_schluessel), der
    zu Beginn jeder Phase gerufen wird — die GUI nutzt ihn, um den
    Live-Stepper pulsieren zu lassen (der Daemon ruft ohne)."""
    from .lock import LockBesetzt, lauf_lock
    try:
        with lauf_lock(config.DATA_DIR, "job_wochenlauf"):
            return _starten_intern(db, settings, fortschritt=fortschritt)
    except LockBesetzt as exc:
        return {"sperrung": str(exc), "kurse": {}, "kalender": {}, "gvz": {},
                "quant": {}, "matrix": {"ok": False, "grund": str(exc)},
                "news": {}, "community": {}, "llm": {}, "pdf": {}, "export": {}}


def _starten_intern(db, settings: dict, fortschritt=None) -> dict:

    def _melde(station: str, text: str | None = None) -> None:
        """Station setzen (+ optionale Live-Meldung) — Anzeige darf nie brechen."""
        if fortschritt is not None:
            try:
                fortschritt(station, text)
            except Exception:
                pass
    protokoll: dict = {"kurse": {}, "kalender": {}, "gvz": {}, "quant": {},
                       "matrix": {}, "news": {}, "community": {}, "llm": {},
                       "pdf": {}, "export": {}}

    lauf = db.lauf_starten(
        "wochenlauf",
        "Kurse + Kalender + Quant-Feeds + Matrix (S2–S5) + LLM-Schicht (S4)")
    try:
        # 1) Kurse frisch halten (Fehler tolerieren: DB-Bestand reicht notfalls)
        _melde("kurse", "Kurse: verbinde mit MetaTrader …")
        _melde("kurse")
        try:
            ergebnis = kurse.kurse_holen(settings)
            if ergebnis.get("ok"):
                neu = sum(db.raten_speichern(ergebnis["symbol"], tf, bars)
                          for tf, bars in ergebnis["raten"].items())
                protokoll["kurse"] = {"ok": True, "terminal": ergebnis["terminal"],
                                      "bars": ergebnis["bars"], "neu": neu}
            else:
                protokoll["kurse"] = {"ok": False, "grund": ergebnis.get("grund")}
            _melde("kurse", "Kurse: "
                   + (f"{protokoll['kurse'].get('bars', {}).get('d1', '?')} D1-Bars"
                      if protokoll["kurse"].get("ok") else "DB-Fallback aktiv"))
        except Exception as exc:
            protokoll["kurse"] = {"ok": False, "grund": f"{type(exc).__name__}: {exc}"}

        # 2) Kalender-Adapter (jede Quelle einzeln fehler-tolerant)
        _melde("kalender")
        protokoll["kalender"] = kalender.wochenabruf(db, settings)

        # 3) GVZ-Historie (implizite Volatilität) — Fehler tolerieren
        _melde("gvz")
        try:
            protokoll["gvz"] = gvz_aktualisieren(db, settings)
        except Exception as exc:
            protokoll["gvz"] = {"ok": False, "grund": f"{type(exc).__name__}: {exc}"}

        # 3b) Quant-Feeds (S5): FRED-Realzins/Dollar/VIX, COT, GLD — jede
        # Quelle einzeln fehler-tolerant; ohne sie bleibt Richtung auf R1/R2
        _melde("quant")
        try:
            protokoll["quant"] = quant_adapter.quant_abruf(db, settings)
        except Exception as exc:
            protokoll["quant"] = {"ok": False, "grund": f"{type(exc).__name__}: {exc}"}

        # 4) Matrix aus lokalen Daten (Klima + HAR + Richtung S5)
        _melde("matrix")
        matrix = baue_matrix(db, settings)
        protokoll["matrix"] = {"ok": True, "woche": matrix["woche"],
                               "modell": matrix["modell"]}

        # 5) News-RSS (Delta-Prinzip) + 6) Community — Fehler tolerieren
        _melde("news")
        try:
            protokoll["news"] = news_adapter.sammle_news(db, settings)
        except Exception as exc:
            protokoll["news"] = {"ok": False, "grund": f"{type(exc).__name__}: {exc}"}
        try:
            protokoll["community"] = community_adapter.sammle_community(settings)
        except Exception as exc:
            protokoll["community"] = {"ok": False,
                                      "grund": f"{type(exc).__name__}: {exc}"}

        # 7) LLM-Schicht: Destillation + Fusion (nur mit Key + Budget)
        client = _client_bauen(settings, db)
        if client is None:
            protokoll["llm"] = {"ok": False,
                                "grund": "Kein GLM-Key gesetzt — Matrix bleibt "
                                         "rein statistisch (Einstellungen → GLM)."}
        else:
            _melde("fusion", "KI: News-Destillation läuft (glm-5.3-flash) …")
            news_d = destillation.news_destillieren(db, settings, client, lauf)
            _melde("fusion", "KI: News-Destillation "
                   + (f"ok · {news_d.get('tokens', 0):,} Token".replace(",", ".")
                      if news_d.get("ok") else "fehlgeschlagen (übersprungen)"))
            community_d = None
            if protokoll["community"].get("ok"):
                _melde("fusion", "KI: Community-Destillation läuft …")
                community_d = destillation.community_destillieren(
                    db, settings, client, protokoll["community"], lauf)
            _melde("fusion", "KI: Analytiker-Fusion läuft (glm-5.3, ±Band) …")
            fusion = analytiker.fusioniere(db, settings, client, matrix,
                                           news_d if news_d.get("ok") else None,
                                           community_d if community_d and community_d.get("ok") else None,
                                           lauf)
            _melde("fusion", "KI: Fusion "
                   + (f"ok · Δmax {fusion.get('delta_max_pp', 0):.0f} pp"
                      if fusion.get("ok") else "fehlgeschlagen"))
            protokoll["llm"] = {
                "ok": bool(fusion.get("ok")),
                "news": {k: news_d.get(k) for k in ("ok", "n_items", "erkenntnis",
                                                    "grund", "tokens")},
                "community": {"ok": community_d.get("ok")} if community_d else {"ok": False},
                "fusion": fusion,
                "tokens": (news_d.get("tokens", 0)
                           + (community_d.get("tokens", 0) if community_d else 0)
                           + fusion.get("tokens", 0)),
            }
            if fusion.get("ok"):
                matrix["llm"] = fusion
                # Fusions-Version der Matrix as_of ablegen (Historie für Tor T4)
                db.prognose_speichern(
                    matrix["woche"], matrix["modell"] + " + llm_fusion",
                    json.dumps(matrix, ensure_ascii=False))

                # 8) Wochen-PDF
                _melde("bericht", "Bericht: Wochen-PDF + MT5-Export …")
                try:
                    pfad = pdf_bericht.baue_wochen_pdf(matrix)
                    protokoll["pdf"] = {"ok": True, "datei": str(pfad)}
                    db.schritt(lauf, "reporter", "pdf", ok=True,
                               antwort=str(pfad))
                except Exception as exc:
                    protokoll["pdf"] = {"ok": False,
                                        "grund": f"{type(exc).__name__}: {exc}"}
                    db.schritt(lauf, "reporter", "pdf", ok=False,
                               fehler=str(exc)[:300])
            else:
                protokoll["llm"]["grund"] = fusion.get("grund", "")

        matrix["protokoll_llm"] = {
            "news": {k: v for k, v in protokoll["news"].items() if k != "quellen"},
            "community_ok": protokoll["community"].get("ok", False),
            "llm_ok": protokoll["llm"].get("ok", False),
            "pdf": protokoll["pdf"],
        }

        # 9) MT5-Export (CSV für eigene EAs) — lokal immer, Common-Files wenn da
        try:
            protokoll["export"] = mt5_export.schreibe_export(matrix)
        except Exception as exc:
            protokoll["export"] = {"ok": False,
                                   "grund": f"{type(exc).__name__}: {exc}"}
        db.schritt(
            lauf, "wochenlauf", "gesamt",
            "kurse→kalender→gvz→quant→matrix→news→community→fusion→pdf",
            f"kurse={'ok' if protokoll['kurse'].get('ok') else 'DB-Fallback'} · "
            f"kalender={'ok' if protokoll['kalender'].get('ok') else 'teilweise'} · "
            f"gvz={'ok' if protokoll['gvz'].get('ok') else 'fehlt'} · "
            f"quant={'ok' if protokoll['quant'].get('ok') else 'teilweise'} · "
            f"matrix={matrix['modell']} · "
            f"richtung={'ok' if matrix.get('richtung') else 'aus'} · "
            f"news={protokoll['news'].get('neu', '?')} neu · "
            f"fusion={'ok' if protokoll['llm'].get('ok') else 'aus'} · "
            f"pdf={'ok' if protokoll['pdf'].get('ok') else 'aus'} · "
            f"export={'ok' if protokoll['export'].get('ok') else 'aus'}",
            ok=bool(protokoll["kalender"].get("ok")))
        db.lauf_beenden(lauf, True)
        protokoll["matrix_objekt"] = matrix
        return protokoll
    except Exception as exc:
        db.schritt(lauf, "wochenlauf", "gesamt", ok=False,
                   fehler=f"{type(exc).__name__}: {exc}"[:500])
        db.lauf_beenden(lauf, False)
        raise
