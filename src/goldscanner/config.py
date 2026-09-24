"""Zentrale Konfiguration: Pfade, Defaults, App-Settings (Vorbild: KiScanner config.py).

Regeln: Credentials NIE hier — nur via secrets_store (Umgebung > .env >
secrets.local.json). Diese Datei ist committbar und enthaelt keine Geheimnisse.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
ASSETS_DIR = ROOT / "assets"
DATA_DIR = ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"
REPORTS_DIR = DATA_DIR / "reports"
CONFIG_DIR = ROOT / "config"
PROMPTS_DIR = CONFIG_DIR / "prompts"
SETTINGS_FILE = CONFIG_DIR / "app_settings.json"
DB_FILE = DATA_DIR / "goldscanner.db"

APP_NAME = "MqlGoldscanner"
APP_VERSION = "0.1"

# LLM — GLM-Zugang (aus dem KiScanner uebernommen): zwei Endpunkte mit
# getrennten Kontingenten. Ein Coding-Plan-Abo-Key liefert auf dem
# Standard-Endpunkt Fehler 1113 ("Insufficient balance").
GLM_BASE_URL_CODING = "https://api.z.ai/api/coding/paas/v4"   # Abo-Keys (Default)
GLM_BASE_URL_API = "https://api.z.ai/api/paas/v4"             # Pay-as-you-go
GLM_BASE_URL = GLM_BASE_URL_CODING

# Zweistufen-Modellwahl: Flash fuer Destillationen, starkes Modell fuer Fusion.
MODEL_STUFE1 = "glm-5.3-flash"
MODEL_STUFE2 = "glm-5.3"

# Ehrlicher User-Agent (Deep-Research-Regel: Default-User-Agents werden
# geblockt; Browser-UA-Vortaeuschung bleibt tabu).


def user_agent(kontakt_mail: str = "") -> str:
    ua = f"{APP_NAME}/{APP_VERSION}"
    if kontakt_mail:
        ua += f" (+mailto:{kontakt_mail.strip()})"
    return ua


DEFAULT_SETTINGS: dict = {
    "mt5_symbol": "XAUUSD",              # Broker-Suffix beachten (z. B. XAUUSD.m)
    "mt5_terminal_pfad": "",             # leer = Default-Attach ans laufende Terminal
    "mt5_start_erlauben": False,         # Standard: Terminal nie selbst starten
    "mt5_lookback_tage": 400,
    "zeitzone": "Europe/Berlin",
    "glm_endpunkt": "coding",            # coding | api
    "model_stufe1": MODEL_STUFE1,
    "model_stufe2": MODEL_STUFE2,
    "llm_max_total_tokens": 5_000_000,   # Budget je Lauf
    "llm_token_budget_tag": 2_000_000,   # Budget je Tag
    "llm_timeout_s": 300,
    "kontakt_fuer_useragent": "",
    "rate_min_interval_s": 2.0,
    # Wochenmatrix (S2)
    "matrix_fenster": 13,          # Wochen für die Schwelle B je Wochentag
    "matrix_k": 1.0,               # Bewegungstag: TR > k × Ø-TR des Wochentags
    # LLM-Schicht (S4)
    "llm_band_pp": 10.0,           # Analytiker darf P_stat nur um ± diese pp verschieben
    "llm_melde_schwelle_pp": 10.0, # Prognoseänderung, ab der eine Meldung entsteht
    "news_fenster_tage": 7,        # RSS-Items älter als das werden ignoriert
    "news_max_items_llm": 80,      # Obergrenze je Destillations-Aufruf
    # Ausbau (S7)
    "rest_api_port": 8606,         # read-only localhost REST; 0 = aus
    # ── Daemon / Automatik (S6; Wochentag = Montag..Sonntag) ───────────
    "daemon_tageslauf_zeit": "06:30",          # täglich
    "daemon_scout_tag": "Sonntag",
    "daemon_scout_zeit": "17:00",
    "daemon_wochenlauf_tag": "Sonntag",
    "daemon_wochenlauf_zeit": "18:00",
    "daemon_verifikation_tag": "Samstag",
    "daemon_verifikation_zeit": "09:00",
}


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    if SETTINGS_FILE.exists():
        try:
            settings.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass  # defekte Datei: Defaults gelten weiter
    return settings


def save_settings(settings: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def glm_base_url(settings: dict) -> str:
    return GLM_BASE_URL_API if settings.get("glm_endpunkt") == "api" else GLM_BASE_URL_CODING
