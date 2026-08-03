"""비밀번호 평문을 저장하지 않는 scrypt 해시 유틸리티다."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_N = 2**14
_R = 8
_P = 1
_KEY_LENGTH = 32


def hash_password(password: str) -> str:
    """새 비밀번호를 salt가 포함된 검증 가능한 scrypt 문자열로 변환한다."""
    if not password:
        raise ValueError("비밀번호는 비어 있을 수 없습니다.")
    salt = os.urandom(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_KEY_LENGTH)
    return "scrypt${}${}${}${}${}${}".format(
        _N, _R, _P, base64.b64encode(salt).decode("ascii"), base64.b64encode(derived).decode("ascii"), _KEY_LENGTH
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    """저장된 scrypt 해시와 후보 비밀번호를 상수 시간 비교로 검증한다."""
    try:
        scheme, n, r, p, salt, expected, length = encoded_hash.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=int(length)
        )
        return hmac.compare_digest(actual, base64.b64decode(expected))
    except (ValueError, TypeError, UnicodeError):
        return False
