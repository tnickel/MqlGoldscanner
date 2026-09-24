# -*- coding: utf-8 -*-
"""Deployment: MqlGoldscanner -> Zielrechner ZIELRECHNER (C:\\Forex\\MqlGoldscanner).

Analog zum KiScanner-Deploy (dort scripts/deploy_ns1mqsv.py), ergaenzt um:

  - Daemon-Autostart (Wochenlauf/Verifikation/Tageslauf laufen dort von
    selbst via goldscanner.betrieb.daemon, detached)
  - Geplante Tasks OHNE Zeitlimit (Register-ScheduledTask mit
    ExecutionTimeLimit 0 — schtasks-Default waere 72 h Killer) plus
    ONSTART-Varianten, damit beide Reboots ueberleben

Schritte: verbinden + Hostname-Absicherung -> Python sicherstellen ->
Code/config/Datenbank-Sync (SQLite via backup-API, konsistent auch bei
laufender App) -> Ziel-Settings patchen (Default-Attach ans laufende
Vantage-Terminal, NIEMALS Selbststart: dort haengt eine Live-Bridge dran)
-> .venv + requirements -> App + Daemon starten -> Health pruefen.

Aufruf:  python scripts/deploy_ns1mqsv.py [--code-only] [--kein-start]
Zugang:  config/deploy.local.json (gitignored) oder
         Env DEPLOY_HOST / DEPLOY_USER / DEPLOY_PASSWORD.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy-cache" / "python-3.12.10-amd64.exe"
INSTALLER_URL = ("https://www.python.org/ftp/python/3.12.10/"
                 "python-3.12.10-amd64.exe")
ERWARTETER_HOSTNAME = "ZIELRECHNER"

CODE_ORDNER_AUS = {".git", "__pycache__", ".venv", "deploy-cache", "data",
                   "node_modules", ".pytest_cache", ".ruff_cache",
                   ".agents", ".claude", ".vscode", "research"}
CODE_ENDUNGEN_AUS = {".pyc", ".pyo", ".log", ".tmp", ".pdf"}
CODE_DATEIEN_AUS = {"deploy.local.json", "scratch_probeziel.py"}
DB_NAME = "goldscanner.db"


def _log(schritt: str, text: str) -> None:
    print(f"[{schritt}] {text}", flush=True)


def lade_zugang() -> dict:
    pfad = ROOT / "config" / "deploy.local.json"
    daten = json.loads(pfad.read_text(encoding="utf-8")) if pfad.exists() else {}
    zugang = {
        "host": os.environ.get("DEPLOY_HOST", daten.get("host", "")),
        "user": os.environ.get("DEPLOY_USER", daten.get("user", "")),
        "password": os.environ.get("DEPLOY_PASSWORD", daten.get("password", "")),
        "ziel": daten.get("ziel", r"ZIELORDNER"),
        "hostname_erwartet": daten.get("hostname_erwartet",
                                       ERWARTETER_HOSTNAME),
    }
    fehlt = [k for k in ("host", "user", "password") if not zugang[k]]
    if fehlt:
        raise SystemExit(f"Zugangsdaten unvollstaendig ({', '.join(fehlt)}): "
                         f"{pfad} anlegen oder Env-Variablen setzen.")
    return zugang


class Ziel:
    def __init__(self, zugang: dict):
        self.zugang = zugang
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(zugang["host"], username=zugang["user"],
                         password=zugang["password"], timeout=15)
        self.sftp = self.ssh.open_sftp()
        self.ziel = zugang["ziel"].replace("\\", "/")

    def run(self, befehl: str, timeout: int = 120) -> tuple[str, str, int]:
        _, out, err = self.ssh.exec_command(befehl, timeout=timeout)
        exit_code = out.channel.recv_exit_status()
        return (out.read().decode("utf-8", errors="replace"),
                err.read().decode("utf-8", errors="replace"),
                exit_code)

    def ps(self, skript: str, timeout: int = 120) -> tuple[str, str, int]:
        kodiert = base64.b64encode(skript.encode("utf-16le")).decode("ascii")
        return self.run(f"powershell -NoProfile -NonInteractive "
                        f"-EncodedCommand {kodiert}", timeout=timeout)

    def mkdir_p(self, pfad: str) -> None:
        aktuell = ""
        for teil in pfad.strip("/").split("/"):
            aktuell += ("/" + teil) if (aktuell or ":" not in teil) else teil
            try:
                self.sftp.stat(aktuell)
            except FileNotFoundError:
                self.sftp.mkdir(aktuell)

    def _put_neu(self, lokal: Path, remote: str) -> bool:
        try:
            st = self.sftp.stat(remote)
            if (st.st_size == lokal.stat().st_size
                    and int(st.st_mtime) == int(lokal.stat().st_mtime)):
                return False
        except FileNotFoundError:
            pass
        self.sftp.put(str(lokal), remote)
        self.sftp.utime(remote, (lokal.stat().st_mtime, lokal.stat().st_mtime))
        return True

    def sync_ordner(self, lokal: Path, remote: str,
                    ordner_aus: set[str] | None = None,
                    endungen_aus: set[str] | None = None,
                    dateien_aus: set[str] | None = None) -> tuple[int, int]:
        ordner_aus = ordner_aus or set()
        endungen_aus = endungen_aus or set()
        dateien_aus = dateien_aus or set()
        self.mkdir_p(remote)
        hochgeladen = geprueft = 0
        for eintrag in sorted(lokal.iterdir()):
            if eintrag.name in ordner_aus or eintrag.name in dateien_aus:
                continue
            ziel_pfad = f"{remote}/{eintrag.name}"
            if eintrag.is_dir():
                h, g = self.sync_ordner(eintrag, ziel_pfad, ordner_aus,
                                        endungen_aus, dateien_aus)
                hochgeladen += h
                geprueft += g
            elif eintrag.suffix.lower() not in endungen_aus:
                geprueft += 1
                if self._put_neu(eintrag, ziel_pfad):
                    hochgeladen += 1
        return hochgeladen, geprueft

    def close(self) -> None:
        try:
            self.sftp.close()
        finally:
            self.ssh.close()


def hostname_absichern(ziel: Ziel) -> None:
    out, _, _ = ziel.run("hostname")
    name = out.strip().upper()
    erwartet = ziel.zugang["hostname_erwartet"].upper()
    if name != erwartet:
        raise SystemExit(f"ABBRUCH — falscher Rechner! '{name}' != '{erwartet}'.")


def python_sicherstellen(ziel: Ziel) -> str:
    """Kandidat-Pfad VOR PATH pruefen (SSH-Dienste sehen HKCU-Aenderungen
    evtl. erst nach Dienst-Neustart)."""
    kandidat = ("C:/Users/" + ziel.zugang["user"]
                + "/AppData/Local/Programs/Python/Python312/python.exe")
    try:
        ziel.sftp.stat(kandidat)
        out, _, _ = ziel.run(f'"{kandidat}" --version')
        _log("python", f"vorhanden: {out.strip()}")
        return kandidat
    except FileNotFoundError:
        pass
    out, _, _ = ziel.ps("$ErrorActionPreference = 'SilentlyContinue'; "
                        "if (Get-Command python -ErrorAction SilentlyContinue) "
                        "{ & python -c 'import sys; print(sys.executable)'; "
                        "& python --version }")
    zeilen = [z.strip() for z in out.splitlines() if z.strip()]
    if zeilen and any(z.startswith("Python 3.1") for z in zeilen):
        _log("python", f"vorhanden: {zeilen[0]} ({zeilen[-1]})")
        return zeilen[0]
    if not INSTALLER.exists():
        raise SystemExit(f"Installer fehlt: {INSTALLER} — einmal laden: "
                         f"curl -L -o \"{INSTALLER}\" {INSTALLER_URL}")
    _log("python", "stiller Install 3.12.10 (per-user) …")
    remote_installer = "C:/Users/Public/python-3.12.10-amd64.exe"
    ziel.sftp.put(str(INSTALLER), remote_installer)
    ziel.run(f'"{remote_installer.replace("/", chr(92))}" /quiet '
             f"InstallAllUsers=0 PrependPath=1 Include_test=0 "
             f"Include_launcher=1", timeout=600)
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            ziel.sftp.stat(kandidat)
            break
        except FileNotFoundError:
            time.sleep(3)
    else:
        raise SystemExit("Python-Installation nach 300 s nicht fertig.")
    _log("python", f"installiert -> {kandidat}")
    return kandidat


def db_lokal_spiegeln() -> Path:
    quelle = ROOT / "data" / DB_NAME
    ziel_datei = ROOT / "deploy-cache" / DB_NAME
    ziel_datei.parent.mkdir(exist_ok=True)
    con_q = sqlite3.connect(quelle)
    con_z = sqlite3.connect(ziel_datei)
    with con_z:
        con_q.backup(con_z)
    con_q.close()
    con_z.close()
    return ziel_datei


def settings_patched() -> dict:
    settings = json.loads((ROOT / "config" / "app_settings.json")
                          .read_text(encoding="utf-8"))
    # Default-Attach ans dort laufende Vantage-Terminal (Live-Bridge!):
    # kein eigener Pfad, KEIN Selbststart — der Goldscanner beendet nur
    # selbst gestartete Terminals, attachen ist read-only sicher.
    settings["mt5_terminal_pfad"] = ""
    settings["mt5_start_erlauben"] = False
    _log("konfig", "mt5_terminal_pfad='' (Attach ans laufende Vantage-"
                   "Terminal), mt5_start_erlauben=False (Bridge-Schutz)")
    return settings


def sync(ziel: Ziel) -> None:
    ziel.mkdir_p(ziel.ziel)
    for ordner in ("src", "app_pages", "assets", "doc", "tests", "scripts",
                   "mql5", "config/prompts"):
        ziel.run(f'if exist "{ziel.ziel.replace("/", chr(92))}\\{ordner}" '
                 f'rmdir /s /q '
                 f'"{ziel.ziel.replace("/", chr(92))}\\{ordner}"')
    h, g = ziel.sync_ordner(ROOT, ziel.ziel, CODE_ORDNER_AUS,
                            CODE_ENDUNGEN_AUS, CODE_DATEIEN_AUS)
    _log("sync", f"Code/Doku/Exporter: {h} von {g} Dateien hochgeladen")

    ziel.mkdir_p(f"{ziel.ziel}/data")
    db_deploy = db_lokal_spiegeln()
    ziel.sftp.put(str(db_deploy), f"{ziel.ziel}/data/{DB_NAME}")
    _log("sync", f"{DB_NAME} ({db_deploy.stat().st_size / 1e6:.1f} MB, "
                 "konsistent gespiegelt; reports/runs/exports entstehen dort neu)")

    settings = settings_patched()
    patch_pfad = ROOT / "deploy-cache" / "app_settings.ziel.json"
    patch_pfad.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    ziel.sftp.put(str(patch_pfad), f"{ziel.ziel}/config/app_settings.json")
    secrets = ROOT / "config" / "secrets.local.json"
    if secrets.exists():
        ziel.sftp.put(str(secrets), f"{ziel.ziel}/config/secrets.local.json")
        _log("konfig", "app_settings (gepatcht) + secrets.local.json "
                       "uebertragen")


def venv_und_pakete(ziel: Ziel, python_exe: str) -> None:
    venv_py = f"{ziel.ziel}/.venv/Scripts/python.exe"
    try:
        ziel.sftp.stat(venv_py)
        _log("venv", "existiert schon")
    except FileNotFoundError:
        _log("venv", f"anlegen mit {python_exe} …")
        _, err, code = ziel.run(f'"{python_exe}" -m venv "{ziel.ziel}/.venv"',
                                timeout=300)
        if code != 0:
            raise SystemExit(f"venv-Anlage fehlgeschlagen: {err[:400]}")
    _log("pip", "installiere/aktualisiere Abhaengigkeiten …")
    _, err, code = ziel.run(
        f'"{venv_py}" -m pip install --upgrade pip '
        f'&& "{venv_py}" -m pip install -r "{ziel.ziel}/requirements.txt" '
        f'&& "{venv_py}" -m pip install "streamlit==1.63.0"',
        timeout=900)
    if code != 0:
        raise SystemExit(f"pip fehlgeschlagen: {err[-400:]}")
    out, err, _ = ziel.run(
        f'"{venv_py}" -m compileall -q "{ziel.ziel}/src" '
        f'"{ziel.ziel}/streamlit_app.py" && "{venv_py}" -c '
        '"import streamlit, plotly, MetaTrader5, reportlab, pandas; '
        "print('deps ok, streamlit', streamlit.__version__)\"",
        timeout=300)
    _log("smoke", out.strip()[-120:] or err.strip()[-200:])


def task_anlegen(ziel: Ziel, name: str, action: str, onstart: bool) -> None:
    """Geplanter Task OHNE Zeitlimit (72-h-Default wuerde die App killen).
    onstart=True: Autostart nach Reboot (Trading-Rechner)."""
    trigger = ("$t = New-ScheduledTaskTrigger -AtStartup"
               if onstart else
               "$t = New-ScheduledTaskTrigger -Once -At "
               "(Get-Date).AddMinutes(10)")
    skript = (
        f"$ErrorActionPreference = 'Stop'; {trigger}; "
        "$a = New-ScheduledTaskAction -Execute 'cmd.exe' "
        f"-Argument '/c {action}'; "
        "$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit "
        "(New-TimeSpan -Seconds 0) -AllowStartIfOnBatteries "
        "-DontStopIfGoingOnBatteries -StartWhenAvailable; "
        "Register-ScheduledTask -TaskName '" + name + "' -Action $a "
        "-Trigger $t -Settings $s -User '" + ziel.zugang["user"] + "' "
        "-Password '" + ziel.zugang["password"] + "' -Force | Out-Null; "
        "Write-Output 'angelegt'")
    out, err, _ = ziel.ps(skript, timeout=90)
    _log("task", f"{name}: {out.strip() or err.strip()[:200]}")


def daemon_starten(ziel: Ziel) -> None:
    """daemon.starte_detached() kapselt DETACHED_PROCESS — der Aufrufer
    endet sofort, der Daemon überlebt die SSH-Session."""
    venv_py = f"{ziel.ziel}/.venv/Scripts/python.exe"
    out, err, _ = ziel.run(
        f'"{venv_py}" -c "import sys; sys.path.insert(0, r\'{ziel.ziel}/src\'); '
        "from goldscanner.betrieb import daemon; "
        "print('gestartet' if daemon.starte_detached() else 'laeuft schon')\"",
        timeout=120)
    _log("daemon", out.strip() or err.strip()[:300])


def app_starten(ziel: Ziel) -> None:
    bat = ziel.ziel.replace("/", chr(92)) + "\\start.bat"
    task_anlegen(ziel, "MqlGoldscannerStart",
                 f'start "MqlGoldscanner" /min "{bat}"', onstart=False)
    task_anlegen(ziel, "MqlGoldscanner Autostart",
                 f'start "MqlGoldscanner" /min "{bat}"', onstart=True)
    ziel.run('schtasks /Run /TN "MqlGoldscannerStart"')
    deadline = time.time() + 420
    antwort = ""
    while time.time() < deadline:
        time.sleep(8)
        out, _, _ = ziel.ps(
            "$ErrorActionPreference = 'SilentlyContinue'; try { "
            "(Invoke-WebRequest -Uri 'http://127.0.0.1:8505"
            "/_stcore/health' -UseBasicParsing -TimeoutSec 4).Content } "
            "catch { 'warte' }")
        antwort = out.strip()
        if antwort == "ok":
            break
    _log("start", f"Streamlit 8505: {antwort}"
          + ("" if antwort == "ok" else
             " — nicht hochgekommen; dort start.bat-Fenster pruefen"))
    out, _, _ = ziel.ps(
        "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8606/health' "
        "-UseBasicParsing -TimeoutSec 5).StatusCode } catch { 'aus' }")
    _log("rest", f"REST 8606 /health: {out.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-only", action="store_true")
    parser.add_argument("--kein-start", action="store_true")
    args = parser.parse_args()

    zugang = lade_zugang()
    _log("verbinde", f"{zugang['user']}@{zugang['host']} …")
    ziel = Ziel(zugang)
    try:
        hostname_absichern(ziel)
        _log("verbinde", "Hostname-Bestaetigung: "
              + ziel.run("hostname")[0].strip())
        python_exe = ""
        if not args.code_only:
            python_exe = python_sicherstellen(ziel)
        sync(ziel)
        if not args.code_only:
            venv_und_pakete(ziel, python_exe)
        if not args.kein_start:
            daemon_starten(ziel)
            app_starten(ziel)
        _log("fertig", f"MqlGoldscanner liegt unter {zugang['ziel']} "
                       "(App 8505, REST 8606, Daemon automatisch).")
    finally:
        ziel.close()


if __name__ == "__main__":
    main()
