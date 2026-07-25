# Red Pen — an autonomous debate fact-checker built on Gemma 4

**Paris Gemma 4 Hackathon · Track 2 — Autonomous Agents**

Red Pen listens to a debate as it happens, decides on its own which sentences are
worth checking, goes and finds evidence on the open web, and returns a verdict with
sources — while the speaker is still talking.

It is an agent, not a chatbot: nobody hands it a claim. It takes observable actions
(retrieve audio, transcribe, search, judge) against a live, unscripted input stream.

---

## The problem

Fact-checking is too slow to matter. A false claim made in a televised debate reaches
its audience instantly; the correction arrives the next morning, to a fraction of that
audience, long after the claim has done its work. The bottleneck is not knowledge — the
evidence is usually a single web search away — it is that a human has to notice the
claim, decide it is checkable, search, read, and judge. That loop takes minutes.

Red Pen closes that loop in seconds, locally.

## How it works

```
YouTube / live stream
        │  yt-dlp + ffmpeg
        ▼
   PCM audio chunks
        │  faster-whisper (on-device)
        ▼
 timestamped transcript ──► rolling 25s window
                                  │
                                  │  ① Gemma 4 — claim spotting
                                  ▼
                          new checkable claims
                                  │  ② SerpApi — evidence retrieval
                                  ▼
                          web evidence snippets
                                  │  ③ Gemma 4 — verdict
                                  ▼
              TRUE / FALSE / MISLEADING / UNVERIFIED + confidence + sources
                                  │  WebSocket
                                  ▼
                        live browser overlay
```

### Where Gemma 4 is essential

Gemma runs **twice per claim, in two deliberately separate roles**:

1. **Claim spotting** (`claims.py`) — given the video's context, a speaker-labelled
   window of live speech, and the claims already flagged, Gemma decides which
   sentences are *checkable factual assertions* rather than opinion, prediction or
   rhetoric; attributes each to whoever said it; resolves pronouns into
   self-contained statements; and **writes the web search that would settle it**.
   This is the judgement call that makes the agent autonomous; a keyword matcher
   cannot do it.
2. **Judging** (`judge.py`) — given the claim, who said it, and the retrieved
   evidence *only*, Gemma returns a structured verdict, a confidence, an
   explanation, and which sources support it.

### Knowing who is talking

A debate claim is usually unanswerable stripped of its speaker. "He cut taxes by
30%", "my opponent voted against it", "under my administration inflation fell" are
all useless as raw search strings. So the agent establishes context *before* the
first claim is spotted:

- **live mode** reads the video's own metadata through yt-dlp — title, channel,
  publication date, description — which for a debate upload usually names the
  participants;
- **transcript mode** reads the `context` block the transcript file declares.

That context, plus speaker-labelled transcript, goes into the claim-spotting prompt.
Gemma resolves the pronoun to a name and puts that name into the search query, so
SerpApi is asked `Marc Devereux vote energy bill` rather than `voted against it`.
The judge is told the speaker too — so it can reject evidence that turns out to be
about somebody else, while weighing both sides by the same standard.

Speaker labels come from the transcript in replay mode. Live audio has no
diarisation, so Gemma attributes from context and cues alone; that is the weakest
link in the chain and the honest place to start if you extend this.

Both calls use Gemma's JSON-constrained output so the agent's decisions are typed data
that drive control flow, not prose for a human to read.

### Separation of powers

This project began as a falsification engine whose core rule was that **Gemma never
judges its own reasoning**. That rule survived into the fact-checker, and it is what
keeps verdicts honest: the judging call is given a claim someone *else* made plus
evidence someone *else* retrieved. It has no memory of, and no stake in, the claim's
origin — so it cannot rationalise its way into defending a previous answer.

## Running it

```bash
pip install -r requirements.txt
ollama pull gemma4          # and make sure `ollama serve` is running
export SERPAPI_API_KEY=...  # optional; without it every claim returns UNVERIFIED
./start_live.sh             # http://localhost:8000
```

`ffmpeg` must be on `PATH` for the live YouTube mode.

### Three ways to run a session

Chosen from the dropdown in the UI, or via `mode` in `POST /api/sessions`:

| Mode | Audio + STT | Gemma | SerpApi | Use |
|---|---|---|---|---|
| `prefetch` | captions, no STT | **real** | **real** | A recorded YouTube video, analysed ahead of playback and synced to it |
| `live` | real | real | real | A live stream, checked in real time |
| `transcript` | bypassed | **real** | **real** | Replay `demo/sample_debate.json`; the agent's reasoning is fully live |
| `cached` | bypassed | bypassed | bypassed | Replay a recorded run verbatim, fully offline |

#### `prefetch` — working ahead of the playhead

A recorded video's transcript already exists, so there is no reason to decode audio
and run speech-to-text: yt-dlp hands us YouTube's own caption track directly. That
drops ffmpeg and Whisper from the path and makes analysis run far faster than
playback, so the agent finishes the whole video before the viewer is a minute into
it.

Each result is then tagged with the video timestamp it is due at — a claim card at
`REVEAL_CLAIM_DELAY` after the claim is spoken, its verdict at
`REVEAL_VERDICT_DELAY` — and the browser holds it until the player's *real*
playhead reaches that point. Pausing, seeking and scrubbing all keep the overlay in
sync, exactly like a subtitle track.

**Be straight about what this is.** The analysis is entirely real: Gemma spots the
claims, SerpApi retrieves the evidence, Gemma judges it. Only the moment of display
is scheduled. It is prefetching applied to inference, and it is the right
architecture for recorded video — but it is *not* a measurement of live latency, and
shouldn't be presented as one. `live` mode is the real-time path.

`transcript` mode exists because the live path chains four dependencies (yt-dlp, ffmpeg,
Whisper, Ollama) and any of them can fail on venue wifi. It removes the fragile half
while keeping the half that matters — Gemma and SerpApi still run for real.

To rehearse the pitch, or to see the UI without a model or an API key:

```bash
python3 demo/rehearse.py    # Gemma + SerpApi stubbed, everything else real
```

Stub verdicts are prefixed `[REHEARSAL STUB]` in the UI so a rehearsal can never be
mistaken for a real run.

To record a real run as an offline fallback:

```bash
curl localhost:8000/api/sessions/<id>/recording > demo/cached_run.json
```

## Design decisions made under time pressure

**Debounced claim spotting.** A local 9.6 GB Gemma takes seconds per call; Whisper emits
segments every few seconds. Calling Gemma on every segment made the pipeline fall
permanently behind the stream within a minute. Claim spotting now waits for
`CLAIM_SCAN_MIN_CHARS` of *new* speech and is single-flight — while a pass is running,
speech accumulates in the window instead of queueing more passes behind it.

**Judging is deliberately not serialised.** Verdicts are independent, so they resolve
concurrently and stream into the UI as each lands. A slow check never blocks the next
claim from being spotted.

**`keep_alive` on every call.** The original prototype measured ~31 s per call because
each one reloaded the model. Keeping it resident is the difference between a demo and a
slideshow.

**Per-stage model selection.** `CLAIM_MODEL` and `JUDGE_MODEL` are separate env vars, so
the continuously-running hot path can use a smaller Gemma than the once-per-claim judge.

## Layout

```
redpen/
  sources.py     three ways transcript enters the pipeline
  ingest.py      YouTube -> PCM via yt-dlp + ffmpeg
  transcribe.py  faster-whisper, on-device
  claims.py      Gemma call ① — claim spotting
  evidence.py    SerpApi retrieval
  judge.py       Gemma call ② — verdict
  pipeline.py    async orchestration, debouncing, recording
  server.py      FastAPI + WebSocket
static/index.html  live overlay UI
demo/              sample transcript + rehearsal harness
tests/             26 tests, external services mocked
```

The project was called **Cassandra** during the sprint and was renamed to **Red Pen**.
`cassandra_v1.py`, `cassandra_demo.py`, `start_demo.sh`, `PASSATION.md` and the root
`test_*.py` scripts are that earlier falsification-engine prototype, kept unchanged for
reference — they are not part of the running application.

## Tests

```bash
python3 -m pytest tests/ -q
```

Ollama, ffmpeg and Whisper are not available in CI, so those boundaries are mocked;
the tests cover the pipeline's control flow, debouncing, deduplication, window
eviction, failure handling, and the replay sources.

## Honest limitations

- Verdicts are only as good as the top few SerpApi snippets — the agent reads search
  results, not primary sources.
- Whisper errors propagate: a misheard number becomes a misjudged claim.
- Claim spotting is tuned to be eager; it prefers flagging a borderline claim over
  missing one, so `UNVERIFIED` is common and expected.
- The system reports what the evidence supports. It is a research aid, not an arbiter.
