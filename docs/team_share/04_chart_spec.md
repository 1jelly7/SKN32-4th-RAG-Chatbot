# [팀 공유 자료 4] 채팅창 그래프(막대+꺾은선) 구현 스펙

- **작성자**: rag_sales 담당 (PM 겸임)
- **읽는 대상**: 통합(backend) 담당
- **성격**: [01_rag_sales_text2sql.md 14.2절](01_rag_sales_text2sql.md)에서 보류하기로 한 그래프
  기능을, 이번에 sales 데이터가 5년치로 늘어나면서 다시 개발 범위에 넣었다. `chat.js`·
  `nodes.py`·`schemas/chat.py`·`index.html`은 전부 통합 담당 소유라 우리가 직접 고치지
  않고, sales 쪽에서 보장할 수 있는 부분(SQL 생성 규칙)만 먼저 구현한 뒤 나머지를 이
  스펙으로 정리해 전달한다.

## 0. 먼저 알려드릴 것 — 이미 고쳐져 있던 것

지난 병합(`367833c`)에서 [03_cross_team_requests.md](03_cross_team_requests.md)의 P1-1(XSS
이스케이프)과 P1-2(`innerHTML +=` 버그)가 **이미 반영되어 있었습니다.** `chat.js`에
`escapeHtml()`이 모든 출력 지점에 적용돼 있고, `insertAdjacentHTML('beforeend', ...)`로
바뀌어 있어서 연속 질문에도 이전 표·차트가 안 사라집니다. 03번 문서에 완료로 표시하겠습니다.

또한 각 차트의 `<canvas>` id가 `chart-${Date.now()}-${chartCounter}`로 매번 고유하게
생성되므로, `innerHTML` 버그가 고쳐진 지금은 이전 차트 인스턴스를 `destroy()`할 필요가
없습니다(새 canvas라 충돌하지 않음). 03번 문서 draft에 있던 "destroy() 필요" 항목은
불필요해졌습니다.

---

## 1. 지금 상태 (실제 코드 확인)

- `chat.js`의 `renderChartPlaceholder`/`drawChart`가 **막대(bar)만** 그린다
  ([app/web/chat.js:41-70](../../app/web/chat.js)).
- `TableData`([app/schemas/chat.py](../../app/schemas/chat.py))에 `chartable`/`label_column`/
  `value_column`은 있지만 `chart_type` 필드가 없다.
- `_build_tables`([app/agent/nodes.py:191-232](../../app/agent/nodes.py))가 라벨·값 컬럼을
  고르는 규칙: **첫 번째 "문자열(str)" 컬럼**을 라벨로, **마지막 숫자 컬럼**을 값으로,
  행 수가 30건 이하면 `chartable=True`.
- `index.html`이 Chart.js를 CDN(`cdnjs.cloudflare.com`)에서 받아온다.

## 2. 실제로 재현한 문제 — "연도별" 질문이 차트가 안 그려짐

sales의 SQL 생성 프롬프트(`text2sql.py`)를 실제 OpenAI로 테스트한 결과다.

```
질문: "연도별 매출 추이 알려줘"
생성된 SQL:
  SELECT order_year, SUM(order_amount) AS total_sales
  FROM v_sales_order
  GROUP BY order_year
  ORDER BY order_year ASC
  LIMIT 60
```

`order_year`는 `v_sales_order` 뷰에서 `YEAR(order_date)` — **정수(INT)** 컬럼이다.
`_build_tables`는 라벨 후보를 "문자열(`isinstance(val, str)`)" 컬럼에서만 찾으므로, 이
결과는 라벨 컬럼을 못 찾아 `chartable=False`가 되어 **표만 나오고 그래프가 안 그려진다.**
"연도별"·"분기별"처럼 자연스러운 질문에서 반복적으로 발생할 문제라 실제 재현 사례로
남겨둔다.

## 3. 요청 내용

### 3-1. `TableData`에 `chart_type` 추가

```python
chart_type: Literal["bar", "line"] | None = None
```

선택 규칙(제안):
- 라벨 컬럼명이 `*_month`/`*_year`/`*_quarter`로 끝나거나, 값이 `YYYY-MM` 패턴이면 **line**
- 그 외 카테고리 비교(고객명·품목명 등)는 **bar**
- 막대는 12개, 꺾은선은 60개 포인트 상한 (sales SQL이 이미 `LIMIT 12`/`LIMIT 60`을 지키도록
  프롬프트에 넣어뒀다 — 4절 참고)

### 3-2. `_build_tables` 개선 (2건)

1. **라벨 후보에 정수형 기간 컬럼도 포함**: 컬럼명이 `order_year`/`order_quarter`처럼
   `_year`/`_quarter`로 끝나면 값이 `int`여도 라벨 후보로 인정한다(2절 재현 사례를
   해결한다). `order_month`는 이미 문자열이라 그대로 둬도 된다.
2. **값 컬럼을 "마지막 숫자"가 아니라 컬럼명 우선순위로 선택**: `revenue`/`amount`/`total`/
   `sales`가 포함된 컬럼명을 우선하고, 없으면 지금처럼 마지막 숫자 컬럼으로 폴백한다.
   (지금도 sales 프롬프트가 "값 컬럼은 SELECT 마지막에" 규칙을 지키므로 당장 급한 문제는
   아니지만, 다른 도메인·다른 질문 형태에서도 안전하게 만드는 개선이다.)

### 3-3. `chat.js` 수정

- `drawChart`가 `table.chart_type`(없으면 `'bar'`)을 `type:`에 그대로 쓴다.
- y축에 천단위 콤마 포맷 추가: `ticks: { callback: v => v.toLocaleString() }`
- 통화 단위 표시: sales 쪽 결과는 항상 JOD 단일이므로(관련 근거는 4절), 툴팁에
  `${value.toLocaleString()} JOD`처럼 붙이면 표와 답변 문장의 숫자 표기가 통일된다
  (이전에 지적했던 03번 문서 P1-5 숫자 표기 불일치와 같은 개선 효과).

### 3-4. `index.html` — CDN 의존 제거

Chart.js를 `app/web/vendor/chart.umd.min.js`로 내려받아 두고 로컬 경로로 로드한다.
사내망·오프라인 시연에서 CDN 차단 시 차트만 조용히 안 뜨는 문제(에러도 안 남)를 없앤다.

## 4. sales가 이미 보장하는 것 (믿고 구현해도 되는 전제)

`mcp_servers/data_tools/sales/text2sql.py`의 `SYSTEM_PROMPT`에 이미 넣어뒀고, 실제 OpenAI
호출로 검증까지 마쳤다(아래 예시가 전부 실제 생성 결과다).

| 전제 | 근거 |
|---|---|
| 기간을 라벨로 쓸 때는 문자열 컬럼(`order_month`)을 우선 쓴다 | "월별 매출 추이" → `GROUP BY order_month` |
| 시간 흐름 질문은 기간 오름차순으로 정렬돼 있다 | 위 결과 `ORDER BY order_month ASC` |
| 값(금액·수량) 컬럼은 SELECT 목록 맨 마지막에 온다 | 모든 검증 케이스에서 `SUM(...)`이 항상 마지막 컬럼 |
| 카테고리 비교는 12건, 시계열은 60건 이하로 제한된다 | "월별 매출 추이" 결과 60행(5년×12개월) |
| 통화는 JOD 단일이다 | `schema['currency'] == "JOD"`, 원본 데이터 실측 |
| 라인 단위(품목별) 지표는 헤더 금액과 섞이지 않는다 | `v_sales_order_line.line_total`만 사용, fan-out 없음 |

단, **정수형 기간 컬럼(`order_year`, `order_quarter`)이 라벨로 쓰이는 경우**는 막지 않는다
(2절 사례). "연도별"·"분기별"처럼 자연스러운 표현일수록 오히려 정수 컬럼을 쓰는 게 SQL로는
더 정확하므로, 프롬프트로 강제 회피시키기보다 3-2절의 `_build_tables` 개선으로 받아들이는
쪽을 권장한다.

## 5. 검증 기준

- [ ] 질문을 3회 연속 했을 때 첫 번째 질문의 표·차트가 화면에 그대로 남아있다 (0절, 이미 해결)
- [ ] "월별 매출 추이" → 꺾은선 그래프
- [ ] "연도별 매출 추이" → 꺾은선 그래프 (2절 재현 사례가 해결됐는지 확인)
- [ ] "고객별 매출 상위 5개" → 막대 그래프
- [ ] 네트워크를 끊은 상태에서도(CDN 차단 시뮬레이션) 차트가 그려진다
- [ ] 표의 숫자와 차트 툴팁의 숫자 표기(콤마·JOD)가 일치한다

## 참고

- 전체 스펙: [SPEC.md](../../SPEC.md)
- sales 방법론: [01_rag_sales_text2sql.md](01_rag_sales_text2sql.md)
- 요청 목록: [03_cross_team_requests.md](03_cross_team_requests.md)
