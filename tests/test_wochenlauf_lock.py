# -*- coding: utf-8 -*-
"""Regressionsschutz für den GUI-Crash vom 23.09.2026:
NameError 'config' in wochenlauf.starten — das Lock referenzierte
config.DATA_DIR, obwohl config auf Modulebene nicht importiert war
(nur lokal in _client_bauen). Der Test übt den ECHTEN Lock-Pfad von
starten() mit gemocktem Innenteil — egal, was starten intern sonst
importiert, fehlende Modul-Globals fliegen hier sofort auf."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import goldscanner.wochenlauf as wochenlauf  # noqa: E402


def test_starten_lock_pfad_ohne_nameerror(monkeypatch):
    gesehen = []

    def fake_intern(db, settings, fortschritt=None):
        gesehen.append(fortschritt)
        return {"ok": True, "fake": True}

    monkeypatch.setattr(wochenlauf, "_starten_intern", fake_intern)
    ergebnis = wochenlauf.starten(None, {})
    assert ergebnis == {"ok": True, "fake": True}
    assert gesehen == [None]                 # Callback optional, Lauf läuft


def test_starten_reicht_fortschritt_durch(monkeypatch):
    gesehen = []

    def fake_intern(db, settings, fortschritt=None):
        gesehen.append(fortschritt)
        return {"ok": True}

    monkeypatch.setattr(wochenlauf, "_starten_intern", fake_intern)
    callback = lambda station, text=None: None
    wochenlauf.starten(None, {}, fortschritt=callback)
    assert gesehen == [callback]             # Callback wandert bis nach innen


def test_starten_meldet_sperrung_sauber(monkeypatch, tmp_path):
    from goldscanner.lock import lauf_lock
    monkeypatch.setattr(wochenlauf.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(wochenlauf, "_starten_intern",
                        lambda db, settings: pytest.fail("darf nicht laufen"))
    with lauf_lock(tmp_path, "job_wochenlauf"):
        ergebnis = wochenlauf.starten(None, {})
    assert "sperrung" in ergebnis
    assert ergebnis["matrix"]["ok"] is False
