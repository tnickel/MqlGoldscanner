@echo off
rem MqlGoldscanner starten (Streamlit, Vorbild-Architektur MqlKiScanner).
rem Browser oeffnet sich automatisch; Fenster offen lassen (beendet die App).
chcp 65001 >nul
cd /d "%~dp0"
where streamlit >nul 2>nul
if errorlevel 1 (
    echo Streamlit nicht gefunden. Bitte 'pip install -r requirements.txt' ausfuehren.
    pause
    exit /b 1
)
streamlit run streamlit_app.py --server.port 8505 --browser.gatherUsageStats false
