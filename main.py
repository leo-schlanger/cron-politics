#!/usr/bin/env python3
"""
Cron Politics - News Aggregator CLI
"""
import sys
import json
import argparse
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from database import (
    setup_database,
    insert_sources_from_json,
    insert_keywords_from_json,
    get_stats,
    cleanup_old_news,
    get_active_sources
)
from fetcher import fetch_all


def get_blog_module():
    """Import blog modules lazily to avoid errors if not configured"""
    try:
        from database_blog import init_blog_tables, get_blog_stats
        from processor import queue_high_priority_news, process_queue
        return {
            "init_blog_tables": init_blog_tables,
            "get_blog_stats": get_blog_stats,
            "queue_high_priority_news": queue_high_priority_news,
            "process_queue": process_queue
        }
    except Exception as e:
        print(f"Blog module not available: {e}")
        return None


def load_sources_json():
    """Load sources.json file"""
    with open("sources.json", "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_setup(args):
    """Setup database tables and load sources"""
    print("Setting up database...")
    setup_database()

    print("\nLoading sources...")
    data = load_sources_json()
    sources_count = insert_sources_from_json(data)
    print(f"Loaded {sources_count} sources")

    print("\nLoading keywords...")
    keywords_count = insert_keywords_from_json(data.get("keywords", {}))
    print(f"Loaded {keywords_count} keywords")

    print("\nSetup complete!")


def cmd_fetch(args):
    """Fetch news from sources"""
    category = args.category if hasattr(args, "category") else None
    quiet = args.quiet if hasattr(args, "quiet") else False

    if category:
        print(f"Fetching news for category: {category}")
    else:
        print("Fetching news from all sources...")

    stats = fetch_all(category=category, quiet=quiet)

    print("\n" + "=" * 50)
    print("FETCH COMPLETE")
    print("=" * 50)
    print(f"Sources:    {stats['successful']}/{stats['total_sources']} successful")
    print(f"Entries:    {stats['total_entries']} found")
    print(f"New:        {stats['new_news']} inserted")
    print(f"Duplicates: {stats['duplicates']} skipped")
    print(f"Filtered:   {stats['filtered']} skipped")
    if stats['failed'] > 0:
        print(f"Failed:     {stats['failed']} sources")


def cmd_stats(args):
    """Show database statistics"""
    stats = get_stats()

    print("\n" + "=" * 50)
    print("DATABASE STATISTICS")
    print("=" * 50)
    print(f"Total news:      {stats['total_news']:,}")
    print(f"Last 24h:        {stats['last_24h']:,}")
    print(f"High priority:   {stats['high_priority']:,}")
    print(f"Active sources:  {stats['active_sources']}")

    print("\nBy category:")
    for cat, count in stats.get("by_category", {}).items():
        print(f"  {cat}: {count:,}")


def cmd_cleanup(args):
    """Cleanup old news"""
    days = args.days if hasattr(args, "days") else 60

    print(f"Cleaning up news older than {days} days...")
    deleted = cleanup_old_news(days)
    print(f"Deleted {deleted:,} old news entries")


def cmd_sources(args):
    """List sources"""
    category = args.category if hasattr(args, "category") else None
    sources = get_active_sources(category)

    print(f"\nActive sources: {len(sources)}")
    print("-" * 60)

    current_cat = None
    for s in sources:
        if s["category"] != current_cat:
            current_cat = s["category"]
            print(f"\n[{current_cat.upper()}]")
        print(f"  - {s['name']} ({s.get('language', 'en')})")


def main():
    parser = argparse.ArgumentParser(
        description="Cron Politics - News Aggregator",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Setup
    subparsers.add_parser("setup", help="Setup database and load sources")

    # Fetch
    fetch_parser = subparsers.add_parser("fetch", help="Fetch news from sources")
    fetch_parser.add_argument("--category", "-c", help="Filter by category")
    fetch_parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")

    # Stats
    subparsers.add_parser("stats", help="Show statistics")

    # Cleanup
    cleanup_parser = subparsers.add_parser("cleanup", help="Cleanup old news")
    cleanup_parser.add_argument("--days", "-d", type=int, default=60, help="Days to keep (default: 60)")

    # Sources
    sources_parser = subparsers.add_parser("sources", help="List sources")
    sources_parser.add_argument("--category", "-c", help="Filter by category")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "setup": cmd_setup,
        "fetch": cmd_fetch,
        "stats": cmd_stats,
        "cleanup": cmd_cleanup,
        "sources": cmd_sources
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
