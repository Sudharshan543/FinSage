import re


STOP_WORDS = {
    "the", "is", "a", "an", "and", "or", "of", "to",
    "in", "on", "for", "with", "what", "which", "who",
    "how", "does", "do", "are", "was", "were", "under",
    "my", "our", "their", "this", "that", "me", "please"
}


def tokenize(text):
    """Extract meaningful keywords from text."""

    words = re.findall(r"\b[a-z0-9]+\b", str(text).lower())

    return {
        word for word in words
        if word not in STOP_WORDS and len(word) > 1
    }


def verify_evidence(
    chunks,
    min_similarity=0.72,
    min_keyword_relevance=0.10,
    question=None
):
    """
    Verify retrieved evidence using similarity and
    keyword relevance.

    Returns only chunks that pass both checks.
    """

    if not chunks:
        return {
            "verified": False,
            "reason": "No supporting evidence was retrieved.",
            "evidence": []
        }

    question_keywords = tokenize(question) if question else set()

    verified_chunks = []

    for chunk in chunks:

        retrieval_method = str(
            chunk.get("retrieval_method", "SEMANTIC")
        ).upper()
        similarity = float(
            chunk.get("similarity_score", 0)
        )

        if (
            retrieval_method != "LEXICAL"
            and similarity < min_similarity
        ):
            continue

        chunk_keywords = tokenize(
            chunk.get("chunk_text", "")
        )

        if question_keywords:

            overlap = question_keywords.intersection(
                chunk_keywords
            )

            relevance = (
                len(overlap) / len(question_keywords)
            )

            if relevance < min_keyword_relevance:
                continue

        else:
            relevance = 1.0

        verified_chunk = dict(chunk)

        verified_chunk["keyword_relevance"] = round(
            relevance, 4
        )

        verified_chunks.append(verified_chunk)

    if not verified_chunks:
        return {
            "verified": False,
            "reason": (
                "Retrieved evidence did not meet the "
                "similarity and relevance requirements."
            ),
            "evidence": []
        }

    return {
        "verified": True,
        "reason": (
            "Supporting evidence passed similarity "
            "and keyword relevance checks."
        ),
        "evidence": verified_chunks
    }