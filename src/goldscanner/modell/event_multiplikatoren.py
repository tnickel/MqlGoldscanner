"""Gemessene Event-Multiplikatoren (S3): Was machen NFP-/FOMC-/GC-Termine
historisch wirklich mit der Tages-Range? Reiner Code — das LLM zitiert nur."""
from __future__ import annotations

_EVENTS = ["nfp", "fomc", "gold_termin"]


def multiplikatoren(zeilen: list[dict]) -> list[dict]:
    """Ø TR_rel an Event-Tagen ÷ Ø TR_rel an Normaltagen + Bewegungs-Anteile."""
    ergebnisse = []
    if not zeilen:
        return ergebnisse
    normal = [z["tr_rel"] for z in zeilen if not any(z.get(e) for e in _EVENTS)]
    normal_bewegung = [z for z in zeilen if not any(z.get(e) for e in _EVENTS)
                       and z.get("bewegung") is not None]
    basis = sum(normal) / len(normal) if normal else None
    basis_p = (sum(1 for z in normal_bewegung if z["bewegung"]) / len(normal_bewegung)
               if normal_bewegung else None)
    for event in _EVENTS:
        tage = [z for z in zeilen if z.get(event) and z.get("tr_rel") is not None]
        if not tage or not basis:
            continue
        mittel = sum(z["tr_rel"] for z in tage) / len(tage)
        bewegungstage = [z for z in tage if z.get("bewegung") is not None]
        p_event = (sum(1 for z in bewegungstage if z["bewegung"]) / len(bewegungstage)
                   if bewegungstage else None)
        ergebnisse.append({
            "event": event,
            "n": len(tage),
            "tr_rel_mittel": round(mittel, 5),
            "multiplikator": round(mittel / basis, 3),
            "p_bewegung_event": round(p_event, 3) if p_event is not None else None,
            "p_bewegung_normal": round(basis_p, 3) if basis_p is not None else None,
            "lift_pp": round((p_event - basis_p) * 100, 1)
                       if p_event is not None and basis_p is not None else None,
        })
    return ergebnisse
