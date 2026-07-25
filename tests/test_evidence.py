from unittest.mock import MagicMock, patch

from cassandra_agent import evidence


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
