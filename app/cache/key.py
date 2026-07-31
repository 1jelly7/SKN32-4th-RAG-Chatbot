from __future__ import annotations

import hashlib
import json

from app.agent.state import GraphState


def make_cache_key(state: GraphState) -> str:
    """재사용 안전성을 보장하는 결정적 캐시 키를 생성한다.

    정규화한 질문, 대화 문맥 해시, 문서 인덱스 버전, DB freshness bucket, 프롬프트
    버전, model ID를 정렬된 직렬화 후 SHA-256으로 해시한다. 질문 원문을 키에 노출하지
    않고, 누락 필드는 명시적 기본값으로 처리해 동일 입력이 항상 동일 키를 만들도록 한다.
    """
    material = {
        "question": " ".join(state.get("question", "").casefold().split()),
        "conversation_context_hash": state.get("conversation_context_hash"),
        "document_index_version": state.get("document_index_version"),
        "database_freshness_bucket": state.get("database_freshness_bucket"),
        "prompt_version": state.get("prompt_version"),
        "model_id": state.get("model_id"),
    }
    serialized = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
