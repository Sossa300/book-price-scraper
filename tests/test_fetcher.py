import pytest
import requests

from book_scraper.fetcher import PoliteSession, RobotsDisallowed, build_session

from .conftest import load

URL = "https://books.toscrape.com/catalogue/page-1.html"
ROBOTS = "https://books.toscrape.com/robots.txt"


def make_response(status=200, body=b"", content_type="text/html"):
    response = requests.Response()
    response.status_code = status
    response._content = body
    response.headers["Content-Type"] = content_type
    response.url = URL
    return response


class FakeRequests:
    """Replaces requests.Session: maps URLs to prepared responses."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, timeout):
        self.calls.append(url)
        result = self.responses[url]
        if isinstance(result, Exception):
            raise result
        return result


def polite(responses, **kwargs):
    sleeps = []
    session = PoliteSession(session=FakeRequests(responses), sleep=sleeps.append, **kwargs)
    return session, sleeps


def test_missing_robots_txt_allows_everything():
    session, _ = polite({ROBOTS: make_response(404), URL: make_response(body=b"<p>ok</p>")})
    assert session.get_html(URL) == "<p>ok</p>"


def test_robots_txt_disallow_is_respected():
    robots = make_response(body=b"User-agent: *\nDisallow: /catalogue/\n", content_type="text/plain")
    session, _ = polite({ROBOTS: robots})
    with pytest.raises(RobotsDisallowed):
        session.get_html(URL)
    assert session.allowed("https://books.toscrape.com/index.html")


def test_robots_txt_forbidden_blocks_site():
    session, _ = polite({ROBOTS: make_response(403)})
    assert not session.allowed(URL)


def test_robots_txt_unreachable_allows():
    session, _ = polite({ROBOTS: requests.ConnectionError("down")})
    assert session.allowed(URL)


def test_robots_txt_loaded_once_per_site():
    session, _ = polite({ROBOTS: make_response(404), URL: make_response(body=b"x")})
    session.get_html(URL)
    session.get_html(URL)
    assert session.session.calls.count(ROBOTS) == 1


def test_respect_robots_can_be_disabled():
    session, _ = polite({URL: make_response(body=b"x")}, respect_robots=False)
    assert session.get_html(URL) == "x"


def test_delay_between_requests():
    session, sleeps = polite({ROBOTS: make_response(404), URL: make_response(body=b"x")}, delay=5)
    session.get_html(URL)  # robots.txt, then wait, then the page
    assert len(sleeps) == 1 and 4 < sleeps[0] <= 5


def test_http_error_is_raised():
    session, _ = polite({ROBOTS: make_response(404), URL: make_response(500)})
    with pytest.raises(requests.HTTPError):
        session.get_html(URL)


def test_encoding_without_charset_header_is_detected():
    # The real site sends "text/html" without charset. requests would
    # decode it as ISO-8859-1 and show "Â£51.77".
    body = load("catalogue_page_1.html").encode("utf-8")
    session, _ = polite({ROBOTS: make_response(404), URL: make_response(body=body)})
    html = session.get_html(URL)
    assert "£51.77" in html
    assert "Â£" not in html


def test_build_session_retries_temporary_errors():
    session = build_session(retries=4, user_agent="test-agent")
    retry = session.get_adapter("https://example.com").max_retries
    assert retry.total == 4
    assert 503 in retry.status_forcelist
    assert session.headers["User-Agent"] == "test-agent"
