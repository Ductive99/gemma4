import asyncio
from unittest.mock import patch

import pytest

from redpen import config
from redpen.events import Snippet, TranscriptSegment, Verdict
from redpen.pipeline import DebateFactCheckPipeline

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

    with patch("redpen.pipeline.extract_claims", return_value=[{"claim": "Unemployment hit 3%.", "speaker": "Speaker B",
                                 "search_query": "unemployment rate 3 percent"}]) as mock_extract, \
         patch("redpen.pipeline.search_evidence", return_value=[Snippet("t", "s", "https://x", "x")]) as mock_search, \
         patch("redpen.pipeline.judge_claim") as mock_judge:
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

    with patch("redpen.pipeline.extract_claims", return_value=[]) as mock_extract:
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

    with patch("redpen.pipeline.extract_claims", return_value=[{"claim": "Already known claim.", "speaker": "", "search_query": "q"}]), \
         patch("redpen.pipeline.search_evidence") as mock_search, \
         patch("redpen.pipeline.judge_claim") as mock_judge:
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

    with patch("redpen.pipeline.extract_claims", return_value=[]) as mock_extract:
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

    with patch("redpen.pipeline.extract_claims", return_value=[{"claim": "a claim", "speaker": "", "search_query": "q"}]), \
         patch("redpen.pipeline.search_evidence", side_effect=RuntimeError("serpapi down")):
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

    with patch("redpen.pipeline.extract_claims", return_value=[]):
        await pipeline._handle_segment(TranscriptSegment(0.0, 5.0, LONG), loop)

    assert len(pipeline.recorded) == 1
    assert pipeline.recorded[0]["event"]["type"] == "transcript"
    assert "at" in pipeline.recorded[0]


@pytest.mark.asyncio
async def test_speaker_aware_search_query_is_what_reaches_serpapi():
    """The whole point of speaker context: search the resolved query, not the raw claim."""
    events, emit = _collector()
    pipeline = DebateFactCheckPipeline(emit=emit)
    loop = asyncio.get_event_loop()

    spotted = [{"claim": "Marc Devereux voted against the energy bill.",
                "speaker": "Dr. Lena Farrow",
                "search_query": "Marc Devereux vote energy bill"}]

    with patch("redpen.pipeline.extract_claims", return_value=spotted), \
         patch("redpen.pipeline.search_evidence", return_value=[]) as mock_search, \
         patch("redpen.pipeline.judge_claim") as mock_judge:
        mock_judge.return_value = Verdict(
            claim_id="", claim_text=spotted[0]["claim"], label="UNVERIFIED",
            confidence=0.2, explanation="", sources=[], speaker="Dr. Lena Farrow")
        await pipeline._handle_segment(TranscriptSegment(0.0, 5.0, LONG), loop)
        await asyncio.sleep(0.05)

    assert mock_search.call_args[0][0] == "Marc Devereux vote energy bill"
    # and the judge is told who spoke, so it can reject evidence about someone else
    assert mock_judge.call_args[0][3] == "Dr. Lena Farrow"
    claim_ev = next(e for e in events if e["type"] == "claim")
    assert claim_ev["speaker"] == "Dr. Lena Farrow"


@pytest.mark.asyncio
async def test_transcript_window_is_speaker_labelled():
    events, emit = _collector()
    pipeline = DebateFactCheckPipeline(emit=emit)
    loop = asyncio.get_event_loop()

    with patch("redpen.pipeline.extract_claims", return_value=[]) as mock_extract:
        await pipeline._handle_segment(
            TranscriptSegment(0.0, 5.0, LONG, speaker="Marc Devereux"), loop)

    assert mock_extract.call_args[0][0].startswith("Marc Devereux: ")


@pytest.mark.asyncio
async def test_prefetch_tags_events_with_video_reveal_times():
    """Analysis runs ahead of playback; each event carries when it is due on screen."""
    events, emit = _collector()
    pipeline = DebateFactCheckPipeline("https://youtu.be/abc", emit=emit, mode="prefetch")
    loop = asyncio.get_event_loop()

    segments = [TranscriptSegment(0.0, 5.0, LONG, speaker="A"),
                TranscriptSegment(5.0, 10.0, LONG, speaker="B")]
    spotted = [{"claim": "A claim.", "speaker": "A", "search_query": "a query"}]

    with patch("redpen.youtube.fetch_transcript", return_value=segments), \
         patch("redpen.pipeline.extract_claims", side_effect=[spotted, []]), \
         patch("redpen.pipeline.search_evidence", return_value=[]), \
         patch("redpen.pipeline.judge_claim") as mock_judge:
        mock_judge.return_value = Verdict(
            claim_id="", claim_text="A claim.", label="TRUE",
            confidence=0.9, explanation="ok", sources=[], speaker="A")
        await pipeline._run_prefetch(loop)

    kinds = [e["type"] for e in events]
    assert "ready" in kinds
    transcripts = [e for e in events if e["type"] == "transcript"]
    assert [t["reveal_at"] for t in transcripts] == [0.0, 5.0]

    claim = next(e for e in events if e["type"] == "claim")
    verdict = next(e for e in events if e["type"] == "verdict")
    assert claim["reveal_at"] == claim["timestamp"] + config.REVEAL_CLAIM_DELAY
    assert verdict["reveal_at"] == claim["timestamp"] + config.REVEAL_VERDICT_DELAY
    # the verdict is computed before it is due on screen — that is the whole point
    assert verdict["reveal_at"] > claim["reveal_at"]


@pytest.mark.asyncio
async def test_prefetch_reports_a_usable_error_when_captions_are_missing():
    events, emit = _collector()
    pipeline = DebateFactCheckPipeline("https://youtu.be/abc", emit=emit, mode="prefetch")

    with patch("redpen.youtube.fetch_transcript",
               side_effect=RuntimeError("This video has no caption track available.")):
        await pipeline._run_prefetch(asyncio.get_event_loop())

    err = next(e for e in events if e["type"] == "error")
    assert "caption track" in err["message"]
