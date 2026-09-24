"""Wochen-Auswertung (S6-Erweiterung): Prognose-Score 0-100 + LLM-Review.

Läuft im Daemon direkt nach der Verifikation (Samstag 09:00) und bewertet
die abgelaufene Handelswoche:

1. Jeder verifizierte Tag bekommt eine **Tagesnote 0-100** aus drei
   Bausteinen (Bewegung 40 / Richtung 40 / Band 20). Fehlende Bausteine
   (z. B. keine Richtung prognostiziert) werden wegnormiert — die Note
   bleibt vergleichbar.
2. **Wochen-Score** = Ø der Tagesnoten. Dazu Teil-Scores je Baustein und
   der Trend zur Vorwoche.
3. **LLM-Review** (GLM, 1 Aufruf/Woche): Fazit in Laiensprache + maximal
   3 Lessons. Die Lessons fließen in die Fusion des Sonntagslaufs
   (analytiker_fusion.md, Slot {lessons}) — das System lernt wöchentlich.

Die Zahl kommt bewusst aus der Formel (reproduzierbar), das LLM liefert
nur die Erklärung dazu. Ohne GLM-Key gibt es den Score trotzdem — das
Review wird dann einfach nachgereicht, sobald wieder ein Key da ist.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from ..agenten.destillation import _chat_mit_failfast, antwort_als_json
from ..llm.client import GlmClient, LlmError
from ..llm.prompts import assert_template_covered, fill_prompt, load_prompt

_MAX_BEWEGUNG = 40.0
_MAX_RICHTUNG = 40.0
_MAX_BAND = 20.0
_WOCHENTAGE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
               "Samstag", "Sonntag")
_STIMMUNGEN = ("gut", "durchschnittlich", "schwach")


def _baustein_wkeit(p: float | None, eingetreten, max_punkte: float) -> float | None:
    """Punkte für einen Wahrscheinlichkeits-Baustein: p vs. 0/1-Realität.

    1−2·(p−y)²  — sicheres Richtigtreffen gibt volle Punktzahl, sicheres
    Falschurteil 0, eine reine 50/50-Raterei die Hälfte."""
    if p is None or eingetreten is None:
        return None
    p = float(p)
    if not 0.0 <= p <= 1.0:
        return None
    y = float(eingetreten)
    return max_punkte * max(0.0, 1.0 - 2.0 * (p - y) ** 2)


def tagesnote(zeile: dict) -> dict | None:
    """Tagesnote 0-100 aus einer verifikationen-Zeile.

    Bewegung wird auf der höchsten verfügbaren Ebene bewertet, die zur
    Prognosezeit galt (P_finale → P_stat → P_klima). Fehlende Bausteine
    entfallen und werden wegnormiert; None = Tag nicht bewertbar."""
    p = zeile.get("p_finale")
    p_ebene = "p_finale"
    if p is None:
        p = zeile.get("p_stat")
        p_ebene = "p_stat"
    if p is None:
        p = zeile.get("p_klima")
        p_ebene = "p_klima"

    teile: dict[str, float] = {}
    bewegung = _baustein_wkeit(p, zeile.get("eingetreten"), _MAX_BEWEGUNG)
    if bewegung is not None:
        teile["bewegung"] = bewegung
    richtung = _baustein_wkeit(zeile.get("richtung_p_hoch"),
                               zeile.get("richtung_eingetreten"), _MAX_RICHTUNG)
    if richtung is not None:
        teile["richtung"] = richtung
    if zeile.get("in_band") is not None:
        teile["band"] = _MAX_BAND if zeile["in_band"] else 0.0
    if not teile:
        return None

    maxima = {"bewegung": _MAX_BEWEGUNG, "richtung": _MAX_RICHTUNG, "band": _MAX_BAND}
    summe = sum(teile.values())
    max_summe = sum(maxima[k] for k in teile)
    return {"note": round(100.0 * summe / max_summe),
            "teile": {k: round(v, 1) for k, v in teile.items()},
            "p_ebene": p_ebene if bewegung is not None else None,
            "p_pct": round(p * 100) if (p is not None and bewegung is not None) else None}


def _teil_score(tage: list[dict], name: str) -> float | None:
    """Baustein-Ø auf 0-100 normiert (nur über Tage mit diesem Baustein)."""
    maxima = {"bewegung": _MAX_BEWEGUNG, "richtung": _MAX_RICHTUNG, "band": _MAX_BAND}
    werte = [t["teile"][name] for t in tage if name in t["teile"]]
    if not werte:
        return None
    return round(100.0 * sum(werte) / (len(werte) * maxima[name]))


def wochenbericht(db, woche: str) -> dict:
    """Bericht für eine Woche (woche = Montag-ISO, wie in verifikationen)."""
    zeilen = sorted((z for z in db.verifikationen() if z.get("woche") == woche),
                    key=lambda z: z["datum"])
    tage: list[dict] = []
    for z in zeilen:
        tn = tagesnote(z)
        if tn is None:
            continue
        richtung_real = z.get("richtung_eingetreten")
        tage.append({
            "datum": z["datum"],
            "wochentag": _WOCHENTAGE[date.fromisoformat(z["datum"]).weekday()],
            "note": tn["note"], "teile": tn["teile"],
            "p_ebene": tn["p_ebene"], "p_bewegung_pct": tn["p_pct"],
            "bewegung_real": z.get("eingetreten"),
            "p_richtung_hoch_pct": (round(z["richtung_p_hoch"] * 100)
                                    if z.get("richtung_p_hoch") is not None else None),
            "richtung_real": richtung_real,
            "tr_usd": z.get("tr_usd"), "schwelle_usd": z.get("schwelle_usd"),
            "in_band": z.get("in_band"),
        })
    if not tage:
        return {"ok": False, "woche": woche, "grund": "keine bewertbaren Tage"}
    return {
        "ok": True, "woche": woche, "n_tage": len(tage), "tage": tage,
        "score": round(sum(t["note"] for t in tage) / len(tage)),
        "teilscores": {name: _teil_score(tage, name)
                       for name in ("bewegung", "richtung", "band")},
    }


def _tage_kompakt(tage: list[dict]) -> list[dict]:
    """Tagesnoten für den LLM-Prompt — knappe, selbsterklärende Felder."""
    aus = []
    for t in tage:
        aus.append({
            "datum": t["datum"], "wochentag": t["wochentag"], "note": t["note"],
            "p_bewegung_pct": t["p_bewegung_pct"], "p_ebene": t["p_ebene"],
            "bewegung_real": ("ja" if t["bewegung_real"] == 1 else "nein"),
            "p_richtung_hoch_pct": t["p_richtung_hoch_pct"],
            "richtung_real": ("hoch" if t["richtung_real"] == 1 else "runter"),
            "tr_usd": t["tr_usd"], "schwelle_usd": t["schwelle_usd"],
            "band": ("getroffen" if t["in_band"] == 1 else
                     "verfehlt" if t["in_band"] == 0 else None),
        })
    return aus


def gesamt_score(db) -> dict:
    """Ø-Tagesnote über alle Verifikationen (für den Review-Kontext)."""
    noten = [tn["note"] for z in db.verifikationen()
             if (tn := tagesnote(z)) is not None]
    if not noten:
        return {"n_tage": 0, "score": None}
    return {"n_tage": len(noten), "score": round(sum(noten) / len(noten))}


def review_erzeugen(db, settings: dict, client: GlmClient, bericht: dict,
                    lauf_id: int | None = None) -> dict:
    """LLM-Review zu einem Wochenbericht. Wirft nie — immer ein Protokoll."""
    woche = bericht["woche"]
    vorwoche_iso = (date.fromisoformat(woche) - timedelta(days=7)).isoformat()
    vorwoche = db.wochenbericht(vorwoche_iso)
    gesamt = gesamt_score(db)
    ts = bericht.get("teilscores") or {}

    template = assert_template_covered(
        load_prompt("auswertung_review"),
        ("{tage_json}", "{score}", "{teil_bewegung}", "{teil_richtung}",
         "{teil_band}", "{vorwoche}", "{n_gesamt}", "{gesamt}"),
        "auswertung_review")
    prompt = fill_prompt(template, {
        "{tage_json}": json.dumps(_tage_kompakt(bericht["tage"]),
                                  ensure_ascii=False),
        "{score}": str(bericht["score"]),
        "{teil_bewegung}": _zahl(ts.get("bewegung")),
        "{teil_richtung}": _zahl(ts.get("richtung")),
        "{teil_band}": _zahl(ts.get("band")),
        "{vorwoche}": (f"{vorwoche['score']}/100" if vorwoche else "keine"),
        "{n_gesamt}": str(gesamt["n_tage"]),
        "{gesamt}": _zahl(gesamt["score"]),
    })
    meta: dict = {}
    fehler = ""
    try:
        daten = _chat_mit_failfast(
            client, prompt,
            system=("Du bist ein nüchterner Auswertungs-Analyst. Du bist "
                    "ehrlich auch bei schwachen Ergebnissen und antwortest "
                    "ausschließlich mit gültigem JSON."),
            stufe=1, max_tokens=8000, meta=meta, parser=antwort_als_json)
        fazit = str(daten.get("fazit") or "").strip()
        if len(fazit) < 30:
            raise LlmError("Fazit fehlt oder ist zu kurz.")
        lessons = [str(lesson).strip()[:250]
                   for lesson in (daten.get("lessons") or [])[:3]
                   if str(lesson).strip()]
        stimmung = str(daten.get("stimmung") or "").lower()
        if stimmung not in _STIMMUNGEN:
            stimmung = "durchschnittlich"
        review = {
            "ok": True, "fazit": fazit[:1200], "lessons": lessons,
            "stimmung": stimmung, "modell": meta.get("model"),
            "tokens": meta.get("prompt_tokens", 0) + meta.get("completion_tokens", 0),
        }
        if lauf_id is not None:
            db.schritt(lauf_id, "auswertung_review", "llm", prompt=prompt,
                       antwort=json.dumps(review, ensure_ascii=False)[:20000],
                       modell=meta.get("model", ""), tokens=review["tokens"],
                       dauer_s=meta.get("dauer_s"), ok=True)
        return review
    except LlmError as exc:
        fehler = str(exc)
        if lauf_id is not None:
            db.schritt(lauf_id, "auswertung_review", "llm", prompt=prompt[:8000],
                       antwort="", modell=meta.get("model", ""), ok=False,
                       fehler=fehler)
        return {"ok": False, "grund": fehler}


def _zahl(wert) -> str:
    return "–" if wert is None else str(int(wert))


def laeuft(db, settings: dict, heute: date | None = None) -> dict:
    """Komplette Wochen-Auswertung (Daemon Samstag 09:00 / UI-Button):

    - Bericht für jede noch nicht berechnete Woche (Backfill, ohne Review)
    - Review für die jüngste Woche, wenn ein GLM-Key vorhanden ist
    Rückgabe: Protokoll (wirft nie)."""
    heute = heute or date.today()
    lauf = db.lauf_starten("auswertung", "Wochen-Auswertung: Score + Review")
    protokoll: dict = {"ok": False}
    try:
        alle = {z["woche"] for z in db.verifikationen()}
        vorhanden = {b["woche"] for b in db.wochenberichte()}
        neu = 0
        letzte: dict | None = None
        for woche in sorted(alle - vorhanden):
            bericht = wochenbericht(db, woche)
            if bericht.get("ok"):
                db.wochenbericht_speichern(bericht)
                neu += 1
                letzte = bericht
        # Jüngste Woche insgesamt (auch wenn der Bericht schon da war) —
        # samstags ist das die gerade abgelaufene Handelswoche. Neu
        # berechnet statt aus der DB gelesen: review_erzeugen braucht die
        # Berichtsform (ok/tage/score).
        woche_aktuell = (heute - timedelta(days=heute.weekday())).isoformat()
        jugendlich = db.wochenberichte()
        if jugendlich:
            letzte = wochenbericht(db, jugendlich[-1]["woche"]) or letzte
        review: dict = {"ok": False, "grund": "keine bewertbare Woche"}
        if letzte is not None and letzte.get("ok"):
            from ..wochenlauf import _client_bauen    # noqa: SLK001 — eigenes Paket
            client = _client_bauen(settings, db)
            if client is None:
                review = {"ok": False,
                          "grund": "Kein GLM-Key — Score gespeichert, Review "
                                   "wartet auf den nächsten Lauf mit Key."}
            elif letzte["woche"] >= woche_aktuell:
                review = review_erzeugen(db, settings, client, letzte, lauf)
                if review.get("ok"):
                    db.wochenbericht_review_speichern(letzte["woche"], review)
            else:
                review = {"ok": False,
                          "grund": f"Jüngste Woche ({letzte['woche']}) liegt "
                                   f"vor der aktuellen ({woche_aktuell}) — "
                                   "kein Review nachgeholt."}
        protokoll = {
            "ok": True, "neu": neu,
            "letzte_woche": (letzte or {}).get("woche"),
            "score_letzte": (letzte or {}).get("score"),
            "review_ok": bool(review.get("ok")),
            "review_grund": review.get("grund", ""),
            "tokens": review.get("tokens", 0),
        }
        db.schritt(lauf, "auswertung", "gesamt",
                   "wochenberichte+review",
                   f"neu={neu} · score_letzte={protokoll['score_letzte']} · "
                   f"review={'ok' if protokoll['review_ok'] else 'aus'}",
                   ok=True)
        db.lauf_beenden(lauf, True)
    except Exception as exc:                     # nie den Daemon killen
        db.schritt(lauf, "auswertung", "gesamt", ok=False,
                   fehler=f"{type(exc).__name__}: {exc}"[:500])
        db.lauf_beenden(lauf, False)
        protokoll = {"ok": False, "grund": f"{type(exc).__name__}: {exc}"}
    return protokoll
