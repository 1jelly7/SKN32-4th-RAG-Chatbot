"""기존 FastAPI scrypt 문자열을 첫 로그인 동안만 검증하는 hasher."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac

from django.contrib.auth.hashers import BasePasswordHasher, mask_hash


class LegacyScryptPasswordHasher(BasePasswordHasher):
    """`scrypt$N$r$p$salt$hash$length` 형식의 기존 비밀번호를 검증한다."""

    algorithm = "scrypt"
    _n = 2**14
    _r = 8
    _p = 1
    _salt_length = 16
    _key_length = 32

    def encode(self, password: str, salt: str) -> str:
        raise NotImplementedError(
            "새 비밀번호에는 Django 기본 hasher를 사용해야 합니다."
        )

    def verify(self, password: str, encoded: str) -> bool:
        try:
            algorithm, n, r, p, salt, expected, length = encoded.split("$")
            salt_bytes = base64.b64decode(salt, validate=True)
            expected_bytes = base64.b64decode(expected, validate=True)
            if (
                algorithm != self.algorithm
                or int(n) != self._n
                or int(r) != self._r
                or int(p) != self._p
                or int(length) != self._key_length
                or len(salt_bytes) != self._salt_length
                or len(expected_bytes) != self._key_length
            ):
                return False
            actual = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt_bytes,
                n=self._n,
                r=self._r,
                p=self._p,
                dklen=self._key_length,
            )
            return hmac.compare_digest(actual, expected_bytes)
        except (ValueError, TypeError, UnicodeError, binascii.Error):
            return False

    def safe_summary(self, encoded: str) -> dict[str, str]:
        try:
            algorithm, n, r, p, salt, expected, length = encoded.split("$", 6)
        except ValueError:
            return {"algorithm": self.algorithm, "hash": mask_hash(encoded)}
        return {
            "algorithm": algorithm,
            "work factor": n,
            "block size": r,
            "parallelism": p,
            "salt": mask_hash(salt),
            "hash": mask_hash(expected),
            "length": length,
        }

    def must_update(self, encoded: str) -> bool:
        """로그인 성공 직후 Django 기본 hasher로 교체하게 한다."""
        return True

    def harden_runtime(self, password: str, encoded: str) -> None:
        """기존 scrypt 자체가 고정 work factor를 수행하므로 추가 연산하지 않는다."""
