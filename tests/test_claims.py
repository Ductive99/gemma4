import json
from unittest.mock import patch

from redpen import claims


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


def test_strip_attribution_removes_the_speakers_own_framing():
    f = claims.strip_attribution
    assert f("Mark Zuckerberg said that Meta has 3 billion users.", "Mark Zuckerberg") \
        == "Meta has 3 billion users."
    assert f("According to Lena Farrow, the Act took force in 2024.", "Lena Farrow") \
        == "The Act took force in 2024."
    assert f("Marc Devereux claims inflation fell.", "Marc Devereux") == "Inflation fell."


def test_strip_attribution_keeps_third_party_attribution_and_subjects():
    f = claims.strip_attribution
    # the IEA is the subject, not the speaker — the attribution IS the claim
    assert f("The IEA said in 2020 that solar is cheapest.", "Lena Farrow") \
        == "The IEA said in 2020 that solar is cheapest."
    # a claim about the opponent must keep their name
    assert f("Marc Devereux voted against the bill.", "Lena Farrow") \
        == "Marc Devereux voted against the bill."
    assert f("Unemployment fell to 3.5 percent.", "Marc") == "Unemployment fell to 3.5 percent."


def test_extract_claims_strips_attribution_from_the_model_output():
    with patch.object(claims, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat({"claims": [
            {"claim": "Mark Zuckerberg said that Meta has 3 billion users.",
             "speaker": "Mark Zuckerberg", "search_query": "Meta monthly active users"}]})
        result = claims.extract_claims("window", already_flagged=[])
    assert result[0]["claim"] == "Meta has 3 billion users."
    assert result[0]["speaker"] == "Mark Zuckerberg"
