"""핵심 패키지의 모든 모듈이 실제로 import 가능한지 검증하는 스모크 테스트.

기존 단위 테스트는 전부 Fake MCP/Fake DB로 도는 격리 테스트라, 실제 import
체인이 살아있는지는 한 번도 검증한 적이 없었다. 그 사각지대 때문에
``mcp_servers/data_tools/purchase/query.py``의 ``query_purchase`` import가
깨져 있던 걸 pytest 205개가 전혀 잡지 못했다(handoff_summary.md 참고).

이 테스트는 app/, mcp_servers/, ingestion/, etl/ 아래 모든 모듈을
``importlib.import_module``로 실제로 import해보기만 한다. 로직은 전혀
검증하지 않으며, "import 시점에 터지는가"만 잡아낸다.

주의: 여기 포함된 네 패키지는 (확인됨) import 시점에 DB/Redis/외부 API
연결을 시도하지 않는다. 만약 새로 추가하는 모듈이 모듈 최상단에서 실제
연결을 맺는다면 이 테스트가 그 모듈을 import하면서 네트워크를 건드리게
되므로, 그런 코드는 함수/클래스 내부로 옮겨야 한다.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest

# 스캔 대상 루트 패키지. 새 도메인(mcp_servers 하위 등)을 추가하면
# 이 리스트에 넣지 않아도 walk_packages가 하위 패키지까지 자동으로 훑는다.
_ROOT_PACKAGES = ["app", "mcp_servers", "ingestion", "etl"]


def _discover_module_names() -> list[str]:
    """루트 패키지들 아래의 모든 모듈 이름(자기 자신 포함)을 수집한다."""
    names: list[str] = []
    for root in _ROOT_PACKAGES:
        package = importlib.import_module(root)
        names.append(root)
        names.extend(
            module_info.name
            for module_info in pkgutil.walk_packages(
                package.__path__, prefix=root + "."
            )
        )
    return sorted(set(names))


_MODULE_NAMES = _discover_module_names()


def test_discovered_at_least_expected_module_count() -> None:
    """수집 로직 자체가 조용히 빈 리스트를 내지 않는지 확인하는 가드.

    walk_packages는 대상 디렉터리에 ``__init__.py``가 없거나 경로가 잘못되면
    아무 것도 못 찾고 조용히 통과해버릴 수 있다. 그러면 아래 파라미터화된
    테스트가 0개로 스킵되어 "모두 통과"처럼 보이는 착시가 생긴다.
    """
    assert len(_MODULE_NAMES) >= 50, (
        f"예상보다 적은 {len(_MODULE_NAMES)}개 모듈만 발견됨 - "
        "수집 로직이 깨졌을 수 있음"
    )


@pytest.mark.parametrize("module_name", _MODULE_NAMES)
def test_module_imports_cleanly(module_name: str) -> None:
    """각 모듈을 개별적으로 import해, 어떤 모듈이 깨졌는지 테스트 이름으로 바로 특정한다."""
    importlib.import_module(module_name)
