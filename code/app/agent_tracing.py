
import json
from datetime import datetime, timezone
from uuid import uuid4

from app.db import get_hana_connection


def _to_hana_timestamp(value):
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        return timestamp
    return timestamp.astimezone(timezone.utc).replace(tzinfo=None)


def _from_hana_timestamp(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat()
    return str(value)


def _display_request_summary(request_type, request_summary):
    if request_type != "FINANCE_QUESTION":
        return request_summary
    return "Finance question (summary redacted)"


def current_timestamp():
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def start_trace(request_type, request_summary):
    """
    Start tracking a FinSage agent request in SAP HANA.
    """

    if request_type == "FINANCE_QUESTION":
        request_summary = "Finance question"

    trace = {
        "trace_id": str(uuid4()),
        "request_type": request_type,
        "request_summary": request_summary,
        "started_at": current_timestamp(),
        "finished_at": None,
        "status": "RUNNING",
        "decision": None,
        "stages": []
    }

    connection = get_hana_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO DBADMIN.FINSAGE_AGENT_TRACES (
                TRACE_ID,
                REQUEST_TYPE,
                REQUEST_SUMMARY,
                STARTED_AT,
                FINISHED_AT,
                STATUS,
                DECISION,
                STAGES_JSON
            )
            VALUES (?, ?, ?, ?, NULL, ?, NULL, ?)
            """,
            (
                trace["trace_id"],
                trace["request_type"],
                trace["request_summary"],
                _to_hana_timestamp(trace["started_at"]),
                trace["status"],
                json.dumps(trace["stages"], ensure_ascii=False)
            )
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    return trace


def add_trace_step(trace, stage, details=None, status="COMPLETED"):
    """
    Add an execution stage to the trace.
    """

    step = {
        "stage": stage,
        "status": status,
        "timestamp": current_timestamp(),
        "details": details or {}
    }

    trace["stages"].append(step)

    return trace


def finish_trace(trace, decision, status="COMPLETED"):
    """
    Complete the trace record in SAP HANA.
    """

    trace["finished_at"] = current_timestamp()
    trace["decision"] = decision
    trace["status"] = status

    connection = get_hana_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE DBADMIN.FINSAGE_AGENT_TRACES
            SET FINISHED_AT = ?,
                STATUS = ?,
                DECISION = ?,
                STAGES_JSON = ?
            WHERE TRACE_ID = ?
            """,
            (
                _to_hana_timestamp(trace["finished_at"]),
                trace["status"],
                trace["decision"],
                json.dumps(trace["stages"], ensure_ascii=False),
                trace["trace_id"]
            )
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    return trace


def read_recent_traces(limit=10):
    """
    Read the most recent execution traces from SAP HANA.
    """

    connection = get_hana_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT
                TRACE_ID,
                REQUEST_TYPE,
                REQUEST_SUMMARY,
                STARTED_AT,
                FINISHED_AT,
                STATUS,
                DECISION,
                STAGES_JSON
            FROM DBADMIN.FINSAGE_AGENT_TRACES
            ORDER BY STARTED_AT DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        return [
            {
                "trace_id": row[0],
                "request_type": row[1],
                "request_summary": _display_request_summary(row[1], row[2]),
                "started_at": _from_hana_timestamp(row[3]),
                "finished_at": (
                    _from_hana_timestamp(row[4])
                    if row[4] is not None
                    else None
                ),
                "status": row[5],
                "decision": row[6],
                "stages": json.loads(row[7])
            }
            for row in rows
        ]
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":

    print("FINSAGE AGENT TRACE TEST")

    # Start a sample finance question trace.
    trace = start_trace(
        request_type="FINANCE_QUESTION",
        request_summary="What is the hotel expense limit?"
    )

    add_trace_step(
        trace,
        stage="INTENT_CLASSIFICATION",
        details={
            "intent": "EXPENSE_POLICY_QUERY"
        }
    )

    add_trace_step(
        trace,
        stage="POLICY_RETRIEVAL",
        details={
            "retrieved_documents": 2
        }
    )

    add_trace_step(
        trace,
        stage="EVIDENCE_VERIFICATION",
        details={
            "evidence_available": True
        }
    )

    finish_trace(
        trace,
        decision="RESPONSE_WITH_CITATIONS",
        status="COMPLETED"
    )

    print("\nTrace saved to SAP HANA successfully.")
    print("Trace ID:", trace["trace_id"])
    print("Status:", trace["status"])
    print("Stages recorded:", len(trace["stages"]))
