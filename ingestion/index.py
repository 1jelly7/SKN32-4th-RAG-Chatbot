from pathlib import Path

from ingestion.types import DocumentChunk, IndexBuildResult


def build_index(
    chunks: list[DocumentChunk],
    vectors: list[list[float]],
    output_path: Path,
) -> IndexBuildResult:
    """chunk와 vector의 1:1 대응을 검증해 FAISS 인덱스와 metadata를 원자적으로 작성한다.

    출력 폴더에 임시 파일로 저장·검증한 뒤 교체하고, chunk metadata/ACL·인덱스 버전·개수를
    함께 기록한다. 벡터 수·차원 불일치, 기존 인덱스 손상은 버전을 올리기 전에 실패시킨다.
    """
    ...


def get_index_version(index_path: Path) -> str:
    """인덱스와 짝을 이루는 metadata에서 cache key용 불변 버전 문자열을 읽는다.

    파일 부재·손상은 이전 버전이나 빈 값으로 숨기지 말고 재인덱싱이 필요함을 알리는 오류로
    처리한다.
    """
    ...
