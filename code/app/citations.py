
def format_citations(retrieved_chunks):
    citations = []

    for index, chunk in enumerate(retrieved_chunks, start=1):
        text = chunk.get("chunk_text", "")

        snippet = text[:300]

        citation = {
            "citation_number": index,
            "chunk_id": chunk.get("chunk_id"),
            "source_name": chunk.get("source_name"),
            "document_type": chunk.get("doc_type"),
            "effective_date": chunk.get("effective_date"),
            "snippet": snippet
        }

        citations.append(citation)

    return citations


if __name__ == "__main__":
    sample_chunks = [
        {
            "chunk_id": "travel_expense_policy-1",
            "source_name": "travel_expense_policy.txt",
            "doc_type": "POLICY",
            "effective_date": "2026-11-01",
            "chunk_text": (
                "Employees may claim hotel accommodation "
                "expenses up to INR 5,000 per night."
            )
        }
    ]

    citations = format_citations(sample_chunks)

    print("FINSAGE EVIDENCE CITATIONS")

    for citation in citations:
        print("\nCitation:", citation["citation_number"])
        print("Source:", citation["source_name"])
        print("Chunk ID:", citation["chunk_id"])
        print("Effective date:", citation["effective_date"])
        print("Evidence:", citation["snippet"])
