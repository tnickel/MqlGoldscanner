"""Session-/Gap-Agent (S5): Intraday-Revision der heutigen Bewegungs-P.

Asia-Range bis 08:00 MEZ + Wochenend-Gap aus den H1-Bars (MT5-Serverzeit ≈
EET/Berlin+1 historisch schwankend — wir gruppieren über UTC-Zeitstempel und
rechnen auf Berlin). Die Revision ist rein empirisch: Aus ~200 Tagen H1-
Historie wird je Tag die Range bis 08:00 Berlin der vollen Tages-Range
gegenübergestellt. Tage mit ähnlicher Asia-Range liefern die bedingte
Wahrscheinlichkeit eines Bewegungstags — kein Modell, nur Zählen (ehrlich,
großes Konfidenz-Intervall, n je Bucket wird mit angezeigt).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
ASIA_ENDE_STUNDE = 8          # bis 08:00 MEZ (Konzept S5)
BUCKET_BREITE = 0.25          # ±25 % der Schwelle B gelten als "ähnlich"


def _bar_zeit_utc(bar: dict) -> datetime:
    return datetime.fromtimestamp(bar["time"], tz=timezone.utc)


def asia_range_und_gap(h1: list[dict], datum_berlin_iso: str) -> dict:
    """Range bis 08:00 Berlin des Tages + Wochenend-Gap (Montag).
    bar_time = Bar-BEGINN (MT5-Konvention): Bar 07:00 zählt zur Asia-Range."""
    ziel = datetime.fromisoformat(datum_berlin_iso).date()
    asia_bars = []
    for bar in h1:
        lokal = _bar_zeit_utc(bar).astimezone(BERLIN)
        if lokal.date() == ziel and lokal.hour < ASIA_ENDE_STUNDE:
            asia_bars.append((lokal, bar))
    if not asia_bars:
        return {"ok": False, "grund": "keine Asia-Bars (Markt geschlossen?)"}
    hoch = max(b["high"] for _, b in asia_bars)
    tief = min(b["low"] for _, b in asia_bars)
    letzter_close = asia_bars[-1][1]["close"]
    ergebnis: dict = {"ok": True, "datum": datum_berlin_iso,
                      "range_usd": round(hoch - tief, 2),
                      "hoch": hoch, "tief": tief,
                      "letzter_close": letzter_close,
                      "bars": len(asia_bars)}
    if ziel.weekday() == 0:                             # Montag: Wochenend-Gap
        vorheriger = [b for b in h1
                      if _bar_zeit_utc(b).astimezone(BERLIN).date() < ziel]
        if vorheriger:
            freitag_close = vorheriger[-1]["close"]
            erste_open = asia_bars[0][1]["open"]
            ergebnis["wochend_gap_usd"] = round(erste_open - freitag_close, 2)
            ergebnis["freitag_close"] = freitag_close
    return ergebnis


def empirie_h1(h1: list[dict], d1: list[dict]) -> list[dict]:
    """Je historischem Tag: (range_bis_0800, volle Tages-Range)."""
    # Volle Range je Berlin-Tag aus H1 (exakter als D1 wegen Sessions)
    volle: dict[str, tuple[float, float]] = {}
    for bar in h1:
        lokal = _bar_zeit_utc(bar).astimezone(BERLIN)
        tag = lokal.date().isoformat()
        if tag not in volle:
            volle[tag] = (bar["high"], bar["low"])
        else:
            h, t = volle[tag]
            volle[tag] = (max(h, bar["high"]), min(t, bar["low"]))
    zeilen: list[dict] = []
    for tag, (hoch, tief) in sorted(volle.items()):
        asia = [b for b in h1
                if _bar_zeit_utc(b).astimezone(BERLIN).date().isoformat() == tag
                and _bar_zeit_utc(b).astimezone(BERLIN).hour < ASIA_ENDE_STUNDE]
        if not asia or datetime.fromisoformat(tag).date() >= datetime.now().date():
            continue
        a_hoch = max(b["high"] for b in asia)
        a_tief = min(b["low"] for b in asia)
        zeilen.append({"datum": tag, "range_0800": a_hoch - a_tief,
                       "range_tag": hoch - tief})
    return zeilen


def bedingte_bewegungs_p(zeilen: list[dict], schwelle_b: float,
                         asia_range: float) -> dict:
    """P(Tagesrange > Schwelle B | Asia-Range ähnlich) — Bucket ±25 % der
    Schwelle um die heutige Asia-Range, plus Vergleichswert ohne Bedingung."""
    if schwelle_b <= 0 or not zeilen:
        return {"ok": False}
    anteil_heute = asia_range / schwelle_b
    in_bucket = [z for z in zeilen
                 if abs(z["range_0800"] / schwelle_b - anteil_heute) <= BUCKET_BREITE]
    alle = [z for z in zeilen if z["range_tag"] > schwelle_b]
    treffer = [z for z in in_bucket if z["range_tag"] > schwelle_b]
    basis = len(alle) / len(zeilen) if zeilen else None
    p = len(treffer) / len(in_bucket) if in_bucket else None
    return {
        "ok": p is not None, "p_bedingt": p, "n_bucket": len(in_bucket),
        "p_ohne_bedingung": basis, "n_gesamt": len(zeilen),
        "asia_anteil_der_schwelle": round(anteil_heute, 2),
    }
