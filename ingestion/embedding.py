class EmbeddingClient:
    """문서 인덱싱 전용 embedding API 어댑터."""
    def __init__(self, api_key: str, model: str) -> None:
        """API 키와 embedding 모델을 보관하고 요청 클라이언트를 초기화한다."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """입력 순서를 보존해 각 비어 있지 않은 텍스트의 동일 차원 벡터를 반환한다.

        배치 크기·재시도·timeout을 적용하고, 반환 수/차원 불일치나 API 실패는 인덱스 작성
        전에 명시적으로 실패시킨다. 텍스트 원문이나 키는 로그에 남기지 않는다.
        """
        ...


def embed(texts: list[str]) -> list[list[float]]:
    """설정된 EmbeddingClient를 이용하는 편의 함수; import 시 API 호출은 하지 않는다."""
    ...
