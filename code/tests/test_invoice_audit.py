from datetime import datetime

import pytest

from app import finance_tools, invoice_actions


class FakeCursor:
    def __init__(self, rows=None, single_row=None, fail_on=None):
        self.rows = rows or []
        self.single_row = single_row
        self.fail_on = fail_on
        self.executed = []
        self.closed = False

    def execute(self, query, parameters):
        self.executed.append((query, parameters))
        if self.fail_on and self.fail_on in query:
            raise RuntimeError("Simulated HANA write failure")

    def fetchone(self):
        return self.single_row

    def fetchall(self):
        return self.rows

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


def test_flag_invoice_updates_invoice_and_inserts_history(monkeypatch):
    cursor = FakeCursor(single_row=("INV004",))
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        invoice_actions,
        "get_hana_connection",
        lambda: connection
    )

    result = invoice_actions.flag_invoice(
        invoice_id="INV004",
        reason="Requires compliance review.",
        confirmed=True
    )

    assert result["success"] is True
    assert result["invoice_id"] == "INV004"
    assert result["case_ref"]
    assert len(cursor.executed) == 3
    assert "UPDATE DBADMIN.FINSAGE_INVOICES" in cursor.executed[1][0]
    assert "INSERT INTO DBADMIN.FINSAGE_INVOICE_FLAGS" in cursor.executed[2][0]
    assert cursor.executed[2][1] == (
        result["case_ref"],
        "INV004",
        "Requires compliance review.",
        "FLAGGED"
    )
    assert connection.committed
    assert connection.closed


def test_flag_invoice_rolls_back_if_history_insert_fails(monkeypatch):
    cursor = FakeCursor(
        single_row=("INV004",),
        fail_on="INSERT INTO DBADMIN.FINSAGE_INVOICE_FLAGS"
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        invoice_actions,
        "get_hana_connection",
        lambda: connection
    )

    with pytest.raises(RuntimeError, match="Simulated HANA write failure"):
        invoice_actions.flag_invoice(
            invoice_id="INV004",
            reason="Requires compliance review.",
            confirmed=True
        )

    assert connection.rolled_back
    assert not connection.committed
    assert connection.closed


def test_get_invoice_flags_reads_recent_hana_events(monkeypatch):
    flagged_at = datetime(2026, 11, 23, 12, 0)
    cursor = FakeCursor(rows=[(
        "case-123",
        "INV004",
        "Requires compliance review.",
        "FLAGGED",
        flagged_at
    )])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        finance_tools,
        "get_hana_connection",
        lambda: connection
    )

    flags = finance_tools.get_invoice_flags(limit=20)

    assert cursor.executed[0][1] == (20,)
    assert flags == [{
        "case_ref": "case-123",
        "invoice_id": "INV004",
        "reason": "Requires compliance review.",
        "status": "FLAGGED",
        "flagged_at": str(flagged_at)
    }]
    assert connection.closed
