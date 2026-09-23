@echo off
rem MqlGoldscanner starten (Streamlit).
rem Fenster offen lassen = App laeuft; Fenster schliessen beendet die App.
rem Browser oeffnet sich automatisch (http://localhost:8505).
chcp 65001 >nul
title MqlGoldscanner
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python nicht gefunden. Bitte Python 3.12+ installieren und PATH setzen.
    pause
    exit /b 1
)

rem Alte Instanz auf Port 8505 beenden, falls noch etwas laeuft
rem (z. B. vergessenes Fenster oder abgestuerzter Prozess).
rem Get-NetTCPConnection nutzt Enum-Werte statt lokalisierte netstat-Texte
rem ("LISTENING" vs. "ABHOREN") und funktioniert auf jedem Windows.
set GEFUNDEN=0
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort 8505 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)"`) do (
    set GEFUNDEN=1
    echo Beende alte Instanz auf Port 8505 ^(PID %%p^) ...
    taskkill /PID %%p /F >nul 2>&1
)
if "%GEFUNDEN%"=="1" (
    timeout /t 2 /nobreak >nul
    echo Port 8505 freigegeben.
) else (
    echo Port 8505 ist frei.
)

echo Starte MqlGoldscanner - Browser oeffnet sich gleich ...
python -m streamlit run streamlit_app.py --server.port 8505 --browser.gatherUsageStats false
if errorlevel 1 (
    echo.
    echo Start fehlgeschlagen. Vermutlich fehlen Pakete - bitte ausfuehren:
    echo     pip install -r requirements.txt
    pause
)
