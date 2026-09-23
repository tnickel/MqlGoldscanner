# -*- coding: utf-8 -*-
"""Destillations-Agenten (S4): News + Community → strukturierte Treiber.

Beide laufen auf dem Flash-Modell (Stufe 1): kleine Aufgaben, kleine
Kosten. Die Ausgabe wird hart validiert — kaputtes JSON wird verworfen
und EINMAL wiederholt; danach gilt der Schritt als fehlgeschlagen und
der Wochenlauf läuft ohne dieses Destillat weiter (niemals Teilergebnis
halbbewertet speichern).
"""
from __future__ import annotations

import json
import re
from datetime import date

from ..llm.client import GlmClient, LlmError
from ..llm.prompts import (assert_template_covered, fill_prompt, load_prompt)

FAIL_FAST_SCHWELLE = 3

_ZAUN_RE = re.compile(r"^\s*```[a-zA-Z]*\s*|\s*```\s*$")


def antwort_als_json(antwort: str) -> dict:
    """LLM-Antwort → dict; wirft LlmError bei kaputtem JSON.
    Verzeiht Markdown-Codezäune und leading/trailing Prosa-Kürzel."""
    text = (antwort or "").strip()
    text = _ZAUN_RE.sub("", text)
    anfang = text.find("{")
    ende = text.rfind("}")
    if anfang >= 0 and ende > anfang:
        text = text[anfang:ende + 1]
    try:
        daten = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlmError(f"Antwort ist kein gültiges JSON: {exc}; "
                       f"Anfang: {antwort[:120]!r}") from exc
    if not isinstance(daten, dict):
        raise LlmError("JSON-Antwort ist kein Objekt.")
    return daten


def _chat_mit_failfast(client: GlmClient, prompt: str, system: str,
                       stufe: int, max_tokens: int, meta: dict,
                       parser=None) -> dict:
    """Chat + Validierung mit Fail-Fast: Systemfehler (Verbindung, Drossel,
    Budget) und kaputtes JSON zählen beide als Fehlversuch — nach 3 Versuchen
    ist Schluss (kein Endlos-Retry gegen ein kaputtes Ziel)."""
    versuche = 0
    letzter_fehler: LlmError | None = None
    while versuche < FAIL_FAST_SCHWELLE:
        try:
            antwort = client.chat(prompt, system=system, stufe=stufe,
                                  temperature=0.2, max_tokens=max_tokens,
                                  meta_out=meta)
            if parser is None:
                return antwort
            return parser(antwort)
        except LlmError as exc:
            letzter_fehler = exc
            versuche += 1
    raise letzter_fehler or LlmError("Destillation nach Fehlversuchen abgebrochen.")


def news_destillieren(db, settings: dict, client: GlmClient,
                      lauf_id: int | None = None) -> dict:
    """Offene (ungedestillierte) News-Items → Treiber-Liste.
    Rückgabe: {ok, treiber, gesamt_stimmung, erkenntnis, n_items, tokens}."""
    max_items = int(settings.get("news_max_items_llm", 80))
    items = db.news_offen(limit=max_items)
    if not items:
        return {"ok": True, "leer": True, "treiber": [], "n_items": 0,
                "erkenntnis": "Keine neuen News-Items seit dem letzten Lauf."}

    kompakt = [{
        "titel": i["titel"][:140], "publisher": i["quelle"],
        "datum": (i["veroeffentlicht"] or "")[:10],
        "text": (i["zusammenfassung"] or "")[:180],
        "relevanz": i["gold_relevanz"], "url": i["url"],
    } for i in items]
    template = assert_template_covered(
        load_prompt("news_destillation"),
        ("{items_json}", "{n_items}", "{fenster_tage}", "{heute}"),
        "news_destillation")
    prompt = fill_prompt(template, {
        "{items_json}": json.dumps(kompakt, ensure_ascii=False),
        "{n_items}": str(len(kompakt)),
        "{fenster_tage}": str(settings.get("news_fenster_tage", 7)),
        "{heute}": date.today().isoformat(),
    })
    meta: dict = {}
    fehler = ""
    try:
        daten = _chat_mit_failfast(
            client, prompt,
            system=("Du bist ein präziser Finanz-Destillations-Agent. "
                    "Antworte ausschließlich mit gültigem JSON."),
            stufe=1, max_tokens=16000, meta=meta, parser=antwort_als_json)
        treiber = daten.get("treiber")
        if not isinstance(treiber, list) or not treiber:
            raise LlmError("JSON enthält keine 'treiber'-Liste.")
        db.news_destilliert_markieren([i["id"] for i in items])
        if lauf_id is not None:
            db.schritt(lauf_id, "news_destillation", "llm", prompt=prompt,
                       antwort=json.dumps(daten, ensure_ascii=False)[:20000],
                       modell=meta.get("model", ""), tokens=meta.get("prompt_tokens", 0)
                       + meta.get("completion_tokens", 0),
                       dauer_s=meta.get("dauer_s"), ok=True)
        return {
            "ok": True, "treiber": treiber[:8],
            "gesamt_stimmung": daten.get("gesamt_stimmung", "neutral"),
            "erkenntnis": daten.get("erkenntnis", ""),
            "n_items": len(items), "tokens": meta.get("prompt_tokens", 0)
            + meta.get("completion_tokens", 0), "modell": meta.get("model"),
        }
    except LlmError as exc:
        fehler = str(exc)
    if lauf_id is not None:
        db.schritt(lauf_id, "news_destillation", "llm", prompt=prompt[:8000],
                   antwort="", modell=meta.get("model", ""), ok=False, fehler=fehler)
    return {"ok": False, "grund": fehler, "treiber": [], "n_items": len(items)}


def community_destillieren(db, settings: dict, client: GlmClient,
                           community_daten: dict, lauf_id: int | None = None) -> dict:
    """Deterministische Community-Daten → interpretiertes Konsens-JSON."""
    template = assert_template_covered(
        load_prompt("community_destillation"),
        ("{community_json}", "{heute}"), "community_destillation")
    prompt = fill_prompt(template, {
        "{community_json}": json.dumps(community_daten, ensure_ascii=False),
        "{heute}": date.today().isoformat(),
    })
    meta: dict = {}
    fehler = ""
    try:
        def _pruefen(antwort: str) -> dict:
            daten = antwort_als_json(antwort)
            if "konsens_richtung" not in daten:
                raise LlmError("JSON enthält kein 'konsens_richtung'.")
            return daten
        daten = _chat_mit_failfast(
            client, prompt,
            system=("Du bist ein präziser Sentiment-Analyst. "
                    "Antworte ausschließlich mit gültigem JSON."),
            stufe=1, max_tokens=3000, meta=meta, parser=_pruefen)
        if lauf_id is not None:
            db.schritt(lauf_id, "community_destillation", "llm", prompt=prompt,
                       antwort=json.dumps(daten, ensure_ascii=False)[:20000],
                       modell=meta.get("model", ""),
                       tokens=meta.get("prompt_tokens", 0)
                       + meta.get("completion_tokens", 0),
                       dauer_s=meta.get("dauer_s"), ok=True)
        return {"ok": True, **daten,
                "tokens": meta.get("prompt_tokens", 0)
                + meta.get("completion_tokens", 0), "modell": meta.get("model")}
    except LlmError as exc:
        fehler = str(exc)
    if lauf_id is not None:
        db.schritt(lauf_id, "community_destillation", "llm", prompt=prompt[:8000],
                   antwort="", modell=meta.get("model", ""), ok=False, fehler=fehler)
    return {"ok": False, "grund": fehler}
