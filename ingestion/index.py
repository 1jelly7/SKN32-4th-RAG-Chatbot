"""
chunk + vector로 FAISS 인덱스를 원자적으로 만들고, 인덱스 버전을 관리합니다.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import faiss
import numpy as np

from ingestion.types import DocumentChunk, IndexBuildResult

INDEX_FILENAME = "index.faiss"
METADATA_FILENAME = "metadata.json"


def build_index(
    chunks: list[DocumentChunk],
    vectors: list[list[float]],
    output_path: Path,
) -> IndexBuildResult:
    """chunk와 vector의 1:1 대응을 검증해 FAISS 인덱스와 metadata를 원자적으로 작성한다.

    - chunk 수와 vector 수가 다르면 즉시 실패시킵니다.
    - 모든 vector가 같은 차원이어야 하며, 아니면 즉시 실패시킵니다.
    - 출력 폴더에 임시 파일(.tmp)로 먼저 쓰고, 두 파일(.faiss, metadata.json) 모두
      정상적으로 써진 뒤에만 최종 파일명으로 교체합니다. 그래야 쓰는 도중 실패해도
      기존 인덱스가 반쪽짜리로 덮어써지지 않습니다.
    - index_version은 매 빌드마다 새로 발급되는 값이라, 캐시 키에 넣으면 재인덱싱 시
      자동으로 캐시가 무효화되는 효과가 있습니다.
    """

    if len(chunks) != len(vectors):
        raise ValueError(f"chunk 수({len(chunks)})와 vector 수({len(vectors)})가 다릅니다.")

    if not chunks:
        raise ValueError("빈 chunk 목록으로는 인덱스를 만들 수 없습니다.")

    dimension = len(vectors[0])
    for i, vector in enumerate(vectors):
        if len(vector) != dimension:
            raise ValueError(f"{i}번째 vector의 차원({len(vector)})이 첫 vector({dimension})와 다릅니다.")

    output_path.mkdir(parents=True, exist_ok=True)

    matrix = np.array(vectors, dtype=np.float32)
    # 코사인 유사도를 쓰려면 벡터를 정규화한 뒤 내적(IndexFlatIP)을 쓰는 게 표준적입니다.
    faiss.normalize_L2(matrix)

    index = faiss.IndexFlatIP(dimension)
    index.add(matrix)

    index_version = f"v{int(time.time())}-{uuid.uuid4().hex[:8]}"

    metadata_payload = {
        "index_version": index_version,
        "dimension": dimension,
        "chunk_count": len(chunks),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "chunks": chunks,  # 순서가 FAISS 인덱스 내 벡터 순서와 정확히 일치해야 합니다.
    }

    tmp_index_path = output_path / f"{INDEX_FILENAME}.tmp"
    tmp_metadata_path = output_path / f"{METADATA_FILENAME}.tmp"
    final_index_path = output_path / INDEX_FILENAME
    final_metadata_path = output_path / METADATA_FILENAME

    faiss.write_index(index, str(tmp_index_path))
    tmp_metadata_path.write_text(json.dumps(metadata_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # 두 파일 다 임시로 쓰기 성공한 뒤에만 원자적으로 교체(rename)합니다.
    tmp_index_path.replace(final_index_path)
    tmp_metadata_path.replace(final_metadata_path)

    return {
        "index_path": str(final_index_path),
        "metadata_path": str(final_metadata_path),
        "index_version": index_version,
        "chunk_count": len(chunks),
    }


def get_index_version(index_path: Path) -> str:
    """인덱스와 짝을 이루는 metadata에서 cache key용 불변 버전 문자열을 읽는다.

    파일 부재·손상은 이전 버전이나 빈 값으로 숨기지 말고, 재인덱싱이 필요함을
    알리는 오류로 명확히 처리합니다.
    """

    metadata_path = index_path.parent / METADATA_FILENAME if index_path.name == INDEX_FILENAME else index_path

    if not metadata_path.exists():
        raise FileNotFoundError(f"인덱스 metadata를 찾을 수 없습니다: {metadata_path} (재인덱싱이 필요합니다)")

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"인덱스 metadata가 손상되었습니다: {metadata_path}") from exc

    version = payload.get("index_version")
    if not version:
        raise ValueError(f"index_version 필드가 없습니다: {metadata_path}")

    return version
