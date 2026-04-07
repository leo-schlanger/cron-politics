"""
Schema de banco de dados para blog de politica.
Versao simplificada - apenas portugues.
"""
import os
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

import psycopg2
from psycopg2.extras import RealDictCursor

# Load .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


class DuplicateBlogPostError(Exception):
    """Erro quando se tenta salvar um post duplicado no blog."""
    pass


def get_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL nao configurada")
    return psycopg2.connect(DATABASE_URL)


def init_blog_tables():
    """Cria tabelas para o blog."""
    conn = get_connection()
    cursor = conn.cursor()

    # Tabela de posts do blog (noticias processadas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blog_posts (
            id SERIAL PRIMARY KEY,
            news_id INTEGER REFERENCES news(id),

            -- Conteudo em Portugues
            title TEXT NOT NULL,
            slug TEXT UNIQUE,
            content TEXT NOT NULL,
            summary TEXT,

            -- Metadata
            image_url TEXT,
            image_local_path TEXT,
            source_url TEXT NOT NULL,
            source_name TEXT NOT NULL,

            -- Categorizacao (para filtros do blog)
            category TEXT,
            region TEXT,
            tags TEXT,
            priority_score REAL DEFAULT 0,

            -- Status
            status TEXT DEFAULT 'draft',
            is_published BOOLEAN DEFAULT FALSE,
            published_at TIMESTAMP,

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- SEO
            meta_description TEXT,
            meta_keywords TEXT
        )
    """)

    # Tabela de imagens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blog_images (
            id SERIAL PRIMARY KEY,
            post_id INTEGER REFERENCES blog_posts(id),
            original_url TEXT NOT NULL,
            local_path TEXT,
            cdn_url TEXT,
            alt_text TEXT,
            is_cover BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabela de processamento (fila)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_queue (
            id SERIAL PRIMARY KEY,
            news_id INTEGER REFERENCES news(id),
            status TEXT DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            UNIQUE(news_id)
        )
    """)

    # Indices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blog_posts_status ON blog_posts(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blog_posts_published ON blog_posts(is_published)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blog_posts_category ON blog_posts(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blog_posts_region ON blog_posts(region)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processing_queue_status ON processing_queue(status)")

    conn.commit()
    conn.close()
    print("[DB] Tabelas de blog criadas")


def add_to_processing_queue(news_id: int) -> int:
    """Adiciona noticia a fila de processamento."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO processing_queue (news_id, status)
            VALUES (%s, 'pending')
            ON CONFLICT (news_id) DO NOTHING
            RETURNING id
        """, (news_id,))
        result = cursor.fetchone()
        queue_id = result[0] if result else None
        conn.commit()
        return queue_id
    finally:
        conn.close()


def get_pending_news(limit: int = 10) -> list:
    """Retorna noticias pendentes para processamento."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT n.*, s.name as source_name, s.category, s.country as region, pq.id as queue_id
            FROM processing_queue pq
            JOIN news n ON pq.news_id = n.id
            JOIN sources s ON n.source_id = s.id
            WHERE pq.status = 'pending'
            ORDER BY
                CASE WHEN s.country = 'Portugal' THEN 0 ELSE 1 END,
                n.priority_score DESC
            LIMIT %s
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows] if rows else []
    finally:
        conn.close()


def check_similar_blog_post(title: str, summary: str, threshold: float = 0.5) -> Optional[dict]:
    """
    Verifica se ja existe um post similar no blog (ultimas 72h).
    Retorna o post similar se encontrado, None caso contrario.
    """
    from deduplication import calculate_similarity
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, title, summary
            FROM blog_posts
            WHERE created_at > NOW() - INTERVAL '72 hours'
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()

        new_text = f"{title} {summary or ''}"
        for row in rows:
            existing_text = f"{row['title']} {row['summary'] or ''}"
            similarity = calculate_similarity(new_text, existing_text)
            if similarity >= threshold:
                return dict(row)

        return None
    finally:
        conn.close()


def save_blog_post(
    news_id: int,
    title: str,
    content: str,
    summary: str,
    image_url: str,
    source_url: str,
    source_name: str,
    category: str,
    region: str,
    tags: list,
    priority_score: float
) -> int:
    """Salva post do blog processado."""
    # Verificar duplicidade antes de salvar
    similar = check_similar_blog_post(title, summary)
    if similar:
        raise DuplicateBlogPostError(
            f"Post similar ja existe: #{similar['id']} - {similar['title'][:60]}"
        )

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Gerar slug unico
        slug = generate_slug(title)
        tags_str = json.dumps(tags) if tags else None

        # Verificar se slug ja existe e gerar alternativo
        cursor.execute("SELECT COUNT(*) FROM blog_posts WHERE slug = %s", (slug,))
        if cursor.fetchone()[0] > 0:
            slug = f"{slug}-{datetime.now().strftime('%H%M%S')}"

        cursor.execute("""
            INSERT INTO blog_posts (
                news_id, title, slug, content, summary,
                image_url, source_url, source_name, category, region, tags, priority_score,
                meta_description,
                status, is_published, published_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                'published', TRUE, NOW()
            ) RETURNING id
        """, (
            news_id, title, slug, content, summary,
            image_url, source_url, source_name, category, region, tags_str, priority_score,
            summary[:160] if summary else None
        ))
        post_id = cursor.fetchone()[0]
        conn.commit()
        return post_id
    finally:
        conn.close()


def update_queue_status(queue_id: int, status: str, error_message: str = None):
    """Atualiza status na fila de processamento."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE processing_queue
            SET status = %s, error_message = %s, processed_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (status, error_message, queue_id))
        conn.commit()
    finally:
        conn.close()


def get_blog_posts(status: str = None, category: str = None, region: str = None, limit: int = 50) -> list:
    """Retorna posts do blog com filtros."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = "SELECT * FROM blog_posts WHERE 1=1"
        params = []

        if status:
            query += " AND status = %s"
            params.append(status)
        if category:
            query += " AND category = %s"
            params.append(category)
        if region:
            query += " AND region = %s"
            params.append(region)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows] if rows else []
    finally:
        conn.close()


def generate_slug(title: str) -> str:
    """Gera slug a partir do titulo."""
    # Normalizar e remover acentos
    slug = unicodedata.normalize('NFKD', title)
    slug = slug.encode('ascii', 'ignore').decode('ascii')

    # Converter para minusculas e substituir espacos
    slug = slug.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')

    return slug[:100]  # Limitar tamanho


def get_blog_stats() -> dict:
    """Retorna estatisticas do blog."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        stats = {}

        cursor.execute("SELECT COUNT(*) FROM blog_posts")
        stats["total_posts"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM blog_posts WHERE status = 'draft'")
        stats["drafts"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM blog_posts WHERE is_published = TRUE")
        stats["published"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM processing_queue WHERE status = 'pending'")
        stats["pending_processing"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM processing_queue WHERE status = 'completed'")
        stats["processed"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM processing_queue WHERE status = 'error'")
        stats["errors"] = cursor.fetchone()[0]

        # Stats por regiao
        cursor.execute("""
            SELECT region, COUNT(*) as count
            FROM blog_posts
            WHERE is_published = TRUE
            GROUP BY region
            ORDER BY count DESC
        """)
        stats["by_region"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Stats por categoria
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM blog_posts
            WHERE is_published = TRUE
            GROUP BY category
            ORDER BY count DESC
        """)
        stats["by_category"] = {row[0]: row[1] for row in cursor.fetchall()}

        return stats
    finally:
        conn.close()


def get_categories() -> list:
    """Retorna lista de categorias disponiveis."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT category
            FROM blog_posts
            WHERE is_published = TRUE
            ORDER BY category
        """)
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_regions() -> list:
    """Retorna lista de regioes disponiveis."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT region
            FROM blog_posts
            WHERE is_published = TRUE
            ORDER BY region
        """)
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    print("Inicializando tabelas de blog...")
    init_blog_tables()

    stats = get_blog_stats()
    print(f"\nEstatisticas:")
    print(f"  Posts: {stats['total_posts']}")
    print(f"  Rascunhos: {stats['drafts']}")
    print(f"  Publicados: {stats['published']}")
    print(f"  Pendentes: {stats['pending_processing']}")
