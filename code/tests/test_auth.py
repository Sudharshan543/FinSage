from fastapi.testclient import TestClient

from app import main
from app.auth import extract_bearer_token


class FakeSecurityContext:
    def __init__(self, granted_scopes):
        self.granted_scopes = set(granted_scopes)

    def check_scope(self, scope):
        return scope in self.granted_scopes


def encode_claims(claims):
    import base64
    import json

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "typ": "JWT"}).encode("ascii")
    ).rstrip(b"=").decode("ascii")
    payload = base64.urlsafe_b64encode(
        json.dumps(claims).encode("ascii")
    ).rstrip(b"=").decode("ascii")
    return f"{header}.{payload}.signature"


def enable_auth(monkeypatch):
    credentials = {
        "xsappname": "finsage-finance-copilot",
        "clientid": "test",
    }
    monkeypatch.setattr(main, "XSUAA_ENABLED", True)
    monkeypatch.setattr(main, "XSUAA_CREDENTIALS", credentials)


def test_unauthenticated_request_returns_401(monkeypatch):
    enable_auth(monkeypatch)
    client = TestClient(main.app)

    response = client.get("/agent/invoices/summary")

    assert response.status_code == 401


def test_invalid_token_returns_401(monkeypatch):
    enable_auth(monkeypatch)

    def invalid_context(token, credentials):
        raise ValueError("invalid token")

    monkeypatch.setattr(main.xssec, "create_security_context", invalid_context)
    client = TestClient(main.app)

    response = client.get(
        "/agent/invoices/summary",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401


def test_expired_token_returns_401(monkeypatch):
    enable_auth(monkeypatch)

    def expired_context(token, credentials):
        raise ValueError("token expired")

    monkeypatch.setattr(main.xssec, "create_security_context", expired_context)
    client = TestClient(main.app)

    response = client.get(
        "/agent/invoices/summary",
        headers={"Authorization": "Bearer expired.user.token"},
    )

    assert response.status_code == 401


def test_viewer_can_read_but_cannot_write(monkeypatch):
    enable_auth(monkeypatch)
    monkeypatch.setattr(main, "summarize_invoices", lambda: [])
    token = encode_claims({
        "sub": "viewer@example.com",
        "email": "viewer@example.com",
        "grant_type": "authorization_code",
        "scope": "finsage-finance-copilot.FinanceViewer",
    })

    def viewer_context(access_token, credentials):
        return FakeSecurityContext({
            "finsage-finance-copilot.FinanceViewer",
        })

    monkeypatch.setattr(main.xssec, "create_security_context", viewer_context)
    client = TestClient(main.app)

    read_response = client.get(
        "/agent/invoices/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    write_response = client.post(
        "/agent/flag-invoice",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "invoice_id": "INV999",
            "reason": "Test only",
            "confirmed": True,
        },
    )

    assert read_response.status_code == 200
    assert write_response.status_code == 403


def test_approver_can_perform_write(monkeypatch):
    enable_auth(monkeypatch)
    token = encode_claims({
        "sub": "approver@example.com",
        "email": "approver@example.com",
        "grant_type": "authorization_code",
    })

    def approver_context(access_token, credentials):
        return FakeSecurityContext({
            "finsage-finance-copilot.FinanceViewer",
            "finsage-finance-copilot.FinanceApprover",
        })

    monkeypatch.setattr(main.xssec, "create_security_context", approver_context)
    monkeypatch.setattr(
        main,
        "flag_invoice",
        lambda **kwargs: {
            "success": True,
            "message": "Invoice successfully flagged."
        }
    )
    client = TestClient(main.app)

    response = client.post(
        "/agent/flag-invoice",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "invoice_id": "INV999",
            "reason": "Test only",
            "confirmed": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_admin_scope_is_authorized(monkeypatch):
    enable_auth(monkeypatch)
    token = encode_claims({
        "sub": "admin@example.com",
        "email": "admin@example.com",
        "grant_type": "authorization_code",
    })

    def admin_context(access_token, credentials):
        return FakeSecurityContext({
            "finsage-finance-copilot.FinanceViewer",
            "finsage-finance-copilot.FinanceApprover",
            "finsage-finance-copilot.FinanceAdmin",
        })

    monkeypatch.setattr(main.xssec, "create_security_context", admin_context)
    client = TestClient(main.app)

    response = client.post(
        "/agent/log-exception",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "employee_id": "TEST001",
            "employee_name": "Test Employee",
            "expense_category": "HOTEL",
            "expense_amount": 6500,
            "currency": "INR",
            "expense_date": "2026-11-22",
            "region": "IN",
            "policy_reference": "TEST-POLICY",
            "exception_reason": "Test only",
            "severity": "HIGH",
            "nights": 1,
            "receipt_status": "UNKNOWN",
            "confirmed": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is False


def test_client_credentials_token_is_not_user_authentication(monkeypatch):
    enable_auth(monkeypatch)
    token = encode_claims({
        "sub": "service",
        "grant_type": "client_credentials",
    })

    def service_context(access_token, credentials):
        return FakeSecurityContext({
            "finsage-finance-copilot.FinanceApprover",
            "finsage-finance-copilot.FinanceAdmin",
        })

    monkeypatch.setattr(main.xssec, "create_security_context", service_context)
    client = TestClient(main.app)

    response = client.get(
        "/agent/invoices/summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_frontend_bearer_header_extraction():
    token = "header.payload.signature"

    assert extract_bearer_token(
        {"Authorization": f"Bearer {token}"}
    ) == token
    assert extract_bearer_token({}) is None
