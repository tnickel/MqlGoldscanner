@echo off
rem MqlGoldscanner starten (Streamlit).
rem Fenster offen lassen = App laeuft; Fenster schliessen beendet die App.
rem Browser oeffnet sich automatisch (http://localhost:8505).
chcp 65001 >nul
title MqlGoldscanner
cd /d "%~dp0"

rem Bevorzugt das Projekt-venv (falls vorhanden, z. B. nach Deploy auf
rem anderen Rechnern), sonst das System-Python.
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

%PYTHON% --version >nul 2>nul
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

rem Browser im Standard-Browser oeffnen, SOBALD der Server lauscht:
rem ein minimiertes PowerShell-Hilfsfenster pollt den Port (max. 30 s,
rem sprachneutral ueber Get-NetTCPConnection) und oeffnet dann die Seite.
if not exist ".venv\Scripts\python.exe" (
    %PYTHON% -c "import streamlit, plotly, MetaTrader5, reportlab, pandas, openpyxl" >nul 2>nul
    if errorlevel 1 (
        echo [Setup] Abhaengigkeiten fehlen - installiere requirements.txt ...
        %PYTHON% -m pip install -r requirements.txt
    )
)

start "" /min powershell -NoProfile -Command "for($i=0;$i -lt 60;$i++){ if(Get-NetTCPConnection -LocalPort 8505 -State Listen -ErrorAction SilentlyContinue){ break }; Start-Sleep -Milliseconds 500 }; Start-Process 'http://localhost:8505/'"

%PYTHON% -m streamlit run streamlit_app.py --server.port 8505 --browser.gatherUsageStats false
if errorlevel 1 (
    echo.
    echo Start fehlgeschlagen. Vermutlich fehlen Pakete - bitte ausfuehren:
    echo     pip install -r requirements.txt
    pause
)
