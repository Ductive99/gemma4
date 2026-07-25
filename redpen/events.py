"""Typed events emitted by the pipeline and streamed to the web overlay as JSON."""

from dataclasses import dataclass, field


@dataclass
class SessionContext:
    """What the agent knows about the video it is watching.

    For a debate this is the difference between searching "he cut taxes by 30%"
    — which is unanswerable — and searching the claim against the name of the
    person who actually said it. Populated from yt-dlp metadata in live mode,
    or from the transcript file's own `context` block in replay mode.
    """

    title: str = ""
    channel: str = ""
    upload_date: str = ""
    description: str = ""
    participants: list = field(default_factory=list)

    def to_prompt_block(self) -> str:
        lines = []
        if self.title:
            lines.append(f"Video title: {self.title}")
        if self.channel:
            lines.append(f"Channel: {self.channel}")
        if self.upload_date:
            lines.append(f"Published: {self.upload_date}")
        if self.participants:
            lines.append(f"Known participants: {', '.join(self.participants)}")
        if self.description:
            lines.append(f"Description: {self.description[:400]}")
        return "\n".join(lines) or "(no context available for this video)"

    def to_event(self) -> dict:
        return {
            "type": "context",
            "title": self.title,
            "channel": self.channel,
            "upload_date": self.upload_date,
            "participants": self.participants,
        }


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: str = ""

    def labelled(self) -> str:
        return f"{self.speaker}: {self.text}" if self.speaker else self.text

    def to_event(self) -> dict:
        return {
            "type": "transcript",
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "speaker": self.speaker,
        }


@dataclass
class Claim:
    id: str
    text: str
    context: str
    timestamp: float
    speaker: str = ""
    search_query: str = ""

    def to_event(self) -> dict:
        return {
            "type": "claim",
            "id": self.id,
            "text": self.text,
            "speaker": self.speaker,
            "search_query": self.search_query,
            "context": self.context,
            "timestamp": self.timestamp,
        }


@dataclass
class Snippet:
    title: str
    text: str
    link: str
    source: str
    # When the source published this. Debate claims are overwhelmingly
    # time-sensitive, so undated evidence is how a correct claim gets rated
    # false against numbers from a different year.
    date: str = ""


@dataclass
class Verdict:
    claim_id: str
    claim_text: str
    label: str  # TRUE, FALSE, MISLEADING, UNVERIFIED
    confidence: float
    explanation: str
    sources: list = field(default_factory=list)
    speaker: str = ""

    def to_event(self) -> dict:
        return {
            "type": "verdict",
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "speaker": self.speaker,
            "label": self.label,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "sources": self.sources,
        }
