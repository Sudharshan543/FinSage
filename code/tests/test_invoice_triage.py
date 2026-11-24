from app import invoice_triage


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.closed = False

    def execute(self, query):
        self.query = query

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


def test_po_overage_includes_currency_without_claiming_currency_conversion(
    monkeypatch
):
    cursor = FakeCursor([(
        "INV-001",
        "Vendor",
        "V-001",
        "PO-001",
        1200,
        1000,
        200,
        "USD"
    )])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        invoice_triage,
        "get_hana_connection",
        lambda: connection
    )

    records = invoice_triage.check_po_amount_mismatches()

    assert "CURRENCY" in cursor.query
    assert records[0]["currency"] == "USD"
    assert records[0]["difference"] == 200.0
    assert connection.closed


def test_missing_po_results_include_invoice_currency(monkeypatch):
    cursor = FakeCursor([(
        "INV-002",
        "Vendor",
        "V-002",
        500,
        "USD"
    )])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        invoice_triage,
        "get_hana_connection",
        lambda: connection
    )

    records = invoice_triage.check_missing_po_numbers()

    assert "CURRENCY" in cursor.query
    assert records[0]["currency"] == "USD"
    assert connection.closed
