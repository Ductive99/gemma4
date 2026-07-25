"""Wires the whole autonomous loop together:

  YouTube audio -> STT -> rolling transcript window -> claim extraction (Gemma)
  -> evidence search (SerpApi) -> verdict (Gemma) -> emitted events

Audio capture + transcription are CPU-bound and blocking, so they run in a
background thread and hand transcript segments back to the asyncio event loop
through a queue. Claim extraction, evidence search and judging each run in
the default executor so they don't block the event loop either.
"""

import asyncio
import threading
import uuid
from typing import Awaitable, Callable

from . import config
from .claims import extract_claims
from .evidence import search_evidence
from .events import Claim, TranscriptSegment
from .ingest import YoutubeAudioSource
from .judge import judge_claim
from .transcribe import Transcriber

EmitFn = Callable[[dict], Awaitable[None]]


class DebateFactCheckPipeline:
    def __init__(
        self,
        youtube_url: str,
        emit: EmitFn,
        *,
        ollama_model: str = None,
        serpapi_key: str = None,
    ):
        self.youtube_url = youtube_url
        self.emit = emit
        self.model = ollama_model or config.OLLAMA_MODEL
        self.serpapi_key = serpapi_key or config.SERPAPI_API_KEY

        self._stop_event = threading.Event()
        self._window: list[TranscriptSegment] = []
        self._flagged_claims: list[str] = []

    def stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        loop = asyncio.get_event_loop()
        segment_queue: "asyncio.Queue[TranscriptSegment | None]" = asyncio.Queue()

        def produce_segments() -> None:
            try:
                transcriber = Transcriber()
                with YoutubeAudioSource(self.youtube_url) as source:
                    for chunk in source.chunks():
                        if self._stop_event.is_set():
                            break
                        for segment in transcriber.transcribe_chunk(chunk):
                            asyncio.run_coroutine_threadsafe(segment_queue.put(segment), loop)
            finally:
                asyncio.run_coroutine_threadsafe(segment_queue.put(None), loop)

        producer_future = loop.run_in_executor(None, produce_segments)

        try:
            while True:
                segment = await segment_queue.get()
                if segment is None or self._stop_event.is_set():
                    break
                await self._handle_segment(segment, loop)
        finally:
            self._stop_event.set()
            await producer_future

    async def _handle_segment(self, segment: TranscriptSegment, loop: asyncio.AbstractEventLoop) -> None:
        await self.emit(segment.to_event())

        self._window.append(segment)
        cutoff = segment.end - config.TRANSCRIPT_WINDOW_SECONDS
        self._window = [s for s in self._window if s.end >= cutoff]
        window_text = " ".join(s.text for s in self._window)

        recent_flagged = self._flagged_claims[-config.MAX_FLAGGED_CLAIMS_MEMORY:]
        new_claims = await loop.run_in_executor(
            None, extract_claims, window_text, recent_flagged, self.model
        )

        for claim_text in new_claims:
            if claim_text in self._flagged_claims:
                continue
            self._flagged_claims.append(claim_text)
            claim = Claim(id=uuid.uuid4().hex, text=claim_text, context=window_text, timestamp=segment.end)
            await self.emit(claim.to_event())
            asyncio.create_task(self._fact_check(claim, loop))

    async def _fact_check(self, claim: Claim, loop: asyncio.AbstractEventLoop) -> None:
        snippets = await loop.run_in_executor(None, search_evidence, claim.text, self.serpapi_key)
        verdict = await loop.run_in_executor(None, judge_claim, claim.text, snippets, self.model)
        verdict.claim_id = claim.id
        await self.emit(verdict.to_event())
