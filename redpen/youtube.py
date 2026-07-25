"""Pulls an existing caption track off a YouTube video.

A recorded video already has a transcript, so for VOD there is no reason to
decode audio and run speech-to-text: yt-dlp can hand us timed text directly.
That removes ffmpeg and Whisper from the path entirely and makes the whole
analysis run far faster than playback, which is what lets the agent work ahead
of the playhead.
"""

import json

import requests

from .events import TranscriptSegment


def _pick_track(info: dict, languages: tuple) -> list:
    """Prefers human-written subtitles, falls back to YouTube's auto-captions."""
    for source in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for lang in languages:
            for key in (lang, f"{lang}-orig"):
                if source.get(key):
                    return source[key]
        # any variant of a requested language, e.g. "en-GB"
        for key, formats in source.items():
            if any(key.startswith(lang) for lang in languages) and formats:
                return formats
    return []


def _parse_json3(payload: dict) -> list[TranscriptSegment]:
    segments = []
    for event in payload.get("events", []):
        segs = event.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs).strip()
        if not text or text == "\n":
            continue
        start = event.get("tStartMs", 0) / 1000.0
        duration = event.get("dDurationMs", 0) / 1000.0
        segments.append(TranscriptSegment(start=start, end=start + duration, text=text))
    return segments


def fetch_transcript(url: str, languages: tuple = ("en",)) -> list[TranscriptSegment]:
    """Returns the video's caption track as timestamped segments.

    Raises RuntimeError if the video has no usable captions — the caller should
    fall back to the audio + Whisper path rather than failing the session.
    """
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)

    track = _pick_track(info, languages)
    if not track:
        raise RuntimeError("This video has no caption track available.")

    fmt = next((f for f in track if f.get("ext") == "json3"), None) or track[0]
    if not fmt.get("url"):
        raise RuntimeError("Caption track has no downloadable URL.")

    response = requests.get(fmt["url"], timeout=20)
    response.raise_for_status()

    try:
        segments = _parse_json3(response.json())
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Could not parse the caption track: {exc}") from None

    if not segments:
        raise RuntimeError("Caption track parsed but contained no text.")
    return segments
