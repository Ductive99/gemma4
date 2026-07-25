"""Runs the real web app with Gemma and SerpApi stubbed out.

Lets the team rehearse the pitch, and lets anyone see the UI working, without
a local model, an API key, or burning SerpApi credits. Everything else — the
server, the WebSocket, the pipeline, the replay timing, the UI — is the real
code path.

    python3 demo/rehearse.py     # then open http://localhost:8000
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redpen.events import Snippet, Verdict  # noqa: E402

# Canned stand-ins, clearly labelled as such in the UI explanation text.
FAKE_EVIDENCE = [
    Snippet("EUR-Lex — Regulation (EU) 2024/1689",
            "The AI Act entered into force on 1 August 2024.",
            "https://eur-lex.europa.eu/eli/reg/2024/1689/oj", "eur-lex.europa.eu"),
    Snippet("European Commission — AI Act overview",
            "Prohibitions apply from 2 February 2025; real-time remote biometric "
            "identification is restricted, with narrow law-enforcement exceptions.",
            "https://digital-strategy.ec.europa.eu", "ec.europa.eu"),
]


FARROW, DEVEREUX = "Dr. Lena Farrow", "Marc Devereux"

# (transcript cue, claim, speaker, the speaker-aware query Gemma would write)
TOPICS = [
    ("AI Act entered", "The EU AI Act entered into force in August 2024.",
     FARROW, "EU AI Act entry into force date 2024"),
    ("bans facial recognition", "The EU AI Act bans facial recognition outright across the EU.",
     FARROW, "EU AI Act facial recognition ban exceptions"),
    ("1.5 percent", "Data centres consumed about 1.5% of global electricity in 2024.",
     DEVEREUX, "IEA data centre share global electricity 2024"),
    ("cheapest electricity", "The IEA said in 2020 that solar is the cheapest electricity in history.",
     FARROW, "IEA World Energy Outlook 2020 cheapest electricity history"),
    ("seventy percent", "France generates more than 70% of its electricity from nuclear power.",
     DEVEREUX, "France nuclear share of electricity generation 2024"),
    ("billion dollars", "Training a single frontier AI model costs over $1 billion per run.",
     DEVEREUX, "frontier AI model training run cost estimate"),
]


_generic = {"n": 0}


def fake_extract(window, flagged, model=None, context_block=""):
    """Spots one claim per topic, the first time that topic appears.

    Falls back to a generic stub every few windows so the timing and visuals can
    be rehearsed against any real video, not just the sample debate. Clearly
    labelled in the UI so a rehearsal can never be mistaken for a real run.
    """
    for cue, claim, speaker, query in TOPICS:
        if cue.lower() in window.lower() and claim not in flagged:
            return [{"claim": claim, "speaker": speaker, "search_query": query}]

    _generic["n"] += 1
    if _generic["n"] % 4 == 0:
        excerpt = " ".join(window.split()[-14:])
        return [{
            "claim": f"[REHEARSAL STUB] Claim placeholder from: “{excerpt}”",
            "speaker": "",
            "search_query": "[rehearsal stub] no search performed",
        }]
    return []


VERDICTS = {
    "The EU AI Act entered into force in August 2024.": (
        "TRUE", 0.94, "[REHEARSAL STUB] EUR-Lex confirms entry into force on 1 August 2024."),
    "The EU AI Act bans facial recognition outright across the EU.": (
        "FALSE", 0.88, "[REHEARSAL STUB] The Act restricts real-time remote biometric ID "
                       "rather than banning facial recognition outright; narrow exceptions exist."),
    "Data centres consumed about 1.5% of global electricity in 2024.": (
        "TRUE", 0.8, "[REHEARSAL STUB] Consistent with IEA's ~415 TWh / ~1.5% estimate for 2024."),
    "The IEA said in 2020 that solar is the cheapest electricity in history.": (
        "TRUE", 0.85, "[REHEARSAL STUB] WEO 2020 described the best solar schemes as "
                      "'the cheapest electricity in history'."),
    "France generates more than 70% of its electricity from nuclear power.": (
        "MISLEADING", 0.7, "[REHEARSAL STUB] Nuclear was ~65% in 2023-24, below 70%, "
                           "though it exceeded 70% in earlier years."),
    "Training a single frontier AI model costs over $1 billion per run.": (
        "UNVERIFIED", 0.45, "[REHEARSAL STUB] Public estimates for the largest runs are in the "
                            "high tens to hundreds of millions; >$1B per run is not established."),
}


def fake_judge(claim_text, snippets, model=None, speaker="", context_block=""):
    label, confidence, explanation = VERDICTS.get(
        claim_text, ("UNVERIFIED", 0.3, "[REHEARSAL STUB] No canned verdict for this claim."))
    return Verdict(claim_id="", claim_text=claim_text, label=label, confidence=confidence,
                   explanation=explanation, sources=[s.link for s in snippets], speaker=speaker)


def main() -> None:
    import uvicorn

    with patch("redpen.pipeline.extract_claims", fake_extract), \
         patch("redpen.pipeline.search_evidence", lambda q, k=None: FAKE_EVIDENCE), \
         patch("redpen.pipeline.judge_claim", fake_judge):
        print("Rehearsal mode: Gemma and SerpApi are stubbed. Open http://localhost:8000")
        uvicorn.run("redpen.server:app", host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
