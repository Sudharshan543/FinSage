
from app.db import get_hana_connection


def summarize_invoices():
    connection = get_hana_connection()
    cursor = connection.cursor()

    sql = """
        SELECT
            PAYMENT_STATUS,
            CURRENCY,
            COUNT(*) AS INVOICE_COUNT,
            SUM(INVOICE_AMOUNT) AS TOTAL_AMOUNT
        FROM DBADMIN.FINSAGE_INVOICES
        GROUP BY PAYMENT_STATUS, CURRENCY
        ORDER BY PAYMENT_STATUS, CURRENCY
    """

    try:
        cursor.execute(sql)
        rows = cursor.fetchall()

        return [
            {
                "payment_status": row[0],
                "currency": row[1],
                "invoice_count": row[2],
                "total_amount": float(row[3] or 0)
            }
            for row in rows
        ]

    finally:
        cursor.close()
        connection.close()


def vendor_terms_lookup(vendor_name):
    connection = get_hana_connection()
    cursor = connection.cursor()

    sql = """
        SELECT
            VENDOR_NAME,
            VENDOR_ID,
            CURRENCY,
            COUNT(*) AS INVOICE_COUNT,
            SUM(INVOICE_AMOUNT) AS TOTAL_INVOICED
        FROM DBADMIN.FINSAGE_INVOICES
        WHERE LOWER(VENDOR_NAME) LIKE ?
        GROUP BY VENDOR_NAME, VENDOR_ID, CURRENCY
    """

    try:
        cursor.execute(sql, (f"%{vendor_name.lower()}%",))
        rows = cursor.fetchall()

        return [
            {
                "vendor_name": row[0],
                "vendor_id": row[1],
                "currency": row[2],
                "invoice_count": row[3],
                "total_invoiced": float(row[4] or 0)
            }
            for row in rows
        ]

    finally:
        cursor.close()
        connection.close()


def get_invoice_details(invoice_id):
    connection = get_hana_connection()
    cursor = connection.cursor()

    sql = """
        SELECT
            INVOICE_ID,
            VENDOR_NAME,
            VENDOR_ID,
            INVOICE_NUMBER,
            PO_NUMBER,
            PO_APPROVED_AMOUNT,
            INVOICE_DATE,
            DUE_DATE,
            CURRENCY,
            INVOICE_AMOUNT,
            TAX_AMOUNT,
            PAYMENT_STATUS,
            REGION,
            TRIAGE_STATUS,
            FLAG_REASON
        FROM DBADMIN.FINSAGE_INVOICES
        WHERE INVOICE_ID = ?
    """

    try:
        cursor.execute(sql, (invoice_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "invoice_id": row[0],
            "vendor_name": row[1],
            "vendor_id": row[2],
            "invoice_number": row[3],
            "po_number": row[4],
            "po_approved_amount": (
                float(row[5]) if row[5] is not None else None
            ),
            "invoice_date": str(row[6]) if row[6] else None,
            "due_date": str(row[7]) if row[7] else None,
            "currency": row[8],
            "invoice_amount": (
                float(row[9]) if row[9] is not None else None
            ),
            "tax_amount": (
                float(row[10]) if row[10] is not None else None
            ),
            "payment_status": row[11],
            "region": row[12],
            "triage_status": row[13],
            "flag_reason": row[14]
        }

    finally:
        cursor.close()
        connection.close()


def get_expense_exceptions():
    connection = get_hana_connection()
    cursor = connection.cursor()

    sql = """
        SELECT
            EXCEPTION_ID,
            EMPLOYEE_ID,
            EMPLOYEE_NAME,
            EXPENSE_CATEGORY,
            EXPENSE_AMOUNT,
            CURRENCY,
            EXPENSE_DATE,
            REGION,
            POLICY_REFERENCE,
            EXCEPTION_REASON,
            SEVERITY,
            APPROVAL_STATUS,
            CREATED_AT
        FROM DBADMIN.FINSAGE_EXPENSE_EXCEPTIONS
        ORDER BY CREATED_AT DESC
    """

    try:
        cursor.execute(sql)
        rows = cursor.fetchall()

        return [
            {
                "exception_id": row[0],
                "employee_id": row[1],
                "employee_name": row[2],
                "expense_category": row[3],
                "expense_amount": (
                    float(row[4]) if row[4] is not None else None
                ),
                "currency": row[5],
                "expense_date": str(row[6]) if row[6] else None,
                "region": row[7],
                "policy_reference": row[8],
                "exception_reason": row[9],
                "severity": row[10],
                "approval_status": row[11],
                "created_at": str(row[12]) if row[12] is not None else None
            }
            for row in rows
        ]

    finally:
        cursor.close()
        connection.close()


def get_invoice_flags(limit=100):
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    connection = get_hana_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                CASE_REF,
                INVOICE_ID,
                REASON,
                STATUS,
                FLAGGED_AT
            FROM DBADMIN.FINSAGE_INVOICE_FLAGS
            ORDER BY FLAGGED_AT DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()

        return [
            {
                "case_ref": row[0],
                "invoice_id": row[1],
                "reason": row[2],
                "status": row[3],
                "flagged_at": str(row[4]) if row[4] is not None else None
            }
            for row in rows
        ]
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":

    print("FINSAGE FINANCE TOOLS TEST")

    print("\n1. INVOICE SUMMARY")
    for invoice in summarize_invoices():
        print(invoice)

    print("\n2. VENDOR LOOKUP")
    print(vendor_terms_lookup("ABC Technologies"))

    print("\n3. INVOICE DETAILS")
    print(get_invoice_details("INV005"))

    print("\n4. EXPENSE EXCEPTIONS")
    for exception in get_expense_exceptions():
        print(exception)
