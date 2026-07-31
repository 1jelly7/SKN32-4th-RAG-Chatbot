def main() -> None:
    # CLI는 API 요청 경로가 아니라 배치로만 문서 인덱싱을 실행해야 한다. 내부 문서 DB에서
    # 파일 경로를 조회한 뒤 load → chunk/metadata → embed → build_index 순서로 호출하고,
    # 성공한 index_version·chunk_count만 요약 출력한다.
    # 부분 생성물은 원자적 index 교체가 끝나기 전 공개하지 않으며 원문/비밀값을 출력하지 않는다.
    ...


if __name__ == "__main__":
    main()
