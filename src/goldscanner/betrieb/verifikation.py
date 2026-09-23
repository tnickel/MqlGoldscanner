"""Verifikations-Agent (S6): Prognose vs. Realität — Grundlage Track-Record.

Für jeden vergangenen Tag D mit Kursdaten wird die Prognose ausgewertet, die
zum Zeitpunkt D GALT (point-in-time: jüngste gespeicherte Matrix-Version mit
as_of-Datum ≤ D — kein Look-ahead, auch nicht in der Auswertung).

Gemessen wird:
- Bewegungstag: TR(D) > Schwelle B (aus der damaligen Matrix) vs. p_klima /
  p_stat / p_finale (LLM) → Brier/BSS und **LLM-Delta-Nutztwert** (Tor T4)
- Richtung: Close(D) > Close(D−1) vs. p_hoch
- Range-Coverage: TR innerhalb Q10–Q90 der damaligen Prognose

Wichtig: Verifikation eines Tages erst NACH Tagesende (vollständige Kerze).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone


def _tr_je_tag(d1: list[dict]) -> dict[str, dict]:
    """{datum: {tr, close, close_vortag}} aus D1-Bars (UTC-Datum)."""
    aus: dict[str, dict] = {}
    for i, b in enumerate(d1):
        tag = datetime.fromtimestamp(b["time"], tz=timezone.utc).date().isoformat()
        prev_close = d1[i - 1]["close"] if i > 0 else b["open"]
        tr = max(b["high"], b["low"], prev_close) - min(b["high"], b["low"], prev_close)
        aus[tag] = {"tr": tr, "close": b["close"], "close_vortag": prev_close}
    return aus


def _prognose_fuer_tag(db, datum_iso: str) -> dict | None:
    """Jüngste Matrix-Version, deren Woche den Tag enthält und deren as_of
    NICHT nach dem Tag liegt (point-in-time)."""
    with db._lock:  # noqa: SLK001 — bewusst direkter Zugriff im eigenen Paket
        zeilen = db._con.execute(
            "SELECT as_of, woche, inhalt FROM prognose_versionen ORDER BY id DESC "
            "LIMIT 400").fetchall()
    for zeile in zeilen:
        try:
            montag = date.fromisoformat(zeile["woche"])
        except ValueError:
            continue
        if not (montag <= date.fromisoformat(datum_iso) <= montag + timedelta(days=6)):
            continue
        if zeile["as_of"][:10] > datum_iso:
            continue
        try:
            matrix = json.loads(zeile["inhalt"])
        except json.JSONDecodeError:
            continue
        for tag in matrix.get("tage", []):
            if tag.get("datum") == datum_iso:
                return {"tag": tag, "llm": matrix.get("llm") or {},
                        "as_of": zeile["as_of"], "woche": zeile["woche"]}
    return None


def nachziehen(db, settings: dict, bis_vor_tagen: int = 1,
               seit_tagen: int = 120, heute: date | None = None) -> dict:
    """Alle bewertbaren Tage seit `seit_tagen` verifizieren (heute selbst
    erst morgen — Kerze muss vollständig sein). Rückgabe: Protokoll."""
    symbol = settings.get("mt5_symbol", "XAUUSD")
    d1 = db.raten_laden(symbol, "d1")
    if len(d1) < 2:
        return {"ok": False, "grund": "keine Kursdaten"}
    kurse = _tr_je_tag(d1)
    heute = heute or date.today()
    von = (heute - timedelta(days=seit_tagen)).isoformat()
    bis = (heute - timedelta(days=bis_vor_tagen)).isoformat()
    neu = 0
    ohne_prognose = 0
    for datum_iso, k in sorted(kurse.items()):
        if not (von <= datum_iso <= bis) or datum_iso >= heute.isoformat():
            continue
        prognose = _prognose_fuer_tag(db, datum_iso)
        if not prognose:
            ohne_prognose += 1
            continue
        tag, llm = prognose["tag"], prognose["llm"]
        fusion_je_tag = {t.get("datum"): t for t in llm.get("tage", [])}
        f = fusion_je_tag.get(datum_iso) or {}
        schwelle = tag.get("schwelle_usd")
        eingetreten = None
        if schwelle:
            eingetreten = 1 if k["tr"] > schwelle else 0
        richtung_p = ((tag.get("richtung") or {}).get("p_hoch"))
        richtung_ein = 1 if k["close"] > k["close_vortag"] else 0
        q10, q90 = tag.get("q10_usd"), tag.get("q90_usd")
        in_band = (1 if (q10 is not None and q90 is not None
                         and q10 <= k["tr"] <= q90) else 0
                   ) if (q10 is not None and q90 is not None) else None
        db.verifikation_speichern({
            "datum": datum_iso, "woche": prognose["woche"],
            "as_of_prognose": prognose["as_of"],
            "p_klima": tag.get("p_klima"),
            "p_stat": tag.get("p_stat"),
            "p_finale": (f.get("p_finale_pct") / 100.0
                         if f.get("p_finale_pct") is not None else None),
            "eingetreten": eingetreten,
            "richtung_p_hoch": richtung_p,
            "richtung_eingetreten": richtung_ein,
            "tr_usd": round(k["tr"], 2), "schwelle_usd": schwelle,
            "q10_usd": q10, "q90_usd": q90, "in_band": in_band,
        })
        neu += 1
    return {"ok": True, "neu": neu, "ohne_prognose": ohne_prognose}


def kennzahlen(zeilen: list[dict]) -> dict:
    """Aggregierte Track-Record-Kennzahlen aus verifikationen-Zeilen."""
    def _brier(p_feld: str) -> tuple[float | None, int]:
        paare = [(z[p_feld], z["eingetreten"]) for z in zeilen
                 if z.get(p_feld) is not None and z.get("eingetreten") is not None]
        if not paare:
            return None, 0
        return sum((p - y) ** 2 for p, y in paare) / len(paare), len(paare)

    brier_klima, n_k = _brier("p_klima")
    brier_stat, n_s = _brier("p_stat")
    brier_finale, n_f = _brier("p_finale")
    bss = (1 - brier_stat / brier_klima
           if (brier_stat is not None and brier_klima) else None)
    llm_delta = (brier_stat - brier_finale
                 if (brier_stat is not None and brier_finale is not None) else None)

    bins: list[dict] = []
    for anfang, ende in ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)):
        gruppe = [z for z in zeilen if z.get("p_finale") is not None
                  and z.get("eingetreten") is not None
                  and anfang <= z["p_finale"] < ende]
        if gruppe:
            bins.append({
                "von": anfang, "bis": min(ende, 1.0), "n": len(gruppe),
                "p_gesagt": sum(z["p_finale"] for z in gruppe) / len(gruppe),
                "treffer_rate": sum(z["eingetreten"] for z in gruppe) / len(gruppe)})

    richtungen = [z for z in zeilen
                  if z.get("richtung_p_hoch") is not None
                  and z.get("richtung_eingetreten") is not None]
    richtungstreffer = (sum(1 for z in richtungen
                            if (z["richtung_p_hoch"] >= 0.5) ==
                            bool(z["richtung_eingetreten"])) / len(richtungen)
                        if richtungen else None)
    bänder = [z for z in zeilen if z.get("in_band") is not None]
    coverage = (sum(z["in_band"] for z in bänder) / len(bänder)) if bänder else None
    return {
        "n_tage": len(zeilen), "brier_klima": brier_klima, "brier_stat": brier_stat,
        "brier_finale": brier_finale, "bss": bss, "llm_delta_nutzt": llm_delta,
        "n_bewegung": n_k, "reliability": bins,
        "richtungstreffer": richtungstreffer, "n_richtung": len(richtungen),
        "range_coverage": coverage, "n_band": len(bänder),
    }
