from unittest.mock import MagicMock, patch

from redpen import fetch
from redpen.events import Snippet

HTML = """<html><head><style>.x{color:red}</style><script>var a=1;</script></head>
<body><nav>Home About</nav>
<p>Cookie policy and newsletter signup blurb that has nothing to do with anything.</p>
<p>Official figures show the unemployment rate stood at 3.5 percent in June 2019,
the lowest level recorded since 1969.</p>
<p>Unrelated filler paragraph about sport that should rank below the figures.</p>
<footer>Contact us</footer></body></html>"""


def test_to_text_strips_markup_and_scripts():
    text = fetch._to_text(HTML)
    assert "var a=1" not in text and "color:red" not in text and "<p>" not in text
    assert "3.5 percent" in text


def test_extract_relevant_picks_the_passage_that_settles_the_claim():
    out = fetch.extract_relevant(fetch._to_text(HTML),
                                 "Unemployment was 3.5 percent in 2019.")
    assert "3.5 percent" in out
    assert "sport" not in out


def test_extract_relevant_respects_the_char_budget():
    assert len(fetch.extract_relevant(fetch._to_text(HTML), "unemployment", max_chars=80)) <= 80


def test_fetch_page_text_skips_non_html():
    resp = MagicMock(); resp.headers = {"Content-Type": "application/pdf"}
    with patch.object(fetch.requests, "get", return_value=resp):
        assert fetch.fetch_page_text("https://x/a.pdf", "claim") == ""


def test_enrich_replaces_snippet_text_and_marks_full_page():
    snips = [Snippet("T", "short snippet", "https://a.com", "a.com")]
    with patch.object(fetch, "fetch_page_text", return_value="a much longer extracted passage"):
        out = fetch.enrich(snips, "claim")
    assert out[0].text == "a much longer extracted passage"
    assert out[0].full_page is True


def test_enrich_keeps_snippet_when_the_fetch_fails():
    snips = [Snippet("T", "short snippet", "https://a.com", "a.com")]
    with patch.object(fetch, "fetch_page_text", side_effect=RuntimeError("dead link")):
        out = fetch.enrich(snips, "claim")
    assert out[0].text == "short snippet"
    assert out[0].full_page is False
