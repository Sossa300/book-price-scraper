from datetime import datetime

import pandas as pd
import pytest

from book_scraper.cleaning import (
    clean_books, filter_books, parse_price, parse_stock, rating_to_int,
)


@pytest.mark.parametrize("text, expected", [
    ("£51.77", 51.77),
    ("Â£51.77", 51.77),   # the classic encoding bug still yields the right number
    ("1,299.00 €", 1299.0),
    ("  £0.99 ", 0.99),
    ("free", None),
    ("", None),
    (None, None),
])
def test_parse_price(text, expected):
    assert parse_price(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("In stock (22 available)", 22),
    ("In stock (1 available)", 1),
    ("Out of stock", 0),
    ("In stock", None),
    (None, None),
])
def test_parse_stock(text, expected):
    assert parse_stock(text) == expected


def test_rating_to_int():
    assert rating_to_int("Five") == 5
    assert rating_to_int("Zero") is None
    assert rating_to_int(None) is None


def raw(**overrides):
    record = {"title": " A Book ", "price": "£10.00", "rating": "Four",
              "availability": "In stock", "url": "https://x/1", "image_url": "https://x/1.jpg"}
    record.update(overrides)
    return record


def test_clean_books_types_and_values():
    df = clean_books([raw()], scraped_at=datetime(2026, 1, 2, 3, 4, 5))
    row = df.iloc[0]
    assert row["title"] == "A Book"
    assert row["price"] == 10.0
    assert row["rating"] == 4
    assert bool(row["in_stock"]) is True
    assert row["scraped_at"] == "2026-01-02T03:04:05"
    assert "stock_count" not in df.columns  # only exists with --details


def test_clean_books_removes_duplicate_urls():
    df = clean_books([raw(), raw(title="Same URL again")])
    assert len(df) == 1


def test_clean_books_with_details():
    df = clean_books([raw(stock="In stock (7 available)", num_reviews="3",
                          category="Travel", upc="abc", description="Nice")])
    assert df.loc[0, "stock_count"] == 7
    assert df.loc[0, "num_reviews"] == 3
    assert list(df.columns)[:6] == ["title", "price", "rating", "in_stock", "stock_count", "category"]


def test_clean_books_empty():
    df = clean_books([])
    assert df.empty
    assert "price" in df.columns


def test_clean_books_out_of_stock():
    df = clean_books([raw(availability="Out of stock")])
    assert bool(df.loc[0, "in_stock"]) is False


def test_filter_books():
    df = pd.DataFrame({
        "price": [5.0, 15.0, 25.0],
        "rating": pd.array([5, 2, None], dtype="Int64"),
        "in_stock": [True, False, True],
    })
    assert len(filter_books(df, max_price=15)) == 2
    assert len(filter_books(df, min_rating=3)) == 1
    assert len(filter_books(df, in_stock_only=True)) == 2
    assert len(filter_books(df)) == 3
