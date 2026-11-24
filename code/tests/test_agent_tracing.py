import json
from datetime import datetime

from app import agent_tracing


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []
        self.closed = False

    def execute(self, query, parameters):
        self.executed.append((query, parameters))

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


def test_start_trace_inserts_running_trace_into_hana(monkeypatch):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        agent_tracing,
        "get_hana_connection",
        lambda: connection
    )

    trace = agent_tracing.start_trace(
        "FINANCE_QUESTION",
        "Show invoice summary"
    )

    query, parameters = cursor.executed[0]
    assert "INSERT INTO DBADMIN.FINSAGE_AGENT_TRACES" in query
    assert parameters[0] == trace["trace_id"]
    assert parameters[1:3] == (
        "FINANCE_QUESTION",
        "Finance question"
    )
    assert parameters[4] == "RUNNING"
    assert json.loads(parameters[5]) == []
    assert connection.committed
    assert connection.closed


def test_finish_trace_updates_hana_record(monkeypatch):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        agent_tracing,
        "get_hana_connection",
        lambda: connection
    )
    trace = {
        "trace_id": "trace-123",
        "started_at": "2026-11-23T00:00:00+00:00",
        "stages": [{"stage": "ROUTING", "status": "COMPLETED"}]
    }

    result = agent_tracing.finish_trace(
        trace,
        decision="RESPONSE_WITH_RESULTS"
    )

    query, parameters = cursor.executed[0]
    assert "UPDATE DBADMIN.FINSAGE_AGENT_TRACES" in query
    assert parameters[1:3] == ("COMPLETED", "RESPONSE_WITH_RESULTS")
    assert json.loads(parameters[3]) == trace["stages"]
    assert parameters[4] == "trace-123"
    assert result["status"] == "COMPLETED"
    assert connection.committed


def test_read_recent_traces_loads_records_from_hana(monkeypatch):
    started_at = datetime(2026, 11, 23, 0, 0, 0)
    stages = [{"stage": "ROUTING", "status": "COMPLETED"}]
    cursor = FakeCursor(rows=[(
        "trace-123",
        "FINANCE_QUESTION",
        "Show invoice summary",
        started_at,
        None,
        "RUNNING",
        None,
        json.dumps(stages)
    )])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        agent_tracing,
        "get_hana_connection",
        lambda: connection
    )

    traces = agent_tracing.read_recent_traces(limit=5)

    assert cursor.executed[0][1] == (5,)
    assert traces == [{
        "trace_id": "trace-123",
        "request_type": "FINANCE_QUESTION",
        "request_summary": "Finance question (summary redacted)",
        "started_at": "2026-11-23T00:00:00+00:00",
        "finished_at": None,
        "status": "RUNNING",
        "decision": None,
        "stages": stages
    }]
    assert connection.closed
