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
        ))
    return snippets
