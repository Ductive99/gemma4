"""Verdict engine: Gemma weighs a claim against external evidence snippets only.

Keeps the original Cassandra principle of separation of powers — Gemma never
judges its own reasoning here. It only ever sees a claim someone else made and
evidence retrieved from the web; it has no memory of, and no stake in, how the
claim was produced.
"""

import json

import ollama

from . import config
from .events import Snippet, Verdict

VALID_LABELS = {"TRUE", "FALSE", "MISLEADING", "UNVERIFIED"}

SYSTEM_PROMPT = """You are a strict, neutral fact-check judge. You are given a CLAIM
made during a live debate, who said it, the context of the video, and EVIDENCE
SNIPPETS retrieved from a web search. Judge only what the evidence actually shows.

You are told the speaker so you can tell whether the evidence is about the right
person — evidence concerning someone else does not support a claim about this
speaker's record. Knowing who spoke must NOT change how favourably you judge them;
weigh both sides of a debate by exactly the same standard.

Respond ONLY with valid JSON with EXACTLY these fields:
- "label": one of "TRUE", "FALSE", "MISLEADING", "UNVERIFIED".
  Use "UNVERIFIED" if the evidence doesn't clearly confirm or contradict the claim,
  or if no evidence was provided.
- "confidence": number between 0 and 1.
- "explanation": one or two sentences citing what the evidence actually says.
- "sources": array of 0-based indices into the evidence list that support your verdict."""


def _format_evidence(snippets: list[Snippet]) -> str:
    if not snippets:
        return "(no evidence found)"
    return "\n".join(f"[{i}] {s.title}: {s.text} ({s.link})" for i, s in enumerate(snippets))


def judge_claim(
    claim_text: str,
    snippets: list[Snippet],
    model: str = None,
    speaker: str = "",
    context_block: str = "",
) -> Verdict:
    user = (
        f"CONTEXT:\n{context_block or '(no context available)'}\n\n"
        f"SPEAKER: {speaker or '(unattributed)'}\n"
        f"CLAIM: {claim_text}\n\n"
        f"EVIDENCE SNIPPETS:\n{_format_evidence(snippets)}"
    )

    response = ollama.chat(
        model=model or config.JUDGE_MODEL,
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
        payload = {}

    label = str(payload.get("label", "UNVERIFIED")).upper()
    if label not in VALID_LABELS:
        label = "UNVERIFIED"

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    source_links = []
    for idx in payload.get("sources", []) or []:
        if isinstance(idx, int) and 0 <= idx < len(snippets):
            source_links.append(snippets[idx].link)

    return Verdict(
        claim_id="",
        claim_text=claim_text,
        label=label,
        confidence=confidence,
        explanation=str(payload.get("explanation", "")),
        sources=source_links,
        speaker=speaker,
    )
