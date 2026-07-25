"""Typed events emitted by the pipeline and streamed to the web overlay as JSON."""

from dataclasses import dataclass, field


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str

    def to_event(self) -> dict:
        return {"type": "transcript", "start": self.start, "end": self.end, "text": self.text}


@dataclass
class Claim:
    id: str
    text: str
    context: str
    timestamp: float

    def to_event(self) -> dict:
        return {
            "type": "claim",
            "id": self.id,
            "text": self.text,
            "context": self.context,
            "timestamp": self.timestamp,
        }


@dataclass
class Snippet:
    title: str
    text: str
    link: str
    source: str


@dataclass
class Verdict:
    claim_id: str
    claim_text: str
    label: str  # TRUE, FALSE, MISLEADING, UNVERIFIED
    confidence: float
    explanation: str
    sources: list = field(default_factory=list)

    def to_event(self) -> dict:
        return {
            "type": "verdict",
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "label": self.label,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "sources": self.sources,
        }
