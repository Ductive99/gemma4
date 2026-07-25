import json
import threading

from redpen import sources


def test_transcript_segments_reads_file(tmp_path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"segments": [
        {"start": 0.0, "end": 1.0, "text": "hello "},
        {"start": 1.0, "end": 2.0, "text": "world"},
    ]}), encoding="utf-8")

    segs = list(sources.transcript_segments(path, threading.Event(), realtime=False))
    assert [s.text for s in segs] == ["hello", "world"]
    assert segs[1].end == 2.0


def test_transcript_segments_honours_stop_event(tmp_path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps([{"start": 0.0, "end": 1.0, "text": "a"}]), encoding="utf-8")

    stop = threading.Event()
    stop.set()
    assert list(sources.transcript_segments(path, stop, realtime=False)) == []


def test_cached_events_replays_event_log(tmp_path):
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"events": [
        {"at": 0.0, "event": {"type": "transcript", "text": "a"}},
        {"at": 0.0, "event": {"type": "claim", "text": "b"}},
    ]}), encoding="utf-8")

    events = list(sources.cached_events(path))
    assert [e["type"] for e in events] == ["transcript", "claim"]
