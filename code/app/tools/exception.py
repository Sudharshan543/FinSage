
from app.db import get_hana_connection
from uuid import uuid4


def log_expense_exception(
    employee_id,
    employee_name,
    expense_category,
    expense_amount,
    currency,
    expense_date,
    region,
    policy_reference,
    exception_reason,
    severity,
    confirmed=False,
    nights=None,
    days=None,
    receipt_status="UNKNOWN"
):
    if not confirmed:
        return {
            "success": False,
            "message": "Confirmation required before logging exception."
        }

    if expense_amount <= 0:
        return {
            "success": False,
            "message": "Expense amount must be greater than zero."
        }

    if not exception_reason or not exception_reason.strip():
        return {
            "success": False,
            "message": "Exception reason is required."
        }

    exception_id = f"EXC-{uuid4().hex[:8].upper()}"

    connection = get_hana_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO DBADMIN.FINSAGE_EXPENSE_EXCEPTIONS (
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
                NIGHTS,
                DAYS,
                RECEIPT_STATUS
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exception_id,
                employee_id,
                employee_name,
                expense_category,
                expense_amount,
                currency,
                expense_date,
                region,
                policy_reference,
                exception_reason.strip(),
                severity,
                "PENDING",
                nights,
                days,
                receipt_status
            )
        )

        connection.commit()

        return {
            "success": True,
            "message": "Expense exception logged successfully.",
            "exception_id": exception_id,
            "approval_status": "PENDING"
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    print("FINSAGE EXPENSE ACTION TEST")

    result = log_expense_exception(
        employee_id="EMP004",
        employee_name="Sample Employee",
        expense_category="HOTEL",
        expense_amount=6500,
        currency="INR",
        expense_date="2026-11-20",
        region="IN",
        policy_reference="TRAVEL-POL-001",
        exception_reason="Hotel expense exceeds policy limit.",
        severity="HIGH",
        confirmed=False
    )

    print(result)
    print("\nNo database record was created because confirmation was not provided.")
