# -*- coding: utf-8 -*-
"""Regelbasierte Termine — deterministisch berechnet statt gescraped
(Konzept §5/§7.1: CME-Kalender ist Akamai-gesperrt; Regeln reichen).

GC-Futures (COMEX-Regeln, vereinfacht nach Deep-Research-Auswertung):
- Liefermonate Golderminate: Feb/Apr/Jun/Aug/Okt/Dez.
- First Notice Day (FND): letzter Geschäftstag VOR dem Liefermonat
  (= letzter Geschäftstag des Vormonats; Regel 706.C).
- Last Trade Day (LTD): drittletzter Geschäftstag des Liefermonats.
- Standard-Options-Verfall (OG): 4 Geschäftstage vor Ende des Vormonats
  (Freitags-/Feiertags-Anpassungen approximiert — gegen CME-Regelbuch
  verifizierbar, aber bewusst ohne Scraping).

Dazu: Quartalsenden, US-/UK-Feiertage (Börsen-Relevanz) und DST-Wechsel
(EU: letzter Sonntag März/Okt; US: 2. So. März / 1. So. Nov).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

LIEFERMONATE = {2, 4, 6, 8, 10, 12}   # GC-Aktivmonate


@dataclass
class Regeltermin:
    datum: date
    titel: str
    klasse: str
    wichtigkeit: int          # 1-3
    gold_relevanz: int        # 0-5

    def als_event(self) -> dict:
        return {
            "quelle": "regel",
            "prioritaet": 6,
            "zeit_utc": None,
            "datum": self.datum.isoformat(),
            "titel": self.titel,
            "klasse": self.klasse,
            "wichtigkeit": self.wichtigkeit,
            "gold_relevanz": self.gold_relevanz,
            "waehrung": "USD",
            "forecast": None, "previous": None, "actual": None,
        }


# ── Feiertage (Börsen-Relevanz, vereinfacht: feste Daten mit Wochenend-Anpassung) ──

def _angepasst(tag: date) -> date:
    """Sa → Fr davor, So → Mo danach (einfache US-Konvention)."""
    if tag.weekday() == 5:
        return tag - timedelta(days=1)
    if tag.weekday() == 6:
        return tag + timedelta(days=1)
    return tag


def us_feiertage(jahr: int) -> list[tuple[date, str]]:
    tage: list[tuple[date, str]] = [
        (_angepasst(date(jahr, 1, 1)), "New Year's Day (US)"),
        (_n_te_woche(jahr, 1, 3, 0), "MLK Day (US)"),
        (_n_te_woche(jahr, 2, 3, 0), "Presidents' Day (US)"),
        (_letzter_wochentag(jahr, 5, 0), "Memorial Day (US)"),
        (_angepasst(date(jahr, 6, 19)), "Juneteenth (US)"),
        (_angepasst(date(jahr, 7, 4)), "Independence Day (US)"),
        (_n_te_woche(jahr, 9, 1, 0), "Labor Day (US)"),
        (_n_te_woche(jahr, 11, 4, 3), "Thanksgiving (US)"),
        (_angepasst(date(jahr, 12, 25)), "Christmas (US)"),
    ]
    return tage


def uk_feiertage(jahr: int) -> list[tuple[date, str]]:
    return [
        (_angepasst(date(jahr, 1, 1)), "New Year's Day (UK)"),
        (_beweglich_uk_osterfest(jahr), "Good Friday (UK/LBMA geschlossen)"),
        (_beweglich_uk_osterfest(jahr, 3), "Easter Monday (UK)"),
        (_n_te_woche(jahr, 5, 1, 0), "Early May Bank Holiday (UK)"),
        (_letzter_wochentag(jahr, 5, 0), "Spring Bank Holiday (UK)"),
        (_letzter_wochentag(jahr, 8, 0), "Summer Bank Holiday (UK)"),
        (_angepasst(date(jahr, 12, 25)), "Christmas (UK)"),
        (_angepasst(date(jahr, 12, 26)), "Boxing Day (UK)"),
    ]


def _n_te_woche(jahr: int, monat: int, n: int, wochentag: int) -> date:
    """n-ter Wochentag (1-basiert; wochentag 0=Mo … 6=So) eines Monats.
    Beispiele: MLK = _n_te_woche(j, 1, 3, 0) · Thanksgiving = _n_te_woche(j, 11, 4, 3)."""
    erster = date(jahr, monat, 1)
    versatz = (wochentag - erster.weekday()) % 7
    return erster + timedelta(days=versatz + 7 * (n - 1))


def _letzter_wochentag(jahr: int, monat: int, wochentag: int) -> date:
    letzter = date(jahr + (monat == 12), (monat % 12) + 1, 1) - timedelta(days=1)
    versatz = (letzter.weekday() - wochentag) % 7
    return letzter - timedelta(days=versatz)


def _beweglich_uk_osterfest(jahr: int, versatz_tage: int = 0) -> date:
    """Ostersonntag nach Gauß/'Butcher-Meeus' (vereinfacht, für Karfreitag/Montag)."""
    a = jahr % 19
    b, c = divmod(jahr, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    monat = (h + l - 7 * m + 114) // 31
    tag = ((h + l - 7 * m + 114) % 31) + 1
    ostern = date(jahr, monat, tag)
    return ostern + timedelta(days=versatz_tage - 2)   # -2 = Karfreitag


# ── Geschäftstage ────────────────────────────────────────────────────────

def ist_wochenende(d: date) -> bool:
    return d.weekday() >= 5


def n_vorletzter_geschaeftstag(monat_jahr: tuple[int, int], n_von_hinten: int) -> date:
    """Der n-von-hinten-te Geschäftstag (ohne Sa/So; Feiertage grob ignoriert —
    für FND/LTD ausreichend, Abweichungen dokumentiert)."""
    jahr, monat = monat_jahr
    letzter = date(jahr + (monat == 12), (monat % 12) + 1, 1) - timedelta(days=1)
    tage = [letzter - timedelta(days=i) for i in range(0, 40)]
    geschaeftstage = [d for d in tage if not ist_wochenende(d)]
    return geschaeftstage[n_von_hinten - 1]


def gc_termine(jahr: int) -> list[Regeltermin]:
    """FND/LTD/Opex für alle GC-Liefermonate eines Jahres."""
    termine: list[Regeltermin] = []
    for liefermonat in LIEFERMONATE:
        vormonat_jahr = jahr - 1 if liefermonat == 1 else jahr
        vormonat = liefermonat - 1 if liefermonat > 1 else 12
        fnd = n_vorletzter_geschaeftstag((vormonat_jahr, vormonat), 1)
        opex = n_vorletzter_geschaeftstag((vormonat_jahr, vormonat), 4)
        ltd = n_vorletzter_geschaeftstag((jahr, liefermonat), 3)
        monat_kurz = date(jahr, liefermonat, 1).strftime("%b")
        termine.append(Regeltermin(fnd, f"GC First Notice Day {monat_kurz}",
                                   "gold_fnd", 2, 3))
        termine.append(Regeltermin(opex, f"GC Options-Verfall {monat_kurz}",
                                   "gold_opex", 2, 3))
        termine.append(Regeltermin(ltd, f"GC Last Trade Day {monat_kurz}",
                                   "gold_ltd", 1, 2))
    return termine


def dst_wechsel(jahr: int) -> list[Regeltermin]:
    eu_frueh = _letzter_wochentag(jahr, 3, 6)          # letzter Sonntag März (6=So)
    eu_herbst = _letzter_wochentag(jahr, 10, 6)
    us_frueh = _n_te_woche(jahr, 3, 2, 6)              # 2. Sonntag März
    us_herbst = _n_te_woche(jahr, 11, 1, 6)            # 1. Sonntag Nov
    return [
        Regeltermin(us_frueh, "US-Zeitumstellung (DST beginnt)", "dst", 1, 1),
        Regeltermin(eu_frueh, "EU-Zeitumstellung (DST beginnt)", "dst", 1, 1),
        Regeltermin(eu_herbst, "EU-Zeitumstellung (DST endet)", "dst", 1, 1),
        Regeltermin(us_herbst, "US-Zeitumstellung (DST endet)", "dst", 1, 1),
    ]


def alle_regeltermine(von: date, bis: date) -> list[dict]:
    """Feiertage, Quartalsenden, GC-Termine und DST im Zeitraum [von, bis]."""
    termine: list[Regeltermin] = []
    for jahr in range(von.year - 1, bis.year + 2):
        for d, titel in us_feiertage(jahr):
            termine.append(Regeltermin(d, titel, "feiertag_us", 1, 2))
        for d, titel in uk_feiertage(jahr):
            termine.append(Regeltermin(d, titel, "feiertag_uk", 1, 1))
        termine.extend(gc_termine(jahr))
        termine.extend(dst_wechsel(jahr))
        for quartal_ende in (date(jahr, 3, 31), date(jahr, 6, 30),
                             date(jahr, 9, 30), date(jahr, 12, 31)):
            termine.append(Regeltermin(quartal_ende, "Quartalsende",
                                       "quartal", 1, 2))
    # an einem Datum zählt der gold-relevanteste Termin (Dedup über Datum)
    beste: dict[date, Regeltermin] = {}
    for t in termine:
        if not (von <= t.datum <= bis):
            continue
        if t.datum not in beste or t.gold_relevanz > beste[t.datum].gold_relevanz:
            beste[t.datum] = t
    return sorted(beste.values(), key=lambda t: t.datum)
