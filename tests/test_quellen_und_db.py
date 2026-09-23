"""Quellen-Bewertung (Wächter-Logik) und DB-Roundtrip mit echter SQLite-Datei."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from goldscanner.db import Db
from goldscanner.quellen_check import _bewerte, katalog


def _eintrag(erwartet="json", nur_kopf=False):
    return {"name": "Test", "url": "https://example.org", "kategorie": "Test",
            "erwartet": erwartet, "nur_kopf": nur_kopf}


def test_katalog_16_quellen():
    assert len(katalog()) == 16


def test_bewertung_ok_typ_und_signatur():
    e = _bewerte(_eintrag("json"), 200, "application/json", 100, b'{"a": 1}', 10, None)
    assert e["ok"] and e["hinweis"].startswith("OK")
    # Typ falsch, aber Signatur stimmt → trotzdem OK (Wächter-Prinzip)
    e2 = _bewerte(_eintrag("json"), 200, "text/html", 100, b'{"a": 1}', 10, None)
    assert e2["ok"]
    # ICS über Signatur
    e3 = _bewerte(_eintrag("ics"), 200, "text/plain", 100,
                  b"BEGIN:VCALENDAR\r\n...", 10, None)
    assert e3["ok"]
    # XLSX über ZIP-Magie
    e4 = _bewerte(_eintrag("xlsx"), 200, "application/octet-stream", 100, b"PK\x03\x04", 10, None)
    assert e4["ok"]


def test_bewertung_format_verdaechtig():
    # 200 + HTML statt JSON und keine JSON-Signatur → verdächtig
    e = _bewerte(_eintrag("json"), 200, "text/html", 100, b"<html>Request Denied", 10, None)
    assert not e["ok"]
    assert "Format verdächtig" in e["hinweis"]


def test_bewertung_blockiert_und_fehler():
    e = _bewerte(_eintrag(), 403, "", 0, b"", 10, None)
    assert not e["ok"] and "Bot-Schutz" in e["hinweis"]
    e2 = _bewerte(_eintrag(), 429, "", 0, b"", 10, None)
    assert not e2["ok"] and "Drosselung" in e2["hinweis"]
    e3 = _bewerte(_eintrag(), 0, "", 0, b"", 10, "ConnectionError: x")
    assert not e3["ok"] and "Transportfehler" in e3["hinweis"]


def test_db_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        db = Db(Path(tmp) / "test.db")
        bar = {"time": 1_700_000_000, "open": 100.0, "high": 110.0,
               "low": 90.0, "close": 105.0, "volumen": 42.0}
        assert db.raten_speichern("XAUUSD", "d1", [bar]) == 1
        assert db.raten_speichern("XAUUSD", "d1", [bar]) == 0     # Dedup
        assert db.raten_anzahl("XAUUSD", "d1") == 1
        geladen = db.raten_laden("XAUUSD", "d1")
        assert geladen[0]["close"] == 105.0

        lauf = db.lauf_starten("testlauf", "Beschreibung")
        db.schritt(lauf, "glm", "ping", "p", "a", "glm-flash", 42, 1.5, True, "")
        db.lauf_beenden(lauf, True)
        schritte = db.letzte_schritte(5)
        assert len(schritte) == 1 and schritte[0]["tokens"] == 42 and schritte[0]["ok"]

        db.token_buchen("glm-flash", 600)
        db.token_buchen("glm-flash", 400)
        assert db.tokens_heute() == 1000
        db.close()
