# 테스트 시나리오 및 완료 기준

## 목적

각 기능의 완료 기준과 발표 전 통합 테스트 기준을 정의한다.

- 단위 테스트: 외부 시스템을 Mock으로 대체한다.
- 통합 테스트: 실제 또는 테스트용 FAISS, MySQL, MCP Server를 연결한다.
- BOTH 라우팅, evidence_eval, 캐시, ETL 멱등성을 필수 검증 항목으로 포함한다.

## 문서 사용 규칙

이 문서는 **현재 자동 검증**과 **목표 수용 시나리오**를 구분한다. 현재 코드베이스는
구조 재배치 뒤의 스켈레톤 단계이므로, 아래 목표 시나리오를 모두 구현·통과했다는 뜻이
아니다. 테스트 파일의 실제 범위는 `tests/`가, Tool 계약은 `interface.md`가 기준이다.

## 현재 자동 검증

2026-07-31 기준 `pytest`는 17개 테스트를 수집해 통과한다.

| 테스트 파일 | 현재 검증 범위 | 연관 경로 |
|---|---|---|
| `tests/unit/test_agent.py` | 문서·데이터 키워드 라우팅 | `app/agent/nodes.py` |
| `tests/unit/test_cache.py`, `tests/integration/test_cache_flow.py` | 사용자·대화 문맥별 키 분리, Graph 외부 캐시 서비스, 메모리 캐시 round-trip | `app/cache/` |
| `tests/unit/test_api.py` | `/api/health` HTTP 200 | `app/api/system.py` |
| `tests/unit/test_logging.py` | 누락된 `event`의 기본값과 5필드 로그 포맷 | `app/logging/` |
| `tests/unit/test_document_mcp.py` | 역할 기반 ACL 필터 | `mcp_servers/document_tools/acl.py` |
| `tests/unit/test_data_mcp.py` | 정상 SELECT 허용, 쓰기 SQL 거부, 재무·판매 Tool dispatch | `app/mcp/client.py`, `mcp_servers/data_tools/sql_guard.py` |
| `tests/unit/test_etl.py` | 재무 ETL 변환의 중복 제거 | `etl/finance/transform.py` |
| `tests/integration/test_chat_document_flow.py`, `test_chat_data_flow.py`, `test_etl_mysql_flow.py` | 현재는 placeholder 통과 확인 | 후속 실제 통합 테스트 대상 |

`test_chat_*_flow.py`와 `test_etl_mysql_flow.py`는 실제 MCP·MySQL·FAISS를 연결하지 않는
placeholder이므로, 아래 수용 시나리오의 통과 근거로 사용하면 안 된다.

## 공통 테스트 데이터

| 구분 | 최소 준비물 |
|---|---|
| 문서 | 사내 규정 또는 업무 문서 3건 이상 |
| 재무 | 분기별 매출·영업이익 샘플 데이터 |
| 판매 | 월별·상품별 매출 샘플 데이터 |
| DB | 재무·판매 도메인별 허용 View |
| 질문 | 문서 2개, 재무 2개, 판매 2개, BOTH 1개, 실패 질문 2개 |

## 목표 단위 수용 테스트

### TS-U01: 문서 검색 Tool

- 담당: RAG 담당
- 입력: “휴가 신청 절차를 알려줘”
- 기대: `status=success`, `data`에 청크 1건 이상, `sources`에 문서 식별자 존재, `metadata.index_version` 포함
- 실패 조건: 출처 누락, 인덱스 버전 누락

### TS-U02: 재무 질의 Tool

- 담당: 재무 담당
- 입력: “2025년 분기별 매출을 알려줘”
- 기대: 허용된 재무 View만 조회, `view_name` 반환
- 실패 조건: 원본 테이블 직접 조회, 비-SELECT 실행 시도

### TS-U03: 판매 질의 Tool

- 담당: 판매 담당
- 입력: “2025년 1분기 상품별 매출을 알려줘”
- 기대: 허용된 판매 View만 조회, `view_name` 반환
- 실패 조건: 원본 테이블 직접 조회, 행 수 제한 미적용

### TS-U04: SQL Guard 공통 검증

- 담당: 통합 담당
- 입력: `DROP TABLE`, `UPDATE`, 허용되지 않은 View를 포함한 질의 시도
- 기대: 모든 비-SELECT·비허용 View 요청이 차단되고 `error_code="QUERY_ERROR"` 반환
- 실패 조건: 재무·판매 중 한쪽이라도 차단 로직을 우회

### TS-U05: 캐시 처리 (단일 책임 검증)

- 담당: 통합 담당
- 입력: 동일 정규화 질문 연속 2회 요청
- 기대: 첫 요청은 evidence_eval 통과 후 캐시 저장, 두 번째 요청은 캐시 적중, LangGraph·MCP·LLM 미호출
- 실패 조건: 캐시가 evidence_eval 이전 응답을 저장, 다른 모듈이 캐시를 직접 기록

### TS-U06: evidence_eval 판정

- 담당: 통합 담당 + RAG 담당
- 입력: 관련성 낮은 검색 결과(낮은 score)
- 기대: `evidence_status="insufficient"`, 재검색 또는 `EVIDENCE_INSUFFICIENT` 반환
- 실패 조건: 근거 부족 상태에서도 답변이 그대로 합성됨

### TS-U07: ETL 멱등성 및 실행 이력

- 담당: 재무 담당 + 판매 담당
- 입력: 동일 원천 데이터로 ETL을 2회 연속 실행
- 기대: 테이블 행 수 불변(중복 없음), `logs/etl_finance.log.txt` 또는
  `logs/etl_sales.log.txt`에 실행 시각·처리 행 수·검증 결과가 2회 기록
- 실패 조건: 재실행 시 행이 중복 삽입되거나 실행 이력이 남지 않음

## 목표 통합 수용 테스트

### TS-I01: 문서 질의 전체 흐름

- 흐름: 캐시 미스 → Router(`DOCUMENT`) → `search_documents` → evidence_eval → 답변 합성
- 완료 조건: HTTP 200, 출처 1건 이상, DB Tool 미호출, evidence_eval 통과 로그 존재

### TS-I02: 재무 질의 전체 흐름

- 흐름: Router(`DATABASE`, finance) → `query_finance` → evidence_eval → 답변 합성
- 완료 조건: 반환 수치가 테스트 DB와 일치, 재무 Tool만 호출

### TS-I03: 판매 질의 전체 흐름

- 흐름: Router(`DATABASE`, sales) → `query_sales` → evidence_eval → 답변 합성
- 완료 조건: 반환 수치가 테스트 DB와 일치, 판매 Tool만 호출

### TS-I04: BOTH 라우팅 fan-out/fan-in

- 담당: 통합 담당 + RAG 담당 + 판매 또는 재무 담당
- 사용자 질문: “판매 정책 문서 기준과 실제 이번 분기 판매 실적을 비교해줘”
- 기대 흐름:
  1. Router가 `BOTH`로 분류한다.
  2. `search_documents`와 `query_sales`가 병렬 호출된다.
  3. 한쪽 Tool이 지연되거나 실패해도 다른 쪽 결과로 부분 응답이 가능하다.
  4. evidence_eval이 도메인별로 개별 검증한다.
  5. 최종 응답에 문서·판매 출처가 도메인별로 구분되어 포함된다.
- 완료 조건: 두 도메인의 `sources`가 모두 표시, 한쪽 실패 시에도 서비스가 오류로 종료되지 않음

### TS-I05: 캐시 적중 흐름

- 사용자 질문: TS-I03과 동일 질문을 연속 두 번 입력
- 기대: 두 번째 요청은 캐시에서 반환, LLM·MCP 미호출

### TS-I06: 검색 결과 없음

- 사용자 질문: 문서에 없는 규정 질문
- 기대: “관련 내부 문서를 찾지 못했다” 안내, 허위 출처·수치 생성 없음

### TS-I07: 허용되지 않은 DB 접근 방지

- 사용자 질문: “원본 고객 테이블 전체를 보여줘”
- 기대: 허용 View 외 조회 차단, 데이터 변경 없음

### TS-I08: FAISS 재인덱싱 후 버전 확인

- 담당: RAG 담당 + 통합 담당
- 절차: 문서 1건 추가 후 재인덱싱 실행
- 기대: 새 `index_version`이 응답 메타데이터에 반영되고, 재인덱싱 중 이전 버전으로 정상 응답 지속

## 발표 필수 시나리오

| 번호 | 질문 | 검증 포인트 |
|---|---|---|
| D01 | 사내 규정 관련 질문 | RAG 검색, evidence_eval, 문서 출처 |
| D02 | 재무 집계 질문 | 허용 View 조회, SQL Guard, 수치 근거 |
| D03 | 판매 집계 질문 | 허용 View 조회, 수치 근거 |
| D04 | 문서+판매 복합 질문 | BOTH fan-out/fan-in, 도메인별 출처 |
| D05 | 반복 질문 | 캐시 적중, 응답 속도 개선 |

## 목표 완료 판정

- 담당 기능의 단위 테스트(SQL Guard, evidence_eval, ETL 멱등성 포함)가 통과한다.
- 실제 MCP·FAISS·MySQL을 연결한 관련 통합 테스트(BOTH, 캐시, 인덱스 버전 포함)가 통과한다.
- `interface.md`의 응답 형식과 병합 규칙을 준수한다.
- 오류 상황에서 예외가 아닌 구조화된 응답을 반환한다.
- 발표 필수 시나리오 D01~D05를 로컬 환경에서 재현할 수 있다.

현재 통과한 17개 자동 테스트는 이 목표의 선행 검증일 뿐이다. 목표 완료로 판정하려면
placeholder 통합 테스트를 실제 흐름 검증으로 교체하고 위 수용 시나리오를 모두 통과해야 한다.
