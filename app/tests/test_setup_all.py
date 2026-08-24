"""통합 초기화 도구의 안전한 실행 계획 계약."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

import setup_all


def _arguments(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
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
        "Django migrations",
        "Document path registration",
        "FAISS document indexing",
        "Purchase ETL",
        "Sales ETL",
    ]
    assert steps[0].mutates_data is False
    assert steps[-1].command[-1] == str(setup_all.DEFAULT_SALES_SOURCE)


def test_build_steps_respects_domain_skips_and_superuser_option() -> None:
    steps = setup_all.build_steps(
        _arguments(skip_documents=True, skip_purchase=True, create_superuser=True)
    )

    assert [step.name for step in steps] == [
        "Django configuration check",
        "Django migrations",
        "Django superuser creation",
        "Sales ETL",
    ]


def test_apply_preconditions_require_env_and_selected_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(setup_all, "PROJECT_ROOT", tmp_path)
    arguments = _arguments(skip_purchase=True, skip_sales=True)

    with pytest.raises(FileNotFoundError, match=".env"):
        setup_all.validate_apply_preconditions(arguments)

    (tmp_path / ".env").write_text("", encoding="utf-8")
    setup_all.validate_apply_preconditions(arguments)
