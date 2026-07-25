import pytest

from redpen import youtube


def test_parse_json3_builds_timed_segments():
    payload = {"events": [
        {"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "Hello "}, {"utf8": "world"}]},
        {"tStartMs": 2000, "dDurationMs": 1500, "segs": [{"utf8": "\n"}]},   # dropped
        {"tStartMs": 3500, "dDurationMs": 1000, "segs": [{"utf8": "Second line"}]},
    ]}
    segs = youtube._parse_json3(payload)
    assert [s.text for s in segs] == ["Hello world", "Second line"]
    assert segs[0].start == 0.0 and segs[0].end == 2.0
    assert segs[1].start == 3.5


def test_pick_track_prefers_manual_over_automatic():
    info = {
        "subtitles": {"en": [{"ext": "json3", "url": "manual"}]},
        "automatic_captions": {"en": [{"ext": "json3", "url": "auto"}]},
    }
    assert youtube._pick_track(info, ("en",))[0]["url"] == "manual"


def test_pick_track_falls_back_to_automatic_captions():
    info = {"subtitles": {}, "automatic_captions": {"en": [{"ext": "json3", "url": "auto"}]}}
    assert youtube._pick_track(info, ("en",))[0]["url"] == "auto"


def test_pick_track_accepts_language_variants():
    info = {"subtitles": {"en-GB": [{"ext": "json3", "url": "gb"}]}, "automatic_captions": {}}
    assert youtube._pick_track(info, ("en",))[0]["url"] == "gb"


def test_pick_track_returns_empty_when_nothing_matches():
    assert youtube._pick_track({"subtitles": {"fr": [{"url": "x"}]}}, ("en",)) == []
