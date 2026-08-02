"""구매 extract→transform→validate→load를 조합할 미구현 배치 진입점."""

from pathlib import Path

from .extract import extract_excel
from .transform import transform
from .validate import validate
from .load import upsert
from .types import PipelineResult


def run_csv_pipeline(
        path: Path,
        table: str,
        required_columns: list[str],
        sheet_name: str | None = None,
        column_mapping: dict[str, str] | None = None,
        type_mapping: dict[str, any] | None = None,
) -> PipelineResult:
    """CSV ETL의 extract → transform → validate → load 순서를 오케스트레이션한다.

    단계별 입력/출력 개수와 오류를 기록하고, validation.is_valid가 false면 load를 호출하지
    않은 채 ``load=None``인 결과를 반환한다. 예외에는 source path와 단계명을 포함하되
    원본 민감 데이터는 로그에 기록하지 않는다.
    """
    # TODO(implementation): 각 단계를 순서대로 호출하고 검증 실패 시 load=None으로
    # 중단한다. API/Agent에서 호출하지 않으며 처리 행 수·검증 결과만 구매 ETL 로그에
    # 남긴다. 성공, 검증 중단, 적재 rollback fake test가 완료 조건이다.
    ...

    try:
        # 1. EXTRACT - 엑셀에서 데이터 읽기
        print(f"  → Extracting from {path}...")
        # sheet_name이 없으면 table 이름을 사용
        sheet_to_read = sheet_name if sheet_name else table
        df_extracted = extract_excel(path, sheet_name=sheet_to_read)
        print(f"    ✓ Extracted {len(df_extracted)} rows")

        # 2. TRANSFORM - 데이터 변환
        print(f"  → Transforming data...")
        df_transformed = transform(df_extracted, column_mapping, type_mapping)
        print(f"    ✓ Transformed to {len(df_transformed)} rows")

        # 3. VALIDATE - 데이터 검증
        print(f"  → Validating data...")
        validation_result = validate(df_transformed, required_columns)
        print(f"    ✓ Validation: {'PASS' if validation_result['is_valid'] else 'FAIL'}")

        if not validation_result['is_valid']:
            for error in validation_result['errors']:
                print(f"      ⚠ {error}")

        # 4. LOAD - 데이터베이스에 저장 (검증 통과했을 때만)
        load_result = None
        if validation_result['is_valid']:
            print(f"  → Loading to table '{table}'...")
            load_result = upsert(df_transformed, table)
            print(f"    ✓ Loaded: inserted={load_result['inserted_count']}, updated={load_result['updated_count']}")
        else:
            print(f"  → Skipping load due to validation failures")

        # 5. 결과 반환
        return PipelineResult(
            source_path=str(path),
            validation=validation_result,
            load=load_result
        )

    except Exception as e:
        print(f"    ❌ Pipeline error: {str(e)}")
        raise