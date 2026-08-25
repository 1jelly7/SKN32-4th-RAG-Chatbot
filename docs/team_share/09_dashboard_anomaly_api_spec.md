# [팀 공유 자료 9] 이상탐지 대시보드 API 스펙 (UI → 통합 요청)

- **작성자**: UI/UX 담당
- **읽는 대상**: 통합(backend) 담당
- **성격**: 채팅 화면 옆에 새 "대시보드" 탭을 추가하는 작업 중, 화면에 필요한 이상탐지
  집계 API가 현재 존재하지 않아 UI 쪽에서 필요한 스펙을 먼저 정리해 요청한다.
  `app/api/`, `mcp_servers/data_tools/`, `database/*/views.sql`은 전부 통합·도메인
  담당 소유라 UI가 직접 구현하지 않는다. 화면 시안은 더미 데이터로 이미 만들어 승인받은
  상태([ui_preview/20260826-dashboard.html](../../ui_preview/20260826-dashboard.html))이고,
  이 문서는 그 화면이 실제로 동작하는 데 필요한 데이터 계약이다.

## 1. 지금 상태 (실제 코드 확인)

- 이상탐지·집계 관련 코드는 저장소 어디에도 없다(`anomaly` 키워드로 전수 검색, 0건).
- 현재 유일한 데이터 API는 `POST /api/chat`이며, 자연어 질문 1건당 LLM이 SQL을 생성해
  표 1~n개를 반환하는 구조다([app/schemas/chat.py](../../app/schemas/chat.py)의
  `ChatResponse`). 대시보드처럼 "이번 달 KPI + 여러 이상 신호를 한 번에" 요구하는
  화면에는 안 맞는다 — 매번 다른 질문을 흉내 내 LLM을 여러 번 호출해야 하고, 임계값
  판단(평균 대비 몇 배 등)을 프론트에서 다시 계산해야 해서 신뢰하기 어렵다.
- `database/sales/views.sql`/`database/purchase/views.sql`에 이미 "매출/구매액의 유일한
  정의"인 `v_sales_order`/`v_purchase_order`가 있고, 연체 추적용 `v_invoice`/
  `v_vendor_invoice`, 취소율 추적용 `v_sales_order_status`/`v_purchase_order_status`도
  있다. 집계 자체는 이 뷰들로 충분히 가능해 보인다(UI가 판단할 문제는 아니라 확인만
  요청).
- 역할별 접근 제어는 `shared/auth_policy.py`에 이미 있다. `hr`은 `document_db`만
  접근 가능하므로, 대시보드 API도 `/api/chat`과 동일하게 `sales_db`/`purchase_db`
  권한이 없는 역할에는 403을 반환해야 한다(화면에서도 `hr` 역할에는 탭 자체를 숨기기로
  했지만, API 자체도 방어적으로 막아야 한다 — 클라이언트 숨김은 UI 편의일 뿐 보안
  경계가 아니다).

## 2. 요청 내용

### 2-1. 새 엔드포인트

```
GET /api/dashboard/anomalies
```

- 인증: 기존 `/api/chat`과 동일한 세션 검증 방식 재사용.
- 인가: `role`이 `sales_db` 또는 `purchase_db` 접근 권한이 없으면 403
  (`shared/auth_policy.allowed_databases`로 판단 — 현재는 `hr`만 해당).
- 쿼리 파라미터는 당장 없어도 된다. 기간을 나중에 파라미터화할 수 있게(`?month=2026-08`
  등) 열어두는 정도로 제안하되, 1차 구현은 "이번 달 vs 이동평균" 고정 로직으로 충분.

### 2-2. 응답 스키마 (제안)

```python
class KpiCard(BaseModel):
    label: str
    value: float
    unit: str  # "KRW" 등
    delta_pct: float | None = None   # 전월 대비 %. 계산 불가하면 None
    is_alert: bool = False           # 카드를 경고 색으로 표시할지

class AnomalySeverity(str, Enum):
    WARNING = "warning"
    SEVERE = "severe"

class Anomaly(BaseModel):
    id: str
    title: str
    detail: str            # 예: "8월 15일 주문 금액 1억 2,000만원"
    reason: str            # 예: "이 고객의 최근 6개월 평균 주문액(1,800만원) 대비 6.7배"
    severity: AnomalySeverity
    domain: Literal["sales", "purchase"]

class TrendPoint(BaseModel):
    period: str             # "2026-03"
    value: float
    is_anomaly: bool = False

class DashboardResponse(BaseModel):
    kpis: list[KpiCard]
    sales_trend: list[TrendPoint]
    purchase_trend: list[TrendPoint]
    sales_anomalies: list[Anomaly]
    purchase_anomalies: list[Anomaly]
    generated_at: str       # ISO timestamp — 화면에 "몇 시 기준" 표시용
```

시안에서 실제로 쓰는 필드만 담았다. `reason`(판단 근거)이 없으면 카드를 못 그리게
막아뒀으면 한다 — "왜 이상으로 판단했는지 안 보여주면 표시하지 않는다"는 원칙을
채팅 화면의 근거 패널과 동일하게 대시보드에도 적용하기로 했다(CLAUDE.md 디자인 원칙
"불확실성을 드러낸다").

### 2-3. 이상탐지 항목별 계산 제안 (참고용 — 실제 구현 방식은 통합 담당 판단)

| 항목 | 데이터 소스 | 판단 규칙(제안) |
|---|---|---|
| 매출 — 이례적 대형 주문 | `v_sales_order` | 고객별 최근 6개월 평균 주문액 대비 특정 단건이 N배 이상 |
| 매출 — 비정상 할인율 | `v_sales_order_line` (뷰에 없으면 원본 join 필요) | 품목별 평균 `discount_percent` 대비 표준편차 벗어난 라인 |
| 매출 — 연체 미수금 | `v_invoice` | `due_date` 경과 + `outstanding_amount > 0` 합계가 최근 3개월 평균 대비 급증 |
| 구매 — 벤더 단가 급등 | `v_purchase_order_line` | 품목별 과거 평균 `unit_price` 대비 급등한 최근 라인 |
| 구매 — 벤더 집중도 | `v_purchase_order` | 이번 달 발주액의 벤더별 비중이 평소보다 특정 벤더에 쏠림 |
| 구매 — 미지급금 연체 | `v_vendor_invoice` | 매출 연체 로직과 동일 |
| 매출/구매 추이 | `v_sales_order`/`v_purchase_order`를 월별 `GROUP BY` | 이동평균 ±2표준편차 벗어난 달을 `is_anomaly: true` |

임계값(몇 배, 표준편차 몇 배)은 통합/도메인 담당이 실제 데이터 분포를 보고 정하는 게
맞다고 생각해서 구체적인 숫자는 제안하지 않았다.

## 3. UI가 이미 보장하는 것 (믿고 구현해도 되는 전제)

- 대시보드 탭은 `hr` 역할에는 아예 표시하지 않는다(프론트에서 role 체크).
- `Anomaly.reason`이 빈 문자열이면 카드를 렌더링하지 않도록 프론트에서 방어한다 —
  API가 실수로 빈 문자열을 보내도 화면이 깨지진 않는다. 다만 "판단 근거 없는 이상탐지"는
  제품 원칙에 어긋나니 애초에 안 보내는 걸 권장한다.
- `sales_trend`/`purchase_trend`가 비어있으면(예: 데이터 없음) 차트 대신 빈 상태 문구를
  보여준다.
- 프론트는 `delta_pct`/`is_alert`/`is_anomaly` 같은 판단 필드를 다시 계산하지 않고
  API 값을 그대로 신뢰한다 — 계산 로직을 프론트와 백엔드 두 곳에 중복 구현하지 않기
  위함.

## 4. 완료 기준

- [ ] `GET /api/dashboard/anomalies`가 `DashboardResponse` 형태로 응답
- [ ] `hr` 역할로 호출 시 403 (기존 `/api/chat`의 `FORBIDDEN` 응답과 같은 방식)
- [ ] `finance`/`admin` 역할로 호출 시 실제 sales/purchase 데이터 기반 값 반환
      (더미 아님)
- [ ] 모든 `Anomaly` 항목에 비어있지 않은 `reason` 포함
- [ ] `docs/interface.md`에 이 엔드포인트 계약 추가 (기존 관례대로 정본 문서 갱신)

## 참고

- 화면 시안: [ui_preview/20260826-dashboard.html](../../ui_preview/20260826-dashboard.html)
- 작업 로그: [docs/ui/ui_plan.md](../ui/ui_plan.md) "이상탐지 대시보드 페이지" 항목
- 매출/구매 뷰 정의: [database/sales/views.sql](../../database/sales/views.sql),
  [database/purchase/views.sql](../../database/purchase/views.sql)
- 역할별 DB 접근 정책: [shared/auth_policy.py](../../shared/auth_policy.py)
- 기존 cross-team 요청 문서 형식 참고: [03_cross_team_requests.md](03_cross_team_requests.md),
  [04_chart_spec.md](04_chart_spec.md)
