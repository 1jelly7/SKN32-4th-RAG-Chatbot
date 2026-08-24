"""sales/purchase/document/account 도메인이 공유하는 PyMySQL 연결 풀.

기존 코드는 매 쿼리마다 ``pymysql.connect()``로 새 TCP 연결을 열고 요청이 끝나면
바로 끊었다. 연결마다 TCP 핸드셰이크 + MySQL 인증 왕복 비용이 들기 때문에, 특히
Sales 질문처럼 한 요청 안에서 EXPLAIN 검증 → 재시도 → 실제 조회로 연결을 여러 번 여는
경로에서는 이 비용이 그대로 누적되어 응답 지연으로 이어진다.

이 모듈은 (host, user, database) 조합별로 ``DBUtils.PooledDB`` 인스턴스를 프로세스당
한 번만 만들어 재사용한다. 풀에서 꺼낸 연결 객체는 pymysql 연결과 동일한 인터페이스
(``cursor()``, ``close()``, ``commit()``)를 그대로 제공하며, ``close()``를 호출해도
실제 TCP 연결은 끊기지 않고 풀에 반납되므로 기존 ``try/finally: connection.close()``
호출부는 변경 없이 그대로 재사용할 수 있다.
"""

from __future__ import annotations

from typing import Any

import pymysql
from dbutils.pooled_db import PooledDB

_pools: dict[tuple[str, str, str, int], PooledDB] = {}


def get_pool(
    host: str,
    user: str,
    password: str,
    database: str,
    *,
    port: int = 3306,
    cursorclass: Any = pymysql.cursors.DictCursor,
    charset: str = "utf8mb4",
    autocommit: bool = False,
    max_connections: int = 10,
) -> PooledDB:
    """(host, user, database, port) 조합별로 풀을 한 번만 생성해 캐싱한다.

    ``ping=1``은 풀에서 연결을 꺼낼 때마다 살아있는지 확인하고, 유휴 시간 동안 MySQL
    서버 쪽에서 먼저 끊어진 연결이면 자동으로 재연결한다(장시간 유휴 후 "MySQL server
    has gone away" 오류를 예방).
    """
    key = (host, user, database, port)
    pool = _pools.get(key)
    if pool is None:
        pool = PooledDB(
            creator=pymysql,
            maxconnections=max_connections,
            mincached=0,  # 0이어야 풀 생성 시점에 미리 연결하지 않는다(완전 지연 연결 유지).
            maxcached=max_connections,
            blocking=True,
            ping=1,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            cursorclass=cursorclass,
            charset=charset,
            autocommit=autocommit,
        )
        _pools[key] = pool
    return pool


def reset_pools() -> None:
    """테스트나 설정 변경 후 캐시된 풀을 모두 비운다. 운영 코드에서는 호출하지 않는다."""
    _pools.clear()
