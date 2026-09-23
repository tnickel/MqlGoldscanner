"""GLM-Client-Fehler-Taxonomie mit Fake-Requests (kein Netz, kein echter Key)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from goldscanner.llm.client import (GlmClient, LlmBudgetError, LlmError,
                                    LlmIncompleteResponseError, LlmNoBalanceError)

ERFOLG = ('{"choices":[{"message":{"content":"Test"},"finish_reason":"stop"}],'
          '"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}')


class FakeAntwort:
    def __init__(self, status, text):
        self.status_code = status
        self.text = text

    def json(self):
        import json
        return json.loads(self.text)


def _client(monkeypatch, antworten, max_total=1_000_000):
    monkeypatch.setattr("goldscanner.secrets_store.get_secret",
                        lambda key: "fake-key" if key == "glm_api_key" else None)
    aufrufe = []

    def fake_post(url, headers=None, data=None, timeout=None):
        aufrufe.append((url, data))
        return antworten[len(aufrufe) - 1] if len(antworten) > 1 else antworten[0]

    monkeypatch.setattr("goldscanner.llm.client.requests.post", fake_post)
    client = GlmClient("glm-flash", "glm", max_total_tokens=max_total, timeout=5)
    return client, aufrufe


def test_happy_path_zaehlt_usage(monkeypatch):
    client, aufrufe = _client(monkeypatch, [FakeAntwort(200, ERFOLG)])
    assert client.chat("Frage") == "Test"
    assert client.usage.total_tokens == 15
    assert client.usage.pro_modell == {"glm-flash": 15}
    assert "/chat/completions" in aufrufe[0][0]
    assert '"model": "glm-flash"' in aufrufe[0][1]


def test_code_1113_wird_kein_guthaben(monkeypatch):
    client, _ = _client(monkeypatch, [FakeAntwort(
        402, '{"error":{"code":"1113","message":"Insufficient balance"}}')])
    with pytest.raises(LlmNoBalanceError) as e:
        client.chat("x")
    assert "Coding-Endpunkt" in str(e.value)


def test_finish_reason_length_wird_unvollstaendig(monkeypatch):
    client, _ = _client(monkeypatch, [FakeAntwort(
        200, '{"choices":[{"message":{"content":"abc"},"finish_reason":"length"}],'
             '"usage":{"total_tokens":9}}')])
    with pytest.raises(LlmIncompleteResponseError) as e:
        client.chat("x")
    assert "finish_reason=length" in str(e.value)
    assert client.usage.total_tokens == 9   # unvollständig zählt trotzdem


def test_budget_blockt_vor_aufruf(monkeypatch):
    client, aufrufe = _client(monkeypatch, [FakeAntwort(200, ERFOLG)], max_total=0)
    with pytest.raises(LlmBudgetError):
        client.chat("x")
    assert aufrufe == []   # kein Request abgesetzt


def test_ohne_key_wird_fehler(monkeypatch):
    monkeypatch.setattr("goldscanner.secrets_store.get_secret", lambda key: None)
    client = GlmClient("a", "b")
    with pytest.raises(LlmError) as e:
        client.chat("x")
    assert "Kein GLM-API-Key" in str(e.value)


def test_ohne_choices_wird_fehler(monkeypatch):
    client, _ = _client(monkeypatch, [FakeAntwort(200, '{"garbage": true}')])
    with pytest.raises(LlmError):
        client.chat("x")
