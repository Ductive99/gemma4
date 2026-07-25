"""Wires the autonomous loop together:

  transcript segments -> rolling window -> claim spotting (Gemma)
  -> evidence retrieval (SerpApi) -> verdict (Gemma) -> emitted events

Segments arrive from one of three sources (see sources.py). Producing them is
blocking and CPU-bound, so it runs in a background thread and hands segments to
the asyncio loop through a queue; each Gemma/SerpApi call runs in the executor
so the event loop keeps streaming to connected clients throughout.

Two throughput rules keep the loop real-time against a local model whose calls
cost seconds, not milliseconds:

  * claim spotting is debounced — it waits for CLAIM_SCAN_MIN_CHARS of new
    speech rather than firing on every segment;
  * claim spotting is single-flight — while one pass is in flight, incoming
    speech accumulates in the window instead of queueing more passes behind it.

Judging is deliberately *not* serialised: verdicts are independent, so they
resolve concurrently and stream into the UI as each one lands.
"""

import asyncio
import threading
import time
import uuid
from typing import Awaitable, Callable

from . import config, sources
from .claims import extract_claims
from .evidence import search_evidence
from .events import Claim, SessionContext, TranscriptSegment
from .judge import judge_claim

EmitFn = Callable[[dict], Awaitable[None]]


class DebateFactCheckPipeline:
    def __init__(
        self,
        youtube_url: str = "",
        emit: EmitFn = None,
        *,
        mode: str = "live",
        source_path: str = "",
        ollama_model: str = None,
        serpapi_key: str = None,
    ):
        self.youtube_url = youtube_url
        self.emit = emit
        self.mode = mode
        self.source_path = source_path
        self.claim_model = ollama_model or config.CLAIM_MODEL
        self.judge_model = ollama_model or config.JUDGE_MODEL
        self.serpapi_key = serpapi_key if serpapi_key is not None else config.SERPAPI_API_KEY

        self.context = SessionContext()
        self._stop_event = threading.Event()
        self._window: list[TranscriptSegment] = []
        self._flagged_claims: list[str] = []
        self._unscanned_chars = 0
        self._scan_in_flight = False
        self._started_at = time.monotonic()
        self.recorded: list[dict] = []

    def stop(self) -> None:
        self._stop_event.set()

    async def _emit(self, event: dict) -> None:
        # Record with a relative timestamp so a run can be replayed later as a
        # fully offline cached demo.
        self.recorded.append({"at": round(time.monotonic() - self._started_at, 2), "event": event})
        await self.emit(event)

    async def run(self) -> None:
        if self.mode == "cached":
            await self._run_cached()
            return

        loop = asyncio.get_event_loop()
        queue: "asyncio.Queue[TranscriptSegment | None]" = asyncio.Queue()

        # Resolve who/what we're watching before any claim is spotted, so the
        # very first claim already benefits from knowing the participants.
        await self._load_context(loop)

        def produce() -> None:
            try:
                if self.mode == "transcript":
                    stream = sources.transcript_segments(self.source_path, self._stop_event)
                else:
                    stream = sources.live_segments(self.youtube_url, self._stop_event)
                for segment in stream:
                    if self._stop_event.is_set():
                        break
                    asyncio.run_coroutine_threadsafe(queue.put(segment), loop)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        producer = loop.run_in_executor(None, produce)
        pending: set[asyncio.Task] = set()

        try:
            while True:
                segment = await queue.get()
                if segment is None or self._stop_event.is_set():
                    break
                await self._handle_segment(segment, loop, pending)
        finally:
            self._stop_event.set()
            await producer
            if pending:
                # let in-flight fact-checks finish so their verdicts still land
                await asyncio.gather(*pending, return_exceptions=True)
            await self._emit({"type": "done"})

    async def _load_context(self, loop: asyncio.AbstractEventLoop) -> None:
        try:
            if self.mode == "transcript":
                self.context = await loop.run_in_executor(
                    None, sources.transcript_context, self.source_path
                )
            elif self.youtube_url:
                from .ingest import fetch_context

                self.context = await loop.run_in_executor(None, fetch_context, self.youtube_url)
        except Exception:  # noqa: BLE001 - run without context rather than not at all
            self.context = SessionContext()
        await self._emit(self.context.to_event())

    async def _run_cached(self) -> None:
        loop = asyncio.get_event_loop()
        queue: "asyncio.Queue[dict | None]" = asyncio.Queue()

        def produce() -> None:
            try:
                for event in sources.cached_events(self.source_path):
                    if self._stop_event.is_set():
                        break
                    asyncio.run_coroutine_threadsafe(queue.put(event), loop)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        producer = loop.run_in_executor(None, produce)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                await self.emit(event)
        finally:
            self._stop_event.set()
            await producer

    async def _handle_segment(
        self, segment: TranscriptSegment, loop: asyncio.AbstractEventLoop, pending: set = None
    ) -> None:
        await self._emit(segment.to_event())

        self._window.append(segment)
        cutoff = segment.end - config.TRANSCRIPT_WINDOW_SECONDS
        self._window = [s for s in self._window if s.end >= cutoff]
        self._unscanned_chars += len(segment.text)

        if self._scan_in_flight or self._unscanned_chars < config.CLAIM_SCAN_MIN_CHARS:
            return

        # Speaker-labelled, so Gemma can attribute claims and resolve pronouns.
        window_text = "\n".join(s.labelled() for s in self._window)
        self._unscanned_chars = 0
        self._scan_in_flight = True
        try:
            recent = self._flagged_claims[-config.MAX_FLAGGED_CLAIMS_MEMORY:]
            new_claims = await loop.run_in_executor(
                None, extract_claims, window_text, recent,
                self.claim_model, self.context.to_prompt_block(),
            )
        finally:
            self._scan_in_flight = False

        for entry in new_claims:
            claim_text = entry["claim"]
            if claim_text in self._flagged_claims:
                continue
            self._flagged_claims.append(claim_text)
            claim = Claim(
                id=uuid.uuid4().hex,
                text=claim_text,
                context=window_text,
                timestamp=segment.end,
                speaker=entry.get("speaker", "") or segment.speaker,
                search_query=entry.get("search_query", "") or claim_text,
            )
            await self._emit(claim.to_event())
            task = asyncio.create_task(self._fact_check(claim, loop))
            if pending is not None:
                pending.add(task)
                task.add_done_callback(pending.discard)

    async def _fact_check(self, claim: Claim, loop: asyncio.AbstractEventLoop) -> None:
        try:
            # Search Gemma's speaker-aware query, not the raw claim text.
            snippets = await loop.run_in_executor(
                None, search_evidence, claim.search_query, self.serpapi_key
            )
            verdict = await loop.run_in_executor(
                None, judge_claim, claim.text, snippets, self.judge_model,
                claim.speaker, self.context.to_prompt_block(),
            )
            verdict.claim_id = claim.id
            await self._emit(verdict.to_event())
        except Exception as exc:  # noqa: BLE001 - one bad claim must not kill the run
            await self._emit({
                "type": "verdict", "claim_id": claim.id, "claim_text": claim.text,
                "speaker": claim.speaker, "label": "UNVERIFIED", "confidence": 0.0,
                "explanation": f"Fact-check failed: {exc}", "sources": [],
            })
