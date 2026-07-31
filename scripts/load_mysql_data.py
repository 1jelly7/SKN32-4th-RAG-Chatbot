def main() -> None:
    # 이 CLI는 ETL 배치의 입력 경로·대상 allowlisted table·필수 컬럼을 받아 pipeline을 호출한다.
    # validation 실패 시 DB load를 시도하지 않고 비영(0이 아닌) 종료 상태와 오류 요약을 남긴다.
    # 채팅 read-only 계정이 아닌 ETL 전용 쓰기 계정 설정만 사용하며 자격증명은 출력하지 않는다.
    ...


if __name__ == "__main__":
    main()
