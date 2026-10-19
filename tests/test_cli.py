import logging

import pandas as pd
import pytest

from book_scraper import cli
from book_scraper.scraper import CATALOGUE_URL

from .conftest import BASE, FakeSession, load


@pytest.fixture(autouse=True)
def reset_logging():
    yield
    root = logging.getLogger()
    for handler in root.handlers:
        handler.close()
    root.handlers.clear()


@pytest.fixture
def fake_site(monkeypatch):
    """Make the CLI use saved HTML instead of the internet."""
    pages = {
        BASE: load("index.html"),
        CATALOGUE_URL: load("catalogue_page_50.html"),  # one page, no "next"
        BASE + "catalogue/category/books/travel_2/index.html": load("category_travel.html"),
    }
    monkeypatch.setattr(cli, "PoliteSession", lambda **kwargs: FakeSession(pages))


def test_defaults():
    args = cli.build_parser().parse_args([])
    assert args.format == ["csv"]
    assert args.pages is None
    assert args.delay == 1.0


def test_invalid_rating_is_rejected():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--min-rating", "9"])


def test_scrape_and_export(fake_site, tmp_path):
    code = cli.main(["--format", "csv", "xlsx", "--output", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "books.xlsx").exists()
    assert len(pd.read_csv(tmp_path / "books.csv")) == 20
    assert "Finished: 20 books" in (tmp_path / "scraper.log").read_text(encoding="utf-8")


def test_category_and_filters(fake_site, tmp_path):
    code = cli.main(["--category", "travel", "--max-price", "30", "--name", "cheap_travel",
                     "--output", str(tmp_path)])
    assert code == 0
    df = pd.read_csv(tmp_path / "cheap_travel.csv")
    assert len(df) > 0 and (df["price"] <= 30).all()


def test_unknown_category_returns_error(fake_site, tmp_path):
    assert cli.main(["--category", "nope", "--output", str(tmp_path)]) == 2


def test_no_matches_returns_1(fake_site, tmp_path):
    assert cli.main(["--max-price", "0.01", "--output", str(tmp_path)]) == 1
    assert not (tmp_path / "books.csv").exists()


def test_list_categories(fake_site, capsys):
    assert cli.main(["--list-categories"]) == 0
    assert "Travel" in capsys.readouterr().out
