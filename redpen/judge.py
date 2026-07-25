"""Verdict engine: Gemma weighs a claim against external evidence snippets only.

Keeps the original Red Pen principle of separation of powers — Gemma never
judges its own reasoning here. It only ever sees a claim someone else made and
evidence retrieved from the web; it has no memory of, and no stake in, how the
claim was produced.
"""

import json
from datetime import date

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

TIME MATTERS, but do not let it paralyse you. You are given today's date, when the
debate took place, and any publication date of each piece of evidence. Many debate
claims are true or false *as of a particular moment*. So:
- read the claim as of the debate date, not as of today;
- if the claim was true when spoken but has since changed, it is TRUE, not FALSE —
  say so in the explanation;
- undated evidence is normal and is still usable. Most web pages carry no date. Use
  it, and lower your confidence a little rather than refusing to judge;
- only withhold a verdict on timing grounds when the evidence genuinely conflicts
  across periods AND you cannot tell which period applies to the claim.
Do not rely on your own sense of the current date; use the dates given.

EVIDENCE THAT ONLY REPORTS THE CLAIM IS NOT EVIDENCE. A page saying "<person>
said X", "<person> claimed X" or "<outlet> reports that X" establishes only that
the statement was made — it does nothing to show whether X is true. Do not count
such coverage as support. If every snippet merely relays somebody asserting the
claim, and none independently establishes the underlying fact, the label is
UNVERIFIED no matter how many outlets repeated it. The exception is when the claim
is itself about what somebody said; then reporting of the statement is exactly the
right evidence.

Respond ONLY with valid JSON with EXACTLY these fields:
- "label": one of "TRUE", "FALSE", "MISLEADING", "UNVERIFIED".
  Reach a verdict whenever the evidence supports one. If the evidence points one way
  but is not conclusive, give that verdict with a LOWER CONFIDENCE — that is what the
  confidence field is for. Do not retreat to "UNVERIFIED" merely because the evidence
  is partial, approximate, indirect or undated.
  Use "MISLEADING" when the claim is technically accurate but omits context, cherry-
  picks a period, or overstates what the evidence shows — this is the right label for
  most half-true debate claims, and it is more useful than "UNVERIFIED".
  Reserve "UNVERIFIED" for when no evidence was provided at all, or the evidence is
  genuinely about a different subject and says nothing either way.
  A number close to the claimed one supports the claim: treat "roughly", "about" and
  ordinary rounding as agreement, not contradiction.
- "confidence": number between 0 and 1.
- "explanation": one or two sentences citing what the evidence actually says.
- "sources": array of 0-based indices into the evidence list that support your verdict."""


def _format_evidence(snippets: list[Snippet]) -> str:
    if not snippets:
        return "(no evidence found)"
    return "\n".join(
        f"[{i}] {s.title}"
        f"{f' [published {s.date}]' if s.date else ' [date unknown]'}"
        f"{' [full page]' if s.full_page else ' [search snippet only]'}"
        f": {s.text} ({s.link})"
        for i, s in enumerate(snippets)
    )


def judge_claim(
    claim_text: str,
    snippets: list[Snippet],
    model: str = None,
    speaker: str = "",
    context_block: str = "",
) -> Verdict:
    user = (
        f"TODAY'S DATE: {date.today().isoformat()}\n\n"
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
