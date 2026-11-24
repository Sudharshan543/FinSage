from fastapi.testclient import TestClient

from app import main


def test_ask_returns_evidence_verification_and_redacted_trace(monkeypatch):
    monkeypatch.setattr(main, "XSUAA_ENABLED", False)
    trace = {
        "trace_id": "trace-123",
        "stages": []
    }
    trace_start = {}
    monkeypatch.setattr(
        main,
        "start_trace",
        lambda **kwargs: trace_start.update(kwargs) or trace
    )
    monkeypatch.setattr(
        main,
        "route_finance_request",
        lambda **kwargs: {
            "intent": "POLICY_QUERY",
            "answer": "A verified answer.",
            "data": [],
            "citations": [],
            "evidence_available": True,
            "evidence_verification": {
                "verified": True,
                "reason": "Evidence passed."
            },
            "ai_usage": {}
        }
    )
    monkeypatch.setattr(main, "add_trace_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "finish_trace", lambda *args, **kwargs: trace)

    response = TestClient(main.app).post(
        "/agent/ask",
        json={
            "question": "My confidential question text",
            "region": "USA"
        }
    )

    assert response.status_code == 200
    assert response.json()["evidence_verification"]["verified"] is True
    assert "confidential" not in trace_start["request_summary"]
    assert trace_start["request_summary"] == "Finance question"


def test_ask_rejects_request_when_trace_cannot_start(monkeypatch):
    monkeypatch.setattr(main, "XSUAA_ENABLED", False)

    def fail_trace(**kwargs):
        raise RuntimeError("trace offline")

    def fail_route(**kwargs):
        raise AssertionError("Finance route must not run without a trace.")

    monkeypatch.setattr(main, "start_trace", fail_trace)
    monkeypatch.setattr(main, "route_finance_request", fail_route)

    response = TestClient(main.app).post(
        "/agent/ask",
        json={"question": "Find duplicate invoices."}
    )

    assert response.status_code == 503
    assert "tracing is unavailable" in response.json()["detail"]


def test_ask_returns_explicit_error_when_trace_cannot_finish(monkeypatch):
    monkeypatch.setattr(main, "XSUAA_ENABLED", False)
    monkeypatch.setattr(
        main,
        "start_trace",
        lambda **kwargs: {"trace_id": "trace-456", "stages": []}
    )
    monkeypatch.setattr(
        main,
        "route_finance_request",
        lambda **kwargs: {
            "intent": "DUPLICATE_CHECK",
            "answer": "No duplicates were found.",
            "data": [],
            "citations": [],
            "evidence_available": True,
            "ai_usage": {}
        }
    )
    monkeypatch.setattr(main, "add_trace_step", lambda *args, **kwargs: None)

    def fail_finish(*args, **kwargs):
        raise RuntimeError("trace write failed")

    monkeypatch.setattr(main, "finish_trace", fail_finish)

    response = TestClient(main.app).post(
        "/agent/ask",
        json={"question": "Find duplicate invoices."}
    )

    assert response.status_code == 503
    assert "trace could not be persisted" in response.json()["detail"]
