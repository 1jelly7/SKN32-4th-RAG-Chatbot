# [팀 공유 자료 3] 다른 팀에게 요청할 개발 내용

- **작성자**: rag_sales 담당 (PM 겸임)
- **읽는 대상**: 통합(backend) 담당 우선, 필요한 항목은 rag_purchase 담당도 함께
- **목적**: `query_sales`/`query_purchase` 구현을 시작하기 전에, **우리(sales·purchase)
  힘으로는 못 고치는 다른 파트 소유 코드의 문제**를 한곳에 모아서 요청한다.
- **근거**: 전부 실제 코드를 읽고 확인한 사실이다. 추측으로 적은 항목은 없다.
  ([SPEC.md](../../SPEC.md), [01_rag_sales_text2sql.md](01_rag_sales_text2sql.md),
  [02_rag_purchase_text2sql.md](02_rag_purchase_text2sql.md)에서 이미 언급된 항목들을
  실행 가능한 요청 목록으로 재정리했다)
- **사용법**: [docs/ownership.md](../ownership.md)의 "공통 영역 변경 절차"에 따라, 이
  목록을 그대로 GitHub Issue로 옮겨서 관련 담당자를 리뷰어로 지정하는 걸 권장한다.

---

## 우선순위 요약

| 우선순위 | 의미 | 항목 수 |
|---|---|---|
| **P0** | 지금 당장 막혀있음 — 우리가 구현을 시작해도 실행 자체가 안 됨 | 2건 |
| **P1** | 이번 기능(표·SQL 노출)이 제대로 동작하려면 필요 | 9건 |
| **P2** | 정합성·정리 차원, 급하지 않음 | 2건 |
| **보류** | 이번 범위에서 요청하지 않음(사유 명시) | 1건 |

---

## P0 — 지금 당장 막혀있는 것

### P0-1. `app/agent/nodes.py`의 존재하지 않는 모듈 import

- **대상팀**: 통합(backend)
- **근거**: [app/agent/nodes.py:17](../../app/agent/nodes.py)
  ```python
  from mcp_servers.data_tools.finance.query import query_finance
  ```
  `finance` 폴더는 이미 `purchase`로 이름이 바뀌어서 존재하지 않는다
  (`2c10b07 Replace finance domain with purchase across project` 커밋 참고).
- **영향**: **현재 브랜치에서 `app/agent/graph.py`를 import하는 순간 실패한다.**
  `query_sales`/`query_purchase`를 아무리 잘 만들어도 LangGraph 전체가 못 돈다.
- **요청 내용**: `finance` → `purchase`로 import 경로 수정, 관련 변수명(`query_finance`
  등)도 함께 정리.
- **완료 기준**: `python -c "import app.agent.graph"`가 에러 없이 통과.

### P0-2. `.env`에 읽기 전용 DB 계정 정보가 없음

- **대상팀**: 통합(backend) — 계정 발급은 sales/purchase가 각자 하더라도, `.env` 항목
  추가와 [app/core/config.py](../../app/core/config.py)의 필드 정리는 통합 담당과
  맞춰야 한다.
- **근거**: `.env`에 `MYSQL_WRITE_*`(ETL용)만 있고 `MYSQL_READ_*`가 없다. README의
  "Read/write separation" 원칙([docs/interface.md](../interface.md))을 지키려면 반드시
  필요하다.
- **요청 내용**:
  ```env
  MYSQL_READ_HOST=localhost
  MYSQL_READ_USER=chatbot_reader          # sales용
  MYSQL_READ_PASSWORD=
  SALES_DB_DATABASE=sales
  ```
  추가로 **sales와 purchase가 같은 조회 계정을 쓸지, 따로 쓸지**를 통합·구매 담당과
  함께 정해야 한다. **권장: 계정을 분리한다** — 그래야 "sales 계정으로는 purchase
  데이터를 원천적으로 못 본다"는 방어(01번 문서 8.1절)가 DB 권한 레벨에서 실제로
  성립한다. 계정을 하나로 합치면 이 방어가 무력화된다.
- **완료 기준**: sales·purchase 각자의 `query_readonly()`가 실제로 연결에 성공.

---

## P1 — 표·SQL 노출 기능이 제대로 동작하려면 필요한 것

이번에 `query_sales`가 SQL과 결과 표를 화면에 노출하기로 하면서(D-14), 기존
[app/web/chat.js](../../app/web/chat.js) 등의 코드가 실제로 그 역할을 감당할 수 있는지
확인했다. 아래 9건은 전부 그 과정에서 실제 코드를 읽고 발견한 것이다.

### P1-1. 사용자 입력·DB 값·LLM 답변에 이스케이프 처리가 없음 (보안, 최우선)

- **대상팀**: 통합(backend)
- **근거**: [app/web/chat.js](../../app/web/chat.js)가 다음을 전부 아무 처리 없이
  `innerHTML`에 그대로 꽂아넣는다.
  ```js
  messages.innerHTML += `<div class="msg user"><b>나</b>${question}</div>`;   // 사용자 입력
  `<td>${cell ?? ''}</td>`                                                     // DB 조회 값
  `<pre>${table.sql}</pre>`                                                    // 생성된 SQL
  data.answer.replace(/\n/g, '<br>')                                           // LLM 답변
  ```
- **영향**: 질문창에 `<img src=x onerror=alert(1)>`을 입력하면 그대로 실행된다.
  DB 값·LLM 답변 경로로도 같은 문제가 생길 수 있다. **표와 SQL을 더 많이 보여줄수록
  이 문제의 노출 면적이 커진다.**
- **요청 내용**: HTML 특수문자 이스케이프 함수 하나 추가해서 위 4곳에 전부 적용.
  ```js
  function esc(v) {
    return String(v ?? '').replace(/[&<>"']/g, c =>
      ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  ```
- **완료 기준**: 질문창에 `<script>alert(1)</script>` 입력 시 실행되지 않고 문자
  그대로 화면에 표시됨.

### P1-2. 두 번째 질문부터 이전 표·그래프가 깨짐

- **대상팀**: 통합(backend)
- **근거**: [app/web/chat.js:81,111](../../app/web/chat.js)가 `messages.innerHTML +=`
  방식을 쓰는데, 이건 기존 DOM 전체를 문자열로 다시 그린다. `<canvas>`처럼 이미 그려진
  요소는 태그만 복원되고 내용은 사라진다.
- **요청 내용**: `insertAdjacentHTML('beforeend', ...)`로 교체.
- **완료 기준**: 질문을 3번 연속 했을 때 첫 번째 질문의 표가 그대로 남아있음.

### P1-3. 표가 옆으로 넘칠 때 스크롤이 안 됨

- **대상팀**: 통합(backend)
- **근거**: [app/web/style.css:24](../../app/web/style.css)의 `.table-wrap`에
  `overflow-x` 설정이 없고, `body`는 `max-width: 820px`로 좁다. 우리 `v_sales_order`
  뷰는 19칼럼이라, 나열형 질문("2025년 1~6월 주문 내역")에서 표가 화면 밖으로 넘친다.
- **요청 내용**:
  ```css
  .table-wrap { overflow-x: auto; }
  .data-table { min-width: max-content; }
  ```
- **완료 기준**: 칼럼 10개 이상인 표에서 페이지 전체가 아니라 표 안에서만 가로
  스크롤됨.

### P1-4. 결과 0건일 때 "없다"는 안내가 최종 답변에 정확히 전달되는지 확인 필요

- **대상팀**: 통합(backend)
- **근거**: `query_sales`/`query_purchase`는 결과가 0건이면 "해당 조건의 데이터가
  없습니다 + 보유 기간 + 다시 확인해서 질문해달라"는 안내 문구를 evidence에 담아
  반환한다(SPEC.md 6.2절). **0건은 오류가 아니라 사실**이므로, 이 안내가 화면에
  뜨는 최종 답변(`app/agent/nodes.py`의 `answer_synthesis`)에 그대로 반영되는지
  확인이 필요하다.
- **요청 내용**: `answer_synthesis`가 evidence의 안내 문구를 누락 없이 답변에 포함하는지
  확인. (참고: 이전 버전 요청에서는 "0건이면 표 자체가 안 그려져서 SQL도 안 보인다"는
  걸 문제로 지적했는데, 다시 검토해보니 핵심은 SQL 노출 여부가 아니라 **"없다"는
  사실이 정직하게 전달되는지**다. SQL을 억지로 보여줄 필요는 없다.)
- **완료 기준**: "2026년 8월 매출 알려줘"처럼 항상 0건인 질문에 대해, 화면 답변에
  "없다 + 보유 기간 + 다시 확인해달라"가 명확히 보임.

### P1-5. 표 숫자와 답변 문장의 숫자 표기가 서로 다르게 보임

- **대상팀**: 통합(backend)
- **근거**: [app/agent/nodes.py](../../app/agent/nodes.py)의 `_json_safe`가
  `Decimal→float`으로 바꿔서 표에는 `6165466.5`처럼 찍히는데, 같은 화면의 답변
  문장에는 LLM이 "약 616만 JOD"처럼 다르게 쓴다. 같은 값인데 달라 보여서 사용자가
  신뢰하지 못한다.
- **요청 내용**: 표의 숫자 칼럼은 천단위 콤마 + 소수점 2자리 고정 + 통화 단위(JOD)
  표기. 우측 정렬.
- **완료 기준**: 표와 답변 문장에서 같은 값이 같은 형식으로 보임.

### P1-6. `rows_for_llm`을 답변 생성 프롬프트가 실제로 쓰도록 연결

- **대상팀**: 통합(backend)
- **근거**: `query_sales`가 화면용 `rows`(전체)와 LLM용 `rows_for_llm`(최대 50행)을
  나눠서 반환하기로 했다(SPEC.md 8.3절). 그런데 [app/agent/nodes.py](../../app/agent/nodes.py)의
  `answer_synthesis`는 지금 `evidence` 전체를 그대로 프롬프트에 넣는다.
- **요청 내용**: `answer_synthesis`가 `rows`가 아니라 `rows_for_llm`을 프롬프트 재료로
  쓰도록 한 줄 수정. (지금 당장 데이터가 작아서 급한 문제는 아니지만, 나중에 결과가
  커지면 프롬프트 토큰이 갑자기 불어난다)
- **완료 기준**: 결과가 50행 넘는 질문에서 LLM 프롬프트에 50행만 들어감(로그로 확인
  가능).

### P1-7. 조회 캐시가 데이터 갱신을 못 따라감

- **대상팀**: 통합(backend)
- **근거**: [app/cache/key.py:20](../../app/cache/key.py)이 캐시 키 재료로 쓰는
  `database_freshness_bucket` 값을 채워주는 코드가 어디에도 없다. 항상 비어있다.
- **영향**: ETL로 데이터를 새로 넣어도 DB 답변 TTL(5분, [app/cache/policy.py:15](../../app/cache/policy.py))
  동안 예전 표가 그대로 나올 수 있다. 지금은 ETL을 자주 안 돌려서 안 보이지만, 시연
  중 데이터를 갈아끼우면 바로 드러난다.
- **요청 내용**: ETL 실행 시각이나 버전을 `database_freshness_bucket`에 채우는 로직
  추가. (구현 방식은 통합 담당 판단에 맡김 — 예: ETL이 마지막 실행 시각을 파일/DB에
  남기고 라우터가 그 값을 읽는 방식 등)
- **완료 기준**: ETL 재실행 후 같은 질문의 캐시 키가 바뀜.

### P1-8. `metadata` 응답 형식에 새 필드 반영

- **대상팀**: 통합(backend)
- **근거**: [docs/interface.md](../interface.md)의 공통 응답 형식에 `views_used`,
  `data_coverage`, `retry_count` 같은 필드가 아직 없다. `query_sales`/`query_purchase`가
  이 필드들을 채워 반환하기로 했다(SPEC.md 8.4절).
- **요청 내용**: `docs/interface.md`의 "Tool 3: 판매 데이터 조회" 응답 예시와 공통
  `metadata` 설명에 위 필드 추가. ([docs/ownership.md](../ownership.md)의 "공통 영역
  변경 절차"에 따라 통합 담당과 도메인 담당이 함께 검토)
- **완료 기준**: `docs/interface.md`가 실제 반환 형식과 일치.

### P1-9. `mcp_servers/data/`와 `mcp_servers/data_tools/` 중복 정리

- **대상팀**: 통합(backend)
- **근거**: `mcp_servers/data_tools/`(우리가 쓰는 경로) 말고 `mcp_servers/data/`라는
  폴더가 하나 더 있다(`mysql.py`, `query.py`, `schema.py`, `server.py`, `text2sql.py`,
  `sql_guard.py` 등 이름이 겹침).
- **요청 내용**: 어느 쪽이 최종본인지 확인하고, 안 쓰는 쪽은 삭제하거나 명확히
  구분되는 용도를 문서화. (구현 중 헷갈림 방지 차원 — 급하지 않지만 착수 전에
  한 번은 확인 필요)
- **완료 기준**: 팀 전체가 어느 경로가 실제 사용 경로인지 합의.

---

## P2 — 정합성·정리 (급하지 않음)

### P2-1. `logs/` 디렉터리에 MCP 조회 로그 추가

- **대상팀**: 통합(backend)
- **근거**: [docs/ownership.md](../ownership.md)의 로그 저장 정책 표에 `app.log.txt`,
  `rag.log.txt`, `etl_purchase.log.txt`, `etl_sales.log.txt`는 있는데, **MCP 도구
  자체의 조회 로그**(SQL 생성, 가드 거부, EXPLAIN 실패, 실행 결과) 항목이 없다.
- **요청 내용**: `logs/mcp_sales.log.txt`, `logs/mcp_purchase.log.txt`를 로그 정책
  표에 추가하고 `.gitignore` 규칙도 기존 로그 파일과 동일하게 적용.
- **완료 기준**: `docs/ownership.md` 로그 표 갱신, `.gitignore`에 반영.

### P2-2. `settings.finance_db_database` 필드명 정리

- **대상팀**: 통합(backend)
- **근거**: [app/core/config.py:31](../../app/core/config.py)에 `finance_db_database: str = "purchase"`로
  이름만 옛날 이름(`finance`)이 남아있다. 값은 정상 동작하지만 헷갈린다.
- **요청 내용**: `purchase_db_database`로 이름 변경 (급하지 않음 — 기능상 문제는 아님).
- **완료 기준**: 필드명과 실제 값이 일치.

---

## 보류 — 이번에는 요청하지 않는 것

### 채팅창 그래프(Chart.js) 관련 전부

- **사유**: PM 판단으로 이번 범위에서 뺐다. 표와 SQL 노출까지만 이번에 처리하고,
  막대그래프 렌더링은 나중에 별도로 다시 다룬다.
- **나중에 참고할 것**: [01_rag_sales_text2sql.md 14.2절](01_rag_sales_text2sql.md)에
  Chart.js 관련 이슈(CDN 오프라인 문제, "그래프 그릴 수 있는 표"의 조건)를 미리
  정리해뒀다. 재개할 때 그대로 이어서 쓰면 된다.

---

## 요약 표 (복붙용)

| 코드 | 제목 | 대상팀 | 우선순위 |
|---|---|---|---|
| P0-1 | nodes.py의 finance import 오류 수정 | 통합 | P0 |
| P0-2 | .env 읽기 전용 DB 계정 추가 (sales/purchase 분리 권장) | 통합 | P0 |
| P1-1 | XSS 이스케이프 처리 | 통합 | P1 |
| P1-2 | innerHTML += 버그 수정 | 통합 | P1 |
| P1-3 | 표 가로 스크롤 CSS | 통합 | P1 |
| P1-4 | 0건 안내 문구가 최종 답변에 반영되는지 확인 | 통합 | P1 |
| P1-5 | 표·답변 숫자 표기 통일 | 통합 | P1 |
| P1-6 | rows_for_llm을 답변 생성에 연결 | 통합 | P1 |
| P1-7 | 캐시 freshness bucket 채우기 | 통합 | P1 |
| P1-8 | interface.md metadata 필드 확장 | 통합 | P1 |
| P1-9 | mcp_servers/data/ 중복 정리 | 통합 | P1 |
| P2-1 | MCP 조회 로그 파일 정책 추가 | 통합 | P2 |
| P2-2 | finance_db_database 필드명 정리 | 통합 | P2 |
| 보류 | 채팅창 그래프 기능 | 통합 | 나중에 |

---

## 참고

- 전체 스펙: [SPEC.md](../../SPEC.md)
- sales 가이드: [01_rag_sales_text2sql.md](01_rag_sales_text2sql.md)
- purchase 가이드: [02_rag_purchase_text2sql.md](02_rag_purchase_text2sql.md)
- 프로젝트 공통 규칙: [RULE.md](../../RULE.md)
