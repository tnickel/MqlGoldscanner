"""Prompt-Vorlagen (S4): externe MD-Dateien in config/prompts/.

Vorteil: Prompts sind editierbar, versioniert und geprüft — ohne Code.
Der Filler ist eine Zwei-Phasen-Ersetzung (Port aus dem KiScanner):
Enthält ein einzufügender Inhalt wortwörtlich einen späteren Platzhalter
wie {items_json}, würde eine .replace()-Kaskade ihn im eingefügten Inhalt
mit-ersetzen und den Prompt verstuemmeln. Erst Steuer-Token setzen, dann
in einem zweiten Durchlauf die Inhalte — eingefügte Inhalte werden nie
erneut gescannt.

assert_template_covered prueft die VORLAGE: Jeder platzhalterartige
Ausdruck muss versorgt sein (Tippfehler in der Vorlage fallen sofort
klar auf, statt stumm beim Modell zu landen).
"""
from __future__ import annotations

import re

from .. import config
from .client import LlmError

KNOWN_SLOTS = frozenset((
    "{items_json}", "{n_items}", "{fenster_tage}", "{heute}",
    "{community_json}", "{matrix_json}", "{news_json}", "{band_pp}",
))

_PLACEHOLDER_RE = re.compile(r"\{[a-z_][a-z_0-9]{1,39}\}")


def load_prompt(name: str) -> str:
    """Lädt config/prompts/{name}.md — fehlt die Datei, ist das ein
    Konfigurationsfehler, der klar benannt wird (kein Fallback-Prompt)."""
    pfad = config.PROMPTS_DIR / f"{name}.md"
    if not pfad.is_file():
        raise LlmError(f"Prompt-Vorlage fehlt: {pfad}")
    inhalt = pfad.read_text(encoding="utf-8").strip()
    if not inhalt:
        raise LlmError(f"Prompt-Vorlage ist leer: {pfad}")
    return inhalt


def assert_template_covered(template: str, keys, vorlage: str) -> str:
    unversorgt = sorted({slot for slot in _PLACEHOLDER_RE.findall(template)
                         if slot not in keys})
    if unversorgt:
        raise LlmError(
            f"Prompt-Vorlage '{vorlage}' enthaelt unversorgte Platzhalter: "
            f"{', '.join(unversorgt)}. Vorlage in config/prompts/ pruefen.")
    return template


def fill_prompt(template: str, mapping: dict[str, str]) -> str:
    """Ersetzt Vorlagen-Platzhalter, ohne eingefügte Inhalte anzutasten."""
    tokens: dict[str, str] = {}
    out = template
    for i, (placeholder, value) in enumerate(mapping.items()):
        if placeholder not in out:
            continue  # Vorlage darf Platzhalter bewusst nicht enthalten
        token = f"\x00PROMPT_SLOT_{i}\x00"
        out = out.replace(placeholder, token)
        tokens[token] = value
    for token, value in tokens.items():
        out = out.replace(token, value)
    return out
