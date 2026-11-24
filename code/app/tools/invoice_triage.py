
from app.db import get_hana_connection


def check_duplicate_invoices():
    connection = get_hana_connection()
    cursor = connection.cursor()

    sql = """
        SELECT
            VENDOR_ID,
            INVOICE_NUMBER,
            COUNT(*) AS DUPLICATE_COUNT
        FROM DBADMIN.FINSAGE_INVOICES
        GROUP BY VENDOR_ID, INVOICE_NUMBER
        HAVING COUNT(*) > 1
    """

    try:
        cursor.execute(sql)
        rows = cursor.fetchall()

        return [
            {
                "vendor_id": row[0],
                "invoice_number": row[1],
                "duplicate_count": row[2],
                "risk": "DUPLICATE_INVOICE"
            }
            for row in rows
        ]

    finally:
        cursor.close()
        connection.close()


def check_missing_po_numbers():
    connection = get_hana_connection()
    cursor = connection.cursor()

    sql = """
        SELECT
            INVOICE_ID,
            VENDOR_NAME,
            INVOICE_NUMBER,
            INVOICE_AMOUNT,
            CURRENCY
        FROM DBADMIN.FINSAGE_INVOICES
        WHERE PO_NUMBER IS NULL
           OR TRIM(PO_NUMBER) = ''
    """

    try:
        cursor.execute(sql)
        rows = cursor.fetchall()

        return [
            {
                "invoice_id": row[0],
                "vendor_name": row[1],
                "invoice_number": row[2],
                "invoice_amount": (
                    float(row[3]) if row[3] is not None else None
                ),
                "currency": row[4],
                "risk": "MISSING_PO_NUMBER"
            }
            for row in rows
        ]

    finally:
        cursor.close()
        connection.close()


def check_po_amount_mismatches():
    """Identify invoices whose amount exceeds the approved PO amount."""

    connection = get_hana_connection()
    cursor = connection.cursor()

    sql = """
        SELECT
            INVOICE_ID,
            VENDOR_NAME,
            INVOICE_NUMBER,
            PO_NUMBER,
            INVOICE_AMOUNT,
            PO_APPROVED_AMOUNT,
            INVOICE_AMOUNT - PO_APPROVED_AMOUNT AS DIFFERENCE,
            CURRENCY
        FROM DBADMIN.FINSAGE_INVOICES
        WHERE PO_APPROVED_AMOUNT IS NOT NULL
          AND INVOICE_AMOUNT > PO_APPROVED_AMOUNT
        ORDER BY DIFFERENCE DESC
    """

    try:
        cursor.execute(sql)
        rows = cursor.fetchall()

        return [
            {
                "invoice_id": row[0],
                "vendor_name": row[1],
                "invoice_number": row[2],
                "po_number": row[3],
                "invoice_amount": float(row[4]),
                "po_approved_amount": float(row[5]),
                "difference": float(row[6]),
                "currency": row[7],
                "risk": "PO_AMOUNT_MISMATCH"
            }
            for row in rows
        ]

    finally:
        cursor.close()
        connection.close()


def check_invoice_review_status():
    connection = get_hana_connection()
    cursor = connection.cursor()

    sql = """
        SELECT
            INVOICE_ID,
            VENDOR_NAME,
            INVOICE_NUMBER,
            INVOICE_AMOUNT,
            TRIAGE_STATUS,
            FLAG_REASON
        FROM DBADMIN.FINSAGE_INVOICES
        WHERE UPPER(TRIM(TRIAGE_STATUS)) IN (
            'REQUIRES_REVIEW',
            'PENDING_REVIEW',
            'FLAGGED'
        )
        ORDER BY CREATED_AT DESC
    """

    try:
        cursor.execute(sql)
        rows = cursor.fetchall()

        return [
            {
                "invoice_id": row[0],
                "vendor_name": row[1],
                "invoice_number": row[2],
                "invoice_amount": (
                    float(row[3]) if row[3] is not None else None
                ),
                "triage_status": row[4],
                "flag_reason": row[5]
            }
            for row in rows
        ]

    finally:
        cursor.close()
        connection.close()


def run_invoice_triage():
    print("FINSAGE INVOICE TRIAGE REPORT")

    duplicates = check_duplicate_invoices()
    missing_po = check_missing_po_numbers()
    po_mismatches = check_po_amount_mismatches()
    review_invoices = check_invoice_review_status()

    print("\n1. DUPLICATE INVOICES")
    print("Found:", len(duplicates))

    for item in duplicates:
        print(item)

    print("\n2. MISSING PURCHASE ORDER NUMBERS")
    print("Found:", len(missing_po))

    for item in missing_po:
        print(item)

    print("\n3. PURCHASE ORDER AMOUNT MISMATCHES")
    print("Found:", len(po_mismatches))

    for item in po_mismatches:
        print(item)

    print("\n4. INVOICES REQUIRING REVIEW")
    print("Found:", len(review_invoices))

    for item in review_invoices:
        print(item)


if __name__ == "__main__":
    run_invoice_triage()
