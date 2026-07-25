"""FastAPI web app: start a fact-checking session against a YouTube URL, then
stream transcript/claim/verdict events to a live overlay UI over a WebSocket.
"""

import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .pipeline import DebateFactCheckPipeline

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Red Pen — Debate Fact Checker")


class Session:
    def __init__(self, session_id: str, youtube_url: str, mode: str = "live", source_path: str = ""):
        self.id = session_id
        self.youtube_url = youtube_url
        self.mode = mode
        self.history: list[dict] = []
        self.websockets: set[WebSocket] = set()
        self.pipeline = DebateFactCheckPipeline(
            youtube_url, emit=self.emit, mode=mode, source_path=source_path
        )
        self.task: asyncio.Task | None = None
        self.error: str | None = None

    async def emit(self, event: dict) -> None:
        self.history.append(event)
        dead = []
        for ws in self.websockets:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.websockets.discard(ws)

    async def start(self) -> None:
        async def guarded_run():
            try:
                await self.pipeline.run()
            except Exception as exc:  # noqa: BLE001 - surface any pipeline failure to the UI
                self.error = str(exc)
                await self.emit({"type": "error", "message": str(exc)})

        self.task = asyncio.create_task(guarded_run())


SESSIONS: dict[str, Session] = {}


DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"


class StartSessionRequest(BaseModel):
    youtube_url: str = ""
    # "prefetch"   -> YouTube captions analysed ahead of playback, results
    #                 released against the video's real playhead
    # "live"       -> YouTube audio + Whisper + Gemma + SerpApi, in real time
    # "transcript" -> replay a transcript file; Gemma + SerpApi still run live
    # "cached"     -> replay a recorded run verbatim, fully offline
    mode: str = "live"
    source_path: str = ""


@app.post("/api/sessions")
async def start_session(req: StartSessionRequest) -> dict:
    source_path = req.source_path
    if req.mode == "transcript" and not source_path:
        source_path = str(DEMO_DIR / "sample_debate.json")
    if req.mode == "cached" and not source_path:
        source_path = str(DEMO_DIR / "cached_run.json")

    session_id = uuid.uuid4().hex[:8]
    session = Session(session_id, req.youtube_url, mode=req.mode, source_path=source_path)
    SESSIONS[session_id] = session
    await session.start()
    return {"session_id": session_id, "mode": req.mode}


@app.get("/api/sessions/{session_id}/recording")
async def session_recording(session_id: str) -> dict:
    """Exports a finished run as a cached event log, replayable offline."""
    session = SESSIONS.get(session_id)
    if session is None:
        return {"error": "session not found"}
    return {"events": session.pipeline.recorded}


@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str) -> dict:
    session = SESSIONS.get(session_id)
    if session is None:
        return {"error": "session not found"}
    session.pipeline.stop()
    return {"ok": True}


@app.get("/api/sessions/{session_id}")
async def session_status(session_id: str) -> dict:
    session = SESSIONS.get(session_id)
    if session is None:
        return {"error": "session not found"}
    return {
        "session_id": session.id,
        "youtube_url": session.youtube_url,
        "running": session.task is not None and not session.task.done(),
        "error": session.error,
        "event_count": len(session.history),
    }


@app.websocket("/ws/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str) -> None:
    session = SESSIONS.get(session_id)
    if session is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    session.websockets.add(websocket)
    try:
        for event in session.history:
            await websocket.send_json(event)
        while True:
            await websocket.receive_text()  # client sends nothing meaningful; just detect disconnects
    except WebSocketDisconnect:
        pass
    finally:
        session.websockets.discard(websocket)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if (STATIC_DIR).exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
