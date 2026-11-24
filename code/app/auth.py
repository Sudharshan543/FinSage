import base64
import json


def extract_bearer_token(headers):
    authorization = (
        headers.get("Authorization")
        or headers.get("authorization")
        or ""
    )
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def get_xsuaa_scope_names(credentials):
    xsappname = credentials.get("xsappname") if credentials else None
    if not xsappname:
        return None

    return {
        "viewer": f"{xsappname}.FinanceViewer",
        "approver": f"{xsappname}.FinanceApprover",
        "admin": f"{xsappname}.FinanceAdmin",
    }


def decode_jwt_claims(access_token):
    parts = access_token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed JWT")

    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
    claims = json.loads(decoded.decode("utf-8"))

    if not isinstance(claims, dict):
        raise ValueError("Malformed JWT claims")
    return claims


def extract_authenticated_identity(access_token):
    claims = decode_jwt_claims(access_token)
    scopes = claims.get("scope", [])
    if isinstance(scopes, str):
        scopes = scopes.split()

    return {
        "subject": claims.get("sub"),
        "user_name": (
            claims.get("user_name")
            or claims.get("email")
            or claims.get("sub")
        ),
        "email": claims.get("email"),
        "grant_type": claims.get("grant_type"),
        "scopes": scopes,
    }
