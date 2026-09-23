"""Prozessübergreifendes Lauf-Lock (Port des KiScanner agenten/lock.py).

Datei-basiert mit PID und Zeitstempel: ein Lock ohne lebenden Halter oder
älter als STALE_S gilt als verwaist und wird ersetzt.
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

STALE_S = 3600


def _pid_lebt(pid: int) -> bool:
    """Lebt der Prozess? Vorsicht Windows: os.kill(pid, 0) würde dort den
    Prozess per TerminateProcess BEENDEN — deshalb ctypes-Abfrage."""
    import sys
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return exit_code.value == STILL_ACTIVE
            return True
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lese(datei: Path) -> dict:
    try:
        return json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@contextmanager
def lauf_lock(basis: Path, name: str = "goldscanner_lauff"):
    datei = basis / f"{name}.lock"
    datei.parent.mkdir(parents=True, exist_ok=True)
    versucht = 0
    gehalten = False
    while versucht < 3 and not gehalten:
        versucht += 1
        try:
            fd = os.open(datei, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"pid": os.getpid(), "name": name, "zeit": int(time.time())}, handle)
            gehalten = True
        except FileExistsError:
            daten = _lese(datei)
            pid = daten.get("pid")
            alter = int(time.time()) - int(daten.get("zeit", 0))
            if isinstance(pid, int) and _pid_lebt(pid) and alter < STALE_S:
                # Auch die EIGENE PID zählt als belegt: verschachtelte Locks
                # desselben Namens im selben Prozess sind ein Logikfehler
                # (z. B. Daemon-Loop + wochenlauf.starten) und dürfen das
                # äußere Lock nicht still ersetzen.
                raise LockBesetzt(
                    f"Ein anderer Lauf hält das Lock (PID {pid}, seit {alter} s).",
                    pid, alter)
            try:
                datei.unlink()          # verwaist/abgestürzt: ersetzen
            except OSError:
                pass
    if not gehalten:
        raise RuntimeError(f"Lock konnte nicht erworben werden: {datei}")
    try:
        yield
    finally:
        try:
            datei.unlink()
        except OSError:
            pass


class LockBesetzt(RuntimeError):
    def __init__(self, message: str, pid: int | None = None, alter_s: int | None = None):
        super().__init__(message)
        self.pid = pid
        self.alter_s = alter_s
