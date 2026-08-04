# 사내 지식 RAG·Text2SQL MCP 챗봇

사내 문서(정책·규정)와 정형 업무 데이터(판매·구매)를 하나의 채팅창에서 answer하는
사내 지식 챗봇입니다. 질문의 성격에 따라 문서 기반 RAG와 MySQL 기반 Text2SQL을
자동으로 선택하거나 함께 사용합니다.

---

## 팀 소개

<table>
  <tr>
    <td align="center" width="220"><img src="docs/assets/team/문동원.png" width="200"/></td>
    <td align="center" width="220"><img src="docs/assets/team/박회종.png" width="200"/></td>
    <td align="center" width="220"><img src="docs/assets/team/이태혁.png" width="200"/></td>
    <td align="center" width="220"><img src="docs/assets/team/이호원.png" width="200"/></td>
  </tr>
  <tr>
    <td align="center"><b>문동원</b></td>
    <td align="center"><b>박회종</b></td>
    <td align="center"><b>이태혁</b></td>
    <td align="center"><b>이호원</b></td>
  </tr>
  <tr>
    <td align="center">PM + rag_sales</td>
    <td align="center">backend</td>
    <td align="center">rag_pdf</td>
    <td align="center">rag_purchasing</td>
  </tr>
</table>

---

## 프로젝트 소개

사용자가 웹 채팅 화면에서 질문하면, 시스템이 질문 성격을 판별해 아래 중 하나로
처리합니다.

- **사내 문서 근거가 필요한 질문** → FAISS 기반 RAG로 사내 정책·규정 문서를 검색
- **정형 업무 데이터가 필요한 질문** → MySQL 기반 Text2SQL로 판매/구매 데이터를 조회
- **둘 다 필요한 질문** → 두 경로를 함께 조회해 근거를 합쳐 답변

문서와 MySQL은 애플리케이션이 직접 접근하지 않고, `Document MCP`/`Data MCP`라는
표준 Tool 경계를 통해서만 접근합니다. 같은 질문은 Answer Cache에서 먼저 찾아
불필요한 LLM·DB 호출을 줄입니다.

## 주요 기능

- **질문 자동 라우팅**: `GENERAL`(일반 지식) / `DOCUMENT`(사내 문서) / `DATABASE`(업무
  데이터) / `BOTH`(문서+데이터) 4가지로 질문을 자동 분류
- **사내 문서 RAG**: 정책·규정 PDF/문서를 벡터 검색해 근거 기반으로 답변
- **Text2SQL (판매·구매)**: 자연어 질문을 SQL로 변환해 조회하고, 생성된 SQL과 결과
  표를 화면에 함께 보여줌
- **채팅 그래프**: 조회 결과를 막대/꺾은선 그래프로 시각화
- **근거 기반 답변(Evidence-grounded)**: 검색·조회 근거가 있는 범위 안에서만 답변,
  없으면 정직하게 "없다"고 안내
- **Answer Cache**: 동일 질문 재요청 시 LLM·DB 호출 없이 즉시 응답
- **로그인·권한(RBAC)**: 역할(admin/hr/finance)별로 접근 가능한 데이터 범위를 구분

## 시스템 아키텍처

```text
사용자
  -> Static Web UI
  -> FastAPI POST /api/chat
  -> Answer Cache 조회
       -> Hit: 캐시 답변 즉시 반환
       -> Miss: LangGraph 실행
            -> Query Router (GENERAL / DOCUMENT / DATABASE / BOTH)
               -> DOCUMENT: Document MCP -> 문서 DB 경로 조회 -> 파일 로드 -> FAISS RAG
               -> DATABASE: Data MCP -> Text2SQL -> MySQL SELECT (읽기 전용 계정)
               -> BOTH: 위 두 경로를 함께 조회
            -> Evidence Eval (근거 검증)
            -> OpenAI 최종 답변 생성
            -> Answer Cache 저장
  -> Web UI에 답변·출처·표·그래프·캐시 여부 표시
```

MySQL 쓰기(ETL)와 읽기(챗봇 조회)는 계정을 분리해서, 챗봇이 원본 테이블을 직접
건드릴 수 없도록 설계했습니다. 자세한 경계는 [docs/architecture.md](docs/architecture.md)
참고.

## 기술 스택

| 영역 | 기술 | 용도 |
|---|---|---|
| Backend | Python, FastAPI | 웹 UI에 HTTP API 제공 |
| LLM | OpenAI | 라우팅 보조, Text2SQL, 최종 답변 생성 |
| Orchestration | LangGraph | 조건부 라우팅, 상태 전달, 노드 실행 제어 |
| External access | MCP | 문서 검색·DB 조회를 표준 Tool 경계로 분리 |
| RAG | FAISS + sentence-transformers | 사내 비정형 문서 검색 |
| DB | MySQL | 정형 업무 데이터(판매·구매·계정) 저장·조회 |
| Cache | Redis / In-memory | 동일 질문의 모델 호출 생략 |
| Chart | Chart.js | 조회 결과 그래프 시각화 |
| Test | pytest | 기능별 단위·통합 테스트 |

## 폴더 구조

```text
app/               FastAPI, LangGraph, 캐시, 인증(RBAC), 공통 로그
mcp_servers/
  document_tools/  Document MCP (사내 문서 RAG)
  data_tools/      Data MCP (sales/purchase Text2SQL, 도메인별 하위 폴더)
ingestion/         문서 수집·정제·임베딩·FAISS 인덱싱
etl/
  sales/           판매 도메인 ETL
  purchase/        구매 도메인 ETL
database/
  sales/, purchase/, account/, document/   도메인별 DDL·뷰·계정 스크립트
data/              원천 데이터, FAISS 인덱스
scripts/           일회성 배치 스크립트(데이터 시딩 등)
docs/              설계 문서, 팀 공유 자료, 진행 이력
tests/             단위·통합 테스트
```

## WBS (작업 분해 구조)

| 일자 | 주요 작업 |
|---|---|
| 수 | 주제 선정, RnR(역할과 책임) 정함 |
| 목 | 데이터 정하기 → GitHub 브랜치 생성·배포 → 백엔드 틀 완료 |
| 금 | 로컬 실행 시 정상 동작 확인 |
| 토 · 일 | 각자 담당 기능(function) 개발 |
| 일 | 각자 기능 개발 완료 |
| 월 | 머지 완료 → 통합 테스트 및 버그 fix → 각자 개발 파트 공유·설명 |
| 화 | 발표 자료 제작 |

## 실행 방법

로컬 실행·ETL·DB 셋업 등 상세 절차는 [README.md](README.md)를 참고하세요.

## 회고

<!-- 각자 아래 항목에 자유롭게 작성해주세요 -->

### 문동원

### 박회종

### 이태혁

### 이호원
