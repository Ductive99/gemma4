import json
from unittest.mock import patch

from cassandra_agent import judge
from cassandra_agent.events import Snippet


def _fake_chat(content):
    return {"message": {"content": json.dumps(content)}}


def test_judge_claim_true_with_sources():
    snippets = [
        Snippet(title="Fact check", text="Confirmed by official records", link="https://example.com/a", source="example.com"),
    ]
    with patch.object(judge, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat({
            "label": "true",
            "confidence": 0.9,
            "explanation": "Official records confirm it.",
            "sources": [0],
        })
        verdict = judge.judge_claim("Some claim", snippets)
    assert verdict.label == "TRUE"
    assert verdict.confidence == 0.9
    assert verdict.sources == ["https://example.com/a"]


def test_judge_claim_invalid_label_falls_back_to_unverified():
    with patch.object(judge, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat({"label": "MAYBE", "confidence": 2.0})
        verdict = judge.judge_claim("Some claim", [])
    assert verdict.label == "UNVERIFIED"
    assert verdict.confidence == 1.0  # clamped


def test_judge_claim_handles_malformed_response():
    with patch.object(judge, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = {"message": {"content": "garbage"}}
        verdict = judge.judge_claim("Some claim", [])
    assert verdict.label == "UNVERIFIED"
    assert verdict.confidence == 0.0
    assert verdict.sources == []


def test_judge_claim_ignores_out_of_range_source_indices():
    with patch.object(judge, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat({
            "label": "false", "confidence": 0.5, "explanation": "x", "sources": [5, -1, 0],
        })
        verdict = judge.judge_claim("claim", [Snippet("t", "s", "https://x", "x")])
    assert verdict.sources == ["https://x"]
