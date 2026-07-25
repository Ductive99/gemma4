# Red Pen — an autonomous debate fact-checker that runs on your laptop

### Gemma 4 spots the checkable claims in live speech, searches the web for evidence, and returns a sourced verdict while the speaker is still talking.

**Track: Autonomous Agents**

---

## The problem

Fact-checking is too slow to matter.

A false claim made in a televised debate reaches its audience instantly. The
correction arrives the next morning, to a fraction of that audience, long after the
claim has done its work. The asymmetry is the whole problem: assertion is free and
instantaneous, verification is expensive and late.

The bottleneck is not knowledge. For most debate claims the evidence is one web
search away. The bottleneck is that a *human* has to notice the sentence, decide it
is checkable, phrase a search, read the results, and reach a judgement. That loop
takes minutes, and there are only so many people doing it.

Every step in that loop except the search itself is a judgement call — which is
exactly what a small language model can now make, locally, in seconds.

## What we built

Red Pen watches a debate — a YouTube video or a live stream — and fact-checks it
autonomously, in real time, with the verdicts overlaid on the video itself.

Nobody hands it a claim. It decides for itself what is worth checking, writes its
own search queries, retrieves real evidence through SerpApi, and returns a verdict
with confidence and sources. It takes observable actions against a live,
unscripted input stream, which is what makes it an agent rather than a chatbot.

## Architecture

```
YouTube / live stream
   │  yt-dlp + ffmpeg          → PCM audio chunks
   │  faster-whisper           → timestamped, speaker-labelled transcript
   ▼
rolling 25-second window
   │  ① Gemma 4                → checkable claims + speaker + search query
   │  ② SerpApi                → real web evidence
   │  ③ Gemma 4                → verdict, confidence, explanation, sources
   ▼
WebSocket → live browser overlay
```

Audio capture and speech-to-text are blocking and CPU-bound, so they run on a
background thread and feed the asyncio loop through a queue. Every model and network
call runs in an executor, so the event loop keeps streaming to the browser
throughout. Claim spotting is serialised; judging is not, so verdicts resolve
concurrently and land in the UI as each one completes.

## How Gemma 4 is used

Gemma runs **twice per claim, in two deliberately separated roles**. Both calls use
JSON-constrained output, so the model's decisions are typed data that drive control
flow — not prose for a human to read.

**① Claim spotting.** Given the video's context, a speaker-labelled window of live
speech, and the claims already flagged, Gemma decides which sentences are *checkable
factual assertions* rather than opinion, prediction or rhetoric. It attributes each
to whoever said it, resolves pronouns into self-contained statements, suppresses
paraphrases of claims it already flagged, and **writes the web search that would
settle it**. No keyword matcher can make that call.

That last output is the one that matters most. A debate claim is usually
unanswerable stripped of its speaker: *"he cut taxes by 30%"*, *"my opponent voted
against it"*, *"under my administration inflation fell"* are useless as raw search
strings. So Red Pen establishes context **before** the first claim is spotted — in
live mode by reading the video's own yt-dlp metadata (title, channel, date,
description, which for a debate upload usually names the participants). Gemma
resolves the pronoun to a name and puts that name in the query, so SerpApi is asked
`Marc Devereux vote energy bill` rather than `voted against it`.

**② Judging.** Given the claim, who said it, and the retrieved evidence *only*,
Gemma returns `TRUE` / `FALSE` / `MISLEADING` / `UNVERIFIED`, a confidence, a
one-sentence explanation, and indices of the snippets that support it.

**Separation of powers.** This project began as a falsification engine whose core
rule was that Gemma never judges its own reasoning. That rule survived into the
fact-checker and is what keeps verdicts honest: the judging call receives a claim
someone *else* made and evidence someone *else* retrieved. It has no memory of, and
no stake in, the claim's origin, so it cannot rationalise its way into defending a
previous answer. The judge is told the speaker so it can reject evidence about the
wrong person — with an explicit instruction that this must never change how
favourably it judges them, and that both sides are weighed by the same standard.

## Engineering process and technical choices

**Making a local model keep up with live speech.** The first working version fell
permanently behind the stream within a minute. Three fixes:

- *`keep_alive` on every call.* Our prototype measured ~31 s per call against a
  9.6 GB model. Without `keep_alive`, every call pays the model load again; keeping
  it resident removes that cost entirely and is the difference between a demo and a
  slideshow.
- *Debounced claim spotting.* Whisper emits segments every few seconds; calling
  Gemma on each one queued work faster than it drained. Spotting now waits for a
  threshold of *new* speech and is single-flight — while a pass runs, speech
  accumulates in the window instead of stacking more passes behind it.
- *Per-stage models.* `CLAIM_MODEL` and `JUDGE_MODEL` are separate, so the
  continuously-running hot path can use a smaller Gemma than the once-per-claim judge.

**Working ahead of the playhead.** For a *recorded* video the transcript already
exists, so we skip audio decoding and speech-to-text entirely and read YouTube's own
caption track through yt-dlp. Analysis then runs far faster than playback, so we tag
each result with the video timestamp it is due at and the browser holds it until the
player's real playhead arrives — pausing, seeking and scrubbing all stay in sync,
like a subtitle track. The analysis is entirely real; only the moment of display is
scheduled. It is prefetching applied to inference, and it is the right architecture
for VOD — though it is deliberately not a live-latency measurement, which is what
`live` mode is for.

**Designing the demo so it cannot die on stage.** The live path chains four
dependencies — yt-dlp, ffmpeg, Whisper, Ollama — any of which can fail on venue
wifi. So a session runs in one of three modes: `live`; `transcript`, which replays a
timestamped transcript while **Gemma and SerpApi still run for real**, removing the
fragile half while keeping the half that matters; and `cached`, which replays a
recorded run fully offline. Every run records its own event log, so a successful
live session can be exported as its own fallback.

**The bug that mattered.** While verifying the interface we found an infinite loop in
the overlay trim:

```js
while (overlay.children.length > 3) retire(overlay.firstElementChild);
```

`retire()` doesn't remove the node — it marks it for an exit animation and removes it
340 ms later. So the child is still there next iteration, already marked, and
`retire()` returns having done nothing. It fires the first time a fourth card arrives
while the first is still animating out — about ten seconds into a run — and wedges
the main thread completely. We caught it only because screenshots kept timing out and
we checked whether the page was still responsive rather than assuming a tooling
quirk. It would have frozen the browser on stage, exactly as the fact-checks started
landing.

## Limitations we are honest about

- Verdicts are only as good as the top few search snippets. Red Pen reads search
  results, not primary sources.
- Whisper errors propagate: a misheard number becomes a misjudged claim.
- Speaker labels come from the transcript in replay mode. Live audio has no
  diarisation, so Gemma attributes from context and cues alone — the weakest link
  in the chain, and the honest place to start extending this.
- Claim spotting is tuned to be eager, so `UNVERIFIED` is common and expected.

Red Pen reports what the evidence supports. It is a research aid, not an arbiter.

---

**Repository:** https://github.com/Ductive99/gemma4 ·
26 tests covering pipeline control flow, debouncing, deduplication, window eviction,
speaker-aware querying and failure handling, with external services mocked.
