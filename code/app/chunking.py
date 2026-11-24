def chunk_text(text, chunk_size=150, overlap=30):
    """
    Split document text into overlapping word-based chunks.
    Uses 150 words per chunk with 30 words of overlap.
    """

    words = text.split()

    if overlap >= chunk_size:
        raise ValueError("Overlap must be smaller than chunk size.")

    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]

        chunk = " ".join(chunk_words).strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(words):
            break

        start = end - overlap

    return chunks