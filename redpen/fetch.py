"""Fetches the actual page behind a search result and extracts the passage that
bears on the claim.

A SerpApi snippet is ~30 words of SEO text and frequently omits the number that
decides the claim, which is how a checkable claim ends up UNVERIFIED. Fetching
the page and pulling the passages that overlap the claim gives the judge
something to actually rule on. Best-effort throughout: any failure falls back to
the snippet rather than failing the check.
"""

import concurrent.futures
import html
import re

import requests

from . import config
from .events import Snippet

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RedPen/1.0; +fact-checking)"}

_STRIP = re.compile(
    r"<(script|style|noscript|nav|header|footer|aside|form|svg)\b[^>]*>.*?</\1>",
    re.I | re.S,
)
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANK = re.compile(r"\n{2,}")
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been", "that",
    "this", "it", "its", "has", "have", "had", "not", "than", "then", "there",
    "their", "they", "he", "she", "his", "her", "we", "our", "you", "your",
}


def _to_text(markup: str) -> str:
    text = _STRIP.sub(" ", markup)
    text = re.sub(r"<(p|div|br|li|h[1-6]|tr)\b[^>]*>", "\n", text, flags=re.I)
    text = _TAGS.sub(" ", text)
    text = html.unescape(text)
    text = _WS.sub(" ", text)
    return _BLANK.sub("\n", text).strip()


def _keywords(claim: str) -> set:
    return {w for w in _WORD.findall(claim.lower()) if w not in _STOP and len(w) > 2}


def _score(passage: str, keys: set) -> float:
    if not keys:
        return 0.0
    words = set(_WORD.findall(passage.lower()))
    hit = len(keys & words) / len(keys)
    # numbers are what usually settle a claim, so a passage carrying them wins ties
    return hit + (0.15 if re.search(r"\d", passage) else 0.0)


def extract_relevant(text: str, claim: str, max_chars: int = None) -> str:
    """Returns the passages of `text` that best overlap `claim`, in document order."""
    max_chars = max_chars or config.PAGE_EXTRACT_CHARS
    keys = _keywords(claim)
    passages = [p.strip() for p in re.split(r"\n+|(?<=[.!?])\s{2,}", text) if len(p.strip()) > 40]
    if not passages:
        return text[:max_chars]

    ranked = sorted(
        ((_score(p, keys), i, p) for i, p in enumerate(passages)),
        key=lambda t: (-t[0], t[1]),
    )
    picked, used = [], 0
    for score, i, p in ranked:
        if score <= 0 and picked:
            break
        p = p[:max_chars]
        if used + len(p) > max_chars:
            continue
        picked.append((i, p))
        used += len(p)
        if used >= max_chars:
            break

    if not picked:
        return text[:max_chars]
    return " … ".join(p for _, p in sorted(picked))


def fetch_page_text(url: str, claim: str, timeout: float = None) -> str:
    timeout = timeout or config.PAGE_FETCH_TIMEOUT
    response = requests.get(url, headers=_HEADERS, timeout=timeout, stream=True)
    response.raise_for_status()
    if "html" not in response.headers.get("Content-Type", "text/html").lower():
        return ""
    # cap the read so one enormous page can't stall the check
    markup = response.raw.read(config.PAGE_MAX_BYTES, decode_content=True)
    if isinstance(markup, bytes):
        markup = markup.decode(response.encoding or "utf-8", errors="replace")
    return extract_relevant(_to_text(markup), claim)


def enrich(snippets: list[Snippet], claim: str, max_pages: int = None) -> list[Snippet]:
    """Replaces snippet text with page content where the fetch succeeds.

    Runs the fetches in parallel — they are IO-bound and the slowest one would
    otherwise set the latency for the whole check.
    """
    if not snippets or not config.FETCH_PAGES:
        return snippets

    targets = snippets[: max_pages or config.PAGE_FETCH_LIMIT]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(targets)) as pool:
        futures = {pool.submit(fetch_page_text, s.link, claim): s for s in targets if s.link}
        for future in concurrent.futures.as_completed(
            futures, timeout=config.PAGE_FETCH_TIMEOUT + 3
        ):
            snippet = futures[future]
            try:
                text = future.result()
            except Exception:  # noqa: BLE001 - a dead link must not fail the fact-check
                continue
            if text and len(text) > len(snippet.text):
                snippet.text = text
                snippet.full_page = True
    return snippets
