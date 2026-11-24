
import json
import os
import traceback
from fastapi.responses import JSONResponse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sap import xssec
from app.auth import (
    decode_jwt_claims,
    get_xsuaa_scope_names,
)

from app.models import (
    AskRequest,
    FlagInvoiceRequest,
    LogExpenseExceptionRequest
)

from app.agent import route_finance_request

from app.tools.finance import (
    summarize_invoices,
    vendor_terms_lookup,
    get_invoice_details,
    get_expense_exceptions,
    get_invoice_flags
)

from app.tools.invoice_triage import (
    check_duplicate_invoices,
    check_missing_po_numbers,
    check_po_amount_mismatches,
    check_invoice_review_status
)

from app.tools.expense_compliance import check_expense_compliance
from app.tools.invoice import flag_invoice
from app.tools.exception import log_expense_exception

from app.agent_tracing import (
    start_trace,
    add_trace_step,
    finish_trace,
    read_recent_traces
)


app = FastAPI(
    title="FinSage Finance Copilot",
    description="Agentic AI Accounts Payable and Expense Compliance Copilot",
    version="1.3.0"
)


# --------------------------------------------------
# XSUAA CONFIGURATION
# --------------------------------------------------

def get_xsuaa_credentials():
    """
    Read XSUAA credentials from Cloud Foundry VCAP_SERVICES.
    """
    vcap_services = os.getenv("VCAP_SERVICES")

    if not vcap_services:
        return None

    try:
        services = json.loads(vcap_services)
        xsuaa_services = services.get("xsuaa", [])

        for service in xsuaa_services:
            if service.get("name") == "finsage-xsuaa":
                return service.get("credentials")

        if xsuaa_services:
            return xsuaa_services[0].get("credentials")

        return None

    except (json.JSONDecodeError, TypeError):
        return None


XSUAA_CREDENTIALS = get_xsuaa_credentials()
IS_CLOUD_FOUNDRY = bool(os.getenv("VCAP_APPLICATION"))
XSUAA_ENABLED = bool(os.getenv("VCAP_SERVICES"))

@app.middleware("http")
async def xsuaa_authentication(request: Request, call_next):

    if request.url.path == "/health":
        return await call_next(request)

    if not request.url.path.startswith("/agent/"):
        return await call_next(request)

    if not XSUAA_ENABLED:
        if IS_CLOUD_FOUNDRY:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "XSUAA authentication is required but unavailable."
                }
            )
        return await call_next(request)

    if not XSUAA_CREDENTIALS:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "XSUAA service credentials are unavailable."
            }
        )

    authorization = request.headers.get("Authorization", "")

    if not authorization.lower().startswith("bearer "):
        return JSONResponse(
            status_code=401,
            content={
                "detail": "A valid Bearer access token is required."
            },
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = authorization.split(" ", 1)[1].strip()

    if not access_token:
        return JSONResponse(
            status_code=401,
            content={"detail": "Access token is missing."},
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        security_context = xssec.create_security_context(
            access_token,
            XSUAA_CREDENTIALS
        )

        request.state.security_context = security_context
        claims = decode_jwt_claims(access_token)

        grant_type = claims.get("grant_type")
        if grant_type == "client_credentials":
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "A user access token is required."
                },
                headers={"WWW-Authenticate": "Bearer"}
            )

        request.state.authenticated_identity = {
            "subject": claims.get("sub"),
            "user_name": (
                claims.get("user_name")
                or claims.get("email")
                or claims.get("sub")
            ),
            "email": claims.get("email"),
        }

        write_endpoints = {
            "/agent/flag-invoice",
            "/agent/log-exception"
        }

        scope_names = get_xsuaa_scope_names(XSUAA_CREDENTIALS)
        if not scope_names:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "XSUAA scope configuration is unavailable."
                }
            )

        if request.url.path in write_endpoints:
            required_scopes = (
                scope_names["approver"],
                scope_names["admin"],
            )
        else:
            required_scopes = (
                scope_names["viewer"],
                scope_names["approver"],
                scope_names["admin"],
            )

        if not any(
            security_context.check_scope(scope)
            for scope in required_scopes
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "You do not have permission to access this resource."
                }
            )

    except Exception:
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Access token validation failed."
            },
            headers={"WWW-Authenticate": "Bearer"}
        )

    return await call_next(request)


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "application": "FinSage",
        "version": "1.3.0",
        "authentication": (
            "XSUAA enabled" if XSUAA_ENABLED
            else "Local development mode"
        )
    }


# --------------------------------------------------
# FINANCE QUESTION AND ANSWER
# --------------------------------------------------

@app.post("/agent/ask")
def ask_finance_question(request: AskRequest):

    try:
        trace = start_trace(
            request_type="FINANCE_QUESTION",
            request_summary="Finance question"
        )
    except Exception as error:
        print(
            "FINSAGE_TRACE_START_ERROR:",
            type(error).__name__,
            str(error)
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Finance request tracing is unavailable; "
                "the request was not processed."
            )
        ) from error

    try:
        result = route_finance_request(
            question=request.question,
            region=request.region,
            user_access_level="INTERNAL"
        )

        intent = result.get("intent", "UNKNOWN")

        add_trace_step(
            trace,
            stage="INTENT_CLASSIFICATION",
            details={"intent": intent}
        )

        data = result.get("data")
        citations = result.get("citations", [])

        if isinstance(data, list):
            result_count = len(data)
        elif isinstance(data, dict):
            result_count = len(data)
        elif data is None:
            result_count = 0
        else:
            result_count = 1

        add_trace_step(
            trace,
            stage="FINANCE_TOOL_EXECUTION",
            details={
                "intent": intent,
                "result_count": result_count,
                "tool_result_available": data is not None
            }
        )

        evidence_available = result.get(
            "evidence_available",
            bool(data) or bool(citations)
        )

        add_trace_step(
            trace,
            stage="EVIDENCE_VERIFICATION",
            details={
                "evidence_available": evidence_available,
                "citation_count": len(citations)
            }
        )

        answer = result.get(
            "answer",
            "The finance request has been processed."
        )

        if intent == "UNKNOWN":
            decision = "UNSUPPORTED_REQUEST"
        elif not evidence_available:
            decision = "INSUFFICIENT_EVIDENCE"
        else:
            decision = "RESPONSE_WITH_RESULTS"

        add_trace_step(
            trace,
            stage="RESPONSE_GENERATION",
            details={"decision": decision}
        )

        ai_usage = result.get("ai_usage", {})
        response_payload = {
            "intent": intent,
            "answer": answer,
            "data": data,
            "citations": citations,
            "evidence_verification": result.get("evidence_verification"),
            "evidence_available": evidence_available,
            "ai_usage": ai_usage,
            "trace_id": trace["trace_id"]
        }

    except Exception as error:
        print(
            "FINSAGE_REQUEST_ERROR:",
            type(error).__name__,
            str(error)
        )
        print(traceback.format_exc())

        try:
            add_trace_step(
                trace,
                stage="REQUEST_ERROR",
                details={"error_type": type(error).__name__},
                status="FAILED"
            )
            finish_trace(
                trace,
                decision="REQUEST_FAILED",
                status="FAILED"
            )
        except Exception as trace_error:
            print(
                "FINSAGE_TRACE_FAILURE_RECORD_ERROR:",
                type(trace_error).__name__,
                str(trace_error)
            )

        raise HTTPException(
            status_code=500,
            detail="Finance request processing failed."
        ) from error

    try:
        finish_trace(
            trace,
            decision=decision,
            status="COMPLETED"
        )
    except Exception as error:
        print(
            "FINSAGE_TRACE_FINISH_ERROR:",
            type(error).__name__,
            str(error)
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Finance response was not returned because its audit trace "
                "could not be persisted."
            )
        ) from error

    return response_payload


# --------------------------------------------------
# AGENT TRACES
# --------------------------------------------------

@app.get("/agent/traces")
def get_agent_traces(limit: int = 10):

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100."
        )

    traces = read_recent_traces(limit)

    return {
        "total_traces": len(traces),
        "traces": traces
    }


# --------------------------------------------------
# INVOICE ENDPOINTS
# --------------------------------------------------

@app.get("/agent/invoices/summary")
def invoice_summary():
    return summarize_invoices()


@app.get("/agent/invoices/{invoice_id}")
def invoice_details(invoice_id: str):

    result = get_invoice_details(invoice_id)

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found."
        )

    return result


@app.get("/agent/vendor/{vendor_name}")
def vendor_lookup(vendor_name: str):
    return vendor_terms_lookup(vendor_name)


# --------------------------------------------------
# EXPENSE ENDPOINTS
# --------------------------------------------------

@app.get("/agent/expense-exceptions")
def expense_exceptions():
    return get_expense_exceptions()


@app.get("/agent/invoice-flags")
def invoice_flags(limit: int = 100):
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100."
        )

    flags = get_invoice_flags(limit)
    return {
        "total_flags": len(flags),
        "flags": flags
    }


@app.get("/agent/expenses/compliance")
def expense_compliance_report():

    try:
        report = check_expense_compliance()

        return {
            "total_exceptions": len(report),
            "compliance_report": report,
            "verification_enabled": True,
            "verification_scope": (
                "IN/INDIA with INR reference limits only. Duration is "
                "required for hotel/meal checks; receipts are submitter-reported "
                "and are not independently inspected. Other regions/currencies "
                "and unsupported categories are not evaluated."
            )
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Expense compliance report generation failed."
        ) from error


# --------------------------------------------------
# INVOICE TRIAGE
# --------------------------------------------------

@app.get("/agent/invoices/triage/report")
def invoice_triage_report():

    return {
        "duplicates": check_duplicate_invoices(),
        "missing_po_numbers": check_missing_po_numbers(),
        "po_amount_mismatches": check_po_amount_mismatches(),
        "requiring_review": check_invoice_review_status()
    }


# --------------------------------------------------
# INVOICE FLAGGING
# Requires FinanceApprover scope
# --------------------------------------------------

@app.post("/agent/flag-invoice")
def flag_invoice_endpoint(request: FlagInvoiceRequest):

    try:
        result = flag_invoice(
            invoice_id=request.invoice_id,
            reason=request.reason,
            confirmed=request.confirmed
        )

        if result.get("message") == "Invoice not found.":
            raise HTTPException(
                status_code=404,
                detail="Invoice not found."
            )

        if result.get("message") == "A flag reason is required.":
            raise HTTPException(
                status_code=400,
                detail="A flag reason is required."
            )

        return result

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Invoice flagging failed."
        ) from error


# --------------------------------------------------
# EXPENSE EXCEPTION LOGGING
# Requires FinanceApprover scope
# --------------------------------------------------

@app.post("/agent/log-exception")
def log_expense_exception_endpoint(
    request: LogExpenseExceptionRequest
):

    try:
        return log_expense_exception(
            employee_id=request.employee_id,
            employee_name=request.employee_name,
            expense_category=request.expense_category,
            expense_amount=request.expense_amount,
            currency=request.currency,
            expense_date=request.expense_date,
            region=request.region,
            policy_reference=request.policy_reference,
            exception_reason=request.exception_reason,
            severity=request.severity,
            confirmed=request.confirmed,
            nights=request.nights,
            days=request.days,
            receipt_status=request.receipt_status
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Expense exception logging failed."
        ) from error
