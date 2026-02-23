"""
Deduplication utilities for news articles
"""
import re
import hashlib


# Common stopwords (PT + EN)
STOPWORDS = {
    # Portuguese
    "a", "o", "e", "de", "da", "do", "em", "para", "com", "que", "um", "uma",
    "os", "as", "dos", "das", "no", "na", "nos", "nas", "por", "se", "ao",
    "aos", "ou", "seu", "sua", "seus", "suas", "mais", "como", "mas", "foi",
    "ser", "são", "tem", "ter", "já", "não", "isso", "este", "esta", "esse",
    "essa", "pelo", "pela", "pode", "sobre", "entre", "até", "após", "ainda",
    # English
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "this", "that",
    "these", "those", "it", "its", "as", "if", "when", "where", "which",
    "who", "whom", "whose", "what", "how", "than", "then", "so", "such",
    "no", "not", "only", "same", "into", "over", "after", "before", "between"
}


def normalize_text(text):
    """Normalize text for comparison"""
    if not text:
        return ""

    text = text.lower()

    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)

    # Remove punctuation
    text = re.sub(r'[^\w\s]', ' ', text)

    # Remove numbers
    text = re.sub(r'\b\d+\b', '', text)

    # Split and filter stopwords
    words = text.split()
    words = [w for w in words if w not in STOPWORDS and len(w) > 2]

    # Sort for consistency
    words.sort()

    return ' '.join(words)


def generate_title_hash(title):
    """Generate hash from normalized title"""
    normalized = normalize_text(title)
    if not normalized:
        return None
    return hashlib.md5(normalized.encode()).hexdigest()


def is_duplicate(title_hash, existing_hashes):
    """Check if title hash exists in set"""
    if not title_hash:
        return False
    return title_hash in existing_hashes


def calculate_similarity(text1, text2):
    """
    Calcula similaridade entre dois textos usando Jaccard.
    Retorna valor entre 0.0 e 1.0.
    """
    words1 = set(normalize_text(text1).split())
    words2 = set(normalize_text(text2).split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union)


def deduplicate_news_for_blog(news_list, threshold=0.5):
    """
    Remove noticias similares da lista, mantendo a de maior prioridade.
    Usado antes de processar para o blog.

    Args:
        news_list: Lista de noticias com campos 'title', 'description', 'priority_score'
        threshold: Limite de similaridade (0.5 = 50% similar = duplicata)

    Returns:
        Lista filtrada sem duplicatas
    """
    if not news_list:
        return []

    # Ordenar por prioridade (maior primeiro)
    sorted_news = sorted(news_list, key=lambda x: x.get('priority_score', 0), reverse=True)

    result = []
    seen_texts = []

    for news in sorted_news:
        title = news.get('title', '')
        desc = news.get('description', '')
        full_text = f"{title} {desc}"

        # Verificar se e similar a alguma noticia ja aceita
        is_similar = False
        for seen in seen_texts:
            if calculate_similarity(full_text, seen) >= threshold:
                is_similar = True
                break

        if not is_similar:
            result.append(news)
            seen_texts.append(full_text)

    return result


def group_similar_news(news_list, threshold=0.5):
    """
    Agrupa noticias similares.

    Returns:
        Lista de grupos, cada grupo e uma lista de noticias similares
    """
    if not news_list:
        return []

    groups = []
    used = set()

    for i, news1 in enumerate(news_list):
        if i in used:
            continue

        group = [news1]
        used.add(i)

        text1 = f"{news1.get('title', '')} {news1.get('description', '')}"

        for j, news2 in enumerate(news_list):
            if j in used or j <= i:
                continue

            text2 = f"{news2.get('title', '')} {news2.get('description', '')}"

            if calculate_similarity(text1, text2) >= threshold:
                group.append(news2)
                used.add(j)

        groups.append(group)

    return groups
