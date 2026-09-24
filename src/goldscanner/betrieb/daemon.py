"""Daemon (S6): läuft getrennt von der UI und fährt den Rhythmus aus
Konzept §10 — Herzschlag in die DB, Merker gegen Wiederholung, Lock gegen
GUI-Doppelläufe, kooperativer Stopp über eine Stop-Datei.

Rhythmus (Wochentage/Uhrzeiten konfigurierbar — Automatik-Seite bzw.
app_settings.json, Keys daemon_*_tag/_zeit):
- Scout       So 17:00  (Quellen-Vorschläge)
- Wochenlauf  So 18:00  (komplett inkl. KI-Fusion, PDF, MT5-Export)
- Tageslauf   tägl. 06:30  (Kurse, Kalender, Actuals)
- Verifikation Sa 09:00  (Prognose → Realität, Wochen-Score 0-100,
                          LLM-Review; Lessons fließen in die Sonntags-
                          Fusion ein)

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

from .. import config
from ..db import Db
from ..lock import LockBesetzt, lauf_lock

STOP_DATEI = config.DATA_DIR / "daemon.stop"
PID_DATEI = config.DATA_DIR / "daemon.pid"
LOG_DATEI = config.DATA_DIR / "daemon.log"
HERZSCHLAG_S = 300
SCHLEIFE_S = 30

WOCHENTAGE = {"Montag": 0, "Dienstag": 1, "Mittwoch": 2, "Donnerstag": 3,
              "Freitag": 4, "Samstag": 5, "Sonntag": 6}
# Alias → (Setting-Tag, Setting-Uhrzeit, Default-Tag, Default-Zeit);
# tageslauf hat keinen Wochentag (läuft täglich).
_ZEIT_KEYS = {
    "scout": ("daemon_scout_tag", "daemon_scout_zeit", "Sonntag", "17:00"),
    "wochenlauf": ("daemon_wochenlauf_tag", "daemon_wochenlauf_zeit",
                   "Sonntag", "18:00"),
    "verifikation": ("daemon_verifikation_tag", "daemon_verifikation_zeit",
                     "Samstag", "09:00"),
}


def _log(text: str) -> None:
    zeile = f"{datetime.now().isoformat(timespec='seconds')} {text}"
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DATEI, "a", encoding="utf-8") as handle:
            handle.write(zeile + "\n")
    except OSError:
        pass


def _stunde_minute(zeit: str, fallback: str) -> tuple[int, int]:
    try:
        teile = str(zeit).strip().split(":")
        return int(teile[0]), int(teile[1])
    except (ValueError, IndexError, AttributeError):
        teile = fallback.split(":")
        return int(teile[0]), int(teile[1])


def zeitplan(settings: dict | None = None) -> dict[str, tuple[int | None, int, int]]:
    """job → (wochentag None=täglich, stunde, minute) — aus den Settings
    (Wochentag als Wort, Zeit 'HH:MM'); ungültige Werte fallen auf die
    Defaults zurück. Wird je Daemon-Loop neu gelesen, damit Änderungen
    aus der Automatik-Seite ohne Neustart greifen."""
    settings = settings if settings is not None else config.load_settings()
    plan: dict[str, tuple[int | None, int, int]] = {
        "tageslauf": (None, *_stunde_minute(
            settings.get("daemon_tageslauf_zeit", "06:30"), "06:30")),
    }
    defaults = config.DEFAULT_SETTINGS
    for job, (key_tag, key_zeit, def_tag, def_zeit) in _ZEIT_KEYS.items():
        tag = str(settings.get(key_tag, def_tag)).strip()
        wt = WOCHENTAGE.get(tag.capitalize())
        if wt is None:                      # Tippfehler → Default-Tag
            wt = WOCHENTAGE[str(defaults[key_tag])]
        h, m = _stunde_minute(settings.get(key_zeit, def_zeit), def_zeit)
        plan[job] = (wt, h, m)
    return plan


def geplant_fuer(job: str, jetzt: datetime,
                 plan: dict | None = None) -> datetime:
    """Letzter vergangener Termin des Jobs (<= jetzt)."""
    wt, stunde, minute = (plan or zeitplan())[job]
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


def faellig(job: str, zuletzt: str | None, jetzt: datetime,
            plan: dict | None = None) -> bool:
    """True, wenn der Termin seit dem letzten Lauf erreicht wurde."""
    termin = geplant_fuer(job, jetzt, plan)
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
    from . import auswertung, verifikation
    prot = verifikation.nachziehen(db, settings)
    aus = auswertung.laeuft(db, settings)
    info = (f"neu={prot.get('neu', 0)} · ohne_prognose="
            f"{prot.get('ohne_prognose', 0)}")
    if aus.get("score_letzte") is not None:
        info += (f" · wochenscore={aus['score_letzte']}/100"
                 f" · review={'ok' if aus.get('review_ok') else 'aus'}")
    else:
        info += " · auswertung=" + ("keine bewertbare Woche"
                                    if aus.get("ok") else str(aus.get("grund", "?")))
    return info


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
         f"{os.getpid()}), Zeitplan: {', '.join(zeitplan(settings))}")
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
            settings = config.load_settings()   # je Loop: UI-Änderungen greifen
            plan = zeitplan(settings)
            zeiten = db.daemon_zeiten()
            for job, fn in JOBS.items():
                if not faellig(job, zeiten.get(job), jetzt, plan):
                    continue
                _log(f"Job {job} startet …")
                try:
                    # wochenlauf.starten() nimmt sein Lock selbst (ein Lock
                    # hier UND dort wäre verschachtelt und kollidiert mit
                    # sich selbst); alle anderen Jobs lockt der Loop.
                    if job == "wochenlauf":
                        info = fn(db, config.load_settings())
                    else:
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
    # Handle bewusst OHNE with: der Daemon-Prozess erbt ihn und schreibt
    # weiter, das Elternteil gibt ihn nach dem Popen ab (kein Leak).
    log = open(LOG_DATEI, "a", encoding="utf-8")  # noqa: SIM115
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
