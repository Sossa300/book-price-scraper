"""Shared test helpers.

All tests run on HTML files saved in tests/fixtures/, never on the live site.
That makes them fast, repeatable and independent of the internet.
"""

from pathlib import Path

import pytest
import requests

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://books.toscrape.com/"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeSession:
    """Stands in for PoliteSession: returns saved HTML instead of downloading."""

    def __init__(self, pages: dict[str, str], fail: set[str] = frozenset()):
        self.pages = pages
        self.fail = set(fail)
        self.requested: list[str] = []

    def get_html(self, url: str) -> str:
        self.requested.append(url)
        if url in self.fail:
            raise requests.ConnectionError(f"simulated network error for {url}")
        if url not in self.pages:
            raise requests.HTTPError(f"404 for {url}")
        return self.pages[url]


@pytest.fixture
def catalogue_page_1():
    return load("catalogue_page_1.html")


@pytest.fixture
def catalogue_page_50():
    return load("catalogue_page_50.html")


@pytest.fixture
def book_detail():
    return load("book_detail.html")


@pytest.fixture
def home_page():
    return load("index.html")


@pytest.fixture
def travel_page():
    return load("category_travel.html")
