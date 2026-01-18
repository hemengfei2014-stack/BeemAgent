import os
import time
from dataclasses import dataclass
from typing import Any

import jwt


@dataclass(frozen=True)
class AuthContext:
    org_id: str
    org_name: str
    user_id: str
    user_name: str


def _jwt_secret() -> str:
    secret = os.getenv("QA_JWT_SECRET")
    if secret:
        return secret
    return "dev-only-secret-change-me"


def create_access_token(ctx: AuthContext, ttl_seconds: int = 60 * 60 * 24 * 7) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "iat": now,
        "exp": now + ttl_seconds,
        "org_id": ctx.org_id,
        "org_name": ctx.org_name,
        "user_id": ctx.user_id,
        "user_name": ctx.user_name,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> AuthContext | None:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
        return AuthContext(
            org_id=str(payload["org_id"]),
            org_name=str(payload["org_name"]),
            user_id=str(payload["user_id"]),
            user_name=str(payload.get("user_name") or ""),
        )
    except Exception:
        return None


