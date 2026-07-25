import asyncio
from unittest.mock import patch

import pytest

from cassandra_agent.events import Snippet, TranscriptSegment, Verdict
from cassandra_agent.pipeline import DebateFactCheckPipeline


@pytest.mark.asyncio
async def test_handle_segment_emits_transcript_claim_and_verdict():
    events = []

    async def emit(event):
        events.append(event)

    pipeline = DebateFactCheckPipeline("https://youtube.com/watch?v=x", emit=emit)
    loop = asyncio.get_event_loop()
    segment = TranscriptSegment(start=0.0, end=5.0, text="The unemployment rate hit 3% last month.")

    with patch("cassandra_agent.pipeline.extract_claims", return_value=["Unemployment hit 3% last month."]) as mock_extract, \
         patch("cassandra_agent.pipeline.search_evidence", return_value=[Snippet("t", "s", "https://x", "x")]) as mock_search, \
         patch("cassandra_agent.pipeline.judge_claim") as mock_judge:
        mock_judge.return_value = Verdict(
            claim_id="", claim_text="Unemployment hit 3% last month.",
            label="TRUE", confidence=0.8, explanation="matches", sources=["https://x"],
        )
        await pipeline._handle_segment(segment, loop)
        await asyncio.sleep(0.05)  # let the fire-and-forget fact-check task run

    types = [e["type"] for e in events]
    assert types == ["transcript", "claim", "verdict"]
    assert events[1]["text"] == "Unemployment hit 3% last month."
    assert events[2]["label"] == "TRUE"
    assert events[2]["claim_id"] == events[1]["id"]
    mock_extract.assert_called_once()
    mock_search.assert_called_once()
    mock_judge.assert_called_once()


@pytest.mark.asyncio
async def test_handle_segment_skips_already_flagged_claims():
    events = []

    async def emit(event):
        events.append(event)

    pipeline = DebateFactCheckPipeline("https://youtube.com/watch?v=x", emit=emit)
    pipeline._flagged_claims.append("Already known claim.")
    loop = asyncio.get_event_loop()
    segment = TranscriptSegment(start=0.0, end=5.0, text="Some text.")

    with patch("cassandra_agent.pipeline.extract_claims", return_value=["Already known claim."]), \
         patch("cassandra_agent.pipeline.search_evidence") as mock_search, \
         patch("cassandra_agent.pipeline.judge_claim") as mock_judge:
        await pipeline._handle_segment(segment, loop)
        await asyncio.sleep(0.05)

    types = [e["type"] for e in events]
    assert types == ["transcript"]
    mock_search.assert_not_called()
    mock_judge.assert_not_called()


@pytest.mark.asyncio
async def test_window_drops_segments_outside_transcript_window():
    events = []

    async def emit(event):
        events.append(event)

    pipeline = DebateFactCheckPipeline("https://youtube.com/watch?v=x", emit=emit)
    loop = asyncio.get_event_loop()

    with patch("cassandra_agent.pipeline.extract_claims", return_value=[]) as mock_extract:
        await pipeline._handle_segment(TranscriptSegment(0.0, 5.0, "old text"), loop)
        await pipeline._handle_segment(TranscriptSegment(100.0, 105.0, "new text"), loop)

    # second call's window should have dropped the far-past "old text" segment
    last_call_args = mock_extract.call_args_list[-1]
    assert "old text" not in last_call_args[0][0]
    assert "new text" in last_call_args[0][0]
