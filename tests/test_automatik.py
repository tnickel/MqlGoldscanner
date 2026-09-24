"""Tests zur Automatik: konfigurierbarer Daemon-Zeitplan (Wochentag +
Uhrzeit)."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from goldscanner import config
from goldscanner.betrieb import daemon


# ── Zeitplan aus Settings ──────────────────────────────────────────────────

def test_zeitplan_defaults():
    plan = daemon.zeitplan(config.DEFAULT_SETTINGS)
    assert plan["tageslauf"] == (None, 6, 30)          # täglich
    assert plan["scout"] == (6, 17, 0)                 # So 17:00
    assert plan["wochenlauf"] == (6, 18, 0)
    assert plan["verifikation"] == (5, 9, 0)           # Sa 09:00


def test_zeitplan_konfigurierbar():
    settings = {**config.DEFAULT_SETTINGS,
                "daemon_verifikation_tag": "Freitag",
                "daemon_verifikation_zeit": "22:15"}
    plan = daemon.zeitplan(settings)
    assert plan["verifikation"] == (4, 22, 15)         # Fr 22:15
    assert plan["wochenlauf"] == (6, 18, 0)            # Rest unverändert


def test_zeitplan_toleriert_tippfehler():
    settings = {**config.DEFAULT_SETTINGS,
                "daemon_scout_tag": "Sontag",          # vertippt
                "daemon_scout_zeit": "kaputt"}
    plan = daemon.zeitplan(settings)
    assert plan["scout"] == (6, 17, 0)                 # Defaults greifen


def test_faellig_mit_verschobenem_tag():
    # Verifikation auf Freitag 23:00 verlegt. Ein Lauf VOR dem Termin
    # macht ihn fällig; ein Lauf GENAU zum Termin erfüllt ihn bis zum
    # nächsten Termin.
    settings = {**config.DEFAULT_SETTINGS,
                "daemon_verifikation_tag": "Freitag",
                "daemon_verifikation_zeit": "23:00"}
    plan = daemon.zeitplan(settings)
    jetzt = datetime(2026, 9, 23, 12, 0)               # Mittwoch
    frueher_lauf = datetime(2026, 9, 17, 12, 0)        # vor Fr 18.09. 23:00
    assert daemon.faellig("verifikation",
                          frueher_lauf.isoformat(), jetzt, plan) is True
    # Lauf genau zum Termin erfüllt ihn bis zum nächsten Termin:
    termin_lauf = datetime(2026, 9, 18, 23, 0)
    assert daemon.faellig("verifikation",
                          termin_lauf.isoformat(), jetzt, plan) is False
    zwischen = datetime(2026, 9, 21, 12, 0)            # vor Fr 25.09. 23:00
    assert daemon.faellig("verifikation",
                          termin_lauf.isoformat(), zwischen, plan) is False
    danach = datetime(2026, 9, 26, 12, 0)              # nach Fr 25.09. 23:00
    assert daemon.faellig("verifikation",
                          termin_lauf.isoformat(), danach, plan) is True
