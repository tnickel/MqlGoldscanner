# -*- coding: utf-8 -*-
"""Geheimnisse: Umgebungsvariablen > .env > config/secrets.local.json (KiScanner-Muster).

secrets.local.json und .env sind via .gitignore ausgeschlossen; hier liegen nur
Schluesselnamen und Reihenfolge.
"""
from __future__ import annotations

import json
import os

from . import config

SECRETS_FILE = config.CONFIG_DIR / "secrets.local.json"
ENV_FILE = config.ROOT / ".env"

_ENV_ALIASE = {
    "glm_api_key": ("MQLGOLDSCANNER_GLM_KEY", "GLM_API_KEY"),
    "such_api_key": ("MQLGOLDSCANNER_SUCH_KEY", "TAVILY_API_KEY"),
    "myfxbook_session": ("MQLGOLDSCANNER_MYFXBOOK_SESSION",),
}


def _load_env_file() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    werte: dict[str, str] = {}
    for zeile in ENV_FILE.read_text(encoding="utf-8").splitlines():
        z = zeile.strip()
        if not z or z.startswith("#") or "=" not in z:
            continue
        key, _, val = z.partition("=")
        werte[key.strip()] = val.strip()
    return werte


def get_secret(key: str) -> str | None:
    for env_name in _ENV_ALIASE.get(key, (key.upper(),)):
        val = os.environ.get(env_name)
        if val:
            return val.strip()
    env = _load_env_file()
    for env_name in _ENV_ALIASE.get(key, (key.upper(),)):
        if env.get(env_name):
            return env[env_name].strip()
    try:
        daten = json.loads(SECRETS_FILE.read_text(encoding="utf-8")) if SECRETS_FILE.exists() else {}
    except (json.JSONDecodeError, OSError):
        return None
    val = daten.get(key)
    return str(val).strip() if val else None


def set_secret(key: str, wert: str) -> None:
    try:
        daten = json.loads(SECRETS_FILE.read_text(encoding="utf-8")) if SECRETS_FILE.exists() else {}
    except (json.JSONDecodeError, OSError):
        daten = {}
    if wert:
        daten[key] = wert.strip()
    else:
        daten.pop(key, None)
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_FILE.write_text(json.dumps(daten, indent=2, ensure_ascii=False), encoding="utf-8")


def maskiert(key: str) -> str:
    val = get_secret(key)
    if not val:
        return "nicht gesetzt"
    if len(val) <= 8:
        return f"gesetzt ({len(val)} Zeichen)"
    return f"{val[:5]}…{val[-4:]} ({len(val)} Zeichen)"
