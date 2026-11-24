from app import expense_actions


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.closed = False

    def execute(self, query, parameters):
        self.executed.append((query, parameters))

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_unconfirmed_exception_does_not_open_database(monkeypatch):
    def unexpected_connection():
        raise AssertionError("Database must not be opened without confirmation.")

    monkeypatch.setattr(
        expense_actions,
        "get_hana_connection",
        unexpected_connection
    )

    result = expense_actions.log_expense_exception(
        employee_id="EMP-001",
        employee_name="Test Employee",
        expense_category="HOTEL",
        expense_amount=6500,
        currency="INR",
        expense_date="2026-11-23",
        region="IN",
        policy_reference="POLICY-001",
        exception_reason="Test",
        severity="HIGH",
        nights=1,
        receipt_status="UNKNOWN",
        confirmed=False
    )

    assert result["success"] is False
    assert "Confirmation required" in result["message"]


def test_confirmed_exception_persists_duration_and_receipt_status(monkeypatch):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        expense_actions,
        "get_hana_connection",
        lambda: connection
    )

    result = expense_actions.log_expense_exception(
        employee_id="EMP-001",
        employee_name="Test Employee",
        expense_category="HOTEL",
        expense_amount=6500,
        currency="INR",
        expense_date="2026-11-23",
        region="IN",
        policy_reference="POLICY-001",
        exception_reason="Test",
        severity="HIGH",
        nights=2,
        receipt_status="SUBMITTED",
        confirmed=True
    )

    query, parameters = cursor.executed[0]
    assert "NIGHTS" in query
    assert "DAYS" in query
    assert "RECEIPT_STATUS" in query
    assert parameters[-3:] == (2, None, "SUBMITTED")
    assert result["success"] is True
    assert connection.committed
    assert connection.closed
