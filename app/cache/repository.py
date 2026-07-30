from __future__ import annotations

from typing import Any, Protocol


CacheValue = dict[str, Any]


class CacheRepository(Protocol):
    """캐시 구현체가 제공해야 할 동기 저장소 계약이다."""
    def get(self, key: str) -> CacheValue | None:
        """만료되지 않은 값의 방어적 사본을 반환하고, 없거나 만료되면 None을 반환한다."""
        ...

    def set(self, key: str, value: CacheValue, ttl_seconds: int) -> None:
        """양수 TTL로 직렬화 가능한 값을 저장한다; 호출자 값을 공유 참조로 보관하지 않는다."""
        ...

    def delete(self, key: str) -> None:
        """키가 존재하면 무효화하고 존재하지 않아도 멱등적으로 성공한다."""
        ...


class MemoryCache:
    """개발·테스트용 프로세스 내 TTL 캐시.

    값과 만료 시각을 저장하고 매 get에서 만료 항목을 제거한다. 운영 환경의 다중 인스턴스
    공유 저장소를 대체하지 않으며 테스트가 접근하는 ``_store``의 계약은 유지한다.
    """
    def __init__(self) -> None:
        """빈 저장소와 만료 메타데이터를 초기화한다."""
        ...

    def get(self, key: str) -> CacheValue | None:
        """키 유효성·만료를 확인한 뒤 안전한 복사본을 반환한다."""
        ...

    def set(self, key: str, value: CacheValue, ttl_seconds: int) -> None:
        """현재 시각 기준 만료 시각과 함께 값을 저장하며 0 이하 TTL은 저장하지 않는다."""
        ...

    def delete(self, key: str) -> None:
        """값과 만료 메타데이터를 함께 제거한다."""
        ...


class RedisCache:
    """운영용 Redis 어댑터; MemoryCache와 동일한 값·TTL·무효화 의미론을 제공한다."""
    def __init__(self, redis_url: str) -> None:
        """Redis 클라이언트를 생성하되 연결 비밀번호를 로그에 남기지 않는다."""
        ...

    def get(self, key: str) -> CacheValue | None:
        """namespace가 적용된 키를 읽어 JSON 등을 역직렬화하고 손상값은 miss 처리한다."""
        ...

    def set(self, key: str, value: CacheValue, ttl_seconds: int) -> None:
        """직렬화 값과 Redis 만료 시간을 원자적으로 기록한다."""
        ...

    def delete(self, key: str) -> None:
        """namespace가 적용된 캐시 키를 삭제한다."""
        ...


# 설정에 따라 RedisCache 또는 개발용 MemoryCache 한 구현체를 주입한다. import 시 네트워크
# 연결 실패 때문에 앱이 즉시 죽지 않도록 생성·fallback 정책은 설정 계층에서 명확히 둔다.
cache: CacheRepository = ...
