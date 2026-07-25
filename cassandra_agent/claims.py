"""Claim spotting: asks Gemma to pick out checkable factual claims from a
rolling window of live transcript, ignoring opinions and things already flagged.
"""

import json

import ollama

from . import config

SYSTEM_PROMPT = """You are a claim-spotting engine for a live debate fact-checker.
You are given a short rolling window of recently spoken transcript, oldest first.
Identify SPECIFIC, CHECKABLE FACTUAL claims made in it — statistics, dates, quotes,
named events, comparisons ("X is the highest since Y") — that a fact-checker could
verify against outside evidence.

Ignore opinions, predictions, value judgements, and rhetorical questions.
Ignore any claim that is already listed under "Already flagged" (including close
paraphrases of it) — only return genuinely NEW claims.

Respond ONLY with valid JSON: {"claims": ["claim 1", "claim 2", ...]}.
If there are no new checkable claims, respond {"claims": []}.
Rephrase each claim as a short, self-contained factual statement — resolve
pronouns ("he", "that") into the actual subject when it's clear from context."""


def extract_claims(transcript_window: str, already_flagged: list[str], model: str = None) -> list[str]:
    transcript_window = (transcript_window or "").strip()
    if not transcript_window:
        return []

    flagged_block = "\n".join(f"- {c}" for c in already_flagged) or "(none yet)"
    user = f"Transcript window:\n{transcript_window}\n\nAlready flagged:\n{flagged_block}"

    response = ollama.chat(
        model=model or config.OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        format="json",
    )

    try:
        payload = json.loads(response["message"]["content"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return []

    claims = payload.get("claims", [])
    if not isinstance(claims, list):
        return []
    return [c.strip() for c in claims if isinstance(c, str) and c.strip()]
