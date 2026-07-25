"""Claim spotting: asks Gemma to pick out checkable factual claims from a
rolling window of live transcript, attribute each one to whoever said it, and
write the web search that would actually settle it.

Having Gemma write the search query is the point of knowing who is talking. A
debate claim is usually unanswerable stripped of its speaker — "he cut taxes by
30%", "my opponent voted against it", "under my administration inflation fell"
are all meaningless as raw search strings. Given the video's context block and
speaker-labelled transcript, Gemma resolves the pronoun to a name and puts that
name into the query.
"""

import json
import re

import ollama

from . import config

SYSTEM_PROMPT = """You are a claim-spotting engine for a live debate fact-checker.

You are given:
  * CONTEXT — what is known about the video being watched, including who is in it;
  * a rolling window of recently spoken, speaker-labelled transcript, oldest first;
  * claims already flagged earlier in this debate.

Identify SPECIFIC, CHECKABLE FACTUAL claims — statistics, dates, voting records,
quotes, named events, comparisons ("the highest since X"), claims about a person's
own record or their opponent's. Ignore opinions, predictions, value judgements and
rhetorical questions. Ignore anything already flagged, including close paraphrases.

Respond ONLY with valid JSON:
{"claims": [{"claim": "...", "speaker": "...", "search_query": "..."}]}
Return {"claims": []} if there are no new checkable claims.

For each claim:
- "claim": the PROPOSITION being asserted, not the act of asserting it. Never write
  "X said that Y", "According to X, Y" or "X claims Y" — write just "Y". Who said it
  belongs in "speaker", never in the claim. The claim is what must be true or false
  in the world; the fact that someone uttered it is not in question.
  Resolve every pronoun and deictic reference using the context and speaker labels:
  "He raised taxes" becomes "<name> raised taxes"; "under my administration" becomes
  "under <that speaker's> administration". A reader who never saw the debate must
  understand the claim on its own.
- "speaker": who asserted it, using the transcript's speaker label or the real
  name from the context when you can identify it. Use "" only if truly unclear.
- "search_query": the web search that finds evidence about whether the claim is TRUE
  — 3 to 10 words. Search the underlying FACT, never the utterance.
  Include a person's name ONLY when that person is the SUBJECT of the claim — their
  vote, their record, their company, something they did. Do NOT include the name of
  whoever merely *said* it. Searching "<speaker> said <claim>" returns news coverage
  of the remark, which proves only that they said it and can never establish whether
  it is true.
  Examples:
    Claim "Meta has more than 3 billion monthly users", spoken by Mark Zuckerberg
      → "Meta monthly active users"        (NOT "Zuckerberg says 3 billion users")
    Claim "<name> voted against the energy bill", spoken by their opponent
      → "<name> vote energy bill"          (name IS the subject — keep it)
    Claim "Inflation fell to 2% last year", spoken by a minister
      → "inflation rate <year>"            (speaker is irrelevant to the fact)
  Add a year or place when it narrows the search."""


# The model mostly follows the "proposition, not utterance" rule, but not always.
# Strip the attribution deterministically so a stray "X said that…" never reaches
# the search — searching an utterance returns coverage of the remark, which can
# only ever confirm it was said, not whether it is true.
#
# Only the SPEAKER's own attribution is removed. "The IEA said in 2020 that solar
# is cheapest" is a claim *about what the IEA said*, where the attribution is the
# substance and stripping it would destroy the claim.
_VERBS = (r"(?:said|says|stated|states|claimed|claims|argued|argues|asserted|"
          r"asserts|noted|notes|insisted|insists|told\s+\w+)")

# Generic form, safe because it demands an explicit "that" — this is what stops
# "said in 2020 that …" being cut down to "in 2020 that …".
_GENERIC = re.compile(
    rf"^\s*[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){{0,3}}\s+{_VERBS}\s+that\s+", re.X)


def strip_attribution(text: str, speaker: str = "") -> str:
    """Turns the speaker's own "X said that Y" into "Y"."""
    original = (text or "").strip()
    out = original

    if speaker:
        name = re.escape(speaker.strip())
        for pattern in (
            rf"^\s*(?:according\s+to\s+){name}\s*,\s*",
            rf"^\s*{name}\s+(?:has\s+|had\s+|also\s+)?{_VERBS}(?:\s+that)?\s+",
        ):
            candidate = re.sub(pattern, "", out, count=1, flags=re.I)
            if candidate != out:
                out = candidate
                break

    if out == original:
        out = _GENERIC.sub("", out, count=1)

    out = out.strip()
    if not out:
        return original
    if out != original and out[:1].islower():
        out = out[0].upper() + out[1:]
    return out


def extract_claims(
    transcript_window: str,
    already_flagged: list[str],
    model: str = None,
    context_block: str = "",
) -> list[dict]:
    """Returns a list of {"claim", "speaker", "search_query"} dicts."""
    transcript_window = (transcript_window or "").strip()
    if not transcript_window:
        return []

    flagged_block = "\n".join(f"- {c}" for c in already_flagged) or "(none yet)"
    user = (
        f"CONTEXT:\n{context_block or '(no context available)'}\n\n"
        f"TRANSCRIPT WINDOW:\n{transcript_window}\n\n"
        f"ALREADY FLAGGED:\n{flagged_block}"
    )

    response = ollama.chat(
        model=model or config.CLAIM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        format="json",
        keep_alive=config.OLLAMA_KEEP_ALIVE,
    )

    try:
        payload = json.loads(response["message"]["content"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return []

    raw_claims = payload.get("claims", [])
    if not isinstance(raw_claims, list):
        return []

    results = []
    for entry in raw_claims:
        # Tolerate the model dropping back to a bare string.
        if isinstance(entry, str):
            text = strip_attribution(entry)
            if text:
                results.append({"claim": text, "speaker": "", "search_query": text})
            continue
        if not isinstance(entry, dict):
            continue
        speaker = str(entry.get("speaker", "") or "").strip()
        text = strip_attribution(str(entry.get("claim", "")), speaker)
        if not text:
            continue
        results.append({
            "claim": text,
            "speaker": speaker,
            # Fall back to the claim itself if Gemma didn't write a query.
            "search_query": str(entry.get("search_query", "") or "").strip() or text,
        })
    return results
