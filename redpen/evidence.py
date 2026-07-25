"""Real web evidence retrieval via SerpApi's HTTP API (no SDK dependency —
just a plain GET, since the official google-search-results package doesn't
install cleanly against modern setuptools).
"""

import requests

from . import config
from .events import Snippet

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


def search_evidence(query: str, api_key: str = None, num_results: int = None) -> list[Snippet]:
    query = (query or "").strip()
    api_key = api_key or config.SERPAPI_API_KEY
    if not query or not api_key:
        return []

    params = {
        "q": query,
        "api_key": api_key,
        "num": num_results or config.EVIDENCE_RESULTS,
        "engine": "google",
    }
    response = requests.get(SERPAPI_ENDPOINT, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    snippets = []
    for item in data.get("organic_results", [])[: num_results or config.EVIDENCE_RESULTS]:
        snippets.append(Snippet(
            title=item.get("title", ""),
            text=item.get("snippet", ""),
            link=item.get("link", ""),
            source=item.get("source") or item.get("displayed_link", ""),
            date=item.get("date") or (item.get("rich_snippet", {})
                                      .get("top", {})
                                      .get("detected_extensions", {})
                                      .get("date", "")) or "",
        ))
    return snippets


def gather_evidence(query: str, claim_text: str = "", api_key: str = None,
                    num_results: int = None) -> list[Snippet]:
    """Searches Gemma's query, falling back to the claim itself if it finds nothing.

    A crafted query can be too narrow — a name plus a bill title with no matching
    page. Retrying on the raw claim usually still finds the topic, and an
    imperfect result beats no evidence, which forces UNVERIFIED.
    """
    snippets = search_evidence(query, api_key, num_results)
    if not snippets and claim_text and claim_text.strip() != (query or "").strip():
        snippets = search_evidence(claim_text, api_key, num_results)
    return snippets
