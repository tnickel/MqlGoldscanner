@echo off
rem MqlGoldscanner starten (Streamlit).
rem Das Fenster offen lassen = App laeuft; Fenster schliessen beendet die App.
rem Der Browser oeffnet sich automatisch (http://localhost:8505).
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python nicht gefunden. Bitte Python 3.12+ installieren und PATH setzen.
    pause
    exit /b 1
)

rem python -m streamlit ist robuster als direkt "streamlit"
rem (funktioniert auch, wenn das Scripts-Verzeichnis nicht im PATH liegt).
python -m streamlit run streamlit_app.py --server.port 8505 --browser.gatherUsageStats false
if errorlevel 1 (
    echo.
    echo Start fehlgeschlagen. Vermutlich fehlen Pakete - bitte ausfuehren:
    echo     pip install -r requirements.txt
    echo.
    echo Ist die App bereits in einem anderen Fenster gestartet? Dann dieses
    echo Fenster schliessen und im Browser http://localhost:8505 oeffnen.
    pause
)
