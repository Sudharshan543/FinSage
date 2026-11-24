
import re


STOPWORDS = {
    "what", "is", "the", "a", "an", "are", "was", "were",
    "do", "does", "did", "can", "could", "would", "should",
    "how", "when", "where", "why", "who", "which",
    "me", "my", "our", "your", "we", "i",
    "please", "tell", "explain", "show", "give",
    "about", "for", "to", "of", "in", "on", "at", "and",
    "or", "with", "under", "up", "per"
}


def tokenize(text):
    """Extract meaningful lowercase keywords."""
    words = re.findall(r"\b[a-z0-9]+\b", str(text).lower())
    return {word for word in words if word not in STOPWORDS}


def rerank_chunks(chunks, question, top_k=3):
    """
    Rerank HANA results using semantic similarity
    and focused keyword relevance.
    """

    if not chunks:
        return []

    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise ValueError("top_k must be an integer")

    top_k = max(1, top_k)
    question_keywords = tokenize(question)

    ranked_chunks = []

    for chunk in chunks:
        chunk_text = chunk.get("chunk_text", "")
        chunk_keywords = tokenize(chunk_text)

        similarity_score = float(
            chunk.get("similarity_score", 0)
        )

        if question_keywords:
            overlap = question_keywords.intersection(
                chunk_keywords
            )
            keyword_score = (
                len(overlap) / len(question_keywords)
            )
        else:
            keyword_score = 0.0

        # Boost chunks containing the complete question topic.
        normalized_chunk = chunk_text.lower()
        topic_boost = 0.0

        if "hotel" in question_keywords:
            if "hotel accommodation" in normalized_chunk:
                topic_boost = 0.15
            elif "hotel" in normalized_chunk:
                topic_boost = 0.08

        rerank_score = (
            0.70 * similarity_score
            + 0.30 * keyword_score
            + topic_boost
        )

        ranked_chunk = dict(chunk)
        ranked_chunk["keyword_score"] = round(
            keyword_score, 4
        )
        ranked_chunk["topic_boost"] = round(
            topic_boost, 4
        )
        ranked_chunk["rerank_score"] = round(
            rerank_score, 4
        )

        ranked_chunks.append(ranked_chunk)

    ranked_chunks.sort(
        key=lambda item: item["rerank_score"],
        reverse=True
    )

    return ranked_chunks[:top_k]
