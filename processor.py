"""
Processador de noticias de politica para blog.
- Reescreve noticias usando IA (apenas portugues)
- Extrai imagens de capa
- Da prioridade a noticias de Portugal
"""
import os
import re
import json
import requests
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from database_blog import (
    get_pending_news, save_blog_post, update_queue_status,
    add_to_processing_queue, get_blog_stats
)
from database import get_connection
from utils import retry, logger, RetryError
from html_parser import extract_image_from_content as extract_image_html

# APIs disponiveis
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Configuracao
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")  # openai ou anthropic
MAX_API_RETRIES = 3


# Mapeamento de categorias para labels do blog
CATEGORY_LABELS = {
    "politics_pt": "Politica Portugal",
    "politics_br": "Politica Brasil",
    "politics_world": "Politica Internacional",
    "politics_latam": "Politica America Latina",
    "controversies": "Controversias",
    "conflicts": "Conflitos",
    "disasters": "Desastres"
}


def extract_image_from_content(content: str, link: str) -> Optional[str]:
    """
    Extrai URL de imagem do conteudo ou pagina.
    """
    page_html = None
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(link, headers=headers, timeout=10)
        page_html = response.text
    except (requests.RequestException, ValueError, AttributeError):
        pass

    return extract_image_html(content, page_html)


@retry(
    max_attempts=MAX_API_RETRIES,
    delay=2.0,
    backoff=2.0,
    exceptions=(requests.exceptions.RequestException, requests.exceptions.Timeout)
)
def rewrite_with_openai(title: str, content: str, source_name: str, category: str) -> dict:
    """Reescreve noticia usando OpenAI GPT-4."""
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY nao configurada")

    category_label = CATEGORY_LABELS.get(category, category)

    prompt = f"""Es um jornalista imparcial e rigoroso.
Reescreve a noticia abaixo em formato de artigo informativo.

NOTICIA ORIGINAL:
Titulo: {title}
Fonte: {source_name}
Categoria: {category_label}
Conteudo: {content[:2000]}

REGRAS DE NEUTRALIDADE (OBRIGATORIO):
- Seres COMPLETAMENTE NEUTRO e IMPARCIAL politicamente
- Reportar APENAS os factos, sem opinioes ou interpretacoes
- NAO usar linguagem sensacionalista ou exagerada
- NAO favorecer nenhum partido, politico ou ideologia
- NAO usar adjetivos valorativos (bom, mau, excelente, terrivel)
- Apresentar todos os lados da questao quando relevante
- Usar verbos neutros: "afirmou", "declarou", "referiu" (nao "atacou", "destruiu")
- Citar fontes e atribuir declaracoes corretamente

INSTRUCOES DE FORMATO:
1. Reescreve com as tuas proprias palavras (nao copies)
2. Mantem TODOS os factos, dados e numeros importantes
3. Tom serio, profissional e factual
4. Estrutura clara com 3-5 paragrafos
5. Titulo informativo e directo (sem sensacionalismo)
6. Resumo factual de 2-3 frases
7. Sugere a categoria mais adequada: politics_pt, politics_br, politics_world, politics_latam, controversies, conflicts, disasters
8. Sugere a regiao mais adequada: Portugal, Brasil, America Latina, Internacional, Misto

IDIOMA: Portugues de Portugal

RESPONDE APENAS EM JSON (sem markdown):
{{
    "title": "titulo informativo e neutro",
    "content": "conteudo factual em portugues (3-5 paragrafos)",
    "summary": "resumo dos factos principais (2-3 frases)",
    "tags": ["tag1", "tag2", "tag3"],
    "suggested_category": "categoria",
    "suggested_region": "regiao"
}}"""

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        },
        timeout=60
    )

    if response.status_code != 200:
        raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

    result = response.json()
    content_json = json.loads(result["choices"][0]["message"]["content"])

    return content_json


@retry(
    max_attempts=MAX_API_RETRIES,
    delay=2.0,
    backoff=2.0,
    exceptions=(requests.exceptions.RequestException, requests.exceptions.Timeout)
)
def rewrite_with_anthropic(title: str, content: str, source_name: str, category: str) -> dict:
    """Reescreve noticia usando Claude."""
    if not ANTHROPIC_API_KEY:
        raise Exception("ANTHROPIC_API_KEY nao configurada")

    category_label = CATEGORY_LABELS.get(category, category)

    prompt = f"""Es um jornalista imparcial e rigoroso.
Reescreve a noticia abaixo em formato de artigo informativo.

NOTICIA ORIGINAL:
Titulo: {title}
Fonte: {source_name}
Categoria: {category_label}
Conteudo: {content[:2000]}

REGRAS DE NEUTRALIDADE (OBRIGATORIO):
- Seres COMPLETAMENTE NEUTRO e IMPARCIAL politicamente
- Reportar APENAS os factos, sem opinioes ou interpretacoes
- NAO usar linguagem sensacionalista ou exagerada
- NAO favorecer nenhum partido, politico ou ideologia
- NAO usar adjetivos valorativos (bom, mau, excelente, terrivel)
- Apresentar todos os lados da questao quando relevante
- Usar verbos neutros: "afirmou", "declarou", "referiu" (nao "atacou", "destruiu")
- Citar fontes e atribuir declaracoes corretamente

INSTRUCOES DE FORMATO:
1. Reescreve com as tuas proprias palavras (nao copies)
2. Mantem TODOS os factos, dados e numeros importantes
3. Tom serio, profissional e factual
4. Estrutura clara com 3-5 paragrafos
5. Titulo informativo e directo (sem sensacionalismo)
6. Resumo factual de 2-3 frases
7. Sugere a categoria mais adequada: politics_pt, politics_br, politics_world, politics_latam, controversies, conflicts, disasters
8. Sugere a regiao mais adequada: Portugal, Brasil, America Latina, Internacional, Misto

IDIOMA: Portugues de Portugal

RESPONDE APENAS EM JSON (sem markdown):
{{
    "title": "titulo informativo e neutro",
    "content": "conteudo factual em portugues (3-5 paragrafos)",
    "summary": "resumo dos factos principais (2-3 frases)",
    "tags": ["tag1", "tag2", "tag3"],
    "suggested_category": "categoria",
    "suggested_region": "regiao"
}}"""

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        },
        json={
            "model": "claude-3-haiku-20240307",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=60
    )

    if response.status_code != 200:
        raise Exception(f"Anthropic API error: {response.status_code} - {response.text}")

    result = response.json()
    text = result["content"][0]["text"]

    # Extrair JSON da resposta
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        json_str = json_match.group()
        json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', json_str)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            def fix_string_newlines(m):
                s = m.group(0)
                s = s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                return s
            json_str = re.sub(r'"[^"]*"', fix_string_newlines, json_str)
            return json.loads(json_str)
    else:
        raise Exception("Nao foi possivel extrair JSON da resposta")


def rewrite_news(title: str, content: str, source_name: str, category: str) -> dict:
    """Reescreve noticia usando o provedor de IA configurado."""
    if AI_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
        return rewrite_with_anthropic(title, content, source_name, category)
    elif OPENAI_API_KEY:
        return rewrite_with_openai(title, content, source_name, category)
    else:
        raise Exception("Nenhuma API de IA configurada. Configure OPENAI_API_KEY ou ANTHROPIC_API_KEY")


def process_single_news(news: dict) -> bool:
    """Processa uma unica noticia."""
    try:
        logger.info(f"Processando: {news['title'][:50]}...")

        # Combinar titulo e descricao para contexto
        full_content = f"{news.get('description', '')} {news.get('content', '')}"

        # Reescrever com IA
        rewritten = rewrite_news(
            title=news["title"],
            content=full_content,
            source_name=news["source_name"],
            category=news["category"]
        )

        # Extrair imagem
        image_url = extract_image_from_content(
            news.get("content", ""),
            news["link"]
        )

        # Determinar regiao e categoria finais
        original_region = news.get("region") or news.get("country") or "Internacional"
        final_region = rewritten.get("suggested_region", original_region)
        final_category = rewritten.get("suggested_category", news["category"])

        # Salvar post do blog
        post_id = save_blog_post(
            news_id=news["id"],
            title=rewritten["title"],
            content=rewritten["content"],
            summary=rewritten["summary"],
            image_url=image_url,
            source_url=news["link"],
            source_name=news["source_name"],
            category=final_category,
            region=final_region,
            tags=rewritten.get("tags", []),
            priority_score=news.get("priority_score", 0)
        )

        # Atualizar fila
        update_queue_status(news["queue_id"], "completed")
        logger.info(f"  Post #{post_id} criado com sucesso")
        return True

    except RetryError as e:
        error_msg = f"Falhou apos {MAX_API_RETRIES} tentativas: {e.last_exception}"
        logger.error(f"  Erro: {error_msg[:80]}")
        update_queue_status(news["queue_id"], "error", error_msg)
        return False
    except Exception as e:
        logger.error(f"  Erro: {str(e)[:80]}")
        update_queue_status(news["queue_id"], "error", str(e))
        return False


def queue_high_priority_news(min_score: float = 2.0, limit: int = 20, portugal_boost: bool = True):
    """
    Adiciona noticias de alta prioridade a fila de processamento.
    Da prioridade a noticias de Portugal.
    """
    conn = get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Query que prioriza Portugal
        cursor.execute("""
            SELECT n.id, n.priority_score, s.country
            FROM news n
            JOIN sources s ON n.source_id = s.id
            LEFT JOIN processing_queue pq ON n.id = pq.news_id
            WHERE n.priority_score >= %s
            AND pq.id IS NULL
            ORDER BY
                CASE WHEN s.country = 'Portugal' THEN 0 ELSE 1 END,
                n.priority_score DESC
            LIMIT %s
        """, (min_score, limit))

        rows = cursor.fetchall()
    finally:
        conn.close()

    count = 0
    portugal_count = 0
    for row in rows:
        news_id = row["id"]
        if add_to_processing_queue(news_id):
            count += 1
            if row["country"] == "Portugal":
                portugal_count += 1

    print(f"[Queue] {count} noticias adicionadas ({portugal_count} de Portugal)")
    return count


def process_queue(limit: int = 10):
    """Processa noticias da fila."""
    logger.info("=" * 50)
    logger.info("PROCESSAMENTO DE NOTICIAS PARA BLOG")
    logger.info("=" * 50)

    # Verificar API
    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        logger.error("ERRO: Configure OPENAI_API_KEY ou ANTHROPIC_API_KEY")
        return

    provider = "Anthropic" if AI_PROVIDER == "anthropic" else "OpenAI"
    logger.info(f"Usando: {provider}")

    # Pegar noticias pendentes (ja priorizadas por Portugal)
    pending = get_pending_news(limit)
    logger.info(f"Noticias na fila: {len(pending)}")

    success = 0
    errors = 0

    for news in pending:
        region = news.get("region") or news.get("country") or "?"
        logger.info(f"[{region}] {news['title'][:40]}...")

        if process_single_news(news):
            success += 1
        else:
            errors += 1

    logger.info("=" * 50)
    logger.info(f"Concluido: {success} sucesso, {errors} erros")
    logger.info("=" * 50)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Processador de noticias para blog")
    subparsers = parser.add_subparsers(dest="command")

    # Init
    subparsers.add_parser("init", help="Inicializa tabelas de blog")

    # Queue
    queue_parser = subparsers.add_parser("queue", help="Adiciona noticias a fila")
    queue_parser.add_argument("--min-score", "-s", type=float, default=2.0)
    queue_parser.add_argument("--limit", "-l", type=int, default=20)

    # Process
    process_parser = subparsers.add_parser("process", help="Processa fila")
    process_parser.add_argument("--limit", "-l", type=int, default=10)

    # Stats
    subparsers.add_parser("stats", help="Estatisticas")

    args = parser.parse_args()

    if args.command == "init":
        from database_blog import init_blog_tables
        init_blog_tables()

    elif args.command == "queue":
        queue_high_priority_news(args.min_score, args.limit)

    elif args.command == "process":
        process_queue(args.limit)

    elif args.command == "stats":
        stats = get_blog_stats()
        print("\nEstatisticas do Blog:")
        print(f"  Total de posts: {stats['total_posts']}")
        print(f"  Rascunhos: {stats['drafts']}")
        print(f"  Publicados: {stats['published']}")
        print(f"  Pendentes: {stats['pending_processing']}")
        print(f"  Processados: {stats['processed']}")
        print(f"  Erros: {stats['errors']}")

        if stats.get("by_region"):
            print("\nPor regiao:")
            for region, count in stats["by_region"].items():
                print(f"  {region}: {count}")

        if stats.get("by_category"):
            print("\nPor categoria:")
            for cat, count in stats["by_category"].items():
                label = CATEGORY_LABELS.get(cat, cat)
                print(f"  {label}: {count}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
