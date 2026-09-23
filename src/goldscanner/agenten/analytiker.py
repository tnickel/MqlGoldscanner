"""Analytiker-Fusion (S4): P_stat (HAR) + Events + Destillate → P_finale.

Band-Disziplin (Konzept §6, Tor T4): Das LLM darf die Modellwahrschein-
lichkeit je Tag nur um ± llm_band_pp (Default 10) Prozentpunkte verschieben
und muss jede Abweichung > 1 pp begründen. Verstöße werden vom SYSTEM
abgewiesen — der Tag fällt auf die Modellwahrscheinlichkeit zurück, der
Verstoß wird protokolliert (fusionen.verstoesse) und ist später die
Grundlage für die Tor-T4-Bewertung („bringt das LLM-Delta etwas?").

Ungültige Antworten (kein JSON, fehlende Tage, absurdere Werte) werden
komplett verworfen — nie gespeichert, nie angezeigt.
"""
from __future__ import annotations

import json
from datetime import date

from ..llm.client import GlmClient, LlmError
from ..llm.prompts import assert_template_covered, fill_prompt, load_prompt
from .destillation import _chat_mit_failfast, antwort_als_json

RICHTUNGEN = ("hoch", "runter", "neutral")
_KONFIDENZ = ("niedrig", "mittel", "hoch")


def _matrix_kompakt(matrix: dict) -> list[dict]:
    """Nur die Felder, die der Analytiker braucht — keine Internas."""
    tage = []
    for t in matrix.get("tage", []):
        basis = t.get("p_stat")
        basis_quelle = "p_stat"
        if basis is None:
            basis = t.get("p_klima")
            basis_quelle = "p_klima"
        tage.append({
            "datum": t["datum"], "wochentag": t["wochentag"],
            "basis_pct": round(basis * 100, 1) if basis is not None else None,
            "basis": basis_quelle,
            "p_klima_pct": round(t["p_klima"] * 100, 1) if t.get("p_klima") is not None else None,
            "schwelle_usd": t.get("schwelle_usd"),
            "q10_usd": t.get("q10_usd"), "q50_usd": t.get("q50_usd"),
            "q90_usd": t.get("q90_usd"),
            "events": [{"zeit": e["zeit"], "titel": e["titel"], "klasse": e.get("klasse")}
                       for e in t.get("top_events", [])],
        })
    return tage


def _tag_pruefen(tag: dict, basis_pct: float, band_pp: float) -> tuple[dict, list[str]]:
    """Ein LLM-Tag validieren + Band-Disziplin durchsetzen.
    Rückgabe: (geprüfter Tag, Verstöße)."""
    verstoesse: list[str] = []
    p_finale = tag.get("p_finale_pct")
    begruendung = str(tag.get("begruendung") or "").strip()
    try:
        p_finale = float(p_finale)
    except (TypeError, ValueError):
        p_finale = None
    if p_finale is None or not 0.0 <= p_finale <= 100.0:
        return ({"datum": tag.get("datum"), "p_finale_pct": basis_pct,
                 "neutralisiert": "ungültiger Wert", "begruendung": begruendung,
                 "richtung": "neutral", "konfidenz": "niedrig", "treiber": []},
                [f"{tag.get('datum')}: p_finale fehlt/ungültig → Basis"])

    abweichung = p_finale - basis_pct
    if abs(abweichung) > band_pp + 0.5:          # 0,5 pp Rundungsgnade
        verstoesse.append(
            f"{tag.get('datum')}: {p_finale:.1f} % verletzt Band "
            f"(±{band_pp:.0f} um {basis_pct:.1f} %) → zurück auf Basis")
        p_finale = basis_pct
        abweichung = 0.0
    elif abs(abweichung) > 1.0 and len(begruendung) < 15:
        verstoesse.append(
            f"{tag.get('datum')}: Abweichung ohne Begründung "
            f"({abweichung:+.1f} pp) → zurück auf Basis")
        p_finale = basis_pct
        abweichung = 0.0

    richtung = str(tag.get("richtung") or "neutral").lower()
    if richtung not in RICHTUNGEN:
        richtung = "neutral"
    konfidenz = str(tag.get("konfidenz") or "niedrig").lower()
    if konfidenz not in _KONFIDENZ:
        konfidenz = "niedrig"

    treiber = []
    for tr in (tag.get("treiber") or [])[:4]:
        if not isinstance(tr, dict) or not tr.get("name"):
            continue
        try:
            einfluss = float(tr.get("einfluss_pp"))
        except (TypeError, ValueError):
            einfluss = 0.0
        treiber.append({
            "name": str(tr["name"])[:120],
            "einfluss_pp": max(-band_pp, min(band_pp, einfluss)),
            "richtung": str(tr.get("richtung") or "neutral").lower(),
            "quelle": str(tr.get("quelle") or "news")[:40],
        })
    return ({"datum": tag.get("datum"), "p_finale_pct": round(p_finale, 1),
             "abweichung_pp": round(abweichung, 1), "begruendung": begruendung,
             "richtung": richtung, "konfidenz": konfidenz, "treiber": treiber},
            verstoesse)


def fusioniere(db, settings: dict, client: GlmClient, matrix: dict,
               news_destillat: dict | None, community_destillat: dict | None,
               lauf_id: int | None = None) -> dict:
    """Fusion bauen, validieren, in DB legen. Wirft nie — Rückgabe immer
    ein Protokoll mit ok=True/False."""
    tage_kompakt = _matrix_kompakt(matrix)
    if not tage_kompakt or all(t["basis_pct"] is None for t in tage_kompakt):
        return {"ok": False, "grund": "Matrix ohne Wahrscheinlichkeiten — "
                                      "kein Anker für die Fusion."}
    band_pp = float(settings.get("llm_band_pp", 10.0))

    template = assert_template_covered(
        load_prompt("analytiker_fusion"),
        ("{matrix_json}", "{news_json}", "{community_json}", "{heute}", "{band_pp}"),
        "analytiker_fusion")
    prompt = fill_prompt(template, {
        "{matrix_json}": json.dumps(tage_kompakt, ensure_ascii=False),
        "{news_json}": json.dumps(
            (news_destillat or {}).get("treiber", [])[:8], ensure_ascii=False),
        "{community_json}": json.dumps(
            {k: v for k, v in (community_destillat or {}).items()
             if k in ("konsens_richtung", "einigkeit", "wichtige_levels",
                      "retail_bias_warnung", "volatilitaet_effekt", "erklaerung")},
            ensure_ascii=False),
        "{heute}": date.today().isoformat(),
        "{band_pp}": f"{band_pp:.0f}",
    })
    meta: dict = {}
    fehler = ""
    try:
        daten = _chat_mit_failfast(
            client, prompt,
            system=("Du bist ein disziplinierter Gold-Analyst. Du hältst das "
                    "±-Band um die Modellwahrscheinlichkeit strikt ein und "
                    "antwortest ausschließlich mit gültigem JSON."),
            stufe=2, max_tokens=12000, meta=meta, parser=antwort_als_json)
        roh_tage = daten.get("tage")
        if not isinstance(roh_tage, list):
            raise LlmError("JSON enthält keine 'tage'-Liste.")
        nach_datum = {t.get("datum"): t for t in roh_tage}
        fehlend = [t["datum"] for t in tage_kompakt if t["datum"] not in nach_datum]
        if len(fehlend) == len(tage_kompakt):
            raise LlmError("Antwort enthält keines der Matrix-Daten.")
    except LlmError as exc:
        fehler = str(exc)
        if lauf_id is not None:
            db.schritt(lauf_id, "analytiker_fusion", "llm", prompt=prompt[:8000],
                       antwort="", modell=meta.get("model", ""), ok=False, fehler=fehler)
        return {"ok": False, "grund": fehler}

    # Band-Disziplin + Validierung je Tag
    fusion_tage: list[dict] = []
    verstoesse: list[str] = list(fehlend and
                                 [f"{d}: Tag fehlt in Antwort → Basis" for d in fehlend])
    for t in tage_kompakt:
        if t["datum"] in nach_datum:
            geprueft, tag_verstoesse = _tag_pruefen(
                nach_datum[t["datum"]], t["basis_pct"], band_pp)
            verstoesse.extend(tag_verstoesse)
        else:
            geprueft = {"datum": t["datum"], "p_finale_pct": t["basis_pct"],
                        "abweichung_pp": 0.0, "begruendung": "",
                        "richtung": "neutral", "konfidenz": "niedrig",
                        "treiber": []}
        geprueft["basis_pct"] = t["basis_pct"]
        geprueft["basis"] = t["basis"]
        fusion_tage.append(geprueft)

    delta_max = max((abs(t["abweichung_pp"]) for t in fusion_tage), default=0.0)
    ergebnis = {
        "ok": True, "modell": meta.get("model"),
        "band_pp": band_pp,
        "zusammenfassung": str(daten.get("zusammenfassung") or "")[:2000],
        "risiken": [str(r)[:300] for r in (daten.get("risiken") or [])[:5]],
        "kontra_hinweis": str(daten.get("kontra_hinweis") or "")[:500],
        "tage": fusion_tage,
        "verstoesse": verstoesse,
        "delta_max_pp": round(delta_max, 1),
        "tokens": meta.get("prompt_tokens", 0) + meta.get("completion_tokens", 0),
    }
    if lauf_id is not None:
        db.schritt(lauf_id, "analytiker_fusion", "llm", prompt=prompt,
                   antwort=json.dumps(ergebnis, ensure_ascii=False)[:30000],
                   modell=meta.get("model", ""), tokens=ergebnis["tokens"],
                   dauer_s=meta.get("dauer_s"), ok=True,
                   fehler="; ".join(verstoesse)[:500])
    db.fusion_speichern(matrix["woche"], meta.get("model") or "?", band_pp,
                        json.dumps(ergebnis, ensure_ascii=False), True,
                        ergebnis["delta_max_pp"], len(verstoesse))
    _delta_meldung(db, settings, matrix["woche"], fusion_tage)
    return ergebnis


def _delta_meldung(db, settings: dict, woche: str, fusion_tage: list[dict]) -> None:
    """Reporter: Prognoseänderung ≥ llm_melde_schwelle_pp vs. letzter
    gespeicherter Fusion → Meldung ins Postfach."""
    schwelle = float(settings.get("llm_melde_schwelle_pp", 10.0))
    letzte = db.fusion_vorherige(woche)
    if letzte is None:
        return
    try:
        alt = {t["datum"]: t["p_finale_pct"]
               for t in json.loads(letzte["inhalt"]).get("tage", [])}
    except (json.JSONDecodeError, KeyError, TypeError):
        return
    for t in fusion_tage:
        if t["datum"] in alt and alt[t["datum"]] is not None:
            delta = t["p_finale_pct"] - float(alt[t["datum"]])
            if abs(delta) >= schwelle:
                db.meldung_speichern(
                    woche, "prognose_geaendert",
                    f"{t['datum']}: P_finale {alt[t['datum']]:.0f} % → "
                    f"{t['p_finale_pct']:.0f} % ({delta:+.1f} pp) — "
                    f"{t['begruendung'][:150]}")
