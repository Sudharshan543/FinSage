
from app.db import get_hana_connection


HOTEL_REFERENCE_LIMIT = 5000
MEAL_REFERENCE_LIMIT = 1200


def check_expense_compliance():
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
            NIGHTS,
            DAYS,
            RECEIPT_STATUS
        FROM DBADMIN.FINSAGE_EXPENSE_EXCEPTIONS
        ORDER BY CREATED_AT DESC
    """

    try:
        cursor.execute(sql)
        rows = cursor.fetchall()

        results = []

        for row in rows:
            amount = float(row[4]) if row[4] is not None else 0.0

            category = (row[3] or "").strip().upper()
            currency = (row[5] or "").strip().upper()
            region = (row[7] or "").strip().upper()
            reason = (row[9] or "").strip()
            nights = row[12]
            days = row[13]
            receipt_status = (row[14] or "UNKNOWN").strip().upper()

            issues = []
            verification_notes = []
            verification_complete = True

            supported_region = region in ("IN", "INDIA")
            supported_currency = currency == "INR"

            if category in ("HOTEL", "MEAL", "MEALS"):
                if not supported_region or not supported_currency:
                    verification_complete = False
                    verification_notes.append(
                        "No approved reference limit is configured for "
                        f"region {row[7]} and currency {row[5]}; "
                        "this claim was not evaluated against a limit."
                    )
                elif category == "HOTEL":
                    if nights is None or int(nights) <= 0:
                        verification_complete = False
                        verification_notes.append(
                            "Per-night compliance cannot be evaluated "
                            "because the number of nights is missing or invalid."
                        )
                    else:
                        per_night_amount = amount / int(nights)
                        if per_night_amount > HOTEL_REFERENCE_LIMIT:
                            issues.append(
                                "Hotel amount per night exceeds the "
                                "INR 5,000 reference limit."
                            )
                elif category in ("MEAL", "MEALS"):
                    if days is None or int(days) <= 0:
                        verification_complete = False
                        verification_notes.append(
                            "Per-day compliance cannot be evaluated "
                            "because the number of days is missing or invalid."
                        )
                    else:
                        per_day_amount = amount / int(days)
                        if per_day_amount > MEAL_REFERENCE_LIMIT:
                            issues.append(
                                "Meal amount per day exceeds the "
                                "INR 1,200 reference limit."
                            )
            else:
                verification_complete = False
                verification_notes.append(
                    f"No automated compliance rule is configured for "
                    f"expense category {category or 'UNKNOWN'}."
                )

            if receipt_status == "MISSING":
                issues.append(
                    "The submitter reported that supporting documentation is missing."
                )
            elif receipt_status == "SUBMITTED":
                verification_complete = False
                verification_notes.append(
                    "Receipt submission is user-reported; the document "
                    "has not been independently inspected."
                )
            else:
                verification_complete = False
                verification_notes.append(
                    "Receipt status is unknown; no independent document check "
                    "was performed."
                )

            # Check policy reference.
            if not row[8] or not str(row[8]).strip():
                issues.append("Policy reference is missing.")

            # Preserve the original recorded reason.
            if reason:
                verification_notes.append(
                    "Recorded exception reason: " + reason
                )

            results.append({
                "exception_id": row[0],
                "employee_id": row[1],
                "employee_name": row[2],
                "expense_category": row[3],
                "expense_amount": amount,
                "currency": currency,
                "expense_date": str(row[6]) if row[6] else None,
                "region": row[7],
                "policy_reference": row[8],
                "compliance_issues": issues,
                "severity": row[10],
                "severity_source": "USER_REPORTED",
                "approval_status": row[11],
                "nights": nights,
                "days": days,
                "receipt_status": receipt_status,
                "compliance_status": (
                    "REQUIRES_REVIEW"
                    if issues
                    else (
                        "NO_CONFIGURED_ISSUE"
                        if verification_complete
                        else "NOT_VERIFIABLE"
                    )
                ),
                "verification_notes": verification_notes
            })

        return results

    finally:
        cursor.close()
        connection.close()


def generate_compliance_report():
    records = check_expense_compliance()

    print("FINSAGE EXPENSE COMPLIANCE REPORT")
    print("Total exceptions:", len(records))

    for record in records:
        print("\nException ID:", record["exception_id"])
        print("Employee:", record["employee_name"])
        print("Category:", record["expense_category"])
        print(
            "Amount:",
            record["currency"],
            record["expense_amount"]
        )

        print("Compliance issues:")
        if record["compliance_issues"]:
            for issue in record["compliance_issues"]:
                print("-", issue)
        else:
            print("No rule-based issues identified.")

        print("Verification notes:")
        if record["verification_notes"]:
            for note in record["verification_notes"]:
                print("-", note)
        else:
            print("No additional verification notes.")

        print("Severity:", record["severity"])
        print("Approval status:", record["approval_status"])


if __name__ == "__main__":
    generate_compliance_report()
