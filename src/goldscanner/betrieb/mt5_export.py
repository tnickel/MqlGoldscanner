"""MT5-Export (S6): Prognosen als CSV für eigene EAs.

Ziel: der Common-Files-Ordner (FILE_COMMON) aller MT5-Terminals — dort kann
ein EA die Datei mit FileOpen(..., FILE_COMMON|FILE_READ) lesen und z. B.
als Handelsfilter (P < Schwelle → kein Trade) oder Lot-Größen-Steuerung
nutzen. Format bewusst simpel (Semikolon, Punkt-Dezimal, ISO-Datum):

datum;wochentag;p_bewegung;p_stat;p_klima;richtung_p_hoch;richtung_symbol;q10_usd;q50_usd;q90_usd;schwelle_usd;warnstufe

p-Werte in Prozent (0–100). Zusätzlich liegt immer eine lokale Kopie unter
data/exports/ — auch ohne laufendes Terminal nachvollziehbar.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .. import config

DATEINAME = "goldscanner_prognose.csv"
KOPF = ("datum;wochentag;p_bewegung;p_stat;p_klima;richtung_p_hoch;"
        "richtung_symbol;q10_usd;q50_usd;q90_usd;schwelle_usd;warnstufe")


def _zeilen(matrix: dict) -> list[str]:
    fusion_je_tag = {t.get("datum"): t for t in (matrix.get("llm") or {}).get("tage", [])}
    aus = []
    for t in matrix.get("tage", []):
        f = fusion_je_tag.get(t["datum"]) or {}
        p_stat = (t.get("p_stat") * 100 if t.get("p_stat") is not None else "")
        p_klima = (t.get("p_klima") * 100 if t.get("p_klima") is not None else "")
        p_finale = f.get("p_finale_pct", "")
        if p_stat != "" and p_finale == "":
            p_finale = round(p_stat, 1)
        richtung = t.get("richtung") or {}
        aus.append(";".join(str(x) for x in [
            t["datum"], t["wochentag"], p_finale, p_stat, p_klima,
            (round(richtung["p_hoch"] * 100, 1)
             if richtung.get("p_hoch") is not None else ""),
            richtung.get("symbol", ""),
            t.get("q10_usd", ""), t.get("q50_usd", ""), t.get("q90_usd", ""),
            t.get("schwelle_usd", ""), t.get("warnstufe", ""),
        ]))
    return aus


def schreibe_export(matrix: dict) -> dict:
    """Schreibt Common-Files-Kopie (falls Terminal-Pfad existiert) und immer
    die lokale Kopie. Rückgabe: {ok, dateien: [pfad, ...]}."""
    if not matrix.get("tage"):
        return {"ok": False, "grund": "Matrix ohne Tage"}
    inhalt = "\n".join([KOPF] + _zeilen(matrix)) + "\n"
    ziel_dateien: list[Path] = []

    lokal = config.DATA_DIR / "exports" / DATEINAME
    lokal.parent.mkdir(parents=True, exist_ok=True)
    lokal.write_text(inhalt, encoding="utf-8")
    ziel_dateien.append(lokal)

    from ..adapter.actuals import mt5_csv_pfade
    for kandidat in mt5_csv_pfade():
        ordner = kandidat.parent          # …/Terminal/Common/Files
        try:
            ordner.mkdir(parents=True, exist_ok=True)
            (ordner / DATEINAME).write_text(inhalt, encoding="utf-8")
            ziel_dateien.append(ordner / DATEINAME)
            break                          # ein Common-Ordner genügt
        except OSError:
            continue
    return {"ok": True, "dateien": [str(p) for p in ziel_dateien],
            "erzeugt_am": datetime.now().isoformat(timespec="seconds")}


def lese_export(pfad: Path | None = None) -> list[dict]:
    """Für Tests/EA-Doku: CSV wieder einlesen."""
    pfad = pfad or (config.DATA_DIR / "exports" / DATEINAME)
    zeilen: list[dict] = []
    text = pfad.read_text(encoding="utf-8").strip().splitlines()
    felder = text[0].split(";")
    for zeile in text[1:]:
        werte = zeile.split(";")
        zeilen.append(dict(zip(felder, werte)))
    return zeilen
