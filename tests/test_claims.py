import json
from unittest.mock import patch

from cassandra_agent import claims


def _fake_chat(content):
    return {"message": {"content": json.dumps(content)}}


def test_extract_claims_returns_new_claims():
    with patch.object(claims, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat({"claims": [{"claim": "Unemployment hit 3% in June 2024.",
                        "speaker": "Speaker A",
                        "search_query": "US unemployment rate June 2024"}]})
        result = claims.extract_claims("some transcript window", already_flagged=[])
    assert result == [{"claim": "Unemployment hit 3% in June 2024.",
                   "speaker": "Speaker A", "search_query": "US unemployment rate June 2024"}]


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
        mock_ollama.chat.return_value = _fake_chat({"claims": [{"claim": "Valid claim"}, 42, {"claim": ""}, {"claim": "  "}]})
        result = claims.extract_claims("window text", already_flagged=[])
    assert [c["claim"] for c in result] == ["Valid claim"]


def test_extract_claims_falls_back_when_model_returns_bare_strings():
    """The model sometimes ignores the schema; a bare string must still work."""
    with patch.object(claims, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat({"claims": ["A bare claim."]})
        result = claims.extract_claims("window", already_flagged=[])
    assert result == [{"claim": "A bare claim.", "speaker": "", "search_query": "A bare claim."}]


def test_extract_claims_defaults_search_query_to_claim_text():
    with patch.object(claims, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat(
            {"claims": [{"claim": "Some claim.", "speaker": "B", "search_query": ""}]})
        result = claims.extract_claims("window", already_flagged=[])
    assert result[0]["search_query"] == "Some claim."


def test_context_block_is_sent_to_the_model():
    with patch.object(claims, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat({"claims": []})
        claims.extract_claims("window", [], context_block="Known participants: Ada, Grace")
    sent = mock_ollama.chat.call_args.kwargs["messages"][1]["content"]
    assert "Known participants: Ada, Grace" in sent
