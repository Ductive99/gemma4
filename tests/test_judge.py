import json
from unittest.mock import patch

from redpen import judge
from redpen.events import Snippet


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


def test_judge_receives_speaker_and_context_and_echoes_speaker():
    with patch.object(judge, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat(
            {"label": "TRUE", "confidence": 0.7, "explanation": "ok", "sources": []})
        verdict = judge.judge_claim(
            "A claim", [], speaker="Marc Devereux", context_block="Video title: A debate")
    sent = mock_ollama.chat.call_args.kwargs["messages"][1]["content"]
    assert "Marc Devereux" in sent
    assert "Video title: A debate" in sent
    assert verdict.speaker == "Marc Devereux"


def test_evidence_dates_and_todays_date_reach_the_model():
    """Undated evidence is how a correct claim gets rated false against another year."""
    from datetime import date
    snippets = [
        Snippet("Bureau of Labor Statistics", "Unemployment was 3.5%.",
                "https://bls.gov/a", "bls.gov", date="Jun 5, 2019"),
        Snippet("News roundup", "Unemployment now 4.1%.", "https://x.com/b", "x.com"),
    ]
    with patch.object(judge, "ollama") as mock_ollama:
        mock_ollama.chat.return_value = _fake_chat(
            {"label": "TRUE", "confidence": 0.8, "explanation": "ok", "sources": [0]})
        judge.judge_claim("Unemployment was 3.5%.", snippets)

    sent = mock_ollama.chat.call_args.kwargs["messages"][1]["content"]
    assert "[published Jun 5, 2019]" in sent      # dated evidence is labelled
    assert "[date unknown]" in sent               # undated evidence is flagged as such
    assert date.today().isoformat() in sent       # and the model isn't left guessing "now"
