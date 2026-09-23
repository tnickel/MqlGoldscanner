# -*- coding: utf-8 -*-
"""Stufe-7-Tests: Wochen-Summenwert, Was-wäre-wenn-Simulation, REST-API."""
from __future__ import annotations

import json
import math
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from goldscanner import config, rest_api
from goldscanner.db import Db
from goldscanner.modell import szenario


def _bar(tag: str, hoch=100.0, tief=90.0, close=95.0):
    return {"time": int(datetime.fromisoformat(f"{tag}T00:00:00+00:00").timestamp()),
            "open": 95.0, "high": hoch, "low": tief, "close": close, "volumen": 0}


# ── Wochen-Summenwert ───────────────────────────────────────────────────────

def test_wochen_summenwert_mathematik():
    matrix = {"tage": [{"p_stat": 0.5}, {"p_stat": 0.5}]}
    # Unabhängig: 1 − 0,5·0,5 = 0,75
    erg = szenario.wochen_summenwert(matrix, d1=[], k=1.0)
    assert erg["p_mindestens_ein_modell"] == pytest.approx(0.75)
    assert erg["n_tage_modell"] == 2
    # Grenzen: P=1 überall → 1; P=0 überall → 0
    assert szenario.wochen_summenwert(
        {"tage": [{"p_stat": 1.0}, {"p_stat": 1.0}]}, [])["p_mindestens_ein_modell"] == 1.0
    assert szenario.wochen_summenwert(
        {"tage": [{"p_stat": 0.0}]}, [])["p_mindestens_ein_modell"] == 0.0
    # ohne Modell-P → None
    assert szenario.wochen_summenwert({"tage": [{"p_klima": 0.4}]}, []) is None


def test_wochen_summenwert_klima_basisrate():
    # Synthetische Historie: 130 Tage (26 Wochen), Bewegungstag-Muster
    d1 = []
    tag0 = datetime(2026, 1, 5).date()          # Montag
    for i in range(130):
        d = tag0 + timedelta(days=i)
        if d.weekday() > 4:
            continue                              # nur Handelstage zählen nicht nötig —
        bewegung = (i % 3 == 0)                   # jeder dritte Tag ist Bewegungstag
        if bewegung:
            d1.append(_bar(d.isoformat(), hoch=120, tief=80, close=100))
        else:
            d1.append(_bar(d.isoformat(), hoch=102, tief=98, close=100))
    matrix = {"tage": [{"p_stat": 0.3}, {"p_stat": 0.3}]}
    erg = szenario.wochen_summenwert(matrix, d1=d1, k=1.0)
    assert 0.0 < erg["p_mindestens_ein_klima"] <= 1.0
    assert erg["n_wochen_schaetzung"] and erg["n_wochen_schaetzung"] > 10


# ── Was-wäre-wenn ───────────────────────────────────────────────────────────

def test_was_waere_wenn_nuetzt_unveraendert():
    mu, sigma = 0.0, 0.2
    ln_b = math.log(0.02)
    basis = szenario.was_waere_wenn({"d": (mu, sigma)}, {"d": ln_b})
    verschoben = szenario.was_waere_wenn({"d": (mu, sigma)}, {"d": ln_b},
                                         vola_shift_pct=0, mu_shift_pct=0,
                                         event_zuschlag_pp=0)
    assert basis == verschoben                     # alles 0 → identisch


def test_was_waere_wenn_richtung_der_effekte():
    mu, sigma = math.log(0.010), 0.5               # 1 % erwartete Tagesrange
    ln_b = math.log(0.012)                          # Schwelle ÜBER Erwartung (p<0,5)
    p0 = szenario.was_waere_wenn({"d": (mu, sigma)}, {"d": ln_b})["d"]
    assert 0.2 < p0 < 0.5                           # realistischer Bereich
    p_vola = szenario.was_waere_wenn({"d": (mu, sigma)}, {"d": ln_b},
                                     vola_shift_pct=50)["d"]
    p_mu = szenario.was_waere_wenn({"d": (mu, sigma)}, {"d": ln_b},
                                   mu_shift_pct=50)["d"]
    p_event = szenario.was_waere_wenn({"d": (mu, sigma)}, {"d": ln_b},
                                      event_zuschlag_pp=15)["d"]
    assert p_vola > p0                              # mehr Vola → Richtung 0,5 → p steigt
    assert p_mu > p0                                # höhere Range → eher über Schwelle
    assert p_event == pytest.approx(min(p0 + 0.15, 1.0))


# ── REST-API ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rest_server():
    server = rest_api.RestServer(18606).start()
    yield server
    server.httpd.shutdown()


def _get(port: int, pfad: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{pfad}", timeout=5) as r:
        return r.status, r.read()


def test_rest_health_und_status(rest_server):
    code, body = _get(rest_server.port, "/health")
    assert code == 200 and json.loads(body)["ok"] is True
    code, body = _get(rest_server.port, "/status")
    daten = json.loads(body)
    assert daten["app"] == config.APP_NAME
    assert "db" in daten and "daemon" in daten


def test_rest_matrix_und_csv(rest_server, tmp_path):
    # Matrix in die echte DB schreiben? Nein — /matrix liest prognose_letzte
    # der konfigurierten DB. Im Test-Kontext: nur Statuscodes prüfen.
    code, body = _get(rest_server.port, "/matrix")
    assert code == 200 or code == 503               # je nach DB-Stand beides ok
    if code == 200:
        assert "matrix" in json.loads(body)
    code, body = _get(rest_server.port, "/prognose.csv")
    assert code in (200, 503)
    # unbekannter Pfad → 404
    try:
        _get(rest_server.port, "/gibtsnicht")
        assert False, "404 erwartet"
    except urllib.error.HTTPError as exc:
        assert exc.code == 404


def test_rest_nur_localhost(rest_server):
    # Der Server-Socket darf nicht 0.0.0.0 sein
    host, port = rest_server.httpd.server_address[:2]
    assert host == "127.0.0.1"
