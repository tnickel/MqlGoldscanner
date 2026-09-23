# -*- coding: utf-8 -*-
"""Daemon (S6): läuft getrennt von der UI und fährt den Rhythmus aus
Konzept §10 — Herzschlag in die DB, Merker gegen Wiederholung, Lock gegen
GUI-Doppelläufe, kooperativer Stopp über eine Stop-Datei.

Rhythmus:
- Scout       So 17:00  (Quellen-Vorschläge)
- Wochenlauf  So 18:00  (komplett inkl. KI-Fusion, PDF, MT5-Export)
- Tageslauf   tägl. 06:30  (Kurse, Kalender, Actuals)
- Verifikation Sa 09:00  (Prognose → Realität, Track-Record füllen)

Start:  python -m goldscanner.betrieb.daemon   (aus src/)
Stopp:  Datei data/daemon.stop anlegen (UI-Button) — Daemon beendet sich
        beim nächsten Schleifendurchlauf (≤ 30 s) sauber.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from .. import config
from ..db import Db
from ..lock import LockBesetzt, lauf_lock

STOP_DATEI = config.DATA_DIR / "daemon.stop"
PID_DATEI = config.DATA_DIR / "daemon.pid"
LOG_DATEI = config.DATA_DIR / "daemon.log"
HERZSCHLAG_S = 300
SCHLEIFE_S = 30

# job → (wochentag None=täglich, stunde, minute)
ZEITPLAN: dict[str, tuple[int | None, int, int]] = {
    "scout": (6, 17, 0),           # Sonntag 17:00
    "wochenlauf": (6, 18, 0),      # Sonntag 18:00
    "tageslauf": (None, 6, 30),    # täglich 06:30
    "verifikation": (5, 9, 0),     # Samstag 09:00
}


def _log(text: str) -> None:
    zeile = f"{datetime.now().isoformat(timespec='seconds')} {text}"
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DATEI, "a", encoding="utf-8") as handle:
            handle.write(zeile + "\n")
    except OSError:
        pass


def geplant_fuer(job: str, jetzt: datetime) -> datetime:
    """Letzter vergangener Termin des Jobs (<= jetzt)."""
    wt, stunde, minute = ZEITPLAN[job]
    kandidat = jetzt.replace(hour=stunde, minute=minute, second=0, microsecond=0)
    if wt is not None:
        while kandidat.weekday() != wt:
            kandidat -= timedelta(days=1)
    schritt = timedelta(days=1 if wt is None else 7)
    while kandidat > jetzt:
        kandidat -= schritt
    while kandidat + schritt <= jetzt:
        kandidat += schritt
    return kandidat


def faellig(job: str, zuletzt: str | None, jetzt: datetime) -> bool:
    """True, wenn der Termin seit dem letzten Lauf erreicht wurde."""
    termin = geplant_fuer(job, jetzt)
    if zuletzt is None:
        # Beim ersten Start: nur nachholen, wenn der Termin heute war
        return jetzt - termin < timedelta(hours=6)
    try:
        letzter = datetime.fromisoformat(zuletzt)
    except ValueError:
        return True
    return letzter < termin


# ── Jobs ───────────────────────────────────────────────────────────────────

def job_tageslauf(db, settings: dict) -> str:
    from ..adapter import kalender
    from ..adapter import actuals
    from ..mt5 import kurse
    info = []
    ergebnis = kurse.kurse_holen(settings)
    if ergebnis.get("ok"):
        neu = sum(db.raten_speichern(ergebnis["symbol"], tf, bars)
                  for tf, bars in ergebnis["raten"].items())
        info.append(f"kurse+{neu}")
    else:
        info.append("kurse=fehler")
    prot = kalender.wochenabruf(db, settings)
    info.append(f"kalender={'ok' if prot.get('ok') else 'teilweise'}")
    try:  # Actuals sind Bonus, nie fatal (Exporter-CSV falls vorhanden)
        ergebnis_a = actuals.mt5_actuals_einlesen(db)
        info.append(f"actuals={'ok' if ergebnis_a.get('ok') else 'nein'}")
    except Exception as exc:
        info.append(f"actuals={type(exc).__name__}")
    return " · ".join(info)


def job_wochenlauf(db, settings: dict) -> str:
    from ..wochenlauf import starten
    prot = starten(db, settings)
    return (f"matrix={prot.get('matrix', {}).get('modell', '?')} · "
            f"fusion={'ok' if prot.get('llm', {}).get('ok') else 'aus'} · "
            f"pdf={'ok' if prot.get('pdf', {}).get('ok') else 'aus'}")


def job_verifikation(db, settings: dict) -> str:
    from . import verifikation
    prot = verifikation.nachziehen(db, settings)
    return (f"neu={prot.get('neu', 0)} · ohne_prognose="
            f"{prot.get('ohne_prognose', 0)}")


def job_scout(db, settings: dict) -> str:
    from . import scout
    prot = scout.suche(db, settings)
    return f"vorschlaege={prot.get('neu', 0)} (domains {prot.get('domains', 0)})"


JOBS = {"tageslauf": job_tageslauf, "wochenlauf": job_wochenlauf,
        "verifikation": job_verifikation, "scout": job_scout}


def hauptschleife() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_DATEI.write_text(str(os.getpid()), encoding="utf-8")
    if STOP_DATEI.exists():
        STOP_DATEI.unlink()
    db = Db()
    settings = config.load_settings()
    _log("Daemon gestartet (PID "
         f"{os.getpid()}), Zeitplan: {', '.join(ZEITPLAN)}")
    db.daemon_status_schreiben("daemon", True, "gestartet")
    letzter_herzschlag = 0.0
    try:
        while True:
            if STOP_DATEI.exists():
                STOP_DATEI.unlink()
                _log("Kooperativer Stopp empfangen — Daemon beendet sich.")
                db.daemon_status_schreiben("daemon", True, "gestoppt (kooperativ)")
                break
            jetzt = datetime.now()
            zeiten = db.daemon_zeiten()
            for job, fn in JOBS.items():
                if not faellig(job, zeiten.get(job), jetzt):
                    continue
                _log(f"Job {job} startet …")
                try:
                    with lauf_lock(config.DATA_DIR, f"job_{job}"):
                        info = fn(db, config.load_settings())
                    db.daemon_zeit_setzen(job)
                    db.daemon_status_schreiben(job, True, info)
                    _log(f"Job {job} ok: {info}")
                except LockBesetzt as exc:
                    _log(f"Job {job} übersprungen (Lock): {exc}")
                    db.daemon_zeit_setzen(job)      # nicht dauernd wiederholen
                except Exception as exc:
                    db.daemon_status_schreiben(job, False,
                                               f"{type(exc).__name__}: {exc}")
                    _log(f"Job {job} FEHLER: {exc}\n{traceback.format_exc()}")
                    db.daemon_zeit_setzen(job)
            if time.monotonic() - letzter_herzschlag > HERZSCHLAG_S:
                db.daemon_status_schreiben("herzschlag", True,
                                           f"pid={os.getpid()}")
                letzter_herzschlag = time.monotonic()
            time.sleep(SCHLEIFE_S)
    finally:
        try:
            PID_DATEI.unlink()
        except OSError:
            pass
        db.close()


# ── Steuerung aus der UI ───────────────────────────────────────────────────

def laeuft() -> bool:
    try:
        pid = int(PID_DATEI.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    from ..lock import _pid_lebt
    return _pid_lebt(pid)


def starte_detached() -> bool:
    """Daemon als unabhängigen Prozess starten (überlebt UI-Schließung)."""
    if laeuft():
        return False
    creationflags = 0
    if sys.platform == "win32":
        creationflags = (subprocess.DETACHED_PROCESS
                         | subprocess.CREATE_NEW_PROCESS_GROUP
                         | subprocess.CREATE_NO_WINDOW)
    log = open(LOG_DATEI, "a", encoding="utf-8")
    subprocess.Popen(
        [sys.executable, "-m", "goldscanner.betrieb.daemon"],
        cwd=str(config.SRC), stdout=log, stderr=log,
        creationflags=creationflags, close_fds=True)
    log.close()
    return True


def stoppe() -> bool:
    """Kooperativer Stopp (Stop-Datei); True wenn ein Daemon lief."""
    if not laeuft():
        return False
    STOP_DATEI.parent.mkdir(parents=True, exist_ok=True)
    STOP_DATEI.write_text("stopp", encoding="utf-8")
    return True


def status() -> dict:
    """Für die UI: läuft, PID, letzter Herzschlag, letzte Jobs."""
    db = Db()
    try:
        zeilen = db.daemon_letzter_status(12)
        zeiten = db.daemon_zeiten()
    finally:
        db.close()
    herz = next((z for z in zeilen if z["job"] in ("herzschlag", "daemon")), None)
    alter_s = None
    if herz:
        try:
            alter_s = (datetime.now()
                       - datetime.fromisoformat(herz["zeit"])).total_seconds()
        except ValueError:
            pass
    return {"laeuft": laeuft(), "herzschlag_alt_s": alter_s,
            "zeilen": zeilen, "zeiten": zeiten}


if __name__ == "__main__":
    hauptschleife()
