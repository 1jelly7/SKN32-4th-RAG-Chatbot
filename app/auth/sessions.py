"""HttpOnly 쿠키에 넣는 짧은 수명의 서명 세션 토큰을 처리한다."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any


def issue_session(payload: dict[str, Any], secret: str, expires_minutes: int) -> str:
    """서버가 재검증할 수 있는 만료 시각 포함 HMAC 세션 토큰을 발급한다."""
    data = {**payload, "sid": str(uuid.uuid4()), "exp": int(time.time()) + expires_minutes * 60}
    encoded = _encode(data)
    signature = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64(signature)}"


def read_session(token: str, secret: str) -> dict[str, Any] | None:
    """서명과 만료를 모두 통과한 서버 발급 세션 payload만 반환한다."""
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(supplied_signature), expected):
            return None
        payload = json.loads(_unb64(encoded))
        return payload if isinstance(payload, dict) and int(payload["exp"]) >= int(time.time()) else None
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _encode(payload: dict[str, Any]) -> str:
    return _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
