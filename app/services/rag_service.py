"""
문서 인덱싱, Vector Search, RAG 답변 생성을 통합합니다.
"""

# 미래 타입 힌트 평가 방식을 사용합니다.
from __future__ import annotations

# 파일 경로 계산을 위해 Path를 가져옵니다.
from pathlib import Path

# 임베딩 서비스를 가져옵니다.
from app.llm.embedding_service import EmbeddingService

# OpenAI 답변 생성 서비스를 가져옵니다.
from app.llm.openai_service import OpenAIService

# 문서 서비스를 가져옵니다.
from app.services.document_service import DocumentService

# Prompt 서비스를 가져옵니다.
from app.services.prompt_service import PromptService

# 벡터 저장소 공통 인터페이스를 가져옵니다.
from app.vectordb.base import VectorStore


# RAG 서비스 클래스를 정의합니다.
class RagService:
    """문서 적재, 검색, 답변 생성을 한 곳에서 처리합니다."""

    # 필요한 하위 서비스를 생성자에서 전달받습니다.
    def __init__(
        self,
        document_service: DocumentService,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        openai_service: OpenAIService,
        prompt_service: PromptService,
        mysql_service=None,
        document_source: str = "filesystem",
    ) -> None:
        # 문서 서비스를 저장합니다.
        self.document_service = document_service

        # 임베딩 서비스를 저장합니다.
        self.embedding_service = embedding_service

        # 벡터 저장소를 저장합니다.
        self.vector_store = vector_store

        # OpenAI 서비스를 저장합니다.
        self.openai_service = openai_service

        # Prompt 서비스를 저장합니다.
        self.prompt_service = prompt_service

        # MySQL 서비스(선택). document_source="mysql"일 때만 실제로 사용됩니다.
        self.mysql_service = mysql_service

        # 문서 목록을 어디서 가져올지("filesystem" 또는 "mysql") 저장합니다.
        self.document_source = document_source

    # 현재 설정에 맞는 문서 레코드 목록을 가져옵니다.
    def _load_document_records(self) -> list[dict] | None:
        """document_source 설정에 따라 문서 목록(파일 경로 포함)을 가져옵니다."""

        # filesystem 모드면 DocumentService가 알아서 docs 폴더를 스캔하도록 None을 반환합니다.
        if self.document_source.lower() != "mysql" or self.mysql_service is None:
            return None

        # MySQL의 documents 테이블에서 활성 문서의 파일 경로 + 메타데이터를 조회합니다.
        return self.mysql_service.list_documents(active_only=True)

    # docs 폴더 전체를 다시 인덱싱합니다.
    def rebuild_index(self) -> dict:
        """전체 문서를 청크로 분할하고 벡터 저장소를 재구축합니다."""

        # 설정된 소스(파일시스템 또는 MySQL)에서 문서 레코드를 가져옵니다.
        document_records = self._load_document_records()

        # 문서 레코드를 청크로 분할합니다. (document_records가 None이면 폴더를 직접 스캔)
        documents = self.document_service.load_chunks(document_records)

        # 각 청크의 본문만 추출합니다.
        texts = [document["content"] for document in documents]

        # 전체 문서 청크를 임베딩 벡터로 변환합니다.
        vectors = self.embedding_service.embed_documents(texts) if texts else []

        # 선택한 벡터 저장소를 전체 재구축합니다.
        count = self.vector_store.rebuild(documents, vectors)

        # 처리 결과를 API 응답용 딕셔너리로 반환합니다.
        return {"indexed_chunks": count, "document_source": self.document_source}

    # 질문과 유사한 문서를 검색합니다.
    def search(
        self, query: str, top_k: int, requester_department: str | None = None
    ) -> list[dict]:
        """Vector Search 결과를 반환합니다.

        requester_department가 주어지면 접근 권한이 없는 문서(청크)는 결과에서 제외합니다.
        권한 필터링 후에도 top_k개를 채울 수 있도록, 내부적으로는 더 많이 가져온 뒤 걸러냅니다.
        """

        # 질문을 임베딩 벡터로 변환합니다.
        query_vector = self.embedding_service.embed_query(query)

        # 접근 제어가 필요 없으면(요청 부서 정보가 없으면) 기존과 동일하게 top_k만 조회합니다.
        if not requester_department:
            return self.vector_store.search(query_vector, top_k)

        # 필터링으로 결과가 줄어들 수 있으므로 넉넉히 더 가져옵니다.
        candidates = self.vector_store.search(query_vector, top_k * 4)

        # 권한이 있는 청크만 남기고 top_k개로 자릅니다.
        allowed = [
            item for item in candidates if self._can_access(item, requester_department)
        ]
        return allowed[:top_k]

    # 청크 하나에 대해 요청 부서가 접근 가능한지 판단합니다.
    @staticmethod
    def _can_access(item: dict, requester_department: str) -> bool:
        """allowed_departments가 비어있으면 전체 공개, 값이 있으면 목록에 포함된 부서만 허용합니다."""

        allowed_departments = item.get("allowed_departments")

        # 값이 없으면(전체 공개 문서) 누구나 접근 가능합니다.
        if not allowed_departments:
            return True

        # 콤마로 구분된 허용 부서 목록에 요청 부서가 포함되는지 확인합니다.
        allowed_list = [d.strip() for d in allowed_departments.split(",") if d.strip()]
        return requester_department in allowed_list

    # RAG 답변과 출처를 생성합니다.
    def ask(
        self, question: str, top_k: int, requester_department: str | None = None
    ) -> dict:
        """검색 문맥을 근거로 답변을 생성합니다."""

        # 질문과 유사한 문서를 검색합니다. (부서 접근 제어 적용)
        results = self.search(
            question, top_k, requester_department=requester_department
        )

        # 검색 결과가 없으면 먼저 인덱스를 만들라는 메시지를 반환합니다.
        if not results:
            message = "검색 결과가 없습니다. 먼저 /api/rag/rebuild를 실행하세요."

            # 부서 정보가 있었는데 결과가 0건이면, 인덱스 문제가 아니라 권한 문제일 수 있음을 안내합니다.
            if requester_department:
                message = (
                    f"'{requester_department}' 권한으로 열람 가능한 관련 문서를 찾지 못했습니다. "
                    "질문과 관련된 문서가 없거나, 접근 권한이 없는 문서일 수 있습니다."
                )

            return {"answer": message, "sources": [], "matches": []}

        # 각 검색 결과를 출처와 본문이 포함된 문맥 문자열로 변환합니다.
        context = "\n\n".join(
            f"[출처: {item.get('source', 'unknown')}]\n{item.get('content', '')}"
            for item in results
        )

        # RAG Prompt 템플릿을 조회합니다.
        prompt_template = self.prompt_service.get_prompt("rag_answer")

        # OpenAI 또는 로컬 대체 방식으로 답변을 생성합니다.
        answer = self.openai_service.answer_with_context(
            question=question,
            context=context,
            prompt_template=prompt_template,
        )

        # 중복되지 않은 출처 파일명을 순서대로 구성합니다.
        sources = list(dict.fromkeys(item.get("source", "unknown") for item in results))

        # 답변, 출처, 검색 상세 결과를 반환합니다.
        return {"answer": answer, "sources": sources, "matches": results}

    # ------------------------------------------------------------------
    # 문서 요약
    # ------------------------------------------------------------------
    def _resolve_file_path(self, filename: str):
        """document_source 설정에 맞춰 filename에 대응하는 실제 파일 경로를 찾습니다."""

        # mysql 모드면 documents 테이블에서 경로를 조회합니다.
        if self.document_source.lower() == "mysql" and self.mysql_service is not None:
            record = self.mysql_service.get_document(filename)
            if record is None:
                return None
            return Path(record["file_path"]), record

        # filesystem 모드면 docs 폴더에서 바로 경로를 계산합니다.
        path = self.document_service.settings.docs_dir / filename
        return (path, {"filename": filename}) if path.exists() else None

    # 문서 1건 전체를 요약합니다.
    def summarize_document(self, filename: str) -> dict:
        """지정한 문서의 전체 텍스트를 읽어 요약을 생성합니다.

        문서가 길면(예: 규정집 수십 페이지) 전체를 한 번에 LLM에 넣기보다,
        먼저 청크 단위로 나눠 각각 짧게 요약한 뒤(map), 그 요약들을 다시
        합쳐 최종 요약을 만듭니다(reduce) - 이른바 map-reduce 요약 방식입니다.
        """

        resolved = self._resolve_file_path(filename)
        if resolved is None:
            raise FileNotFoundError(f"문서를 찾을 수 없습니다: {filename}")

        path, meta = resolved
        full_text = self.document_service._read_file(path)

        if not full_text.strip():
            return {
                "filename": filename,
                "summary": "문서에서 추출된 텍스트가 없습니다.",
                "method": "empty",
            }

        # 아주 짧은 문서는 굳이 map-reduce할 필요 없이 바로 요약합니다.
        chunks = self.document_service._split_text(full_text)
        summary_prompt = self.prompt_service.get_prompt("document_summary")

        if self.openai_service.client is None:
            # API 키가 없을 때는 앞부분 발췌 + 기초 통계로 대체합니다. (완전한 요약은 아님)
            preview = full_text.strip()[:400]
            return {
                "filename": filename,
                "summary": (
                    "[로컬 데모 요약]\n"
                    "OPENAI_API_KEY가 없어 실제 GPT 요약은 생략했습니다.\n"
                    f"문서 길이: 약 {len(full_text)}자, 청크 {len(chunks)}개\n\n"
                    f"본문 앞부분 미리보기:\n{preview}..."
                ),
                "method": "demo",
                "department": meta.get("department"),
                "category": meta.get("category"),
            }

        # 청크가 몇 개 안 되면(짧은 문서) 굳이 map 단계 없이 한 번에 요약합니다.
        if len(chunks) <= 3:
            final_summary = self.openai_service.answer(
                question=summary_prompt.format(document_text=full_text),
                system_prompt="당신은 사내 규정 문서를 정확하고 간결하게 요약하는 어시스턴트입니다.",
            )
            method = "single_pass"
        else:
            # map 단계: 각 청크를 짧게 요약합니다.
            partial_summaries = []
            for chunk in chunks:
                partial = self.openai_service.answer(
                    question=f"다음 문서 일부를 3문장 이내로 핵심만 요약하세요:\n\n{chunk}",
                    system_prompt="당신은 사내 규정 문서를 정확하고 간결하게 요약하는 어시스턴트입니다.",
                )
                partial_summaries.append(partial)

            # reduce 단계: 부분 요약들을 다시 합쳐 최종 요약을 만듭니다.
            combined = "\n\n".join(partial_summaries)
            final_summary = self.openai_service.answer(
                question=summary_prompt.format(document_text=combined),
                system_prompt="당신은 여러 부분 요약을 하나의 일관된 요약으로 종합하는 어시스턴트입니다.",
            )
            method = "map_reduce"

        return {
            "filename": filename,
            "summary": final_summary,
            "method": method,
            "department": meta.get("department"),
            "category": meta.get("category"),
            "version_date": (
                str(meta.get("version_date")) if meta.get("version_date") else None
            ),
        }
