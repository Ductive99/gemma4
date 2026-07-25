# Red Pen — 2-minute pitch

Spoken script ≈ 300 words. Stage directions in brackets. **The demo runs under you
while you talk — don't narrate the UI, narrate the idea.**

---

### 0:00 — 0:20 · The problem

> A politician makes a false claim on live television. Twenty million people hear it.
> The correction runs tomorrow morning — to about forty thousand of them.
>
> That gap is the whole problem. Assertion is instant and free. Verification is slow
> and expensive. Not because the evidence is hard to find — it's usually one search
> away — but because a *human* has to notice the sentence, decide it's checkable,
> search, read, and judge.

### 0:20 — 0:35 · What it is

> This is Red Pen. It does that entire loop by itself, on a laptop, with Gemma 4.

*[Paste the URL. Hit Start. Let the video play — keep talking.]*

### 0:35 — 1:35 · Demo

> Nobody tells it what to check. Gemma is reading the transcript and deciding which
> sentences are actually checkable facts — not opinion, not prediction, not rhetoric.

*[First card appears]*

> There. It spotted a claim, and it's out searching for evidence.

*[Verdict lands]*

> False — 88% — with the sources it used to decide.

*[Point at a claim with a pronoun in it]*

> Now this one matters. The speaker says *"he voted against it."* You cannot search
> that. It's meaningless without a name. So Gemma resolves who "he" is from the
> video's own metadata, and writes the search query itself —

*[Read the ⌕ query off the card]*

> — that is the difference between a fact-checker and a keyword matcher.

### 1:35 — 1:55 · How Gemma is used

> Gemma runs twice per claim, in two deliberately separate roles. Once to spot the
> claim and write the query. Once to judge it — and the judge only ever sees the
> claim and the evidence. It never grades its own reasoning.
>
> Both calls return structured JSON that drives the pipeline — not prose for a human
> to read. All of it local.

### 1:55 — 2:00 · Close

> Red Pen. Fact-checking at the speed of the lie.

---

## If the demo dies

Don't debug on stage. Keep talking and switch:

1. Clear the URL box and hit Start → the sample debate runs (Gemma + SerpApi still real).
2. If Ollama is down → `demo/cached_run.json` replays a recorded run, fully offline.

Say it plainly: *"venue wifi — here's a run from ten minutes ago."* Nobody minds.

## Likely questions

**"What's the latency?"**
> On a recorded video we analyse ahead of the playhead and sync results to video
> time, like a subtitle track — so they land the instant they're due. For a live
> stream there's a real-time path: claim spotting is debounced and single-flight so
> it never falls behind the speaker.

**"What stops it being biased?"**
> The judge is given the claim and the evidence only — never who to favour. It's told
> the speaker purely so it can reject evidence about the wrong person, with an
> explicit instruction to weigh both sides by the same standard.

**"How accurate is it?"**
> It reads search results, not primary sources — so it reports what the evidence
> supports, and says UNVERIFIED when the evidence doesn't settle it. It's a research
> aid, not an arbiter. We'd rather it abstain than guess.

**"Why Gemma and not an API model?"**
> It runs on the machine in front of you. No transcript of a private debate leaves
> the room, and there's no per-claim API cost — which matters when you're checking
> continuously for ninety minutes.
