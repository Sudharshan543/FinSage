import argparse
import re
from pathlib import Path

from app.chunking import chunk_text
from app.db import get_hana_connection
from app.embeddings import generate_embedding


DOCUMENTS_ROOT = (
    Path(__file__).resolve().parent.parent / "data" / "documents"
)

FOLDER_METADATA = {
    "policies": {
        "doc_type": "POLICY",
        "effective_date": "2026-11-01"
    },
    "invoices": {
        "doc_type": "INVOICE",
        "effective_date": "2026-11-15"
    },
    "tax": {
        "doc_type": "TAX",
        "effective_date": "2026-11-01"
    }
}

CATEGORY_MAPPING = {
    "tax": "TAX_COMPLIANCE",
    "travel": "TRAVEL_EXPENSE",
    "expense": "TRAVEL_EXPENSE",
    "reimbursement": "TRAVEL_EXPENSE",
    "accounts_payable": "ACCOUNTS_PAYABLE",
    "invoice": "ACCOUNTS_PAYABLE",
    "purchase_order": "PROCUREMENT",
    "procurement": "PROCUREMENT",
    "vendor": "VENDOR_MANAGEMENT",
    "supplier": "VENDOR_MANAGEMENT"
}


def get_document_category(file_name):
    """Determine category using the document filename."""

    name = file_name.lower()

    for keyword, category in CATEGORY_MAPPING.items():
        if keyword in name:
            return category

    return "GENERAL_FINANCE"


def extract_document_region(text, doc_type):
    """
    Extract region from document contents.

    Priority:
    1. Explicit Region declaration.
    2. Strong India-specific invoice/tax indicators.
    3. UNKNOWN when region cannot be established.

    Never guess USA or another country.
    """

    # Check for an explicit Region declaration.
    region_match = re.search(
        r"(?im)^\s*\*{0,2}Region\s*:\s*\*{0,2}\s*"
        r"([A-Za-z][A-Za-z\s-]*?)\s*\*{0,2}\s*$",
        text
    )

    if region_match:
        region = region_match.group(1).strip()
        return region.upper() if region else "UNKNOWN"

    text_upper = text.upper()

    # Strong indicators of Indian invoices and tax documents.
    has_indian_tax_id = bool(
        re.search(r"\bGSTIN\b", text_upper)
    )

    has_inr_currency = bool(
        re.search(r"\bINR\b|₹", text_upper)
    )

    has_indian_location = bool(
        re.search(
            r"\bINDIA\b|"
            r"\bKARNATAKA\b|"
            r"\bBENGALURU\b|"
            r"\bMUMBAI\b|"
            r"\bNEW DELHI\b",
            text_upper
        )
    )

    if doc_type in ("INVOICE", "TAX"):
        if has_indian_tax_id and (
            has_inr_currency or has_indian_location
        ):
            return "INDIA"

        if has_indian_tax_id and doc_type == "TAX":
            return "INDIA"

    return "UNKNOWN"


def process_documents(file_name=None):
    """Read policy, invoice and tax documents and create chunks."""

    processed_documents = []
    matched_file = False

    for folder_name, metadata in FOLDER_METADATA.items():

        folder_path = DOCUMENTS_ROOT / folder_name

        if not folder_path.exists():
            print(f"Folder not found, skipping: {folder_path}")
            continue

        for file_path in sorted(folder_path.glob("*.txt")):
            if file_name and file_path.name != file_name:
                continue

            matched_file = True

            text = file_path.read_text(
                encoding="utf-8"
            ).strip()

            if not text:
                print(f"Skipping empty file: {file_path.name}")
                continue

            category = get_document_category(file_path.stem)

            region = extract_document_region(
                text,
                metadata["doc_type"]
            )

            chunks = chunk_text(
                text,
                chunk_size=150,
                overlap=30
            )

            print(
                f"Processing {file_path.name} "
                f"[{metadata['doc_type']}/{category}/{region}]"
            )

            for index, chunk in enumerate(chunks, start=1):

                processed_documents.append({
                    "chunk_id": f"{file_path.stem}-{index}",
                    "doc_type": metadata["doc_type"],
                    "category": category,
                    "region": region,
                    "source_name": file_path.name,
                    "effective_date": metadata["effective_date"],
                    "access_level": "INTERNAL",
                    "chunk_text": chunk
                })

    if file_name and not matched_file:
        raise FileNotFoundError(
            f"Document not found in configured source folders: {file_name}"
        )

    return processed_documents


def save_chunks_to_hana(documents):

    if not documents:
        print("No documents found. Nothing to ingest.")
        return

    connection = get_hana_connection()
    cursor = connection.cursor()

    upsert_sql = """
        UPSERT DBADMIN.FINSAGE_DOCUMENT_CHUNKS
        (CHUNK_ID, DOC_TYPE, CATEGORY, REGION, SOURCE_NAME,
         EFFECTIVE_DATE, ACCESS_LEVEL, CHUNK_TEXT, EMBEDDING)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, TO_REAL_VECTOR(?))
        WITH PRIMARY KEY
    """

    try:
        for index, document in enumerate(documents, start=1):

            print(
                f"Generating embedding {index}/{len(documents)}: "
                f"{document['source_name']} "
                f"[{document['doc_type']}/"
                f"{document['category']}/"
                f"{document['region']}]"
            )

            embedding = generate_embedding(
                document["chunk_text"]
            )

            embedding_string = (
                "[" + ",".join(str(value) for value in embedding) + "]"
            )

            cursor.execute(
                upsert_sql,
                (
                    document["chunk_id"],
                    document["doc_type"],
                    document["category"],
                    document["region"],
                    document["source_name"],
                    document["effective_date"],
                    document["access_level"],
                    document["chunk_text"],
                    embedding_string
                )
            )

        connection.commit()

        print(
            f"\nSuccessfully inserted or updated "
            f"{len(documents)} document chunks "
            f"with Gemini embeddings in SAP HANA!"
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Ingest FinSage finance documents into SAP HANA."
    )
    parser.add_argument(
        "--file",
        help="Process only this document filename from the configured folders."
    )
    arguments = parser.parse_args()

    documents = process_documents(file_name=arguments.file)

    print("\nFINSAGE DOCUMENT INGESTION")
    print("==========================")

    for folder_name, metadata in FOLDER_METADATA.items():

        count = sum(
            1 for document in documents
            if document["doc_type"] == metadata["doc_type"]
        )

        print(f"{metadata['doc_type']} chunks: {count}")

    region_counts = {}

    for document in documents:
        region = document["region"]
        region_counts[region] = region_counts.get(region, 0) + 1

    print("\nREGION DISTRIBUTION")

    for region, count in sorted(region_counts.items()):
        print(f"{region}: {count} chunks")

    print("\nTotal chunks found:", len(documents))

    save_chunks_to_hana(documents)