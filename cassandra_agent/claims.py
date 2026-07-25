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
- "claim": a short, SELF-CONTAINED factual statement. Resolve every pronoun and
  every deictic reference using the context and the speaker labels. "He raised
  taxes" becomes "<name> raised taxes". "Under my administration" becomes
  "Under <that speaker's> administration". A reader who never saw the debate must
  be able to understand the claim on its own.
- "speaker": who asserted it, using the transcript's speaker label or the real
  name from the context when you can identify it. Use "" only if truly unclear.
- "search_query": the web search that would settle this claim — 3 to 10 words.
  NAME THE PEOPLE INVOLVED whenever the claim concerns a person's record,
  statement or actions; a query like "voted against the bill" is useless, while
  "<name> vote <bill name>" is checkable. Add a year or place when it narrows the
  search. Write the query to find EVIDENCE, not to confirm what the speaker said."""


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
            text = entry.strip()
            if text:
                results.append({"claim": text, "speaker": "", "search_query": text})
            continue
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("claim", "")).strip()
        if not text:
            continue
        results.append({
            "claim": text,
            "speaker": str(entry.get("speaker", "") or "").strip(),
            # Fall back to the claim itself if Gemma didn't write a query.
            "search_query": str(entry.get("search_query", "") or "").strip() or text,
        })
    return results
