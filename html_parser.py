"""
Modulo de parsing HTML robusto usando BeautifulSoup.
"""
from typing import Optional, List
import re

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


def clean_html(text: str) -> str:
    """
    Remove tags HTML de um texto de forma segura.

    Args:
        text: Texto com possiveis tags HTML

    Returns:
        Texto limpo sem HTML
    """
    if not text:
        return ""

    if HAS_BS4:
        # Usar BeautifulSoup para parsing robusto
        soup = BeautifulSoup(text, 'html.parser')
        # Extrair texto, preservando espacos entre elementos
        clean = soup.get_text(separator=' ')
    else:
        # Fallback para regex (menos confiavel)
        clean = re.sub(r'<[^>]+>', ' ', text)

    # Normalizar espacos
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def extract_og_image(html: str) -> Optional[str]:
    """
    Extrai URL da imagem Open Graph de uma pagina HTML.

    Args:
        html: Conteudo HTML da pagina

    Returns:
        URL da imagem ou None
    """
    if not html:
        return None

    if HAS_BS4:
        soup = BeautifulSoup(html, 'html.parser')

        # Tentar og:image primeiro
        og_tag = soup.find('meta', property='og:image')
        if og_tag and og_tag.get('content'):
            return og_tag['content']

        # Fallback para twitter:image
        twitter_tag = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_tag and twitter_tag.get('content'):
            return twitter_tag['content']

        # Tentar variacoes (alguns sites usam name em vez de property)
        og_tag_alt = soup.find('meta', attrs={'name': 'og:image'})
        if og_tag_alt and og_tag_alt.get('content'):
            return og_tag_alt['content']
    else:
        # Fallback regex
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)

    return None


def extract_first_image(html: str) -> Optional[str]:
    """
    Extrai URL da primeira imagem encontrada no HTML.

    Args:
        html: Conteudo HTML

    Returns:
        URL da imagem ou None
    """
    if not html:
        return None

    if HAS_BS4:
        soup = BeautifulSoup(html, 'html.parser')
        img_tag = soup.find('img', src=True)
        if img_tag:
            return img_tag['src']
    else:
        # Fallback regex
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def extract_image_from_content(content: str, page_html: str = None) -> Optional[str]:
    """
    Extrai a melhor imagem disponivel do conteudo ou pagina.

    Ordem de prioridade:
    1. og:image da pagina
    2. twitter:image da pagina
    3. Primeira imagem no conteudo

    Args:
        content: Conteudo do artigo (pode conter HTML)
        page_html: HTML completo da pagina (opcional)

    Returns:
        URL da melhor imagem encontrada ou None
    """
    # Tentar extrair de meta tags primeiro (maior qualidade)
    if page_html:
        og_image = extract_og_image(page_html)
        if og_image:
            return og_image

    # Fallback para imagem no conteudo
    if content:
        return extract_first_image(content)

    return None


def extract_text_content(html: str, max_length: int = None) -> str:
    """
    Extrai conteudo textual principal de HTML.

    Args:
        html: Conteudo HTML
        max_length: Tamanho maximo do texto (opcional)

    Returns:
        Texto extraido
    """
    text = clean_html(html)

    if max_length and len(text) > max_length:
        # Cortar no ultimo espaco antes do limite
        text = text[:max_length].rsplit(' ', 1)[0] + '...'

    return text
