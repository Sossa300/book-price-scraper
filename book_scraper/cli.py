"""Command line interface.

Examples:
    python main.py --pages 3
    python main.py --category Travel --details --format csv xlsx sqlite
    python main.py --max-price 20 --min-rating 4 --format xlsx
    python main.py --list-categories

argparse also generates the help text for free: python main.py --help
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .cleaning import clean_books, filter_books
from .exporters import FORMATS, export
from .fetcher import PoliteSession
from .scraper import CATALOGUE_URL, find_category_url, list_categories, scrape_books

log = logging.getLogger("book_scraper")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="book-price-scraper",
        description="Scrape books (title, price, rating, stock) from books.toscrape.com "
                    "and export them as CSV, Excel, JSON or SQLite.",
    )
    what = parser.add_argument_group("what to scrape")
    what.add_argument("--pages", type=int, default=None, metavar="N",
                      help="maximum number of listing pages (default: all)")
    what.add_argument("--category", metavar="NAME",
                      help='only scrape one category, e.g. "Travel"')
    what.add_argument("--details", action="store_true",
                      help="also open each book page for category, UPC, stock count "
                           "(one extra request per book, much slower)")
    what.add_argument("--list-categories", action="store_true",
                      help="print all category names and exit")

    filters = parser.add_argument_group("filters")
    filters.add_argument("--max-price", type=float, metavar="GBP",
                         help="only keep books up to this price")
    filters.add_argument("--min-rating", type=int, choices=range(1, 6), metavar="1-5",
                         help="only keep books with at least this many stars")
    filters.add_argument("--in-stock", action="store_true",
                         help="only keep books that are in stock")

    out = parser.add_argument_group("output")
    out.add_argument("--format", nargs="+", choices=FORMATS, default=["csv"],
                     help="one or more output formats (default: csv)")
    out.add_argument("--output", type=Path, default=Path("output"), metavar="DIR",
                     help="output folder (default: output)")
    out.add_argument("--name", default="books", help="file name without extension")
    out.add_argument("--append", action="store_true",
                     help="SQLite: add rows instead of replacing them (price history)")

    polite = parser.add_argument_group("politeness and logging")
    polite.add_argument("--delay", type=float, default=1.0, metavar="SECONDS",
                        help="pause between requests (default: 1.0)")
    polite.add_argument("--retries", type=int, default=3,
                        help="retries for temporary errors (default: 3)")
    polite.add_argument("--timeout", type=float, default=15.0, metavar="SECONDS",
                        help="timeout per request (default: 15)")
    polite.add_argument("-v", "--verbose", action="store_true",
                        help="show every request (debug logging)")
    return parser


def setup_logging(log_file: Path | None, verbose: bool) -> None:
    """Log to the console and, if given, to a file (always in full detail)."""
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
    handlers: list[logging.Handler] = [console]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        handlers.append(file_handler)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)
    for handler in handlers:
        root.addHandler(handler)
    # urllib3 is very chatty on DEBUG; only show its warnings.
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(None if args.list_categories else args.output / "scraper.log", args.verbose)

    session = PoliteSession(delay=args.delay, retries=args.retries, timeout=args.timeout)

    if args.list_categories:
        for name in list_categories(session):
            print(name)
        return 0

    start_url = CATALOGUE_URL
    if args.category:
        try:
            start_url = find_category_url(session, args.category)
        except ValueError as exc:
            log.error("%s", exc)
            return 2

    records = scrape_books(session, start_url, max_pages=args.pages, details=args.details)
    df = clean_books(records)
    df = filter_books(df, max_price=args.max_price, min_rating=args.min_rating,
                      in_stock_only=args.in_stock)

    if df.empty:
        log.warning("No books matched, nothing exported.")
        return 1

    for fmt in args.format:
        path = export(df, fmt, args.output, args.name, append=args.append)
        log.info("Saved %d books to %s", len(df), path)

    log.info("Average price: GBP %.2f | cheapest: GBP %.2f | most expensive: GBP %.2f",
             df["price"].mean(), df["price"].min(), df["price"].max())
    return 0


if __name__ == "__main__":
    sys.exit(main())
