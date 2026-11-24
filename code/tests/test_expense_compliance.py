from datetime import date

from pydantic import ValidationError
import pytest

from app import expense_compliance
from app.models import LogExpenseExceptionRequest


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []
        self.closed = False

    def execute(self, query):
        self.executed.append(query)

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def compliance_row(
    *,
    amount=9000,
    currency="INR",
    region="IN",
    category="HOTEL",
    nights=2,
    days=None,
    receipt_status="SUBMITTED",
    reason="Hotel exception"
):
    return (
        "EXC-001",
        "EMP-001",
        "Test Employee",
        category,
        amount,
        currency,
        date(2026, 11, 23),
        region,
        "POLICY-001",
        reason,
        "MEDIUM",
        "PENDING",
        nights,
        days,
        receipt_status
    )


def run_report(monkeypatch, row):
    cursor = FakeCursor([row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        expense_compliance,
        "get_hana_connection",
        lambda: connection
    )

    report = expense_compliance.check_expense_compliance()

    assert "NIGHTS" in cursor.executed[0]
    assert "DAYS" in cursor.executed[0]
    assert "RECEIPT_STATUS" in cursor.executed[0]
    assert cursor.closed
    assert connection.closed
    return report[0]


def test_hotel_total_is_compared_per_night(monkeypatch):
    record = run_report(monkeypatch, compliance_row())

    assert record["compliance_issues"] == []
    assert record["compliance_status"] == "NOT_VERIFIABLE"
    assert record["nights"] == 2
    assert any("not been independently inspected" in note
               for note in record["verification_notes"])


def test_unsupported_usa_expense_is_not_checked_against_inr_limits(
    monkeypatch
):
    record = run_report(
        monkeypatch,
        compliance_row(
            amount=600,
            currency="USD",
            region="USA",
            nights=1,
            receipt_status="UNKNOWN"
        )
    )

    assert record["compliance_issues"] == []
    assert record["compliance_status"] == "NOT_VERIFIABLE"
    assert any("No approved reference limit" in note
               for note in record["verification_notes"])


def test_per_night_overage_and_missing_receipt_are_reported(monkeypatch):
    record = run_report(
        monkeypatch,
        compliance_row(
            amount=6000,
            nights=1,
            receipt_status="MISSING"
        )
    )

    assert len(record["compliance_issues"]) == 2
    assert record["compliance_status"] == "REQUIRES_REVIEW"
    assert record["severity_source"] == "USER_REPORTED"


def test_invalid_duration_is_not_treated_as_compliant(monkeypatch):
    record = run_report(
        monkeypatch,
        compliance_row(nights=-1)
    )

    assert record["compliance_status"] == "NOT_VERIFIABLE"
    assert any("missing or invalid" in note
               for note in record["verification_notes"])


def test_meal_limit_is_checked_per_day(monkeypatch):
    record = run_report(
        monkeypatch,
        compliance_row(
            amount=3000,
            category="MEAL",
            nights=None,
            days=2,
            receipt_status="MISSING"
        )
    )

    assert any("per day exceeds" in issue
               for issue in record["compliance_issues"])


def test_exception_request_requires_supported_region_currency_and_duration():
    valid_request = {
        "employee_id": "EMP-001",
        "employee_name": "Test Employee",
        "expense_category": "HOTEL",
        "expense_amount": 250,
        "currency": "USD",
        "expense_date": "2026-11-23",
        "region": "USA",
        "policy_reference": "DEMO-ONLY",
        "exception_reason": "Test",
        "severity": "LOW",
        "nights": 1,
        "receipt_status": "UNKNOWN"
    }

    request = LogExpenseExceptionRequest(**valid_request)
    assert request.region == "USA"

    with pytest.raises(ValidationError, match="requires currency"):
        LogExpenseExceptionRequest(**{
            **valid_request,
            "currency": "INR"
        })

    with pytest.raises(ValidationError, match="number of nights"):
        LogExpenseExceptionRequest(**{
            **valid_request,
            "nights": None
        })
