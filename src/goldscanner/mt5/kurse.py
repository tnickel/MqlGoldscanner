# -*- coding: utf-8 -*-
"""MetaTrader-Kursdaten — offizielles MetaTrader5-Paket, NUR LESEND.

Port der bewährten KiScanner agenten/marktdata.py, erweitert um volle
Ratenreihen (D1/H4/H1) für den Chart. Eiserne Regel: AUSSCHLIESSLICH
Lese-Aufrufe (Whitelist; ein statischer Test bewacht das Modul). Das LLM
bekommt nur fertige Kennzahlen, niemals Rohkurse.

Start-Politik: Standardmäßig startet der Scanner das Terminal NICHT selbst.
Mit Freigabe (mt5_start_erlauben) startet initialize() es PORTABEL. ABWEICHEND
vom KiScanner gilt: Ein bereits laufendes Terminal (z. B. für andere Monitore
des Nutzers) wird NICHT beendet — nur ein selbst gestartetes wird sauber
beendet. Ohne Terminal-Pfad attacht initialize() ans laufende Terminal.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

# Whitelist der angebundenen MT5-Aufrufe (statischer Test in tests/ bewacht sie).
ERLAUBTE_MT5_AUFRUFE = frozenset((
    "initialize", "shutdown", "terminal_info", "version", "last_error",
    "symbol_select", "symbol_info_tick", "copy_rates_from_pos",
    "copy_rates_range", "copy_ticks_from", "copy_ticks_range",
))

MAX_H1 = 5000   # ≈ 208 Handelstage — genug für ATR(14) H1 und Saisonalie-Vorschau


def _terminal_prozesse(terminal_pfad: str) -> list[tuple[int, str]]:
    """(PID, Pfad) aller terminal64-Prozesse mit genau DIESEM Pfad."""
    try:
        ziel = str(Path(terminal_pfad).resolve()).lower()
    except (OSError, ValueError):
        return []
    try:
        ausgabe = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process "
             "-Filter \"Name='terminal64.exe'\" "
             "| Select-Object ProcessId, ExecutablePath "
             "| ConvertTo-Json -Compress)"],
            capture_output=True, timeout=20,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    roh = (ausgabe.stdout or "").strip()
    if not roh:
        return []
    import json as _json
    try:
        daten = _json.loads(roh) if roh.startswith(("[", "{")) \
            else [{"ProcessId": int(e.split()[0]),
                   "ExecutablePath": e.split(None, 1)[1] if " " in e else ""}
                  for e in roh.splitlines()]
    except (ValueError, IndexError, _json.JSONDecodeError):
        return []
    if isinstance(daten, dict):  # ConvertTo-Json: EIN Prozess → Objekt
        daten = [daten]
    ergebnis = []
    for eintrag in daten:
        try:
            pfad = str(eintrag.get("ExecutablePath") or "").strip().lower()
            if pfad == ziel:
                ergebnis.append((int(eintrag["ProcessId"]), pfad))
        except (KeyError, ValueError, TypeError):
            continue
    return ergebnis


def terminal_beenden(terminal_pfad: str) -> bool:
    """Beendet das Terminal dieses Pfads — sanft, dann hart (nur Selbststart!)."""
    prozesse = _terminal_prozesse(terminal_pfad)
    if not prozesse:
        return True

    def _taskkill(hart: bool) -> None:
        for pid, _pfad in _terminal_prozesse(terminal_pfad):
            befehl = ["taskkill", "/PID", str(pid)] + (["/F", "/T"] if hart else [])
            try:
                subprocess.run(befehl, capture_output=True, timeout=15,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except (OSError, subprocess.SubprocessError):
                pass

    import time as _time
    _taskkill(hart=False)          # WM_CLOSE — Terminal darf Logfiles schreiben
    if _terminal_prozesse(terminal_pfad):
        _time.sleep(4)
        _taskkill(hart=True)
    return not _terminal_prozesse(terminal_pfad)


def _bar(rate) -> dict:
    return {"time": int(rate["time"]), "open": float(rate["open"]),
            "high": float(rate["high"]), "low": float(rate["low"]),
            "close": float(rate["close"]), "volumen": float(rate["tick_volume"])}


def kurse_holen(settings: dict) -> dict:
    """Volle Ratenreihen D1/H4/H1 + Kennzahlen. Rückgabe {ok, grund?, ...}."""
    symbol = str(settings.get("mt5_symbol") or "XAUUSD")
    terminal_pfad = str(settings.get("mt5_terminal_pfad") or "")
    start_erlauben = bool(settings.get("mt5_start_erlauben", False))
    lookback = int(settings.get("mt5_lookback_tage", 400))

    if terminal_pfad:
        lief_schon = bool(_terminal_prozesse(terminal_pfad))
        if not lief_schon and not start_erlauben:
            return {"ok": False,
                    "grund": ("MetaTrader-Terminal läuft nicht und Selbststart ist nicht "
                              "erlaubt (Standard-Politik) — Terminal öffnen oder Selbststart "
                              "in den Einstellungen freigeben.")}
        selbststart = not lief_schon
    else:
        lief_schon = True
        selbststart = False

    import MetaTrader5 as mt5   # spät: nur wenn wirklich verbunden wird

    def _verbinden() -> bool:
        pfad = terminal_pfad if (terminal_pfad and Path(terminal_pfad).exists()) else None
        if pfad:
            # portable=Nur beim Selbststart: die Scanner-eigene Instanz soll
            # die Hauptinstallation (Profile/Logs) unberührt lassen.
            return bool(mt5.initialize(pfad, portable=selbststart))
        return bool(mt5.initialize())

    if not _verbinden():
        fehler = str(mt5.last_error())
        mt5.shutdown()
        if selbststart:
            terminal_beenden(terminal_pfad)
        return {"ok": False, "grund": f"MT5-Verbindung fehlgeschlagen: {fehler}"}

    try:
        info = mt5.terminal_info()
        if not mt5.symbol_select(symbol, True):
            return {"ok": False,
                    "grund": f"Symbol {symbol} beim Broker nicht wählbar (Suffix prüfen?)."}
        soll = {"d1": lookback + 1, "h4": lookback * 6 + 8,
                "h1": min(lookback * 24, MAX_H1)}
        konstanten = {"d1": mt5.TIMEFRAME_D1, "h4": mt5.TIMEFRAME_H4, "h1": mt5.TIMEFRAME_H1}
        raten: dict[str, list[dict]] = {}
        ohne_daten: list[str] = []
        for tf, anzahl in soll.items():
            bars = mt5.copy_rates_from_pos(symbol, konstanten[tf], 0, anzahl)
            if bars is None or len(bars) == 0:
                ohne_daten.append(tf)
                continue
            raten[tf] = [_bar(b) for b in bars]
        if not raten:
            return {"ok": False,
                    "grund": "Kein Timeframe lieferte Daten: " + ", ".join(ohne_daten or ["?"])}

        from ..kennzahlen import kennzahlen_aus_d1
        ergebnis = {
            "ok": True,
            "terminal": info.name if info else "unbekannt",
            "selbststart": selbststart,
            "symbol": symbol,
            "raten": raten,
            "bars": {tf: len(z) for tf, z in raten.items()},
            "kennzahlen": kennzahlen_aus_d1(raten.get("d1", []), raten.get("h1")),
        }
        if ohne_daten:
            ergebnis["ohne_daten"] = ohne_daten
        return ergebnis
    finally:
        mt5.shutdown()
        # ABWEICHUNG KiScanner: nur selbst gestartete Terminals beenden — ein
        # für andere Tools laufendes Terminal bleibt am Leben.
        if selbststart and terminal_pfad:
            terminal_beenden(terminal_pfad)


def verbindung_testen(settings: dict) -> dict:
    """Attach-Test für die Einstellungen: liest EINE Bar und trennt wieder."""
    symbol = str(settings.get("mt5_symbol") or "XAUUSD")
    terminal_pfad = str(settings.get("mt5_terminal_pfad") or "")
    start_erlauben = bool(settings.get("mt5_start_erlauben", False))
    lief_schon = bool(_terminal_prozesse(terminal_pfad)) if terminal_pfad else True
    if not lief_schon and not start_erlauben:
        return {"ok": False,
                "grund": ("Terminal läuft nicht. Standard-Politik: der Scanner startet es "
                          "nicht selbst — Terminal öffnen und erneut testen, oder Pfad "
                          "leer lassen (Attach ans laufende Terminal).")}
    import MetaTrader5 as mt5
    selbststart = not lief_schon
    pfad = terminal_pfad if (terminal_pfad and Path(terminal_pfad).exists()) else None
    verbunden = (bool(mt5.initialize(pfad, portable=selbststart)) if pfad
                 else bool(mt5.initialize()))
    if not verbunden:
        fehler = str(mt5.last_error())
        mt5.shutdown()
        if selbststart:
            terminal_beenden(terminal_pfad)
        return {"ok": False, "grund": f"Verbindung fehlgeschlagen: {fehler}"}
    try:
        info = mt5.terminal_info()
        mt5.symbol_select(symbol, True)
        bars = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 2)
        if bars is None or len(bars) == 0:
            return {"ok": False,
                    "grund": f"Verbunden, aber {symbol} liefert keine Kursdaten "
                             f"(Symbol beim Broker?)"}
        hinweis = " — portable Selbststart" if selbststart else ""
        return {"ok": True,
                "grund": f"Verbunden mit {info.name if info else 'Terminal'} — "
                         f"{symbol}-H1-Close {float(bars[-1]['close']):.2f}{hinweis}"}
    finally:
        mt5.shutdown()
        if selbststart and terminal_pfad:
            terminal_beenden(terminal_pfad)
