
from uuid import uuid4

from app.db import get_hana_connection


def flag_invoice(invoice_id, reason, confirmed=False):

    if not confirmed:
        return {
            "success": False,
            "message": "Confirmation required before flagging invoice.",
            "invoice_id": invoice_id
        }

    if not reason or not reason.strip():
        return {
            "success": False,
            "message": "A flag reason is required."
        }

    connection = get_hana_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT INVOICE_ID
            FROM DBADMIN.FINSAGE_INVOICES
            WHERE INVOICE_ID = ?
            """,
            (invoice_id,)
        )

        if cursor.fetchone() is None:
            return {
                "success": False,
                "message": "Invoice not found.",
                "invoice_id": invoice_id
            }

        cursor.execute(
            """
            UPDATE DBADMIN.FINSAGE_INVOICES
            SET TRIAGE_STATUS = ?,
                FLAG_REASON = ?
            WHERE INVOICE_ID = ?
            """,
            ("FLAGGED", reason.strip(), invoice_id)
        )

        case_ref = str(uuid4())
        cursor.execute(
            """
            INSERT INTO DBADMIN.FINSAGE_INVOICE_FLAGS (
                CASE_REF,
                INVOICE_ID,
                REASON,
                STATUS
            )
            VALUES (?, ?, ?, ?)
            """,
            (case_ref, invoice_id, reason.strip(), "FLAGGED")
        )

        connection.commit()

        return {
            "success": True,
            "message": "Invoice successfully flagged.",
            "invoice_id": invoice_id,
            "case_ref": case_ref,
            "status": "FLAGGED",
            "reason": reason.strip()
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":

    print("FINSAGE INVOICE ACTION TEST")

    # First test: confirmation is missing.
    result = flag_invoice(
        invoice_id="INV001",
        reason="Invoice requires compliance review.",
        confirmed=False
    )

    print("\nTest 1 - Without confirmation:")
    print(result)

    # Second test: show the confirmation request only.
    print("\nTest 2 - Confirmation required:")
    print("Ready to flag INV001?")
    print("Reason: Invoice requires compliance review.")
    print("No database update has been performed.")
