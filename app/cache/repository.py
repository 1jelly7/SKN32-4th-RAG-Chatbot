from __future__ import annotations

from typing import Any, Protocol


CacheValue = dict[str, Any]


class CacheRepository(Protocol):
    def get(self, key: str) -> CacheValue | None:
        ...

    def set(self, key: str, value: CacheValue, ttl_seconds: int) -> None:
        ...

    def delete(self, key: str) -> None:
        ...


class MemoryCache:
    def __init__(self) -> None:
        ...

    def get(self, key: str) -> CacheValue | None:
        ...

    def set(self, key: str, value: CacheValue, ttl_seconds: int) -> None:
        ...

    def delete(self, key: str) -> None:
        ...


class RedisCache:
    def __init__(self, redis_url: str) -> None:
        ...

    def get(self, key: str) -> CacheValue | None:
        ...

    def set(self, key: str, value: CacheValue, ttl_seconds: int) -> None:
        ...

    def delete(self, key: str) -> None:
        ...


cache: CacheRepository = ...
