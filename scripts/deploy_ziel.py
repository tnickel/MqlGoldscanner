# -*- coding: utf-8 -*-
"""Deployment: MqlGoldscanner auf den konfigurierten Zielrechner.

Analog zum KiScanner-Deploy (dort scripts/deploy_ziel.py), ergaenzt um:

  - Daemon-Autostart (Wochenlauf/Verifikation/Tageslauf laufen dort von
    selbst via goldscanner.betrieb.daemon, detached)
  - Geplante Tasks OHNE Zeitlimit (Register-ScheduledTask mit
    ExecutionTimeLimit 0 — schtasks-Default waere 72 h Killer) plus
    ONSTART-Varianten, damit beide Reboots ueberleben

Schritte: verbinden + Hostname-Absicherung -> Python sicherstellen ->
Code/config/Datenbank-Sync (SQLite via backup-API, konsistent auch bei
laufender App) -> Ziel-Settings patchen (Default-Attach ans laufende
Broker-Terminal, NIEMALS Selbststart) -> .venv + requirements ->
App + Daemon starten -> Health pruefen.

Aufruf:  python scripts/deploy_ns1mqsv.py [--code-only] [--kein-start]
Zugang:  config/deploy.local.json (gitignored) mit host, user, password,
         ziel (Zielordner), hostname_erwartet (Falsch-Rechner-Schutz),
         ziel_user (Session, in der die Apps laufen sollen) und
         tools_python_pfad (portables Python am Ziel) — oder Env
         DEPLOY_HOST / DEPLOY_USER / DEPLOY_PASSWORD.
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
NUGET = ROOT / "deploy-cache" / "python-3.12.10.nupkg"
NUGET_URL = "https://www.nuget.org/api/v2/package/python/3.12.10"

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
        "ssh_key_pfad": daten.get("ssh_key_pfad", ""),
        "ziel": os.environ.get("DEPLOY_ZIEL", daten.get("ziel", "")),
        "hostname_erwartet": os.environ.get(
            "DEPLOY_HOSTNAME_ERWARTET", daten.get("hostname_erwartet", "")),
        "ziel_user": os.environ.get("DEPLOY_ZIEL_USER",
                                    daten.get("ziel_user", "")),
        "tools_python_pfad": daten.get("tools_python_pfad", ""),
    }
    key = ROOT / zugang["ssh_key_pfad"] if zugang["ssh_key_pfad"] else None
    if key and key.exists():
        zugang["password"] = ""          # Key-Auth: Passwort nicht noetig
    fehlt = [k for k in ("host", "user", "ziel", "hostname_erwartet",
                         "ziel_user", "tools_python_pfad") if not zugang[k]]
    if not zugang["password"] and not (key and key.exists()):
        fehlt.append("password ODER ssh_key_pfad")
    if fehlt:
        raise SystemExit(f"Zugangsdaten unvollstaendig ({', '.join(fehlt)}): "
                         f"{pfad} anlegen oder Env-Variablen setzen.")
    return zugang


class Ziel:
    def __init__(self, zugang: dict):
        self.zugang = zugang
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key_pfad = zugang.get("ssh_key_pfad") or ""
        key = (paramiko.Ed25519Key.from_private_key_file(
                   str(ROOT / key_pfad)) if key_pfad else None)
        self.ssh.connect(zugang["host"], username=zugang["user"],
                         pkey=key, password=zugang["password"] or None,
                         timeout=15)
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
            if eintrag.is_symlink():
                continue              # kaputte Repo-Symlinks (JAR-Reste)
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


def tools_python_sicherstellen(ziel: Ziel) -> str:
    """Portables Python am Ziel (NuGet-Paket, ausserhalb der
    Nutzerprofile — laeuft auch in der Session des Ziel-Users).

    NuGet statt python.org-Installer: der Bootstrapper sieht ein
    vorhandenes per-user-Python als 'bereits installiert' und tut dann
    still nichts. NuGet-Python bringt pip NICHT mit -> einmal
    ensurepip im Basis-Python, sonst bekommen die venvs kein pip."""
    tools_py = ziel.zugang["tools_python_pfad"].replace("\\", "/")
    out, _, _ = ziel.run(f'"{tools_py}" --version')
    if not out.strip().startswith("Python 3.1"):
        if not NUGET.exists():
            raise SystemExit(f"NuGet-Paket fehlt lokal: {NUGET} — einmal "
                             f'laden: curl -L -o "{NUGET}" {NUGET_URL}')
        _log("python", "entpacke portables Python (NuGet) …")
        ziel.sftp.put(str(NUGET), "C:/Users/Public/python.nupkg.zip")
        basis = tools_py.rsplit("/", 1)[0]
        ziel.ps(f"Remove-Item -Recurse -Force '{basis}', "
                f"'{basis}_tmp' -ErrorAction SilentlyContinue; "
                "Expand-Archive -Path C:\\Users\\Public\\python.nupkg.zip "
                f"-DestinationPath '{basis}_tmp' -Force; "
                f"Move-Item '{basis}_tmp\\tools\\*' '{basis}\\'; "
                f"Remove-Item -Recurse -Force '{basis}_tmp'",
                timeout=300)
        out, err, _ = ziel.run(f'"{tools_py}" --version')
        if not out.strip().startswith("Python"):
            raise SystemExit(f"Tools-Python laeuft nicht: {out.strip()} "
                             f"{err.strip()[:200]}")
    out, _, _ = ziel.run(f'"{tools_py}" -m pip --version')
    if "No module named pip" in out:
        _log("python", "pip fehlt im Basis-Python -> ensurepip …")
        ziel.run(f'"{tools_py}" -m ensurepip --upgrade', timeout=300)
    _log("python", f"bereit: {out.strip() or tools_py}")
    return tools_py


def rechte_setzen(ziel: Ziel) -> None:
    """Der Ziel-User braucht Vollzugriff auf Projekt und Python — beide
    liegen bewusst ausserhalb seines Nutzerprofils."""
    for pfad in (ziel.ziel,
                 ziel.zugang["tools_python_pfad"].replace("\\", "/")
                 .rsplit("/", 1)[0]):
        _, err, _ = ziel.run(
            f'icacls "{pfad.replace("/", chr(92))}" '
            f"/grant {ziel.zugang['ziel_user']}:(OI)(CI)F /T /C /Q",
            timeout=600)
        _log("rechte", f"{pfad} -> {ziel.zugang['ziel_user']} voll"
              + ("" if "fehler" not in (err or "").lower() else
                 f" (Hinweis: {err[:100]})"))


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
    # ATOMAR: erst unter Temp-Namen hochladen, dann tauschen. Ein SFTP-put
    # direkt auf die Zieldatei trunciert sie — scheitert der Upload (App/
    # Daemon haelt die Datei offen), bliebe eine KORRUPTEDB zurueck.
    tmp_remote = f"{ziel.ziel}/data/{DB_NAME}.upload_tmp"
    ziel_db = f"{ziel.ziel}/data/{DB_NAME}"
    try:
        ziel.sftp.put(str(db_deploy), tmp_remote)
        ziel.sftp.remove(ziel_db)          # scheitert, wenn Datei offen ist
        ziel.sftp.rename(tmp_remote, ziel_db)
        for suffix in ("-wal", "-shm"):
            try:
                ziel.sftp.remove(ziel_db + suffix)
            except FileNotFoundError:
                pass
        _log("sync", f"{DB_NAME} ({db_deploy.stat().st_size / 1e6:.1f} MB, "
                     "konsistent gespiegelt, atomar getauscht; reports/runs/"
                     "exports entstehen dort neu)")
    except OSError as exc:
        try:
            ziel.sftp.remove(tmp_remote)   # Halbupload weg, Original intakt
        except OSError:
            pass
        _log("sync", f"{DB_NAME} NICHT synchronisiert ({exc}) — am Ziel "
                     "laeuft die App/Daemon und haelt die Datei; DB-Sync "
                     "später wiederholen, wenn kein Lauf aktiv ist.")

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


def task_anlegen(ziel: Ziel, name: str, bat: str, onstart: bool) -> None:
    """Task ALS ZIEL-USER (Interactive ohne Passwort — laeuft in dessen
    Desktop-Session, solange er angemeldet ist). OHNE Zeitlimit: der
    schtasks-Default killt nach 72 h.

    Die .bat wird DIREKT als Execute eingetragen (mit WorkingDirectory)
    — kein `cmd /c start "Titel" /min ...`: dieses verschachtelte
    Quoting zerbricht im Task-Kontext ("start ... konnte nicht gefunden
    werden")."""
    ziel_user = ziel.zugang["ziel_user"]
    ordner = bat.rsplit("\\", 1)[0]
    trigger = ("$t = New-ScheduledTaskTrigger -AtStartup"
               if onstart else
               "$t = New-ScheduledTaskTrigger -Once -At "
               "(Get-Date).AddMinutes(10)")
    skript = (
        f"$ErrorActionPreference = 'Stop'; {trigger}; "
        f"$a = New-ScheduledTaskAction -Execute '{bat}' "
        f"-WorkingDirectory '{ordner}'; "
        "$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit "
        "(New-TimeSpan -Seconds 0) -AllowStartIfOnBatteries "
        "-DontStopIfGoingOnBatteries -StartWhenAvailable; "
        f"Register-ScheduledTask -TaskName '{name}' -Action $a -Trigger $t "
        f"-Settings $s -User '{ziel_user}' -Force | Out-Null; 'angelegt'")
    out, err, _ = ziel.ps(skript, timeout=90)
    _log("task", f"{name}: {out.strip() or err.strip()[:160]}")


def alte_app_tasks_entfernen(ziel: Ziel) -> None:
    """Defekte App-Tasks (altes cmd/start-Quoting) entsorgen — die Apps
    startet der Nutzer per Doppelklick der start.bat."""
    for name in ("MqlGoldscannerStart", "MqlGoldscanner Autostart"):
        ziel.run(f'schtasks /Delete /TN "{name}" /F >nul 2>&1')
    _log("task", "alte App-Tasks entfernt (Apps startet der Nutzer selbst)")


def daemon_neu_starten(ziel: Ziel) -> None:
    """Daemon sauber stoppen und über den Task mit aktuellem Code neu
    starten (starte_detached verhindert Doppelläufe selbst)."""
    bat = ziel.ziel.replace("/", chr(92)) + "\\start_goldscanner_daemon.bat"
    task_anlegen(ziel, "MqlGoldscanner Daemon", bat, onstart=True)
    venv_py = f"{ziel.ziel}/.venv/Scripts/python.exe"
    ziel.run('schtasks /End /TN "MqlGoldscanner Daemon" >nul 2>&1')
    ziel.run(f'"{venv_py}" -c "import sys; sys.path.insert(0, '
             f"r'{ziel.ziel}/src'); from goldscanner.betrieb import daemon; "
             'print(daemon.stoppe())"', timeout=60)
    time.sleep(4)
    ziel.run('schtasks /Run /TN "MqlGoldscanner Daemon"')
    deadline = time.time() + 120
    while time.time() < deadline:
        time.sleep(6)
        out, _, _ = ziel.run(f'"{venv_py}" -c "import sys; sys.path.insert(0, '
                             f"r'{ziel.ziel}/src'); from goldscanner.betrieb "
                             "import daemon; print(daemon.laeuft())\"",
                             timeout=60)
        if out.strip() == "True":
            break
    _log("daemon", "neu gestartet, läuft: " + out.strip())


def app_health(ziel: Ziel) -> None:
    """Nur Statusmeldung: die App selbst startet der Nutzer per
    Doppelklick der start.bat (bewusste Konvention — kein Autostart)."""
    out, _, _ = ziel.ps(
        "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8505"
        "/_stcore/health' -UseBasicParsing -TimeoutSec 4).Content } "
        "catch { 'aus' }")
    zustand = out.strip()
    if zustand == "ok":
        _log("app", "App läuft bereits auf :8505 (Streamlit lädt neuen "
                    "Code beim nächsten Seitenaufruf selbst)")
    else:
        _log("app", "App aus — am Zielrechner per Doppelklick "
                    "C:\\Forex\\MqlGoldscanner\\start.bat starten")
    out, _, _ = ziel.ps(
        "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8606/health' "
        "-UseBasicParsing -TimeoutSec 5).StatusCode } catch { 'aus (lazy, "
        "kommt mit der App)' }")
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
            python_exe = tools_python_sicherstellen(ziel)
        sync(ziel)
        if not args.code_only:
            venv_und_pakete(ziel, python_exe)
        rechte_setzen(ziel)
        if not args.kein_start:
            alte_app_tasks_entfernen(ziel)
            daemon_neu_starten(ziel)
        app_health(ziel)
        _log("fertig", f"MqlGoldscanner liegt unter {zugang['ziel']} "
                       f"(App startet {zugang['ziel_user']} per Doppelklick: "
                       ":8505, REST :8606 lazy, Daemon-Task aktiv).")
    finally:
        ziel.close()


if __name__ == "__main__":
    main()
