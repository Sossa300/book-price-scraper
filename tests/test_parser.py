from book_scraper.parser import (
    next_page_url, parse_book_detail, parse_categories, parse_listing,
)

PAGE_1 = "https://books.toscrape.com/catalogue/page-1.html"
PAGE_50 = "https://books.toscrape.com/catalogue/page-50.html"


def test_listing_finds_all_20_books(catalogue_page_1):
    assert len(parse_listing(catalogue_page_1, PAGE_1)) == 20


def test_listing_first_book_fields(catalogue_page_1):
    book = parse_listing(catalogue_page_1, PAGE_1)[0]
    assert book["title"] == "A Light in the Attic"  # full title, not "A Light in the ..."
    assert book["price"] == "£51.77"
    assert book["rating"] == "Three"
    assert book["availability"] == "In stock"


def test_listing_links_are_absolute(catalogue_page_1):
    book = parse_listing(catalogue_page_1, PAGE_1)[0]
    assert book["url"] == "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    assert book["image_url"].startswith("https://books.toscrape.com/media/cache/")


def test_listing_of_empty_html_is_empty():
    assert parse_listing("<html><body>No books</body></html>", PAGE_1) == []


def test_next_page_url(catalogue_page_1):
    assert next_page_url(catalogue_page_1, PAGE_1) == "https://books.toscrape.com/catalogue/page-2.html"


def test_last_page_has_no_next(catalogue_page_50):
    assert next_page_url(catalogue_page_50, PAGE_50) is None


def test_categories(home_page):
    categories = parse_categories(home_page, "https://books.toscrape.com/")
    assert len(categories) == 50
    assert categories["Travel"] == "https://books.toscrape.com/catalogue/category/books/travel_2/index.html"
    assert "Books" not in categories  # the parent entry is not a real category


def test_book_detail(book_detail):
    detail = parse_book_detail(book_detail)
    assert detail["category"] == "Poetry"
    assert detail["upc"] == "a897fe39b1053632"
    assert detail["stock"] == "In stock (22 available)"
    assert detail["num_reviews"] == "0"
    assert detail["description"].startswith("It's hard to imagine a world without")


def test_book_detail_missing_parts_give_none():
    detail = parse_book_detail("<html><body><h1>Broken page</h1></body></html>")
    assert detail == {"category": None, "upc": None, "stock": None,
                      "num_reviews": None, "description": None}
