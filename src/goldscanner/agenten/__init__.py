"""Agenten der LLM-Schicht (S4): Destillation + Analytiker-Fusion.

Gemeinsame Regeln (Konzept §4 „Engine rechnet, LLM zitiert"):
- Das LLM sieht ausschließlich lokale Daten (DB-Snapshots), nie live.
- Ungültige/unvollständige Antworten werden nie gespeichert
  (finish_reason != stop wirft ohnehin im Client).
- Nach 3 systemischen Fehlern in Folge: Fail-Fast, kein Endlos-Retry.
- Jeder Aufruf landet vollständig (Prompt/Antwort/Modell/Tokens) im
  Journal — Grundlage für die Tor-T4-Bewertung des LLM-Deltas.
"""
from .destillation import community_destillieren, news_destillieren
from .analytiker import fusioniere

__all__ = ["news_destillieren", "community_destillieren", "fusioniere"]
