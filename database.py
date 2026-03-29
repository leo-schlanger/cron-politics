"""
Database driver for Supabase/PostgreSQL
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta


DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_connection():
    """Get database connection"""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not configured")
    return psycopg2.connect(DATABASE_URL)


def setup_database():
    """Create all tables"""
    conn = get_connection()
    cur = conn.cursor()

    # Sources table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            country TEXT,
            language TEXT DEFAULT 'en',
            is_active BOOLEAN DEFAULT true,
            last_fetch TIMESTAMP,
            fetch_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # News table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id SERIAL PRIMARY KEY,
            source_id INTEGER REFERENCES sources(id),
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            description TEXT,
            content TEXT,
            author TEXT,
            published_at TIMESTAMP,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category TEXT,
            priority_score REAL DEFAULT 0,
            matched_keywords TEXT,
            title_hash TEXT
        )
    """)

    # Keywords table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id SERIAL PRIMARY KEY,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT,
            weight REAL DEFAULT 1.0,
            is_negative BOOLEAN DEFAULT false
        )
    """)

    # Fetch logs table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fetch_logs (
            id SERIAL PRIMARY KEY,
            source_id INTEGER REFERENCES sources(id),
            status TEXT NOT NULL,
            news_count INTEGER DEFAULT 0,
            error_message TEXT,
            duration_ms INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_news_source ON news(source_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_news_category ON news(category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_news_priority ON news(priority_score DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_news_title_hash ON news(title_hash)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sources_category ON sources(category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sources_active ON sources(is_active)")

    conn.commit()
    cur.close()
    conn.close()
    print("Database setup complete!")


def insert_sources_from_json(sources_data):
    """Insert sources from JSON config"""
    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    for category, data in sources_data.items():
        if category == "keywords":
            continue
        feeds = data.get("feeds", [])
        for feed in feeds:
            try:
                cur.execute("""
                    INSERT INTO sources (name, url, category, country, language, is_active)
                    VALUES (%s, %s, %s, %s, %s, true)
                    ON CONFLICT (url) DO UPDATE SET
                        name = EXCLUDED.name,
                        category = EXCLUDED.category,
                        country = EXCLUDED.country,
                        language = EXCLUDED.language,
                        is_active = true
                """, (
                    feed.get("name"),
                    feed.get("url"),
                    category,
                    feed.get("country"),
                    feed.get("language", "en")
                ))
                inserted += 1
            except Exception as e:
                print(f"Error inserting {feed.get('name')}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    return inserted


def insert_keywords_from_json(keywords_data):
    """Insert keywords from JSON config"""
    conn = get_connection()
    cur = conn.cursor()

    inserted = 0

    # High priority keywords
    high_priority = keywords_data.get("high_priority", {})
    for category, words in high_priority.items():
        for word in words:
            try:
                cur.execute("""
                    INSERT INTO keywords (keyword, category, weight, is_negative)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (keyword) DO UPDATE SET
                        category = EXCLUDED.category,
                        weight = EXCLUDED.weight,
                        is_negative = EXCLUDED.is_negative
                """, (word.lower(), category, 2.0, False))
                inserted += 1
            except Exception as e:
                print(f"Error inserting keyword {word}: {e}")

    # Filter out keywords
    filter_out = keywords_data.get("filter_out", {}).get("terms", [])
    for word in filter_out:
        try:
            cur.execute("""
                INSERT INTO keywords (keyword, category, weight, is_negative)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (keyword) DO UPDATE SET
                    category = EXCLUDED.category,
                    weight = EXCLUDED.weight,
                    is_negative = EXCLUDED.is_negative
            """, (word.lower(), "filter", -1.0, True))
            inserted += 1
        except Exception as e:
            print(f"Error inserting filter keyword {word}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    return inserted


def get_active_sources(category=None):
    """Get active sources, optionally filtered by category"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if category:
        cur.execute("""
            SELECT * FROM sources
            WHERE is_active = true AND category = %s
            ORDER BY name
        """, (category,))
    else:
        cur.execute("""
            SELECT * FROM sources
            WHERE is_active = true
            ORDER BY category, name
        """)

    sources = cur.fetchall()
    cur.close()
    conn.close()
    return sources


def get_keywords():
    """Get all keywords"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT * FROM keywords")
    keywords = cur.fetchall()

    cur.close()
    conn.close()

    positive = [k["keyword"] for k in keywords if not k["is_negative"]]
    negative = [k["keyword"] for k in keywords if k["is_negative"]]

    return positive, negative


def insert_news(news_item, source_id):
    """Insert a news item"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO news (
                source_id, title, link, description, content, author,
                published_at, category, priority_score, matched_keywords, title_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (link) DO NOTHING
            RETURNING id
        """, (
            source_id,
            news_item.get("title"),
            news_item.get("link"),
            news_item.get("description"),
            news_item.get("content"),
            news_item.get("author"),
            news_item.get("published_at"),
            news_item.get("category"),
            news_item.get("priority_score", 0),
            news_item.get("matched_keywords"),
            news_item.get("title_hash")
        ))

        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise e


def update_source_fetch(source_id, success=True, error_message=None):
    """Update source after fetch attempt"""
    conn = get_connection()
    cur = conn.cursor()

    if success:
        cur.execute("""
            UPDATE sources SET
                last_fetch = CURRENT_TIMESTAMP,
                fetch_count = fetch_count + 1,
                error_count = 0
            WHERE id = %s
        """, (source_id,))
    else:
        cur.execute("""
            UPDATE sources SET
                error_count = error_count + 1
            WHERE id = %s
        """, (source_id,))

    conn.commit()
    cur.close()
    conn.close()


def insert_fetch_log(source_id, status, news_count=0, error_message=None, duration_ms=0):
    """Insert fetch log entry"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO fetch_logs (source_id, status, news_count, error_message, duration_ms)
        VALUES (%s, %s, %s, %s, %s)
    """, (source_id, status, news_count, error_message, duration_ms))

    conn.commit()
    cur.close()
    conn.close()


def get_recent_title_hashes(hours=24):
    """Get title hashes from recent news for deduplication.
    Optimized: reduced from 72h to 24h to save egress.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Otimização: limite de 500 registros para reduzir egress
    cur.execute("""
        SELECT title_hash FROM news
        WHERE fetched_at > %s AND title_hash IS NOT NULL
        ORDER BY fetched_at DESC
        LIMIT 500
    """, (datetime.utcnow() - timedelta(hours=hours),))

    hashes = set(row[0] for row in cur.fetchall())
    cur.close()
    conn.close()
    return hashes


def cleanup_old_news(days=60, preserve_high_priority=True):
    """Delete news older than specified days, preserving high-impact articles for ML.

    Args:
        days: Days of retention for normal articles
        preserve_high_priority: If True, preserves articles with priority_score >= 4.0 for ML
    """
    conn = get_connection()
    cur = conn.cursor()

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Cleanup news (preserve high priority for ML analysis)
    if preserve_high_priority:
        cur.execute("""
            DELETE FROM news
            WHERE fetched_at < %s
            AND priority_score < 4.0
        """, (cutoff,))
    else:
        cur.execute("DELETE FROM news WHERE fetched_at < %s", (cutoff,))

    deleted_news = cur.rowcount

    # Cleanup fetch_logs (no historical value)
    cur.execute("DELETE FROM fetch_logs WHERE created_at < %s", (cutoff,))
    deleted_logs = cur.rowcount

    conn.commit()
    cur.close()
    conn.close()

    print(f"Deleted {deleted_news} news articles")
    print(f"Deleted {deleted_logs} fetch logs")
    if preserve_high_priority:
        print("Preserved: articles with priority_score >= 4.0 for ML")

    return deleted_news


def get_stats():
    """Get database statistics"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    stats = {}

    # Total news
    cur.execute("SELECT COUNT(*) as total FROM news")
    stats["total_news"] = cur.fetchone()["total"]

    # News by category
    cur.execute("""
        SELECT category, COUNT(*) as count
        FROM news
        GROUP BY category
        ORDER BY count DESC
    """)
    stats["by_category"] = {row["category"]: row["count"] for row in cur.fetchall()}

    # News last 24h
    cur.execute("""
        SELECT COUNT(*) as count FROM news
        WHERE fetched_at > NOW() - INTERVAL '24 hours'
    """)
    stats["last_24h"] = cur.fetchone()["count"]

    # Sources
    cur.execute("SELECT COUNT(*) as total FROM sources WHERE is_active = true")
    stats["active_sources"] = cur.fetchone()["total"]

    # High priority news (score >= 2)
    cur.execute("SELECT COUNT(*) as count FROM news WHERE priority_score >= 2")
    stats["high_priority"] = cur.fetchone()["count"]

    cur.close()
    conn.close()

    return stats
