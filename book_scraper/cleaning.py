"""Turn raw scraped text into a clean, typed pandas DataFrame.

Raw data from websites is always messy: prices are text with currency
symbols, ratings are words, stock levels hide inside sentences. Each small
function below fixes exactly one of these problems, which makes them easy
to test and easy to reuse for other sites.
"""

from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

# Column order of the final table. Columns that were not scraped
# (e.g. "category" without --details) are simply left out.
COLUMNS = [
    "title", "price", "rating", "in_stock", "stock_count", "category",
    "num_reviews", "upc", "url", "image_url", "description", "scraped_at",
]


def parse_price(text: object) -> float | None:
    """'£51.77' -> 51.77, '1,299.00 €' -> 1299.0, '' or None -> None.

    Assumes "." as decimal separator (English sites). For German prices
    like "1.299,00" you would swap the separators first.
    """
    if not isinstance(text, str):
        return None
    number = re.sub(r"[^\d.]", "", text)  # keep only digits and the dot
    try:
        return float(number)
    except ValueError:
        return None


def parse_stock(text: object) -> int | None:
    """'In stock (22 available)' -> 22, 'Out of stock' -> 0, unknown -> None."""
    if not isinstance(text, str):
        return None
    match = re.search(r"(\d+)\s+available", text)
    if match:
        return int(match.group(1))
    if "out of stock" in text.lower():
        return 0
    return None


def rating_to_int(word: object) -> int | None:
    """'Three' -> 3. Unknown values become None instead of crashing."""
    return RATING_WORDS.get(word) if isinstance(word, str) else None


def clean_books(records: list[dict], scraped_at: datetime | None = None) -> pd.DataFrame:
    """Convert the list of raw dictionaries into a clean DataFrame."""
    if not records:
        return pd.DataFrame(columns=["title", "price", "rating", "in_stock",
                                     "url", "image_url", "scraped_at"])

    df = pd.DataFrame(records)
    df["title"] = df["title"].str.strip()
    df["price"] = df["price"].map(parse_price)
    df["rating"] = df["rating"].map(rating_to_int).astype("Int64")
    df["in_stock"] = df["availability"].str.contains("in stock", case=False, na=False)

    if "stock" in df:  # only present when detail pages were scraped
        df["stock_count"] = df["stock"].map(parse_stock).astype("Int64")
    if "num_reviews" in df:
        df["num_reviews"] = pd.to_numeric(df["num_reviews"], errors="coerce").astype("Int64")

    # A timestamp makes the data useful for price tracking over time.
    # Stored as text so it looks the same in CSV, Excel and SQLite.
    df["scraped_at"] = (scraped_at or datetime.now()).isoformat(timespec="seconds")

    # The same book can appear twice (e.g. when a page shifts during scraping).
    df = df.drop_duplicates(subset="url").reset_index(drop=True)
    return df[[c for c in COLUMNS if c in df.columns]]


def filter_books(df: pd.DataFrame, max_price: float | None = None,
                 min_rating: int | None = None, in_stock_only: bool = False) -> pd.DataFrame:
    """Keep only the rows a client is interested in."""
    mask = pd.Series(True, index=df.index)
    if max_price is not None:
        mask &= df["price"] <= max_price
    if min_rating is not None:
        mask &= df["rating"].fillna(0) >= min_rating
    if in_stock_only:
        mask &= df["in_stock"].astype(bool)
    return df[mask].reset_index(drop=True)
