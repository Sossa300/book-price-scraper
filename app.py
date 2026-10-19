"""Streamlit dashboard for the scraped books.

Start with:  streamlit run app.py

Three data sources:
- the bundled example data (data/sample_books.csv, a full scrape of 1000 books)
- your own result file from the output/ folder (CSV or SQLite)
- a live scrape of a few pages straight from the browser
"""

from __future__ import annotations

import io
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from book_scraper.cleaning import clean_books
from book_scraper.exporters import SQLITE_TABLE
from book_scraper.fetcher import PoliteSession
from book_scraper.scraper import CATALOGUE_URL, list_categories, scrape_books

ROOT = Path(__file__).parent
SAMPLE = ROOT / "data" / "sample_books.csv"
OUTPUT = ROOT / "output"

st.set_page_config(page_title="Book Price Scraper", page_icon="📚", layout="wide")


# ----------------------------------------------------------------- loading

@st.cache_data
def load_file(path: str) -> pd.DataFrame:
    if path.endswith(".db"):
        with sqlite3.connect(path) as con:
            return pd.read_sql(f"SELECT * FROM {SQLITE_TABLE}", con)
    return pd.read_csv(path, encoding="utf-8-sig")


@st.cache_data(ttl=3600, show_spinner="Loading categories ...")
def categories() -> dict[str, str]:
    return list_categories(PoliteSession(delay=0.5))


def live_scrape(start_url: str, pages: int, details: bool) -> pd.DataFrame:
    bar = st.progress(0.0, text="Starting ...")
    records = scrape_books(
        PoliteSession(delay=0.5), start_url, max_pages=pages, details=details,
        on_page=lambda page, total: bar.progress(page / pages, text=f"Page {page}: {total} books"),
    )
    bar.empty()
    return clean_books(records)


def to_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name="Books")
    return buffer.getvalue()


# ----------------------------------------------------------------- sidebar

st.sidebar.title("📚 Book Price Scraper")
own_files = sorted(OUTPUT.glob("*.csv")) + sorted(OUTPUT.glob("*.db")) if OUTPUT.exists() else []
sources = ["Example data (1000 books)"] + (["File from output/"] if own_files else []) + ["Scrape live"]
source = st.sidebar.radio("Data source", sources)

df: pd.DataFrame | None = None
if source.startswith("Example"):
    df = load_file(str(SAMPLE))
elif source.startswith("File"):
    chosen = st.sidebar.selectbox("File", own_files, format_func=lambda p: p.name)
    df = load_file(str(chosen))
else:
    st.sidebar.caption("Scrapes books.toscrape.com politely (0.5 s pause per request).")
    try:
        names = ["All books"] + list(categories())
    except Exception as exc:  # no internet etc.
        st.sidebar.error(f"Could not reach the website: {exc}")
        names = ["All books"]
    category = st.sidebar.selectbox("Category", names)
    pages = st.sidebar.slider("Max. pages (20 books each)", 1, 10, 2)
    details = st.sidebar.checkbox("Include details (category, stock, UPC)", value=False,
                                  help="One extra request per book, about 20x slower.")
    if st.sidebar.button("Start scraping", type="primary"):
        start = CATALOGUE_URL if category == "All books" else categories()[category]
        st.session_state["live"] = live_scrape(start, pages, details)
    df = st.session_state.get("live")

if df is None or df.empty:
    st.title("Book Price Scraper")
    st.info("Choose your options in the sidebar and click **Start scraping**.")
    st.stop()

# ----------------------------------------------------------------- filters

st.sidebar.divider()
st.sidebar.subheader("Filters")
search = st.sidebar.text_input("Title contains")
low, high = float(df["price"].min()), float(df["price"].max())
price_range = st.sidebar.slider("Price (£)", low, high, (low, high)) if low < high else (low, high)
min_rating = st.sidebar.select_slider("Minimum rating", options=[1, 2, 3, 4, 5], value=1,
                                      format_func=lambda n: "★" * n)
chosen_categories = []
if "category" in df:
    chosen_categories = st.sidebar.multiselect("Categories", sorted(df["category"].dropna().unique()))

view = df[df["price"].between(*price_range) & (df["rating"].fillna(0) >= min_rating)]
if search:
    view = view[view["title"].str.contains(search, case=False, na=False)]
if chosen_categories:
    view = view[view["category"].isin(chosen_categories)]

# ----------------------------------------------------------------- page

st.title("📚 Book Price Scraper")
st.caption(f"Source: {source} · scraped at {df['scraped_at'].iloc[0]} · "
           f"showing {len(view)} of {len(df)} books")

if view.empty:
    st.warning("No books match these filters.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Books", f"{len(view):,}")
k2.metric("Average price", f"£{view['price'].mean():.2f}")
k3.metric("Cheapest", f"£{view['price'].min():.2f}")
k4.metric("5-star books", f"{(view['rating'] == 5).mean():.0%}")

left, right = st.columns(2)
with left:
    fig = px.histogram(view, x="price", nbins=30, title="Price distribution",
                       labels={"price": "Price (£)"})
    fig.update_layout(yaxis_title="Books", bargap=0.05)
    st.plotly_chart(fig, width="stretch")
with right:
    by_rating = view.groupby("rating", as_index=False).agg(
        books=("title", "size"), avg_price=("price", "mean"))
    fig = px.bar(by_rating, x="rating", y="avg_price", text="books",
                 title="Average price by rating",
                 labels={"rating": "Stars", "avg_price": "Average price (£)"})
    fig.update_traces(texttemplate="%{text} books", textposition="outside")
    st.plotly_chart(fig, width="stretch")

if "category" in view:
    top = (view.groupby("category", as_index=False)
           .agg(books=("title", "size"), avg_price=("price", "mean"))
           .sort_values("books", ascending=False).head(15))
    fig = px.bar(top, x="books", y="category", orientation="h", color="avg_price",
                 color_continuous_scale="Blues", title="Top 15 categories",
                 labels={"books": "Books", "category": "", "avg_price": "Avg £"})
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=480)
    st.plotly_chart(fig, width="stretch")

st.subheader("Books")
shown = [c for c in ["image_url", "title", "price", "rating", "category", "stock_count",
                     "in_stock", "url"] if c in view.columns]
st.dataframe(
    view[shown].sort_values("price"),
    hide_index=True,
    width="stretch",
    column_config={
        "image_url": st.column_config.ImageColumn("Cover", width="small"),
        "title": st.column_config.TextColumn("Title", width="large"),
        "category": st.column_config.TextColumn("Category"),
        "price": st.column_config.NumberColumn("Price", format="£%.2f"),
        "rating": st.column_config.NumberColumn("Rating", format="%d ★"),
        "stock_count": st.column_config.NumberColumn("Stock"),
        "in_stock": st.column_config.CheckboxColumn("In stock"),
        "url": st.column_config.LinkColumn("Link", display_text="open"),
    },
)

d1, d2, _ = st.columns([1, 1, 4])
d1.download_button("⬇ CSV", view.to_csv(index=False).encode("utf-8-sig"),
                   "books.csv", "text/csv")
d2.download_button("⬇ Excel", to_excel(view), "books.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
