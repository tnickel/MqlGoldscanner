"""Feature-Matrix für das HAR-Modell (S3) — strikt point-in-time.

Jede Zeile gehört zu einem Handelstag t und enthält NUR Informationen, die
vor Handelsbeginn von t bekannt waren:
- Ziel: y = ln(TR_rel_t)  ·  Bewegungstag = TR_rel_t > k × Ø-TR_rel der
  vorherigen `fenster` gleichen Wochentage (identisch zur Klimatologie-Definition).
- HAR-Lags: ln(TR_rel) von t−1, Ø der letzten 5 und 22 Handelstage.
- Wochentags-Dummies des ZIELTAGES (Montag = Referenz).
- Events am Zieltag — im Voraus bekannt: NFP-Proxy (erster Freitag),
  FOMC aus der Fed-Historie, GC-Regeltermine.
- IV: GVZ-Premium des letzten verfügbaren Tages VOR t (t−1-Information).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from ..klimatologie import _wochentag

# Feature-Gruppen der Backtest-Konfigurationen (A = Klimatologie ohne Regression)
FEATURES_B = ["ln_lag1", "ln_mean5", "ln_mean22", "wd_di", "wd_mi", "wd_do", "wd_fr"]
FEATURES_C = FEATURES_B + ["nfp", "fomc", "gold_termin"]
FEATURES_D = FEATURES_C + ["iv_daily", "regime"]

KONFIGURATIONEN = {
    "B_har": FEATURES_B,
    "C_har_events": FEATURES_C,
    "D_har_events_iv": FEATURES_D,
}

# HAR-Fenster: Ø der letzten 5 Handelstage (Woche) und 22 (Monat)


def nfp_proxy_datum(jahr: int, monat: int) -> date:
    """Erster Freitag des Monats — dokumentierter NFP-Proxy (Ausnahmen selten)."""
    erster = date(jahr, monat, 1)
    versatz = (4 - erster.weekday()) % 7      # Freitag = 4
    return erster + timedelta(days=versatz)


def nfp_tage(von: date, bis: date) -> set[date]:
    tage: set[date] = set()
    jahr, monat = von.year, von.month
    while (jahr, monat) <= (bis.year, bis.month):
        tage.add(nfp_proxy_datum(jahr, monat))
        monat += 1
        if monat > 12:
            monat, jahr = 1, jahr + 1
    return tage


def fomc_tage_aus_db(db) -> set[date]:
    """FOMC-Sitzungstage aus der Fed-Historie (kalender.json enthält Vergangenheit)."""
    with db._lock:
        zeilen = db._con.execute(
            "SELECT DISTINCT datum FROM calendar_events WHERE klasse='fomc'").fetchall()
    return {date.fromisoformat(r["datum"]) for r in zeilen}


def gold_regeltermine(von: date, bis: date) -> set[date]:
    from ..adapter.regeltermine import alle_regeltermine
    return {t.datum for t in alle_regeltermine(von, bis)
            if t.klasse.startswith("gold_")}


def _iv_daily(gvz: dict[str, float], ziel: date) -> float | None:
    """Letzter GVZ-Schluss VOR dem Zieltag → erwartete tägliche rel. Schwankung."""
    ziel_iso = ziel.isoformat()
    fruehere = [tag for tag in gvz if tag < ziel_iso]
    if not fruehere:
        return None
    return gvz[max(fruehere)] / 100.0 / 252 ** 0.5


def tages_zeilen(d1: list[dict], db, k: float = 1.0, fenster: int = 13,
                 min_vorgaenger: int = 6) -> list[dict]:
    """Baut die Punkt-in-Time-Zeilen (nur voll bewertbare Tage)."""
    if len(d1) < 30:
        return []
    gvz = db.quant_laden("gvz")
    von_datum = datetime.fromtimestamp(d1[0]["time"], tz=timezone.utc).date()
    bis_datum = datetime.fromtimestamp(d1[-1]["time"], tz=timezone.utc).date()
    nfp = nfp_tage(von_datum, bis_datum)
    fomc = fomc_tage_aus_db(db)
    gold_termine = gold_regeltermine(von_datum, bis_datum)

    # relative TR je Bar (Bar 0 ohne)
    rel: list[float | None] = [None]
    for i in range(1, len(d1)):
        pc = d1[i - 1]["close"]
        tr = max(d1[i]["high"] - d1[i]["low"],
                 abs(d1[i]["high"] - pc), abs(d1[i]["low"] - pc))
        rel.append(tr / d1[i]["close"] if d1[i]["close"] else None)

    import math
    zeilen: list[dict] = []
    hist: dict[int, list[float]] = {}
    for i in range(1, len(d1)):
        zeit = datetime.fromtimestamp(d1[i]["time"], tz=timezone.utc)
        ziel = zeit.date()
        wt = zeit.weekday()
        tr_rel = rel[i]
        if tr_rel is None:
            continue
        vorg = hist.get(wt, [])[-fenster:]
        if len(vorg) >= min_vorgaenger:
            schwelle_rel = k * (sum(vorg) / len(vorg))
            ln_lag1 = math.log(rel[i - 1]) if rel[i - 1] else None
            letzte22 = [r for r in rel[max(1, i - 22):i] if r is not None]
            letzte5 = letzte22[-5:]
            if ln_lag1 is not None and len(letzte22) >= 22:
                ln_mean5 = math.log(sum(letzte5) / len(letzte5))
                ln_mean22 = math.log(sum(letzte22) / len(letzte22))
                iv = _iv_daily(gvz, ziel)
                zeilen.append({
                    "datum": ziel.isoformat(), "wochentag": wt,
                    "y": math.log(tr_rel),
                    "tr_rel": tr_rel,
                    "schwelle_rel": schwelle_rel,
                    "bewegung": tr_rel > schwelle_rel,
                    "ln_lag1": ln_lag1, "ln_mean5": ln_mean5, "ln_mean22": ln_mean22,
                    "wd_di": float(wt == 1), "wd_mi": float(wt == 2),
                    "wd_do": float(wt == 3), "wd_fr": float(wt == 4),
                    "nfp": float(ziel in nfp), "fomc": float(ziel in fomc),
                    "gold_termin": float(ziel in gold_termine),
                    "iv_daily": iv,
                    "regime": ln_lag1 - ln_mean22,
                })
        hist.setdefault(wt, []).append(tr_rel)
    return zeilen
