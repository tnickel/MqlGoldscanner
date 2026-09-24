"""Tests zur Wochen-Auswertung (S6): Tagesnote 0-100, Wochenbericht,
DB-Roundtrip inkl. Review-Merge, Backfill-Lauf ohne Key, LLM-Review mit
Fake-Client und Fehlerpfad."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from goldscanner import config
from goldscanner.betrieb import auswertung
from goldscanner.db import Db


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "test.db")


def _verifizieren(db, zeilen: list[dict]) -> None:
    basis = {"as_of_prognose": "2026-09-14T18:00:00"}
    for z in zeilen:
        db.verifikation_speichern({**basis, **z})


# ── Tagesnote ──────────────────────────────────────────────────────────────

def test_tagesnote_perfekt_und_komplett_falsch():
    perfekt = {"p_finale": 1.0, "eingetreten": 1,
               "richtung_p_hoch": 1.0, "richtung_eingetreten": 1, "in_band": 1}
    tn = auswertung.tagesnote(perfekt)
    assert tn["note"] == 100
    assert tn["teile"] == {"bewegung": 40.0, "richtung": 40.0, "band": 20.0}
    assert tn["p_ebene"] == "p_finale"

    falsch = {"p_finale": 0.0, "eingetreten": 1,
              "richtung_p_hoch": 0.0, "richtung_eingetreten": 1, "in_band": 0}
    assert auswertung.tagesnote(falsch)["note"] == 0


def test_tagesnote_muenzwurf_und_ebene():
    # 50/50-Raterei ohne Band: je Baustein halbe Punkte → 50/100
    tn = auswertung.tagesnote({"p_stat": 0.5, "eingetreten": 1,
                               "richtung_p_hoch": 0.5,
                               "richtung_eingetreten": 0})
    assert tn["note"] == 50
    assert tn["p_ebene"] == "p_stat"          # p_finale fehlt → nächste Ebene
    # nur Klimatologie da → Bewertung auf p_klima
    tn2 = auswertung.tagesnote({"p_klima": 0.5, "eingetreten": 1})
    assert tn2["p_ebene"] == "p_klima"


def test_tagesnote_wegnormierung_und_unbewertbar():
    # nur Richtung vorhanden → auf 100 wegnormiert, nicht auf 40 gedeckelt
    tn = auswertung.tagesnote({"richtung_p_hoch": 1.0,
                               "richtung_eingetreten": 1})
    assert tn["note"] == 100 and tn["teile"] == {"richtung": 40.0}
    # nichts Bewertbares
    assert auswertung.tagesnote({"p_stat": 0.5, "tr_usd": 12.0}) is None


# ── Wochenbericht ──────────────────────────────────────────────────────────

def test_wochenbericht_score_und_teilscores(db):
    _verifizieren(db, [
        # Woche B, Tag 1: Bewegung 27,2 + Richtung 20 + Band 0 → 47
        {"datum": "2026-09-21", "woche": "2026-09-21", "p_finale": 0.6,
         "eingetreten": 1, "richtung_p_hoch": 0.5, "richtung_eingetreten": 1,
         "in_band": 0, "tr_usd": 90.0, "schwelle_usd": 50.0},
        # Woche B, Tag 2: nur p_klima + Richtung → wegnormiert auf 100
        {"datum": "2026-09-22", "woche": "2026-09-21", "p_klima": 0.3,
         "eingetreten": 0, "richtung_p_hoch": 0.6, "richtung_eingetreten": 0,
         "tr_usd": 20.0, "schwelle_usd": 40.0},
    ])
    bericht = auswertung.wochenbericht(db, "2026-09-21")
    assert bericht["ok"] and bericht["n_tage"] == 2
    assert bericht["score"] == 51                # Ø(47, 55)
    assert bericht["teilscores"]["bewegung"] == 75
    assert bericht["teilscores"]["richtung"] == 39   # Tag 2: 60 % "hoch" kam runter
    assert bericht["teilscores"]["band"] == 0
    assert bericht["tage"][0]["wochentag"] == "Montag"
    assert not auswertung.wochenbericht(db, "2026-01-05")["ok"]


# ── DB-Roundtrip: Upsert ohne Review-Verlust ───────────────────────────────

def test_db_wochenbericht_roundtrip_und_lessons(db):
    bericht = {"woche": "2026-09-21", "score": 60, "n_tage": 2,
               "teilscores": {"bewegung": 75, "richtung": 57, "band": 0},
               "tage": [{"datum": "2026-09-21", "note": 47}]}
    db.wochenbericht_speichern(bericht)
    gelesen = db.wochenbericht("2026-09-21")
    assert gelesen["score"] == 60 and gelesen["n_tage"] == 2
    assert gelesen["teilscores"]["bewegung"] == 75
    assert gelesen["tagesnoten"][0]["note"] == 47
    assert gelesen["fazit"] is None

    # Score-Update (Neuberechnung) darf das Review nicht löschen
    db.wochenbericht_review_speichern("2026-09-21", {
        "fazit": "Durchwachsene Woche.", "lessons": ["L1", "L2"],
        "stimmung": "durchschnittlich", "modell": "fake"})
    bericht["score"] = 70
    db.wochenbericht_speichern(bericht)
    gelesen = db.wochenbericht("2026-09-21")
    assert gelesen["score"] == 70 and gelesen["fazit"] == "Durchwachsene Woche."
    assert gelesen["lessons"] == ["L1", "L2"]
    assert db.lessons_letzte() == ["L1", "L2"]

    # wochenberichte(): aufsteigend, Review-Felder mitgeliefert
    db.wochenbericht_speichern({"woche": "2026-09-14", "score": 40,
                                "n_tage": 1, "teilscores": {}, "tage": []})
    reihe = db.wochenberichte()
    assert [b["woche"] for b in reihe] == ["2026-09-14", "2026-09-21"]
    assert reihe[1]["stimmung"] == "durchschnittlich"
    # lessons_letzte(): nur Wochen MIT Review zählen
    assert db.wochenbericht("2026-09-14")["fazit"] is None


# ── Läuft-Kette: Backfill ohne Key ────────────────────────────────────────

def test_laeuft_backfill_ohne_key(db, monkeypatch):
    monkeypatch.setattr("goldscanner.secrets_store.get_secret",
                        lambda schluessel: None)
    _verifizieren(db, [
        {"datum": "2026-09-15", "woche": "2026-09-14", "p_stat": 0.8,
         "eingetreten": 1, "richtung_p_hoch": 0.7, "richtung_eingetreten": 1,
         "in_band": 1, "tr_usd": 60.0, "schwelle_usd": 30.0},
        {"datum": "2026-09-21", "woche": "2026-09-21", "p_finale": 0.6,
         "eingetreten": 1, "richtung_p_hoch": 0.5, "richtung_eingetreten": 1,
         "in_band": 0, "tr_usd": 90.0, "schwelle_usd": 50.0},
        {"datum": "2026-09-22", "woche": "2026-09-21", "p_klima": 0.3,
         "eingetreten": 0, "richtung_p_hoch": 0.6, "richtung_eingetreten": 0,
         "tr_usd": 20.0, "schwelle_usd": 40.0},
    ])
    prot = auswertung.laeuft(db, config.DEFAULT_SETTINGS,
                             heute=date(2026, 9, 26))       # Samstag
    assert prot["ok"] and prot["neu"] == 2
    assert prot["letzte_woche"] == "2026-09-21"
    assert prot["score_letzte"] == 51
    assert prot["review_ok"] is False               # kein Key → kein Review
    assert len(db.wochenberichte()) == 2
    # idempotent: zweite Runde legt nichts Neues an
    prot2 = auswertung.laeuft(db, config.DEFAULT_SETTINGS,
                              heute=date(2026, 9, 26))
    assert prot2["neu"] == 0 and prot2["score_letzte"] == 51


# ── LLM-Review: Fake-Client, Parse, Fehlerpfad ────────────────────────────

class FakeClient:
    def __init__(self, antwort: str | None = None,
                 fehler: Exception | None = None):
        self.antwort = antwort
        self.fehler = fehler

    def chat(self, prompt, system="", model=None, stufe=1,
             temperature=0.4, max_tokens=1600, meta_out=None):
        if self.fehler is not None:
            raise self.fehler
        return self.antwort


ANTWORT = ('{"fazit": "Die Woche war durchwachsen: Bewegungstag-Montag '
           'traf ein, aber das Band war zu eng.", "lessons": '
           '["Band an Event-Tagen verbreitern"], "stimmung": "schwach"}')


def test_review_erzeugen_parsen(db):
    db.verifikation_speichern(
        {"datum": "2026-09-21", "woche": "2026-09-21",
         "as_of_prognose": "x", "p_stat": 0.8, "eingetreten": 1})
    bericht = auswertung.wochenbericht(db, "2026-09-21")
    review = auswertung.review_erzeugen(
        db, config.DEFAULT_SETTINGS, FakeClient(ANTWORT), bericht)
    assert review["ok"]
    assert review["fazit"].startswith("Die Woche")
    assert review["lessons"] == ["Band an Event-Tagen verbreitern"]
    assert review["stimmung"] == "schwach"


def test_review_erzeugen_fehlerpfad(db, monkeypatch):
    db.verifikation_speichern(
        {"datum": "2026-09-21", "woche": "2026-09-21",
         "as_of_prognose": "x", "p_stat": 0.8, "eingetreten": 1})
    bericht = auswertung.wochenbericht(db, "2026-09-21")
    from goldscanner.llm.client import LlmError
    review = auswertung.review_erzeugen(
        db, config.DEFAULT_SETTINGS,
        FakeClient(fehler=LlmError("Kein Kontingent")), bericht)
    assert review["ok"] is False and "Kontingent" in review["grund"]


def test_gesamt_score(db):
    assert auswertung.gesamt_score(db) == {"n_tage": 0, "score": None}
    _verifizieren(db, [
        {"datum": "2026-09-21", "woche": "2026-09-21", "p_finale": 1.0,
         "eingetreten": 1, "richtung_p_hoch": 1.0, "richtung_eingetreten": 1,
         "in_band": 1},
        {"datum": "2026-09-22", "woche": "2026-09-21", "p_finale": 0.0,
         "eingetreten": 1, "richtung_p_hoch": 0.0, "richtung_eingetreten": 1,
         "in_band": 0},
    ])
    assert auswertung.gesamt_score(db) == {"n_tage": 2, "score": 50}
