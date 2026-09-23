# -*- coding: utf-8 -*-
"""Kalender-Adapter-Tests: Parsing mit realen Format-Fixtures (aus den
Deep-Research-Berichten), Zeitzone-Normalisierung, Dedup, Klassifizierung."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from goldscanner.adapter.kalender import (dedup_ereignisse, fed_events,
                                          ff_events, ics_events,
                                          klassifiziere, treasury_events,
                                          PRIO_BLS, PRIO_FF)

FF_JSON = """[
 {"title":"Nonfarm Payrolls","country":"USD","date":"2026-10-02T08:30:00-04:00",
  "impact":"High","forecast":"140K","previous":"150K"},
 {"title":"Rightmove HPI m/m","country":"GBP","date":"2026-09-21T00:01:00+01:00",
  "impact":"Low","forecast":"","previous":"-2.0%"},
 {"title":"German Flash Manufacturing PMI","country":"EUR",
  "date":"2026-09-24T04:30:00-04:00","impact":"High","forecast":"","previous":""}
]"""

BLS_ICS = """BEGIN:VCALENDAR
PRODID:-//Department of Labor//Bureau of Labor Statistics//EN
BEGIN:VEVENT
SUMMARY:Employment Situation (NFP)
DTSTART;TZID=US-Eastern:20261002T083000
END:VEVENT
BEGIN:VEVENT
SUMMARY:Consumer Price Index
DTSTART;TZID=US-Eastern:20261013T083000
END:VEVENT
BEGIN:VEVENT
SUMMARY:Something Without Time
DTSTART;VALUE=DATE:20261119
END:VEVENT
END:VCALENDAR"""

FED_JSON = ('﻿{"events":['
            '{"title":"FOMC Meeting","month":"2026-10","days":"27-28","time":"","type":"FOMC"},'
            '{"title":"Speech - Governor","month":"2026-09","days":"23",'
            '"time":"10:05 a.m.","type":"Speeches"}]}')

TREASURY_JSON = """[
 {"cusip":"A","securityType":"Note","securityTerm":"10-Year",
  "auctionDate":"2026-09-23T00:00:00"},
 {"cusip":"B","securityType":"Note","securityTerm":"2-Year",
  "auctionDate":"2026-09-22T00:00:00"},
 {"cusip":"C","securityType":"FRN","securityTerm":"2-Year",
  "auctionDate":"2026-09-24T00:00:00"},
 {"cusip":"D","securityType":"BILL","securityTerm":"26-Week",
  "auctionDate":"2026-09-25T00:00:00"}
]"""


def test_ff_parsing_und_filter():
    events = ff_events(FF_JSON)
    titel = [e["titel"] for e in events]
    assert "Nonfarm Payrolls" in titel
    assert "German Flash Manufacturing PMI" in titel      # High-Impact EUR bleibt
    assert "Rightmove HPI m/m" not in titel                # GBP/Low gefiltert
    nfp = events[0]
    assert nfp["zeit_utc"] == "2026-10-02T12:30:00+00:00"  # EDT → UTC
    assert nfp["datum"] == "2026-10-02"
    assert nfp["klasse"] == "nfp" and nfp["gold_relevanz"] == 5
    assert nfp["forecast"] == "140K" and nfp["previous"] == "150K"


def test_ics_parsing_und_zonen():
    events = ics_events(BLS_ICS, "bls", PRIO_BLS)
    nfp = [e for e in events if "Employment" in e["titel"]][0]
    assert nfp["zeit_utc"] == "2026-10-02T12:30:00+00:00"  # US-Eastern ≈ NY
    cpi = [e for e in events if "Consumer Price" in e["titel"]][0]
    assert cpi["klasse"] == "cpi" and cpi["gold_relevanz"] == 5
    ohne_zeit = [e for e in events if "Without Time" in e["titel"]][0]
    assert ohne_zeit["zeit_utc"] is None
    assert ohne_zeit["datum"] == "2026-11-19"


def test_fed_parsing_mit_bom_und_uhrzeiten():
    events = fed_events(FED_JSON)
    fomc = [e for e in events if "FOMC" in e["titel"]][0]
    rede = [e for e in events if "Speech" in e["titel"]][0]
    assert fomc["datum"] == "2026-10-27" and fomc["zeit_utc"] is None  # mehrtägig → 1. Tag
    assert rede["datum"] == "2026-09-23"
    assert rede["zeit_utc"] == "2026-09-23T14:05:00+00:00"            # 10:05 a.m. ET


def test_treasury_filter_nur_notes_bonds():
    events = treasury_events(TREASURY_JSON)
    assert len(events) == 2                                 # FRN + BILL raus
    zehn = [e for e in events if "10-Year" in e["titel"]][0]
    assert zehn["datum"] == "2026-09-23" and zehn["zeit_utc"] is None


def test_dedup_ff_gewinnt_gegen_bls():
    ff = ff_events(FF_JSON)
    bls = ics_events(BLS_ICS, "bls", PRIO_BLS)
    kombiniert = dedup_ereignisse(ff + bls)
    nfp_treffer = [e for e in kombiniert if e.get("klasse") == "nfp"
                   and e["datum"] == "2026-10-02"]
    assert len(nfp_treffer) == 1                            # Dublette eingesammelt
    assert nfp_treffer[0]["quelle"] == "ff"                 # höhere Priorität
    assert nfp_treffer[0]["forecast"] == "140K"             # FF bringt Werte mit


def test_klassifizierung():
    assert klassifiziere("Core CPI m/m") == ("cpi", 3, 5)
    assert klassifiziere("Fed Chair Powell Speaks") == ("fed_rede", 2, 4)
    assert klassifiziere("Initial Jobless Claims")[0] == "claims"
    assert klassifiziere("Irgendein Event") == ("sonstiges", 1, 1)
