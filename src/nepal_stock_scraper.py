"""
Nepal Stock Financial News Scraper
Sources: Sharesansar, Merolagani, Nepsealpha, SharehubNepal
"""

import requests
import os
from bs4 import BeautifulSoup
from datetime import datetime, date
import json
import csv
import news_sentiment_analyzer as analyzer

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
CSV_FILE = "data/nepal_stock_news.csv"
CSV_COLUMNS = ["id", "source", "title", "url", "date", "scraped_at", "content"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ─────────────────────────────────────────────
# CSV HELPERS
# ─────────────────────────────────────────────
def load_existing_urls(csv_file: str) -> set[str]:
    """Return a set of URLs already saved in the CSV (for deduplication)."""
    if not os.path.exists(csv_file):
        return set()
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["url"] for row in reader if row.get("url")}



def save_to_csv(articles: list[dict], csv_file: str) -> int:
    """
    Append new articles to the CSV.
    Creates the file with headers if it doesn't exist.
    Returns the number of rows actually written.
    """
    if not articles:
        return 0
 
    file_exists = os.path.exists(csv_file)
    with open(csv_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()          # write header only for new files
        for article in articles:
            writer.writerow({col: article.get(col, "") for col in CSV_COLUMNS})
 
    return len(articles)


def fetch_page(url: str) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        print(f"  [ERROR] Failed to fetch {url}: {e}")
        return None


# ─────────────────────────────────────────────
# 1. SHARESANSAR
# ─────────────────────────────────────────────
def scrape_sharesansar_article(url: str):
    """
    Scrape full content from a Sharesansar news detail page.
    Returns a dict with title, date, content, and tags.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Could not fetch URL: {e}")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")

    # ── Title ──────────────────────────────────────
    title_tag = soup.select_one("h1.newsdetail-titl, h1.news-title, h1")
    title = title_tag.get_text(strip=True) if title_tag else "N/A"

    # ── Published date ─────────────────────────────
    date_tag = soup.select_one("span.share-time, span.news-date, time")
    date = date_tag.get_text(strip=True) if date_tag else "N/A"

    # ── Main content ───────────────────────────────
    content_tag = soup.select_one("div#newsdetail-content")

    if content_tag:
        # Remove unwanted embedded tags (ads, scripts, share buttons)
        for tag in content_tag.select("script, style, iframe, .social-share, .advertisement"):
            tag.decompose()

        # Extract paragraph text
        paragraphs = [p.get_text(strip=True) for p in content_tag.find_all("p") if p.get_text(strip=True)]
        content = "\n\n".join(paragraphs)

        # Fallback: grab all text if no <p> tags found
        if not content:
            content = content_tag.get_text(separator="\n", strip=True)
    else:
        content = "N/A"

    return content


def scrape_sharesansar(max_articles: int = 10) -> list[dict]:
    """Scrape latest news from sharesansar.com"""
    print("Scraping Sharesansar...")
    url = "https://www.sharesansar.com/category/latest"
    soup = fetch_page(url)
    if not soup:
        return []

    results = []
    articles = soup.select("div.featured-news-list")[:max_articles]

    today = date.today()
    sn = 0

    for article in articles:
        title_tag = article.select_one("h4.featured-news-title")
        date_tag = article.select_one("span.text-org")
        link_tag = title_tag.find_parent("a")
        sn=sn+1

        if title_tag:
            results.append({
                "id": today.strftime('%Y%m%d')+"SS"+("00"+str(sn))[-3:],
                "source": "Sharesansar",
                "title": title_tag.get_text(strip=True),
                "url": link_tag.get("href", ""),
                "date": date_tag.get_text(strip=True) if date_tag else "N/A",
                "scraped_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "content": scrape_sharesansar_article(link_tag.get("href", "")),
            })

    print(f"  Found {len(results)} articles.")
    return results


# ─────────────────────────────────────────────
# 2. MEROLAGANI
# ─────────────────────────────────────────────
def scrape_merolagani(max_articles: int = 10) -> list[dict]:
    """Scrape latest news from merolagani.com"""
    print("Scraping Merolagani...")
    url = "https://merolagani.com/NewsList.aspx"
    soup = fetch_page(url)
    if not soup:
        return []

    results = []
    articles = soup.select("div.media-news")[:max_articles]

    for article in articles:
        title_tag = article.select_one("a.media-heading")
        date_tag = article.select_one("span.media-label")

        if title_tag:
            href = title_tag.get("href", "")
            full_url = f"https://merolagani.com/{href}" if href.startswith("/") else href
            results.append({
                "source": "Merolagani",
                "title": title_tag.get_text(strip=True),
                "url": full_url,
                "date": date_tag.get_text(strip=True) if date_tag else "N/A",
            })

    print(f"  Found {len(results)} articles.")
    return results


# ─────────────────────────────────────────────
# 3. NEPSEALPHA
# ─────────────────────────────────────────────
def scrape_nepsealpha(max_articles: int = 10) -> list[dict]:
    """Scrape latest news from nepsealpha.com"""
    print("Scraping Nepsealpha...")
    url = "https://nepsealpha.com/news"
    soup = fetch_page(url)
    if not soup:
        return []

    results = []
    articles = soup.select("div.news-item, article.news-card, div.single-blog")[:max_articles]

    for article in articles:
        title_tag = article.select_one("h2 a, h3 a, .news-title a")
        date_tag = article.select_one("span.date, time, .news-date")

        if title_tag:
            href = title_tag.get("href", "")
            full_url = f"https://nepsealpha.com{href}" if href.startswith("/") else href
            results.append({
                "source": "Nepsealpha",
                "title": title_tag.get_text(strip=True),
                "url": full_url,
                "date": date_tag.get_text(strip=True) if date_tag else "N/A",
            })

    print(f"  Found {len(results)} articles.")
    return results


# ─────────────────────────────────────────────
# 4. SHAREHUB NEPAL
# ─────────────────────────────────────────────
def scrape_sharehubnepal(max_articles: int = 10) -> list[dict]:
    """Scrape latest news from sharehubnepal.com/news"""
    print("Scraping SharehubNepal...")
    url = "https://sharehubnepal.com/news"
    soup = fetch_page(url)
    if not soup:
        return []

    results = []
    # Try common news listing patterns
    articles = soup.select("div.news-card, article, div.post-item, li.news-item")[:max_articles]

    for article in articles:
        title_tag = article.select_one("h2 a, h3 a, .title a, a.news-link")
        date_tag = article.select_one("span.date, time, .post-date, .published")

        if title_tag:
            href = title_tag.get("href", "")
            full_url = f"https://sharehubnepal.com{href}" if href.startswith("/") else href
            results.append({
                "source": "SharehubNepal",
                "title": title_tag.get_text(strip=True),
                "url": full_url,
                "date": date_tag.get_text(strip=True) if date_tag else "N/A",
            })

    print(f"  Found {len(results)} articles.")
    return results


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def scrape_all(max_per_source: int = 10) -> list[dict]:
    """Run all scrapers and return combined results."""
    print(f"\n{'='*55}")
    print("  Nepal Stock News Scraper")
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}\n")

    all_news = []
    scrapers = [
        scrape_sharesansar #,
        #scrape_merolagani,
        #scrape_nepsealpha,
        #scrape_sharehubnepal,
    ]

    for scraper in scrapers:
        articles = scraper(max_per_source)
        all_news.extend(articles)
        print()

    print(f"{'='*55}")
    print(f"  Total articles collected: {len(all_news)}")
    print(f"{'='*55}\n")
    return all_news


def display(news: list[dict]) -> None:
    """Pretty-print news articles grouped by source."""
    from itertools import groupby

    sorted_news = sorted(news, key=lambda x: x["source"])
    for source, articles in groupby(sorted_news, key=lambda x: x["source"]):
        print(f"\n{'─'*55}")
        print(f"  {source}")
        print(f"{'─'*55}")
        for i, article in enumerate(articles, 1):
            print(f"\n  {i}. {article['title']}")
            print(f"     Date : {article['date']}")
            print(f"     URL  : {article['url']}")


if __name__ == "__main__":
    print(f"\n{'='*55}")
    print("  Nepal Stock News Scraper")
    print(f"  Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  CSV file: {CSV_FILE}")
    print(f"{'='*55}\n")
 
    # Load URLs already in the CSV
    existing_urls = load_existing_urls(CSV_FILE)
    print(f"  Existing articles in CSV : {len(existing_urls)}\n")

    # Scrape all sources
    scraped = scrape_all(max_per_source=10)

    # Filter out duplicates (by URL)
    new_articles = [a for a in scraped if a["url"] and a["url"] not in existing_urls]
    print(f"  New (not in CSV yet)     : {len(new_articles)}")

    # Append only new articles
    written = save_to_csv(new_articles, CSV_FILE)

    print(f"  Written to CSV           : {written}")
    print(f"\n{'='*55}")
    if written:
        print(f"  ✅ {written} new article(s) appended to '{CSV_FILE}'")
    else:
        print(f"  ℹ️  No new articles found. CSV is already up to date.")
    print(f"{'='*55}\n")

    analyzer.analyze_n_save(new_articles)