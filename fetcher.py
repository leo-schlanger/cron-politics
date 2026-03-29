"""
RSS Feed Fetcher for Politics/News
"""
import re
import time
import json
import feedparser
import requests
from datetime import datetime
from dateutil import parser as date_parser

from database import (
    get_active_sources,
    get_keywords,
    insert_news,
    update_source_fetch,
    insert_fetch_log,
    get_recent_title_hashes
)
from deduplication import generate_title_hash, is_duplicate


USER_AGENT = "PoliticsNewsCron/1.0"
FETCH_TIMEOUT = 30


def clean_html(text):
    """Remove HTML tags from text"""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def parse_date(date_str):
    """Parse date string to datetime"""
    if not date_str:
        return None
    try:
        return date_parser.parse(date_str)
    except:
        return None


def calculate_priority(title, description, positive_keywords, negative_keywords):
    """Calculate priority score based on keywords"""
    text = f"{title} {description}".lower()

    # Check negative keywords first
    for kw in negative_keywords:
        if kw in text:
            return -1.0, []

    # Calculate positive score
    score = 0.0
    matched = []

    for kw in positive_keywords:
        if kw in text:
            matched.append(kw)
            if kw in title.lower():
                score += 2.0  # Title match = higher weight
            else:
                score += 1.0  # Description match

    return score, matched


def fetch_feed(source):
    """Fetch and parse a single RSS feed"""
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(source["url"], headers=headers, timeout=FETCH_TIMEOUT)
        response.raise_for_status()

        feed = feedparser.parse(response.content)
        return feed.entries
    except Exception as e:
        raise Exception(f"Failed to fetch {source['name']}: {str(e)}")


def process_entry(entry, source, positive_kw, negative_kw):
    """Process a single feed entry"""
    title = clean_html(entry.get("title", ""))
    if not title:
        return None

    link = entry.get("link", "")
    if not link:
        return None

    description = clean_html(
        entry.get("description", "") or
        entry.get("summary", "")
    )

    content = ""
    if "content" in entry and entry["content"]:
        content = clean_html(entry["content"][0].get("value", ""))

    author = entry.get("author", "")

    # Parse date
    date_str = entry.get("published", "") or entry.get("updated", "")
    published_at = parse_date(date_str)

    # Calculate priority
    score, matched = calculate_priority(title, description, positive_kw, negative_kw)

    # Skip filtered content
    if score < 0:
        return None

    # Generate title hash for deduplication
    title_hash = generate_title_hash(title)

    return {
        "title": title,
        "link": link,
        "description": description,
        "content": content,
        "author": author,
        "published_at": published_at,
        "category": source["category"],
        "priority_score": score,
        "matched_keywords": json.dumps(matched) if matched else None,
        "title_hash": title_hash
    }


def fetch_all(category=None, quiet=False):
    """Fetch news from all active sources"""
    sources = get_active_sources(category)
    positive_kw, negative_kw = get_keywords()
    # Otimização: 24h é suficiente para dedup (era 72h)
    existing_hashes = get_recent_title_hashes(hours=24)

    stats = {
        "total_sources": len(sources),
        "successful": 0,
        "failed": 0,
        "total_entries": 0,
        "new_news": 0,
        "duplicates": 0,
        "filtered": 0
    }

    for source in sources:
        start_time = time.time()

        try:
            entries = fetch_feed(source)
            stats["total_entries"] += len(entries)

            source_new = 0
            source_dup = 0
            source_filtered = 0

            for entry in entries:
                news_item = process_entry(entry, source, positive_kw, negative_kw)

                if news_item is None:
                    source_filtered += 1
                    continue

                # Check for duplicate
                if is_duplicate(news_item["title_hash"], existing_hashes):
                    source_dup += 1
                    continue

                # Insert news
                news_id = insert_news(news_item, source["id"])
                if news_id:
                    source_new += 1
                    existing_hashes.add(news_item["title_hash"])
                else:
                    source_dup += 1

            stats["new_news"] += source_new
            stats["duplicates"] += source_dup
            stats["filtered"] += source_filtered
            stats["successful"] += 1

            duration_ms = int((time.time() - start_time) * 1000)
            update_source_fetch(source["id"], success=True)
            insert_fetch_log(source["id"], "success", source_new, duration_ms=duration_ms)

            if not quiet:
                print(f"[OK] {source['name']}: {source_new} new, {source_dup} dup, {source_filtered} filtered")

        except Exception as e:
            stats["failed"] += 1
            duration_ms = int((time.time() - start_time) * 1000)
            update_source_fetch(source["id"], success=False, error_message=str(e))
            insert_fetch_log(source["id"], "error", error_message=str(e), duration_ms=duration_ms)

            if not quiet:
                print(f"[FAIL] {source['name']}: {str(e)[:50]}")

    return stats
