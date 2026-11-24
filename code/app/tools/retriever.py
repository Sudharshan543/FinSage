
import json

from app.db import get_hana_connection
from app.embeddings import generate_embedding
from app.tools.reranker import rerank_chunks


def retrieve_finance_knowledge(
    question,
    category=None,
    doc_type=None,
    region="India",
    user_access_level="INTERNAL",
    as_of_date="2026-11-20",
    top_k=3,
    include_usage=False
):
    """
    Retrieve finance evidence using Gemini embeddings
    and SAP HANA cosine similarity, then rerank results.
    """

    if not question or not question.strip():
        if include_usage:
            return [], False
        return []

    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise ValueError("top_k must be an integer")

    top_k = max(1, min(top_k, 20))

    connection = get_hana_connection()
    cursor = connection.cursor()

    try:
        question_embedding = generate_embedding(question)
        embedding_string = json.dumps(question_embedding)
    except Exception as error:
        print(
            "FINSAGE_EMBEDDING_RETRIEVAL_FALLBACK:",
            type(error).__name__
        )
        results = retrieve_finance_knowledge_fallback(
            cursor=cursor,
            connection=connection,
            question=question,
            category=category,
            doc_type=doc_type,
            region=region,
            user_access_level=user_access_level,
            as_of_date=as_of_date,
            top_k=top_k
        )
        if include_usage:
            return results, False
        return results

    sql = f"""
        SELECT TOP {top_k}
            CHUNK_ID,
            DOC_TYPE,
            SOURCE_NAME,
            CATEGORY,
            REGION,
            EFFECTIVE_DATE,
            ACCESS_LEVEL,
            CHUNK_TEXT,
            COSINE_SIMILARITY(
                EMBEDDING,
                TO_REAL_VECTOR(?)
            ) AS SIMILARITY_SCORE
        FROM DBADMIN.FINSAGE_DOCUMENT_CHUNKS
        WHERE EMBEDDING IS NOT NULL
          AND ACCESS_LEVEL IN ('PUBLIC', ?)
          AND EFFECTIVE_DATE <= ?
    """

    params = [
        embedding_string,
        user_access_level,
        as_of_date
    ]

    if category:
        sql += " AND CATEGORY = ?"
        params.append(category)

    if doc_type:
        sql += " AND DOC_TYPE = ?"
        params.append(doc_type)

    if region:
        sql += " AND UPPER(REGION) = UPPER(?)"
        params.append(region)

    sql += """
        ORDER BY SIMILARITY_SCORE DESC
        WITH HINT (NO_VECTOR_INDEX)
    """

    try:
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

        results = []

        for row in rows:
            results.append({
                "chunk_id": row[0],
                "doc_type": row[1],
                "source_name": row[2],
                "category": row[3],
                "region": row[4],
                "effective_date": str(row[5]),
                "access_level": row[6],
                "chunk_text": str(row[7] or ""),
                "similarity_score": float(row[8])
            })

        # Rerank retrieved chunks before returning evidence.
        reranked_results = rerank_chunks(
            chunks=results,
            question=question,
            top_k=top_k
        )

        if include_usage:
            return reranked_results, True
        return reranked_results

    finally:
        cursor.close()
        connection.close()


def retrieve_finance_knowledge_fallback(
    cursor,
    connection,
    question,
    category=None,
    doc_type=None,
    region="India",
    user_access_level="INTERNAL",
    as_of_date="2026-11-20",
    top_k=3
):
    """Retrieve evidence from HANA text columns when Gemini embeddings fail."""

    sql = """
        SELECT
            CHUNK_ID,
            DOC_TYPE,
            SOURCE_NAME,
            CATEGORY,
            REGION,
            EFFECTIVE_DATE,
            ACCESS_LEVEL,
            CHUNK_TEXT
        FROM DBADMIN.FINSAGE_DOCUMENT_CHUNKS
        WHERE ACCESS_LEVEL IN ('PUBLIC', ?)
          AND EFFECTIVE_DATE <= ?
    """

    params = [user_access_level, as_of_date]

    if category:
        sql += " AND CATEGORY = ?"
        params.append(category)

    if doc_type:
        sql += " AND DOC_TYPE = ?"
        params.append(doc_type)

    if region:
        sql += " AND UPPER(REGION) = UPPER(?)"
        params.append(region)

    sql += " ORDER BY EFFECTIVE_DATE DESC LIMIT ?"
    params.append(max(top_k * 5, 20))

    try:
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        results = []

        for row in rows:
            chunk_text = str(row[7] or "")

            results.append({
                "chunk_id": row[0],
                "doc_type": row[1],
                "source_name": row[2],
                "category": row[3],
                "region": row[4],
                "effective_date": str(row[5]),
                "access_level": row[6],
                "chunk_text": chunk_text,
                "similarity_score": 0.0,
                "retrieval_method": "LEXICAL"
            })

        return rerank_chunks(
            chunks=results,
            question=question,
            top_k=top_k
        )

    finally:
        cursor.close()
        connection.close()


def format_evidence_citations(retrieved_chunks):
    """Format retrieved evidence with source citations."""

    citations = []

    for index, chunk in enumerate(retrieved_chunks, start=1):
        citation = {
            "citation_number": index,
            "chunk_id": chunk["chunk_id"],
            "source_name": chunk["source_name"],
            "effective_date": chunk["effective_date"],
            "snippet": chunk["chunk_text"][:300]
        }

        if chunk.get("retrieval_method") == "LEXICAL":
            citation["retrieval_method"] = "keyword fallback"
            citation["keyword_relevance"] = chunk.get(
                "keyword_relevance",
                chunk.get("keyword_score", 0.0)
            )
        else:
            citation["retrieval_method"] = "semantic"
            citation["similarity_score"] = round(
                chunk["similarity_score"], 4
            )

        citations.append(citation)

    return citations


if __name__ == "__main__":

    question = "What is the hotel expense limit?"

    print("FINSAGE SEMANTIC VECTOR SEARCH")
    print("Question:", question)

    chunks = retrieve_finance_knowledge(
        question=question,
        category="TRAVEL_EXPENSE",
        doc_type="POLICY",
        region="India",
        user_access_level="INTERNAL",
        as_of_date="2026-11-20",
        top_k=3
    )

    citations = format_evidence_citations(chunks)

    print("\nRetrieved chunks:", len(chunks))
    print("\nSEMANTIC SEARCH RESULTS")

    for citation in citations:
        print("\nCitation:", citation["citation_number"])
        print("Source:", citation["source_name"])
        print("Chunk ID:", citation["chunk_id"])
        print("Similarity score:", citation["similarity_score"])
        print("Effective date:", citation["effective_date"])
        print("Evidence:", citation["snippet"])
