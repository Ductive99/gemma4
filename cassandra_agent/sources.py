"""Segment sources — the three ways transcript can enter the pipeline.

The pipeline only needs *timestamped transcript segments*; where they come from
is swappable. This matters for demos: the live YouTube path chains yt-dlp,
ffmpeg and Whisper, any of which can fail on venue wifi, while the replay paths
keep the interesting half of the system (Gemma + SerpApi, live) fully real.

  live      YouTube/stream audio -> ffmpeg -> Whisper -> segments
  transcript  pre-written timestamped transcript -> segments  (Gemma+SerpApi live)
  cached    a recorded event log replayed verbatim            (fully offline)
"""

import json
import time
from pathlib import Path

from . import config
from .events import TranscriptSegment


def live_segments(youtube_url: str, stop_event):
    """Yields segments transcribed from live YouTube/stream audio."""
    from .ingest import YoutubeAudioSource
    from .transcribe import Transcriber

    transcriber = Transcriber()
    with YoutubeAudioSource(youtube_url) as source:
        for chunk in source.chunks():
            if stop_event.is_set():
                return
            yield from transcriber.transcribe_chunk(chunk)


def transcript_segments(path, stop_event, speed: float = None, realtime: bool = True):
    """Replays a pre-written timestamped transcript at (accelerated) wall-clock pace.

    Gemma and SerpApi still run for real against these segments — only the
    audio-decode and speech-to-text stages are bypassed.
    """
    speed = speed or config.REPLAY_SPEED
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    segments = data["segments"] if isinstance(data, dict) else data

    started = time.monotonic()
    for raw in segments:
        if stop_event.is_set():
            return
        segment = TranscriptSegment(
            start=float(raw["start"]), end=float(raw["end"]), text=raw["text"].strip()
        )
        if realtime:
            # Release at the segment's START so captions appear as the words are
            # spoken and the client can reveal them across the segment's duration.
            # Releasing at .end would always put captions behind the audio.
            due = segment.start / speed
            delay = due - (time.monotonic() - started)
            if delay > 0:
                # sleep in slices so a stop request is honoured promptly
                deadline = time.monotonic() + delay
                while time.monotonic() < deadline:
                    if stop_event.is_set():
                        return
                    time.sleep(min(0.2, deadline - time.monotonic()))
        yield segment


def cached_events(path, speed: float = None):
    """Replays a previously recorded run's event log verbatim, fully offline.

    Last-resort demo mode: no Gemma, no network, no audio. Used only if live
    inference is unavailable at pitch time.
    """
    speed = speed or config.REPLAY_SPEED
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    events = data["events"] if isinstance(data, dict) else data

    previous = 0.0
    for entry in events:
        offset = float(entry.get("at", previous))
        gap = (offset - previous) / speed
        if gap > 0:
            time.sleep(min(gap, 3.0))
        previous = offset
        yield entry["event"]
