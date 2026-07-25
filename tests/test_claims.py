import json
from unittest.mock import patch

from cassandra_agent import claims


def _fake_chat(content):
    return {"message": {"content": json.dumps(content)}}


def test_extract_claims_returns_new_claims():
    with patch.object(claims, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat({"claims": ["Unemployment hit 3% in June 2024."]})
        result = claims.extract_claims("some transcript window", already_flagged=[])
    assert result == ["Unemployment hit 3% in June 2024."]


def test_extract_claims_empty_window_skips_call():
    with patch.object(claims, "ollama") as mock_ollama:
        result = claims.extract_claims("   ", already_flagged=[])
    mock_ollama.chat.assert_not_called()
    assert result == []


def test_extract_claims_handles_invalid_json():
    with patch.object(claims, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = {"message": {"content": "not json"}}
        result = claims.extract_claims("some transcript", already_flagged=[])
    assert result == []


def test_extract_claims_filters_non_strings():
    with patch.object(claims, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat({"claims": ["Valid claim", 42, "", "  "]})
        result = claims.extract_claims("window text", already_flagged=[])
    assert result == ["Valid claim"]
