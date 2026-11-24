
from app.db import get_hana_connection


def retrieve_chunks(
    category=None,
    doc_type=None,
    region=None,
    keyword=None,
    user_access_level="INTERNAL",
    as_of_date=None,
    top_k=3
):
    connection = get_hana_connection()
    cursor = connection.cursor()

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
    """

    params = [user_access_level]

    if category:
        sql += " AND CATEGORY = ?"
        params.append(category)

    if doc_type:
        sql += " AND DOC_TYPE = ?"
        params.append(doc_type)

    if region:
        sql += " AND REGION = ?"
        params.append(region)

    if keyword:
        sql += " AND LOWER(CHUNK_TEXT) LIKE ?"
        params.append(f"%{keyword.lower()}%")

    if as_of_date:
        sql += " AND EFFECTIVE_DATE <= ?"
        params.append(as_of_date)

    sql += """
        ORDER BY EFFECTIVE_DATE DESC
        LIMIT ?
    """

    params.append(top_k)

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
                "chunk_text": row[7]
            })

        return results

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    results = retrieve_chunks(
        category="TRAVEL_EXPENSE",
        doc_type="POLICY",
        region="India",
        keyword="hotel",
        user_access_level="INTERNAL",
        as_of_date="2026-11-20",
        top_k=3
    )

    print("FINSAGE ADVANCED POLICY RETRIEVAL")
    print("Matching chunks:", len(results))

    for result in results:
        print("\nChunk ID:", result["chunk_id"])
        print("Document type:", result["doc_type"])
        print("Source:", result["source_name"])
        print("Category:", result["category"])
        print("Region:", result["region"])
        print("Effective date:", result["effective_date"])
        print("Access level:", result["access_level"])
        print("Text:", result["chunk_text"])
