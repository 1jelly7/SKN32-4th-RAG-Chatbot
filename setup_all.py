"""Django·문서·구매·판매 초기화 배치를 안전하게 조립하는 진입점.

기본 실행은 계획만 출력한다. DB migration, 문서 등록·인덱싱, 구매·판매 ETL은
데이터를 변경하므로 ``--apply``를 명시해야 한다.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_PURCHASE_SOURCE = Path("data/raw/source_data/ERP_Purchasing_Analytics.xlsx")
DEFAULT_SALES_SOURCE = Path("data/raw/source_data/ERP_Sales_Data_Full_5y.xlsx")


@dataclass(frozen=True)
class SetupStep:
    """실행 순서와 데이터 변경 여부를 함께 표현하는 초기화 한 단계다."""

    name: str
    command: list[str]
    mutates_data: bool = True


def build_steps(arguments: argparse.Namespace) -> list[SetupStep]:
    """선택된 도메인과 입력 파일로 결정적 초기화 명령 목록을 만든다."""
    python = sys.executable
    steps: list[SetupStep] = [
        SetupStep("Django configuration check", [python, "django_app/manage.py", "check"], mutates_data=False),
    ]
    if not arguments.skip_infra:
        steps.append(SetupStep("MySQL 데이터베이스·쓰기 계정 준비", [python, "scripts/ensure_databases_and_accounts.py"]))
    if not arguments.skip_django:
        steps.append(SetupStep("Django migrations", [python, "django_app/manage.py", "migrate"]))
        if arguments.create_superuser:
            steps.append(SetupStep("Django superuser creation", [python, "django_app/manage.py", "createsuperuser"]))
    if not arguments.skip_documents:
        steps.extend(
            [
                SetupStep("Document path registration", [python, "scripts/register_documents.py"]),
                SetupStep("FAISS document indexing", [python, "scripts/ingest_documents.py"]),
            ]
        )
    if not arguments.skip_purchase:
        steps.append(
            SetupStep(
                "Purchase ETL",
                [python, "-m", "etl.purchase.run_all", str(arguments.purchase_source)],
            )
        )
    if not arguments.skip_sales:
        steps.append(
            SetupStep(
                "Sales ETL",
                [python, "-m", "etl.sales.run_all", str(arguments.sales_source)],
            )
        )
    if not arguments.skip_infra and not (arguments.skip_purchase and arguments.skip_sales):
        # 뷰는 ETL이 만든 테이블을 참조하므로 반드시 ETL 이후에 실행해야 한다.
        steps.append(SetupStep("구매·판매 뷰 + reader 계정 준비", [python, "scripts/ensure_views_and_readers.py"]))
    return steps


def parse_arguments() -> argparse.Namespace:
    """데이터 변경 동의와 도메인별 생략 옵션을 읽는다."""
    parser = argparse.ArgumentParser(description="Django·문서·구매·판매 초기화 orchestration")
    parser.add_argument("--apply", action="store_true", help="계획만 출력하지 않고 실제 명령을 실행")
    parser.add_argument("--skip-infra", action="store_true", help="DB/계정/뷰 생성 단계를 생략(이미 다 되어 있을 때)")
    parser.add_argument("--skip-django", action="store_true", help="Django migration 단계를 생략")
    parser.add_argument("--skip-documents", action="store_true", help="문서 등록·FAISS 인덱싱 단계를 생략")
    parser.add_argument("--skip-purchase", action="store_true", help="구매 ETL 단계를 생략")
    parser.add_argument("--skip-sales", action="store_true", help="판매 ETL 단계를 생략")
    parser.add_argument("--purchase-source", type=Path, default=DEFAULT_PURCHASE_SOURCE)
    parser.add_argument("--sales-source", type=Path, default=DEFAULT_SALES_SOURCE)
    parser.add_argument("--create-superuser", action="store_true", help="migration 뒤 Django 대화형 관리자 생성")
    return parser.parse_args()


def validate_apply_preconditions(arguments: argparse.Namespace) -> None:
    """실제 변경 전에 환경 파일과 선택된 ETL 원본을 확인한다."""
    if not (PROJECT_ROOT / ".env").is_file():
        raise FileNotFoundError(".env 파일이 없습니다. .env.example을 복사하고 연결 정보를 설정하세요.")
    for name, source, skipped in (
        ("purchase", arguments.purchase_source, arguments.skip_purchase),
        ("sales", arguments.sales_source, arguments.skip_sales),
    ):
        if not skipped and not (PROJECT_ROOT / source).is_file():
            raise FileNotFoundError(f"{name} ETL 원본 파일이 없습니다: {source}")


def run_step(step: SetupStep) -> None:
    """프로젝트 루트에서 한 단계를 실행하고 실패를 즉시 호출자에게 전달한다."""
    print(f"\n==> {step.name}")
    print(" ".join(step.command))
    subprocess.run(step.command, cwd=PROJECT_ROOT, check=True)


def main() -> int:
    """계획 출력 또는 명시적으로 승인된 전체 초기화를 수행한다."""
    arguments = parse_arguments()
    steps = build_steps(arguments)
    print("초기화 계획:")
    for index, step in enumerate(steps, start=1):
        kind = "변경" if step.mutates_data else "검사"
        print(f"{index}. [{kind}] {step.name}")

    if not arguments.apply:
        print("\n실제 실행은 --apply 옵션을 추가하세요.")
        return 0

    validate_apply_preconditions(arguments)
    for step in steps:
        run_step(step)
    print("\n초기화가 완료되었습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())