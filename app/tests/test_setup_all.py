"""통합 초기화 도구의 안전한 실행 계획 계약."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

import setup_all


def _arguments(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "skip_infra": False,
        "skip_django": False,
        "skip_documents": False,
        "skip_purchase": False,
        "skip_sales": False,
        "create_superuser": False,
        "purchase_source": setup_all.DEFAULT_PURCHASE_SOURCE,
        "sales_source": setup_all.DEFAULT_SALES_SOURCE,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_build_steps_orders_django_documents_and_domain_etl() -> None:
    steps = setup_all.build_steps(_arguments())

    assert [step.name for step in steps] == [
        "Django configuration check",
        "MySQL 데이터베이스·쓰기 계정 준비",
        "Django migrations",
        "Document path registration",
        "FAISS document indexing",
        "Purchase ETL",
        "Sales ETL",
        "구매·판매 뷰 + reader 계정 준비",
    ]
    assert steps[0].mutates_data is False
    assert steps[-2].command[-1] == str(setup_all.DEFAULT_SALES_SOURCE)


def test_build_steps_respects_domain_skips_and_superuser_option() -> None:
    steps = setup_all.build_steps(
        _arguments(skip_documents=True, skip_purchase=True, create_superuser=True)
    )

    assert [step.name for step in steps] == [
        "Django configuration check",
        "MySQL 데이터베이스·쓰기 계정 준비",
        "Django migrations",
        "Django superuser creation",
        "Sales ETL",
        "구매·판매 뷰 + reader 계정 준비",
    ]


def test_build_steps_skip_infra_omits_db_account_and_view_steps() -> None:
    """실제 사고 재현(2026-08-2X): DB/계정/뷰가 이미 다 되어 있는 환경에서
    setup_all.py를 반복 실행할 때, --skip-infra로 이 무거운 단계들을 건너뛸 수
    있어야 한다."""
    steps = setup_all.build_steps(_arguments(skip_infra=True))

    names = [step.name for step in steps]
    assert "MySQL 데이터베이스·쓰기 계정 준비" not in names
    assert "구매·판매 뷰 + reader 계정 준비" not in names


def test_build_steps_omits_view_step_when_both_domains_skipped() -> None:
    """purchase와 sales를 둘 다 생략하면, 뷰를 만들 테이블 자체가 없으므로
    뷰 생성 단계도 같이 생략되어야 한다(그렇지 않으면 존재하지 않는 테이블을
    참조하려다 실패한다)."""
    steps = setup_all.build_steps(_arguments(skip_purchase=True, skip_sales=True))

    assert "구매·판매 뷰 + reader 계정 준비" not in [step.name for step in steps]


def test_apply_preconditions_require_env_and_selected_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup_all, "PROJECT_ROOT", tmp_path)
    arguments = _arguments(skip_purchase=True, skip_sales=True)

    with pytest.raises(FileNotFoundError, match=".env"):
        setup_all.validate_apply_preconditions(arguments)

    (tmp_path / ".env").write_text("", encoding="utf-8")
    setup_all.validate_apply_preconditions(arguments)