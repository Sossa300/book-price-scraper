import pytest

from book_scraper.fetcher import RobotsDisallowed
from book_scraper.scraper import CATALOGUE_URL, find_category_url, scrape_books

from .conftest import BASE, FakeSession

PAGE_2 = BASE + "catalogue/page-2.html"
TRAVEL = BASE + "catalogue/category/books/travel_2/index.html"


def test_follows_next_link_until_max_pages(catalogue_page_1):
    # Page 2 reuses page 1's HTML: we only care that the link is followed.
    session = FakeSession({CATALOGUE_URL: catalogue_page_1, PAGE_2: catalogue_page_1})
    records = scrape_books(session, max_pages=2)
    assert session.requested == [CATALOGUE_URL, PAGE_2]
    assert len(records) == 40


def test_stops_on_last_page(catalogue_page_50):
    session = FakeSession({CATALOGUE_URL: catalogue_page_50})
    records = scrape_books(session)  # no max_pages: runs until there is no "next"
    assert len(records) == 20
    assert session.requested == [CATALOGUE_URL]


def test_network_error_keeps_collected_books(catalogue_page_1):
    session = FakeSession({CATALOGUE_URL: catalogue_page_1}, fail={PAGE_2})
    records = scrape_books(session)
    assert len(records) == 20  # page 1 survives, page 2 failed


def test_robots_disallowed_stops_gracefully():
    class Blocked:
        def get_html(self, url):
            raise RobotsDisallowed(url)

    assert scrape_books(Blocked()) == []


def test_details_are_merged(travel_page, book_detail):
    pages = {TRAVEL: travel_page}
    # Every book link returns the same saved detail page.
    for book in scrape_books(FakeSession(pages), TRAVEL):
        pages[book["url"]] = book_detail
    session = FakeSession(pages)
    records = scrape_books(session, TRAVEL, details=True)
    assert len(records) == 11
    assert all(r["upc"] == "a897fe39b1053632" for r in records)
    assert len(session.requested) == 1 + 11


def test_failed_detail_page_is_skipped(travel_page):
    session = FakeSession({TRAVEL: travel_page})  # detail pages missing -> 404
    records = scrape_books(session, TRAVEL, details=True)
    assert len(records) == 11
    assert "upc" not in records[0]


def test_progress_callback(catalogue_page_50):
    calls = []
    scrape_books(FakeSession({CATALOGUE_URL: catalogue_page_50}),
                 on_page=lambda page, total: calls.append((page, total)))
    assert calls == [(1, 20)]


def test_find_category_is_case_insensitive(home_page):
    session = FakeSession({BASE: home_page})
    assert find_category_url(session, "  travel ") == TRAVEL


def test_unknown_category_lists_options(home_page):
    with pytest.raises(ValueError, match="Available: .*Travel"):
        find_category_url(FakeSession({BASE: home_page}), "Cooking with Python")
