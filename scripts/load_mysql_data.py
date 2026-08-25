"""도메인 ETL pipeline을 선택해 실행할 미구현 통합 CLI."""


def main() -> None:
    """검증된 입력으로 purchase 또는 sales 배치만 선택해 실행한다."""
    # TODO(implementation): 도메인, 원천 경로, allowlisted table을 CLI에서 검증한 뒤 해당
    # pipeline을 호출한다. validation 실패 시 load하지 않고 비영 종료 상태를 반환하며,
    # 채팅 read-only 계정이나 ETL을 API 요청 경로에서 사용하지 않는다.
    # Completion criteria:
    # - purchase/sales dispatch와 잘못된 table/path를 fake로 검증한다.
    # - 처리 행 수·단계·검증 결과만 출력하고 자격증명/원본 행은 출력하지 않는다.
    # - 도메인 pipeline 실패의 종료 코드가 자동화에서 구분 가능하다.
    ...


if __name__ == "__main__":
    main()
