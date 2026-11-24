from app import finance_tools


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.parameters = None
        self.closed = False

    def execute(self, query, parameters=None):
        self.query = query
        self.parameters = parameters

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


def install_fake_connection(monkeypatch, rows):
    cursor = FakeCursor(rows)
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        finance_tools,
        "get_hana_connection",
        lambda: connection
    )
    return cursor, connection


def test_invoice_summary_keeps_currency_totals_separate(monkeypatch):
    cursor, connection = install_fake_connection(
        monkeypatch,
        [
            ("PAID", "INR", 2, 1000),
            ("PAID", "USD", 1, 200)
        ]
    )

    summary = finance_tools.summarize_invoices()

    assert "GROUP BY PAYMENT_STATUS, CURRENCY" in cursor.query
    assert summary == [
        {
            "payment_status": "PAID",
            "currency": "INR",
            "invoice_count": 2,
            "total_amount": 1000.0
        },
        {
            "payment_status": "PAID",
            "currency": "USD",
            "invoice_count": 1,
            "total_amount": 200.0
        }
    ]
    assert connection.closed


def test_vendor_history_is_grouped_by_currency(monkeypatch):
    cursor, connection = install_fake_connection(
        monkeypatch,
        [
            ("ABC Technologies", "V-1", "INR", 2, 1000),
            ("ABC Technologies", "V-1", "USD", 1, 200)
        ]
    )

    history = finance_tools.vendor_terms_lookup("ABC Technologies")

    assert "GROUP BY VENDOR_NAME, VENDOR_ID, CURRENCY" in cursor.query
    assert cursor.parameters == ("%abc technologies%",)
    assert [entry["currency"] for entry in history] == ["INR", "USD"]
    assert [entry["total_invoiced"] for entry in history] == [
        1000.0,
        200.0
    ]
    assert connection.closed
