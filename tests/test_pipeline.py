import asyncio
from unittest.mock import patch

import pytest

from cassandra_agent import config
from cassandra_agent.events import Snippet, TranscriptSegment, Verdict
from cassandra_agent.pipeline import DebateFactCheckPipeline

LONG = "x" * (config.CLAIM_SCAN_MIN_CHARS + 1)


def _collector():
    events = []

    async def emit(event):
        events.append(event)

    return events, emit


@pytest.mark.asyncio
async def test_handle_segment_emits_transcript_claim_and_verdict():
    events, emit = _collector()
    pipeline = DebateFactCheckPipeline("https://youtube.com/watch?v=x", emit=emit)
    loop = asyncio.get_event_loop()
    segment = TranscriptSegment(start=0.0, end=5.0, text=LONG)

    with patch("cassandra_agent.pipeline.extract_claims", return_value=["Unemployment hit 3%."]) as mock_extract, \
         patch("cassandra_agent.pipeline.search_evidence", return_value=[Snippet("t", "s", "https://x", "x")]) as mock_search, \
         patch("cassandra_agent.pipeline.judge_claim") as mock_judge:
        mock_judge.return_value = Verdict(
            claim_id="", claim_text="Unemployment hit 3%.",
            label="TRUE", confidence=0.8, explanation="matches", sources=["https://x"],
        )
        await pipeline._handle_segment(segment, loop)
        await asyncio.sleep(0.05)

    assert [e["type"] for e in events] == ["transcript", "claim", "verdict"]
    assert events[2]["claim_id"] == events[1]["id"]
    assert events[2]["label"] == "TRUE"
    mock_extract.assert_called_once()
    mock_search.assert_called_once()
    mock_judge.assert_called_once()


@pytest.mark.asyncio
async def test_claim_scan_is_debounced_until_enough_new_speech():
    events, emit = _collector()
    pipeline = DebateFactCheckPipeline(emit=emit)
    loop = asyncio.get_event_loop()

    with patch("cassandra_agent.pipeline.extract_claims", return_value=[]) as mock_extract:
        await pipeline._handle_segment(TranscriptSegment(0.0, 1.0, "short"), loop)
        mock_extract.assert_not_called()  # below threshold - no Gemma call

        await pipeline._handle_segment(TranscriptSegment(1.0, 2.0, LONG), loop)
        mock_extract.assert_called_once()  # threshold crossed


@pytest.mark.asyncio
async def test_handle_segment_skips_already_flagged_claims():
    events, emit = _collector()
    pipeline = DebateFactCheckPipeline(emit=emit)
    pipeline._flagged_claims.append("Already known claim.")
    loop = asyncio.get_event_loop()

    with patch("cassandra_agent.pipeline.extract_claims", return_value=["Already known claim."]), \
         patch("cassandra_agent.pipeline.search_evidence") as mock_search, \
         patch("cassandra_agent.pipeline.judge_claim") as mock_judge:
        await pipeline._handle_segment(TranscriptSegment(0.0, 5.0, LONG), loop)
        await asyncio.sleep(0.05)

    assert [e["type"] for e in events] == ["transcript"]
    mock_search.assert_not_called()
    mock_judge.assert_not_called()


@pytest.mark.asyncio
async def test_window_drops_segments_outside_transcript_window():
    events, emit = _collector()
    pipeline = DebateFactCheckPipeline(emit=emit)
    loop = asyncio.get_event_loop()

    with patch("cassandra_agent.pipeline.extract_claims", return_value=[]) as mock_extract:
        await pipeline._handle_segment(TranscriptSegment(0.0, 5.0, "old text " + LONG), loop)
        await pipeline._handle_segment(TranscriptSegment(100.0, 105.0, "new text " + LONG), loop)

    window = mock_extract.call_args_list[-1][0][0]
    assert "old text" not in window
    assert "new text" in window


@pytest.mark.asyncio
async def test_fact_check_failure_emits_unverified_instead_of_crashing():
    events, emit = _collector()
    pipeline = DebateFactCheckPipeline(emit=emit)
    loop = asyncio.get_event_loop()

    with patch("cassandra_agent.pipeline.extract_claims", return_value=["a claim"]), \
         patch("cassandra_agent.pipeline.search_evidence", side_effect=RuntimeError("serpapi down")):
        await pipeline._handle_segment(TranscriptSegment(0.0, 5.0, LONG), loop)
        await asyncio.sleep(0.05)

    verdict = events[-1]
    assert verdict["type"] == "verdict"
    assert verdict["label"] == "UNVERIFIED"
    assert "serpapi down" in verdict["explanation"]


@pytest.mark.asyncio
async def test_run_records_events_for_offline_replay():
    events, emit = _collector()
    pipeline = DebateFactCheckPipeline(emit=emit)
    loop = asyncio.get_event_loop()

    with patch("cassandra_agent.pipeline.extract_claims", return_value=[]):
        await pipeline._handle_segment(TranscriptSegment(0.0, 5.0, LONG), loop)

    assert len(pipeline.recorded) == 1
    assert pipeline.recorded[0]["event"]["type"] == "transcript"
    assert "at" in pipeline.recorded[0]
