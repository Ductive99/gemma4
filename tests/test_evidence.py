from unittest.mock import MagicMock, patch

from redpen import evidence


def test_search_evidence_returns_snippets():
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "organic_results": [
            {"title": "A", "snippet": "snippet a", "link": "https://a.com", "source": "a.com"},
            {"title": "B", "snippet": "snippet b", "link": "https://b.com"},
        ]
    }
    with patch.object(evidence.requests, "get", return_value=fake_response) as mock_get:
        results = evidence.search_evidence("some query", api_key="key123", num_results=2)

    mock_get.assert_called_once()
    assert [s.title for s in results] == ["A", "B"]
    assert results[1].source == ""  # no "source" or "displayed_link" key present
    assert results[0].link == "https://a.com"


def test_search_evidence_without_api_key_returns_empty():
    with patch.object(evidence.requests, "get") as mock_get:
        results = evidence.search_evidence("q", api_key="")
    mock_get.assert_not_called()
    assert results == []


def test_search_evidence_without_query_returns_empty():
    with patch.object(evidence.requests, "get") as mock_get:
        results = evidence.search_evidence("   ", api_key="key")
    mock_get.assert_not_called()
    assert results == []


def test_search_evidence_captures_publication_dates():
    fake_response = MagicMock()
    fake_response.json.return_value = {"organic_results": [
        {"title": "A", "snippet": "s", "link": "https://a.com", "date": "Aug 1, 2024"},
        {"title": "B", "snippet": "s", "link": "https://b.com",
         "rich_snippet": {"top": {"detected_extensions": {"date": "Mar 3, 2021"}}}},
        {"title": "C", "snippet": "s", "link": "https://c.com"},
    ]}
    with patch.object(evidence.requests, "get", return_value=fake_response):
        results = evidence.search_evidence("q", api_key="k", num_results=3)

    assert [r.date for r in results] == ["Aug 1, 2024", "Mar 3, 2021", ""]


def test_gather_evidence_retries_with_the_claim_when_the_query_finds_nothing():
    with patch.object(evidence, "search_evidence", side_effect=[[], ["hit"]]) as mock:
        out = evidence.gather_evidence("a very narrow query", "the raw claim text", "k")
    assert out == ["hit"]
    assert mock.call_count == 2
    assert mock.call_args_list[1][0][0] == "the raw claim text"


def test_gather_evidence_does_not_retry_when_the_query_worked():
    with patch.object(evidence, "search_evidence", side_effect=[["hit"]]) as mock:
        evidence.gather_evidence("q", "claim", "k")
    assert mock.call_count == 1
