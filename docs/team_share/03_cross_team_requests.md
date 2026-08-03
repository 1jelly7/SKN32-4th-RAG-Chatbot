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
- **04번 문서와의 관계**: 이 문서는 여러 도메인에 걸친 **짧은 요청 목록**이다. 그래프
  기능처럼 구현 상세(필드 추가, 알고리즘 변경, 검증 체크리스트)가 긴 항목은 여기 다
  담지 않고 [04_chart_spec.md](04_chart_spec.md)로 분리했다 — 아래 P1-11 항목이 그
  문서를 가리킨다. 04번은 별도 요청이 아니라 이 목록의 한 항목(P1-11)을 자세히 푼
  것이다.
---

## 우선순위 요약

> 2026-08-02 sales 세션 갱신: `query_sales` 구현을 실제로 마치면서 아래 항목 중 다수의
> 상태가 바뀌었다. P0-1·P0-2(sales 쪽)·P1-1·P1-2는 **완료 확인**, P1-6·P1-8은 실제 구현
> 결과에 맞춰 **재작성**, 신규 항목 P1-10(envelope 확장)·P1-11(차트 UI, `04_chart_spec.md`
> 링크)을 추가했다. "보류"로 남겨뒀던 그래프 기능은 이번에 사용자가 범위에 다시 넣었다.

> 2026-08-03 추가: 실제 채팅 화면 테스트 중 새 P0 1건(purchase DB 접근 거부로 정상
> 질문이 502가 됨)과 4-1절 차트 버그 2건(04_chart_spec.md)을 발견해 추가했다.

| 우선순위 | 의미 | 항목 수 |
|---|---|---|
| **완료** | 이번 세션에 확인·구현됨 | 4건 |
| **P0** | 지금 당장 막혀있음 — 정상적인 질문도 실행이 안 됨 | 1건 |
| **P1** | 이번 기능(표·SQL·그래프 노출)이 제대로 동작하려면 필요 | 9건 + 차트 버그 2건(04번 문서) |
| **P2** | 정합성·정리 차원, 급하지 않음 | 2건 |

---

## 완료 — 이번 세션에 확인·구현됨

### (완료) 구 P0-1. `app/agent/nodes.py`의 존재하지 않는 모듈 import

- **상태**: 해결됨. Agent는 `MCPClient.purchase_query()`를 통해 정본 purchase Tool을
  호출하며, 앱 진입점 import로 경로가 검증된다(SPEC.md 14.1절 C-01).

### (완료) 구 P0-2. `.env` 읽기 전용 DB 계정 — sales 쪽 해결

- **상태**: sales는 해결됨. `SALES_READ_USER`/`SALES_READ_PASSWORD` +
  `app/core/config.py`의 `sales_read_user`/`sales_read_password` 필드로 `sales_reader`
  전용 조회 계정을 만들었다(SPEC.md 5절). `MYSQL_READ_*`는 건드리지 않아 purchase에
  영향이 없다.
- **아직 필요한 것**: purchase가 같은 패턴(`PURCHASE_DB_*`+`PURCHASE_READ_*`)을
  독립적으로 추가할 예정이다(사용자 확인: "purchase는 두자, 내일 팀원과 논의 후
  진행"). sales 쪽에서 미리 관찰한 바로는 purchase 담당이 `.env`에 자체 블록을
  추가하는 작업을 이미 진행 중이었다 — 통합 담당은 두 블록이 서로 겹치지 않는지만
  최종 확인하면 된다.

### (완료) 구 P1-1. XSS 이스케이프 처리

- **상태**: 이미 반영돼 있었다. `04_chart_spec.md` 작성 중 `chat.js`를 다시 읽어보니
  `escapeHtml()`이 사용자 입력·DB 값·LLM 답변 등 모든 출력 지점에 이미 적용돼 있었다
  (`367833c` 병합에서 반영된 것으로 보인다). 재발 방지를 위한 확인만 필요.

### (완료) 구 P1-2. `innerHTML +=` 버그

- **상태**: 이미 반영돼 있었다. `insertAdjacentHTML('beforeend', ...)`로 이미 바뀌어
  있어서 연속 질문에도 이전 표·차트가 사라지지 않는다. 각 `<canvas>` id가
  `chart-${Date.now()}-${chartCounter}`로 매번 고유해서 `.destroy()` 호출도 불필요하다
  (`04_chart_spec.md` 0절 참고).

---

## P0 — 지금 당장 막혀있는 것

### P0-3. (신규, 2026-08-03) purchase 조회가 DB 접근 거부로 항상 실패함

- **대상팀**: 통합(backend) 또는 rag_purchase 담당 (계정 발급은 purchase가, `mysql.py`
  연결 코드는 통합 담당 검토가 필요할 수 있음)
- **근거**: 채팅 화면에서 "공급업체별 발주액 알려줘"(정상적인 purchase 범위 질문, 도메인
  밖 아님)를 물으면 화면에 "서버 오류: 조회 서비스에서 오류가 발생했습니다."(502)가 뜬다.
  `query_purchase()`를 직접 호출해 재현한 실제 예외:
  ```
  OperationalError: (1044, "Access denied for user 'JangGGo'@'%' to database 'purchase'")
  ```
  [mcp_servers/data_tools/purchase/mysql.py](../../mcp_servers/data_tools/purchase/mysql.py)의
  `_get_default_client()`가 `settings.mysql_read_user`(공용 admin 계정 `JangGGo`)를 그대로
  쓰는데, 이 계정은 `purchase` DB에 대한 조회 권한이 없다. 도메인 라우팅(`route_data_domain`)
  자체는 정상 동작한다 — 문제는 순수하게 DB 계정 연결이다.
- **요청 내용**: sales가 `sales_reader` 패턴을 위해 만들어둔 것과 동일하게,
  `app/core/config.py`에 이미 `purchase_read_user`/`purchase_read_password` 필드를
  추가해뒀다(비어 있으면 `mysql_read_*`로 폴백). `mcp_servers/data_tools/purchase/mysql.py`의
  `_get_default_client()`가 `settings.purchase_read_user or settings.mysql_read_user`를
  쓰도록 한 줄 수정하고, `.env`의 `PURCHASE_READ_USER=purchase_reader`/
  `PURCHASE_READ_PASSWORD`(이미 존재)에 맞는 DB 권한(`purchase.*`에 `SELECT`)이 실제로
  부여돼 있는지 확인이 필요하다.
- **완료 기준**: "공급업체별 발주액 알려줘" 같은 purchase 질문에서 "서버 오류: 조회 서비스에서 오류가 발생했습니다."
대신 "다른 부서 데이터베이스는 열람할 수 없습니다." 같은 원인이 짐작 가는 문장이 뜬다.
 (502 자체를 없애야 한다는 뜻이 아니라, 사용자가 보는 문장만 명확해지면 된다.)

---

## P1 — 표·SQL·그래프 노출 기능이 제대로 동작하려면 필요한 것

이번에 `query_sales`가 SQL과 결과 표를 화면에 노출하기로 하면서(D-14), 기존
[app/web/chat.js](../../app/web/chat.js) 등의 코드가 실제로 그 역할을 감당할 수 있는지
확인했다. (구 P1-1·P1-2는 이미 해결돼 있었음을 확인해 위 "완료" 절로 옮겼다.)

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

### P1-6. (재작성) LLM 프롬프트용 행 수를 화면과 분리

- **대상팀**: 통합(backend)
- **상태 변경**: 초안(구 P1-6)은 `query_sales`가 `rows`(화면용 전체)와
  `rows_for_llm`(LLM용 50행)을 나눠 반환할 계획이었다. **실제로는 이 분리를 구현하지
  않았다** — `mcp_servers/data_tools/server.py::_execute_query`의 공통 envelope가
  `rows` 하나만 그대로 `data`에 실어 보내는 구조로 고정돼 있어서, sales가 아무리
  `rows_for_llm` 필드를 따로 만들어도 전달할 방법이 없었기 때문이다(SPEC.md 8.3·8.4절).
- **근거**: 데이터가 800건·5년치로 늘면서 `sales_order_lines` 뷰(2,207행) 같은 큰
  결과에서 `LIMIT 200`이 실제로 잘리기 시작했다(초안 작성 시점의 70건 데이터에서는
  "제일 큰 표도 192행"이라 이 문제가 없었다). 지금은 화면과 LLM이 똑같이 최대 200행을
  본다 — LLM 프롬프트 토큰이 늘어날 수 있다.
- **요청 내용**: 아래 P1-10(envelope 확장)이 먼저 되어야 순서상 가능하다. envelope가
  `metadata`를 통과시키게 되면, `answer_synthesis`가 `rows`를 그대로 쓰지 않고 앞
  N행만 잘라 프롬프트에 넣도록 수정.
- **완료 기준**: 결과가 큰 질문에서 LLM 프롬프트에 들어가는 행 수가 화면 표시 행 수보다
  작게 제한됨(로그로 확인 가능).

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

### P1-8. (재작성) `metadata` 응답 형식에 새 필드 반영

- **대상팀**: 통합(backend)
- **근거**: `query_sales`는 이제 실제로 `metadata`에 `views_used`, `data_coverage`,
  `retry_count`, `currency`, `truncated`, `chart_hint` 6개 필드를 채워 반환한다
  (SPEC.md 8.3절, `mcp_servers/data_tools/sales/query.py`). 하지만
  `mcp_servers/data_tools/server.py::_execute_query`가 성공 응답에서는 이 중
  `generated_sql`/`row_count`/`elapsed_ms` 3개로 줄이고, 실패 응답에서는 `metadata`를
  아예 빈 객체로 버린다(SPEC.md 8.4·9.1절). `docs/interface.md`도 이 실제 필드명과
  맞지 않는다.
- **요청 내용**: (1) `server.py::_execute_query`가 도메인이 반환한 `metadata` 전체(또는
  최소 `views_used`/`data_coverage`/`chart_hint`)를 통과시키도록 확장. (2) 그 다음
  `docs/interface.md`의 "Tool 3: 판매 데이터 조회" 응답 예시를 실제 필드명으로 갱신.
  ([docs/ownership.md](../ownership.md)의 "공통 영역 변경 절차"에 따라 통합 담당과
  도메인 담당이 함께 검토)
- **완료 기준**: `docs/interface.md`가 실제 반환 형식과 일치하고, sales의 `chart_hint`가
  응답까지 도달함(P1-11 차트 작업의 전제 조건이기도 하다).

### P1-10. (신규) `server.py` envelope가 도메인별 거절 사유·안내 문장을 전달하지 못함

- **대상팀**: 통합(backend)
- **근거**: sales 설계(SPEC.md 9.2절, D-08)는 "답할 수 없습니다"로 끝내지 않고 왜 안
  되는지·대안을 함께 안내하려 했다(예: "영업이익은 원가 정보가 없어 계산할 수
  없습니다. 매출 기준으로는 안내해 드릴 수 있습니다."). 그런데 `server.py`는 `rows`가
  비어있으면 이유를 가리지 않고 고정 문장 "조회 가능한 결과가 없습니다."로 덮어쓴다
  (`_error_envelope`, `error_code: NO_RESULT`). 범위 밖 질문·답할 수 없는 지표·정말
  0건인 경우가 전부 사용자 입장에서 구분 없이 똑같이 보인다.
- **요청 내용**: `query_sales`/`query_purchase`가 `metadata`(또는 새 필드, 예:
  `reason`/`message`)에 거절 사유를 담아 반환하도록 도메인 쪽 계약을 먼저 정하고,
  `server.py`가 그 값을 `message`에 반영하도록 확장.
- **완료 기준**: "이번 달 영업이익 알려줘"와 "2026년 8월 매출 알려줘"(우연히 0건인 경우)가
  화면에서 서로 다른 안내 문장을 받음.

### P1-11. (신규) 채팅 그래프(막대+꺾은선) UI 구현

- **대상팀**: 통합(backend)
- **근거**: 5년치 데이터로 확장되며 그래프 기능이 다시 개발 범위에 들어왔다(사용자
  결정: sales는 SQL 생성 프롬프트 규칙만, UI는 통합 담당). sales가 실제 OpenAI 호출로
  재현한 버그(정수형 `order_year` 컬럼이 라벨일 때 `_build_tables`가 문자열 컬럼만
  찾아 차트가 안 그려짐)를 포함해 상세 스펙을 이미 작성해뒀다.
- **요청 내용**: [04_chart_spec.md](04_chart_spec.md) 전체(요약: `TableData.chart_type`
  필드 추가, `_build_tables` 라벨/값 컬럼 선택 개선, `chat.js`의 `drawChart`가
  `chart_type`을 반영하도록 수정, Chart.js를 CDN에서 `app/web/vendor/`로 이관).
- **완료 기준**: 04번 문서 5절의 검증 체크리스트 전부 통과.

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

## 요약 표 (복붙용)

| 코드 | 제목 | 대상팀 | 우선순위 | 상태 |
|---|---|---|---|---|
| 구 P0-1 | nodes.py의 finance import 오류 수정 | 통합 | — | 완료 |
| 구 P0-2 | .env 읽기 전용 DB 계정 추가 (sales 쪽) | 통합 | — | 완료(sales), purchase는 별도 진행 중 |
| 구 P1-1 | XSS 이스케이프 처리 | 통합 | — | 완료(이미 반영돼 있었음) |
| 구 P1-2 | innerHTML += 버그 수정 | 통합 | — | 완료(이미 반영돼 있었음) |
| P0-3 | purchase DB 접근 거부(502) — `purchase_read_user` 연결 필요 (신규) | 통합/purchase | P0 | 미착수 |
| P1-3 | 표 가로 스크롤 CSS | 통합 | P1 | 미착수 |
| P1-4 | 0건 안내 문구가 최종 답변에 반영되는지 확인 | 통합 | P1 | 미착수 |
| P1-5 | 표·답변 숫자 표기 통일 | 통합 | P1 | 미착수 |
| P1-6 | LLM 프롬프트용 행 수를 화면과 분리 (P1-10 선행 필요) | 통합 | P1 | 미착수 |
| P1-7 | 캐시 freshness bucket 채우기 | 통합 | P1 | 미착수 |
| P1-8 | interface.md/metadata 실제 필드명으로 갱신 (P1-10과 연관) | 통합 | P1 | 미착수 |
| P1-9 | mcp_servers/data/ 중복 정리 | 통합 | P1 | 미착수 |
| P1-10 | server.py envelope가 거절 사유·안내 문장 전달하도록 확장 (신규) | 통합 | P1 | 미착수 |
| P1-11 | 채팅 그래프(막대+꺾은선) UI 구현, 스펙은 [04_chart_spec.md](04_chart_spec.md) (신규) | 통합 | P1 | 스펙 전달 완료, 구현 대기 |
| 04-A | 60행 시계열 질문에서 차트 안 그려짐 (`nodes.py` chartable 상한 30) (신규) | 통합 | P1 | [04_chart_spec.md](04_chart_spec.md) 4-1절, 미착수 |
| 04-B | 차트 크기가 저절로 진동함 (Chart.js `maintainAspectRatio`/CSS 고정 높이 필요) (신규) | 통합 | P1 | [04_chart_spec.md](04_chart_spec.md) 4-1절, 미착수 |
| P2-1 | MCP 조회 로그 파일 정책 추가 | 통합 | P2 | 미착수 |
| P2-2 | finance_db_database 필드명 정리 | 통합 | P2 | 미착수 |

---

## 참고

- 전체 스펙: [SPEC.md](../../SPEC.md)
- sales 가이드: [01_rag_sales_text2sql.md](01_rag_sales_text2sql.md)
- purchase 가이드: [02_rag_purchase_text2sql.md](02_rag_purchase_text2sql.md)
- 차트 구현 스펙: [04_chart_spec.md](04_chart_spec.md)
- sales 진행 이력: [docs/progress/sales/2026-08-02.md](../progress/sales/2026-08-02.md)
- 프로젝트 공통 규칙: [RULE.md](../../RULE.md)
