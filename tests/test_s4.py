"""Stufe-4-Tests: RSS-Adapter, Community, Prompt-Filler, JSON-Validierung,
Band-Disziplin, Fail-Fast, Delta-Meldung, DB v4, PDF-Smoke."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from goldscanner import config
from goldscanner.adapter import community, news
from goldscanner.agenten import analytiker, destillation
from goldscanner.agenten.destillation import antwort_als_json
from goldscanner.bericht import pdf as pdf_bericht
from goldscanner.db import Db
from goldscanner.llm.client import LlmError
from goldscanner.llm.prompts import (assert_template_covered, fill_prompt,
                                     load_prompt)

# ── Fixtures ────────────────────────────────────────────────────────────────

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test-Feed</title>
<item>
  <title>Gold price surges after Fed hint</title>
  <link>https://example.com/gold-a</link>
  <description>&lt;p&gt;Gold &lt;b&gt;rose&lt;/b&gt; sharply.&lt;/p&gt;</description>
  <pubDate>Wed, 23 Sep 2026 10:00:00 GMT</pubDate>
  <source url="https://kitco.com">Kitco.com</source>
</item>
<item>
  <title>SpaceX stock slides after launch - TechCrunch</title>
  <link>https://example.com/tech</link>
  <description>Rocket news.</description>
  <pubDate>Wed, 23 Sep 2026 09:00:00 GMT</pubDate>
</item>
<item>
  <title>Dollar rally pressures bullion</title>
  <link>https://example.com/usd</link>
  <description></description>
  <pubDate>Tue, 22 Sep 2026 09:00:00 GMT</pubDate>
</item>
</channel></rss>"""


@pytest.fixture
def db(tmp_path):
    return Db(tmp_path / "test.db")


class FakeClient:
    """Zeichnet Prompts auf und spielt eine (oder mehrere) Antworten vor."""

    def __init__(self, antworten: list[str]):
        self.antworten = list(antworten)
        self.prompts: list[str] = []

    def chat(self, prompt, system="", model=None, stufe=1, temperature=0.4,
             max_tokens=1600, meta_out=None):
        self.prompts.append(prompt)
        if meta_out is not None:
            meta_out.update({"model": "fake", "prompt_tokens": 100,
                             "completion_tokens": 50, "dauer_s": 0.1})
        if not self.antworten:
            raise LlmError("keine vorbereitete Antwort mehr")
        antwort = self.antworten.pop(0)
        if antwort.startswith("RAISE:"):
            raise LlmError(antwort[6:])
        return antwort


def matrix_fixture() -> dict:
    return {
        "woche": "2026-09-21", "bis": "2026-09-25",
        "modell": "har_B_har (BSS +0.161)",
        "erzeugt_am": "2026-09-23T12:00:00+00:00",
        "basis": {"symbol": "XAUUSD", "bars_d1": 1001, "fenster": 13,
                  "p_global": 0.412, "n_global": 970},
        "schwellen_tabelle": [],
        "tage": [
            {"datum": "2026-09-21", "wochentag": "Montag", "p": 0.36,
             "p_klima": 0.355, "p_stat": 0.36, "warnstufe": "ruhig",
             "schwelle_usd": 41.0, "schwelle_pct": 0.95, "q10_usd": 22.0,
             "q50_usd": 33.0, "q90_usd": 52.0, "events_count": 1,
             "top_events": [{"zeit": "14:30", "titel": "Fed-Rede",
                             "gold_relevanz": 4, "klasse": "rede"}]},
            {"datum": "2026-09-22", "wochentag": "Dienstag", "p": 0.436,
             "p_klima": 0.436, "p_stat": None, "warnstufe": "normal",
             "schwelle_usd": 42.0, "schwelle_pct": 0.96, "q10_usd": 23.0,
             "q50_usd": 34.0, "q90_usd": 54.0, "events_count": 0,
             "top_events": []},
        ],
    }


def fusion_antwort(p1=44.0, p2=45.0, begruendung="Fed-Rede plus starke News-Lage "
                   "rechtfertigt die Anhebung über die Basisrate hinaus.") -> str:
    return json.dumps({
        "zusammenfassung": "Ruhige Woche nach Beruhigung der Volatilität.",
        "tage": [
            {"datum": "2026-09-21", "p_finale_pct": p1,
             "begruendung": begruendung if p1 != 36.0 else "",
             "richtung": "hoch", "konfidenz": "mittel",
             "treiber": [{"name": "Fed-Rede", "einfluss_pp": 5.0,
                          "richtung": "auf", "quelle": "event"},
                         {"name": "Gold-Nachfrage", "einfluss_pp": 3.0,
                          "richtung": "auf", "quelle": "news"}]},
            {"datum": "2026-09-22", "p_finale_pct": p2,
             "begruendung": "keine Events, Modell unverändert plausibel"
             if abs(p2 - 43.6) <= 10 else "x" * 20,
             "richtung": "neutral", "konfidenz": "niedrig", "treiber": []},
        ],
        "risiken": ["Geopolitische Eskalation"],
    })


# ── RSS-Adapter ─────────────────────────────────────────────────────────────

def test_parse_rss_publisher_und_bereinigung():
    items = news.parse_rss(RSS_FIXTURE, "test")
    assert len(items) == 3
    gold = items[0]
    assert gold["publisher"] == "Kitco.com"                       # <source>-Tag
    assert "rose sharply." in gold["zusammenfassung"]             # HTML raus
    assert gold["veroeffentlicht"].startswith("2026-09-23T10:00")
    ohne_source = items[1]
    assert ohne_source["publisher"] == "TechCrunch"               # Titelsuffix


def test_gold_relevanz_filter():
    assert news.gold_relevanz("Gold price surges") == 3
    assert news.gold_relevanz("Fed decision looms over markets") == 2
    assert news.gold_relevanz("SpaceX stock slides") == 0
    assert news.gold_relevanz("Quiet day", "dollar weakness persists") == 1


def test_dedup_hash_stabil_und_unabhaengig_vom_query():
    h1 = news._hash("q", "Gold  Steigt ", "https://a.de/x?utm=1")
    h2 = news._hash("q", "gold steigt", "https://a.de/x")
    assert h1 == h2


def test_news_delta_prinzip(db):
    items = news.parse_rss(RSS_FIXTURE, "test")
    frisch = [{"quelle": "test", "url": i["url"], "titel": i["titel"],
               "autor": None, "veroeffentlicht": i["veroeffentlicht"],
               "dedup_hash": news._hash("test", i["titel"], i["url"]),
               "gold_relevanz": 2, "zusammenfassung": i["zusammenfassung"]}
              for i in items]
    assert db.news_speichern(frisch) == 3
    assert db.news_speichern(frisch) == 0            # Delta: nichts Neues
    assert db.news_anzahl(offen=True) == 3
    db.news_destilliert_markieren([i["id"] for i in db.news_offen()])
    assert db.news_anzahl(offen=True) == 0


# ── Community ───────────────────────────────────────────────────────────────

def test_richtung_aus_text():
    assert community.richtung_aus_text("XAUUSD bullish breakout", "") == "bullish"
    assert community.richtung_aus_text("Gold bearish rejection", "") == "bearish"
    assert community.richtung_aus_text("When to withdraw a level", "") == "neutral"


def test_level_cluster():
    texte = ["Gold 4316 and maybe 4,230", "watch 4230 again", "4316 key"]
    cluster = community.level_cluster(texte)
    level = {c["level"]: c["nennungen"] for c in cluster}
    assert level[4310] == 2 and level[4230] == 2


# ── Prompt-Filler ───────────────────────────────────────────────────────────

def test_fill_prompt_injektionssicher():
    template = "A {items_json} B"
    boese = "inhalt mit {items_json} drin"
    out = fill_prompt(template, {"{items_json}": boese})
    assert out == f"A {boese} B"          # Literal bleibt, kein Doppel-Ersatz


def test_assert_template_covered_reagiert_auf_tippfehler():
    with pytest.raises(LlmError):
        assert_template_covered("x {kaputter_slot} y", ("{guter}",), "test")


def test_prompt_dateien_versorgt():
    for name, slots in (("news_destillation",
                         ("{items_json}", "{n_items}", "{fenster_tage}", "{heute}")),
                        ("community_destillation", ("{community_json}", "{heute}")),
                        ("analytiker_fusion", ("{matrix_json}", "{news_json}",
                                               "{community_json}", "{heute}",
                                               "{band_pp}"))):
        assert_template_covered(load_prompt(name), slots, name)


# ── JSON-Validierung ────────────────────────────────────────────────────────

def test_antwort_als_json_verzeiht_zaeune_und_prosa():
    gut = '{"a": 1}'
    assert antwort_als_json(gut) == {"a": 1}
    assert antwort_als_json(f"```json\n{gut}\n```") == {"a": 1}
    assert antwort_als_json(f"Ergebnis: {gut} Ende") == {"a": 1}
    with pytest.raises(LlmError):
        antwort_als_json("kein json")
    with pytest.raises(LlmError):
        antwort_als_json("[1, 2]")               # Liste, kein Objekt


# ── Band-Disziplin (Kern von Tor T4) ───────────────────────────────────────

def test_band_verstoss_wird_abgewiesen():
    tag, verstoesse = analytiker._tag_pruefen(
        {"datum": "2026-09-21", "p_finale_pct": 70.0,
         "begruendung": "sehr gute gruende" * 5}, basis_pct=36.0, band_pp=10.0)
    assert tag["p_finale_pct"] == 36.0 and tag["abweichung_pp"] == 0.0
    assert len(verstoesse) == 1 and "Band" in verstoesse[0]


def test_abweichung_ohne_begruendung_wird_abgewiesen():
    tag, verstoesse = analytiker._tag_pruefen(
        {"datum": "2026-09-21", "p_finale_pct": 42.0, "begruendung": "zu kurz"},
        basis_pct=36.0, band_pp=10.0)
    assert tag["p_finale_pct"] == 36.0
    assert any("Begründung" in v for v in verstoesse)


def test_gueltige_anpassung_innerhalb_band_bleibt():
    tag, verstoesse = analytiker._tag_pruefen(
        {"datum": "2026-09-21", "p_finale_pct": 44.0,
         "begruendung": "Fed-Rede und News-Lage heben das Risiko sauber an.",
         "richtung": "hoch", "konfidenz": "mittel",
         "treiber": [{"name": "Fed", "einfluss_pp": 5.0, "richtung": "auf"}]},
        basis_pct=36.0, band_pp=10.0)
    assert tag["p_finale_pct"] == 44.0 and tag["abweichung_pp"] == 8.0
    assert not verstoesse and tag["richtung"] == "hoch"
    assert tag["treiber"][0]["einfluss_pp"] == 5.0


def test_ungueltiger_wert_faellt_auf_basis():
    tag, verstoesse = analytiker._tag_pruefen(
        {"datum": "2026-09-21", "p_finale_pct": "kaputt"}, 36.0, 10.0)
    assert tag["p_finale_pct"] == 36.0 and verstoesse


# ── Fusion Ende-zu-Ende ────────────────────────────────────────────────────

def test_fusion_speichert_und_delta_meldung(db):
    settings = {**config.DEFAULT_SETTINGS, "llm_band_pp": 10.0,
                "llm_melde_schwelle_pp": 5.0}
    client = FakeClient([fusion_antwort(p1=44.0, p2=48.0)])
    ergebnis = analytiker.fusioniere(db, settings, client, matrix_fixture(),
                                     None, None)
    assert ergebnis["ok"] and ergebnis["delta_max_pp"] == 8.0
    assert db.fusion_letzte("2026-09-21")["delta_max_pp"] == 8.0
    assert db.meldungen() == []                    # erste Fusion: kein Vergleich

    # Zweiter Lauf: Dienstag springt von 48 auf 40 → Meldung
    client2 = FakeClient([fusion_antwort(p1=44.0, p2=40.0)])
    analytiker.fusioniere(db, settings, client2, matrix_fixture(), None, None)
    meldungen = db.meldungen(nur_offene=True)
    assert len(meldungen) == 1 and "2026-09-22" in meldungen[0]["text"]


def test_fusion_fehlt_tag_wird_neutralisiert_nicht_abgelehnt(db):
    antwort = json.dumps({"zusammenfassung": "ok", "tage": [
        {"datum": "2026-09-21", "p_finale_pct": 36.0, "begruendung": "",
         "richtung": "neutral", "konfidenz": "niedrig", "treiber": []}]})
    ergebnis = analytiker.fusioniere(db, config.DEFAULT_SETTINGS,
                                     FakeClient([antwort]), matrix_fixture(),
                                     None, None)
    assert ergebnis["ok"]
    dienstag = next(t for t in ergebnis["tage"] if t["datum"] == "2026-09-22")
    assert dienstag["p_finale_pct"] == dienstag["basis_pct"] == 43.6
    assert ergebnis["verstoesse"]


def test_fusion_kaputtes_json_nie_gespeichert(db):
    client = FakeClient(["RAISE:kaputt", "RAISE:kaputt", "RAISE:kaputt"])
    ergebnis = analytiker.fusioniere(db, config.DEFAULT_SETTINGS, client,
                                     matrix_fixture(), None, None)
    assert not ergebnis["ok"]
    assert db.fusion_letzte() is None              # nichts Halbfertiges


def test_fail_fast_nach_drei_fehlern(db):
    items = news.parse_rss(RSS_FIXTURE, "test")
    db.news_speichern([{"quelle": "test", "url": i["url"], "titel": i["titel"],
                        "autor": None, "veroeffentlicht": i["veroeffentlicht"],
                        "dedup_hash": news._hash("test", i["titel"], i["url"]),
                        "gold_relevanz": 2,
                        "zusammenfassung": i["zusammenfassung"]} for i in items])
    client = FakeClient(["RAISE:verbindung", "RAISE:verbindung",
                         "RAISE:verbindung", "RAISE:zu-viel"])
    ergebnis = destillation.news_destillieren(db, config.DEFAULT_SETTINGS,
                                              client)
    assert not ergebnis["ok"]
    assert len(client.prompts) == 3                # Fail-Fast nach genau 3 Versuchen
    assert db.news_anzahl(offen=True) == 3         # nichts als verarbeitet markiert


def test_news_destillation_markiert_items(db):
    items = news.parse_rss(RSS_FIXTURE, "test")
    db.news_speichern([{"quelle": "test", "url": i["url"], "titel": i["titel"],
                        "autor": None, "veroeffentlicht": i["veroeffentlicht"],
                        "dedup_hash": news._hash("test", i["titel"], i["url"]),
                        "gold_relevanz": 2,
                        "zusammenfassung": i["zusammenfassung"]} for i in items])
    antwort = json.dumps({"treiber": [{"name": "Fed-Pivot", "richtung": "auf",
                                       "horizont": "woche", "konfidenz": "mittel",
                                       "erklaerung": "x", "beleg_url": "y"}],
                          "gesamt_stimmung": "auf", "erkenntnis": "bullish"})
    ergebnis = destillation.news_destillieren(db, config.DEFAULT_SETTINGS,
                                              FakeClient([antwort]))
    assert ergebnis["ok"] and ergebnis["n_items"] == 3
    assert db.news_anzahl(offen=True) == 0         # Delta: alles verarbeitet


# ── PDF ─────────────────────────────────────────────────────────────────────

def test_pdf_smoke(tmp_path):
    matrix = matrix_fixture()
    llm = json.loads(fusion_antwort())
    llm.update({"ok": True, "modell": "fake", "band_pp": 10.0,
                "delta_max_pp": 8.0, "verstoesse": [], "risiken": ["x"],
                "kontra_hinweis": "", "tokens": 150})
    matrix["llm"] = llm
    pfad = pdf_bericht.baue_wochen_pdf(matrix, tmp_path / "bericht.pdf")
    assert pfad.exists()
    assert pfad.read_bytes()[:5] == b"%PDF-"


# ── DB v4 ───────────────────────────────────────────────────────────────────

def test_db_schema_v4_fusionen_meldungen(db):
    assert db.fusion_letzte() is None
    db.fusion_speichern("2026-09-21", "fake", 10.0, "{}", True, 3.0, 1)
    db.fusion_speichern("2026-09-21", "fake", 10.0, "{}", True, 1.0, 0)
    assert db.fusion_letzte("2026-09-21")["delta_max_pp"] == 1.0
    assert db.fusion_vorherige("2026-09-21")["delta_max_pp"] == 3.0
    db.meldung_speichern("2026-09-21", "prognose_geaendert", "Test")
    assert len(db.meldungen(nur_offene=True)) == 1
    db.meldung_gelesen_markieren(db.meldungen()[0]["id"])
    assert db.meldungen(nur_offene=True) == []
