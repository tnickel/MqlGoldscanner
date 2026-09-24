@echo off
rem MqlGoldscanner-Daemon starten (Tageslauf 06:30, Scout So 17:00,
rem Wochenlauf So 18:00, Verifikation+Auswertung Sa 09:00).
rem Detached: dieses Fenster kann sofort wieder zu; der Daemon laeuft weiter.
rem Laeuft schon ein Daemon, macht das Skript nichts (starte_detached prueft).
chcp 65001 >nul
title MqlGoldscanner-Daemon
cd /d "%~dp0"

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" -c "import sys; sys.path.insert(0, r'src'); from goldscanner.betrieb import daemon; print('Daemon gestartet (PID siehe data/daemon.pid)' if daemon.starte_detached() else 'Daemon laeuft bereits')"
timeout /t 3 >nul
