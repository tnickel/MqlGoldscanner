"""GLM-Client (Z.ai, OpenAI-kompatibel) mit Token-Budget und Backoff.

Port des bewährten KiScanner-Clients (llm/client.py), ergänzt um ein
persistiertes Tagesbudget (budget_token-Tabelle):
- Endpunkt-Verwechslung Abo/PAYG → Z.ai-Code 1113 ("Insufficient balance").
- 429 / Code 1302 = Drossel/Parallelitätslimit → Backoff 5·(Versuch+1) s.
- Transportfehler: genau 1 Wiederholung, dann Abbruch.
- finish_reason != "stop" → Antwort verwerfen, nie als Ergebnis speichern.
- Auch unvollständige/leere Antworten zählen ins Budget.
"""
from __future__ import annotations

import json
import threading
import time

import requests

from .. import config, secrets_store


class LlmError(RuntimeError):
    """Basisfehler des LLM-Layers."""


class LlmNoBalanceError(LlmError):
    """Key gültig, aber kein Kontingent auf diesem Endpunkt (Z.ai-Code 1113)."""


class LlmBudgetError(LlmError):
    """Token-Budget (Lauf oder Tag) erschöpft."""


class LlmIncompleteResponseError(LlmError):
    """Antwort abgebrochen — darf nie als fertiges Ergebnis gelten."""


class LlmUsage:
    def __init__(self) -> None:
        self.total_tokens = 0
        self.requests = 0
        self.pro_modell: dict[str, int] = {}
        self._lock = threading.Lock()

    def add(self, modell: str, tokens: int) -> None:
        with self._lock:
            self.total_tokens += max(0, tokens)
            self.requests += 1
            self.pro_modell[modell] = self.pro_modell.get(modell, 0) + max(0, tokens)


class GlmClient:
    def __init__(self, model_stufe1: str, model_stufe2: str,
                 max_total_tokens: int = 5_000_000, timeout: int = 300,
                 base_url: str | None = None, db=None):
        self.base_url = (base_url or config.GLM_BASE_URL).rstrip("/")
        self.model_stufe1 = model_stufe1
        self.model_stufe2 = model_stufe2
        self.max_total_tokens = max_total_tokens
        self.timeout = timeout
        self.db = db              # optional: persistiertes Tagesbudget
        self.usage = LlmUsage()
        self.last_call: dict = {}
        self._lock = threading.Lock()

    @property
    def has_key(self) -> bool:
        return bool(secrets_store.get_secret("glm_api_key"))

    def _headers(self) -> dict:
        key = secrets_store.get_secret("glm_api_key")
        if not key:
            raise LlmError("Kein GLM-API-Key gesetzt (Einstellungen oder GLM_API_KEY).")
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _budget_pruefen(self) -> None:
        if self.usage.total_tokens >= self.max_total_tokens:
            raise LlmBudgetError(
                f"Lauf-Budget erschöpft ({self.max_total_tokens} Tokens). "
                "Budget in den Einstellungen erhöhen.")
        if self.db is not None:
            verbraucht = self.db.tokens_heute()
            max_tag = config.load_settings().get("llm_token_budget_tag", 2_000_000)
            if verbraucht >= max_tag:
                raise LlmBudgetError(
                    f"Tagesbudget erschöpft ({verbraucht}/{max_tag} Tokens). "
                    "Morgen weiter oder Budget erhöhen.")

    def chat(self, prompt: str, system: str = "", model: str | None = None,
             stufe: int = 1, temperature: float = 0.4,
             max_tokens: int = 1600, meta_out: dict | None = None) -> str:
        model = model or (self.model_stufe1 if stufe == 1 else self.model_stufe2)
        with self._lock:
            self._budget_pruefen()

        body = {
            "model": model,
            "messages": ([{"role": "system", "content": system}] if system else [])
            + [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        last_error: Exception | None = None
        for attempt in range(3):
            start = time.monotonic()
            r = None
            for transport_attempt in range(2):
                try:
                    r = requests.post(f"{self.base_url}/chat/completions",
                                      headers=self._headers(), data=json.dumps(body),
                                      timeout=self.timeout)
                    break
                except requests.RequestException as exc:
                    if transport_attempt:
                        raise LlmError(
                            f"GLM-Verbindungsfehler nach 2 Versuchen: "
                            f"{type(exc).__name__}: {exc}") from exc
                    time.sleep(5)
            assert r is not None
            if r.status_code >= 400:
                try:
                    err = r.json().get("error", {})
                except ValueError:
                    err = {}
                code = str(err.get("code") or "")
                if code == "1113":
                    raise LlmNoBalanceError(
                        "GLM-Key gültig, aber kein Kontingent auf diesem Endpunkt "
                        f"(Z.ai-Code {code}). Bei Abo-Keys (GLM Coding Plan) muss der "
                        "Coding-Endpunkt gesetzt sein (api.z.ai/api/coding/paas/v4), bei "
                        "Guthaben-Keys der Standard-Endpunkt (api.z.ai/api/paas/v4) — "
                        "in den Einstellungen umstellbar.")
                if r.status_code == 429 or code == "1302":
                    last_error = LlmError(
                        f"GLM-Drosselung (HTTP {r.status_code}, "
                        f"Code {code or 'unbekannt'}): {r.text[:200]}")
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                    continue
                raise LlmError(f"GLM-API HTTP {r.status_code}: {r.text[:300]}")
            try:
                data = r.json()
            except ValueError as exc:
                raise LlmError(
                    f"GLM-API lieferte kein JSON (HTTP {r.status_code}): "
                    f"{r.text[:200]!r}") from exc
            try:
                choice0 = data["choices"][0]
                content = (choice0.get("message") or {}).get("content") or ""
                finish = choice0.get("finish_reason")
            except (KeyError, IndexError, TypeError) as exc:
                raise LlmError(
                    f"GLM-API-Antwort ohne gültige choices: {str(data)[:200]}") from exc
            usage = data.get("usage", {})
            total_tokens = int(usage.get("total_tokens", 0))
            call_meta = {
                "model": model,
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "reasoning_tokens": int((usage.get("completion_tokens_details") or {})
                                        .get("reasoning_tokens", 0) or 0),
                "dauer_s": round(time.monotonic() - start, 1),
                "finish_reason": finish,
                "zeichen": len(content),
            }
            with self._lock:
                self.usage.add(model, total_tokens)
                if self.db is not None:
                    self.db.token_buchen(model, total_tokens)
                self.last_call = dict(call_meta)
                if meta_out is not None:
                    meta_out.clear()
                    meta_out.update(call_meta)
            if finish not in (None, "stop"):
                raise LlmIncompleteResponseError(
                    f"Unvollständige Antwort von {model} (finish_reason={finish}). "
                    "Nicht als fertiges Ergebnis gespeichert; bei 'length' das "
                    "Ausgabelimit erhöhen oder kürzer anfordern.")
            if not content:
                raise LlmError(
                    f"Leere Antwort von {model} (finish_reason={finish}, "
                    f"completion_tokens={call_meta['completion_tokens']}). "
                    "Mögliche Ursache: Reasoning hat das max_tokens-Budget aufgebraucht.")
            return content
        raise last_error or LlmError("GLM-Aufruf fehlgeschlagen.")

    def test_connection(self) -> dict:
        """Mini-Test für die Einstellungen/Agenten-Seite. max_tokens bewusst
        hoch: glm-5.x verbrauchen Reasoning-Tokens, bevor Content entsteht."""
        content = self.chat("Antworte mit genau einem Wort: Test",
                            model=self.model_stufe1, stufe=1, max_tokens=2048)
        return {"ok": True, "antwort": content.strip(), "usage": {
            "total_tokens": self.usage.total_tokens,
            "pro_modell": self.usage.pro_modell}}
