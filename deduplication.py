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
