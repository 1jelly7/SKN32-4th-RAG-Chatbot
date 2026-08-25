// 이상탐지 대시보드. 실제 GET /api/dashboard/anomalies가 만들어지기 전까지는
// 더미 데이터로 화면만 그린다 (docs/team_share/09_dashboard_anomaly_api_spec.md
// 참고). API가 생기면 이 파일의 DUMMY_DASHBOARD_DATA와 fetchDashboardData()만
// 교체하면 된다 — 렌더링 함수들은 DashboardResponse 스키마를 그대로 소비하도록
// 이미 그 모양에 맞춰 작성했다.
// DASHBOARD_ROLES는 auth.js가 이미 선언한다(탭 숨김 판단에도 같은 목록을 씀).
const dashboardRoot = document.querySelector('#dashboard-root');

const DUMMY_DASHBOARD_DATA = {
  kpis: [
    { label: '이번 달 매출', value: '4억 3,100만', deltaText: '▼ 전월 대비 5.5%', deltaDirection: 'down', isAlert: false },
    { label: '이번 달 구매액', value: '2억 1,800만', deltaText: '▲ 전월 대비 12.1%', deltaDirection: 'up', isAlert: false },
    { label: '연체 미수·미지급금', value: '7,400만', deltaText: '▲ 전월 대비 38%', deltaDirection: 'down', isAlert: true },
    { label: '이상 신호', value: '6건', deltaText: '이번 달 새로 감지됨', deltaDirection: null, isAlert: true },
  ],
  sales_trend: [
    { period: '3월', value: 28.5 }, { period: '4월', value: 32 }, { period: '5월', value: 41.2 },
    { period: '6월', value: 39.8 }, { period: '7월', value: 45.6, is_anomaly: true }, { period: '8월', value: 43.1 },
  ],
  purchase_trend: [
    { period: '3월', value: 15.2 }, { period: '4월', value: 16.8 }, { period: '5월', value: 15.9 },
    { period: '6월', value: 17.4 }, { period: '7월', value: 18.1 }, { period: '8월', value: 21.8, is_anomaly: true },
  ],
  sales_anomalies: [
    { id: 's1', title: '고객 "㈜대한물산" 이례적 대형 주문', detail: '8월 15일 주문 금액 1억 2,000만원', reason: '이 고객의 최근 6개월 평균 주문액(1,800만원) 대비 6.7배', severity: 'severe' },
    { id: 's2', title: '비정상 할인율 라인 3건', detail: '평균 할인율 8% 대비 35~42% 할인 적용된 주문 라인', reason: '품목별 평균 할인율 대비 표준편차 3배 이상', severity: 'warning' },
    { id: 's3', title: '연체 미수금 급증', detail: '만기 지난 미수금 4,200만원 (12건)', reason: '지난 3개월 평균 대비 38% 증가', severity: 'warning' },
  ],
  purchase_anomalies: [
    { id: 'p1', title: '품목 "원자재-A" 단가 급등', detail: '벤더 "글로벌소재"로부터 단가 4,200원 → 6,800원', reason: '최근 6개월 평균 단가 대비 62% 상승', severity: 'severe' },
    { id: 'p2', title: '특정 벤더 발주 집중', detail: '이번 달 발주의 71%가 벤더 "한성부품" 한 곳에 집중', reason: '최근 6개월 평균 집중도(28%) 대비 2.5배', severity: 'warning' },
    { id: 'p3', title: '미지급금 연체', detail: '만기 지난 미지급금 3,200만원 (7건)', reason: '지난 3개월 평균 대비 22% 증가', severity: 'warning' },
  ],
};

async function fetchDashboardData() {
  // TODO(백엔드 완료 후 교체): GET /api/dashboard/anomalies 실제 호출로 대체.
  return DUMMY_DASHBOARD_DATA;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
}

function kpiCardHtml(kpi) {
  const deltaClass = kpi.deltaDirection ? ` ${kpi.deltaDirection}` : '';
  return `
  <div class="kpi-card${kpi.isAlert ? ' is-alert' : ''}">
    <div class="kpi-label">${escapeHtml(kpi.label)}</div>
    <div class="kpi-value">${escapeHtml(kpi.value)}</div>
    <div class="kpi-delta${deltaClass}">${escapeHtml(kpi.deltaText)}</div>
  </div>`;
}

function anomalyCardHtml(anomaly) {
  const severityLabel = anomaly.severity === 'severe' ? '심각' : '주의';
  return `
  <div class="anomaly-card${anomaly.severity === 'severe' ? ' is-severe' : ''}">
    <div class="anomaly-head">
      <span class="anomaly-title">${escapeHtml(anomaly.title)}</span>
      <span class="anomaly-severity">${severityLabel}</span>
    </div>
    <div class="anomaly-detail">${escapeHtml(anomaly.detail)}</div>
    <div class="anomaly-reason"><strong>판단 근거:</strong> ${escapeHtml(anomaly.reason)}</div>
  </div>`;
}

function drawTrendChart(canvasId, points) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined') return;
  const labels = points.map(p => p.period);
  const values = points.map(p => p.value);
  const pointColors = points.map(p => p.is_anomaly ? '#b42318' : '#3b82f6');
  const pointRadius = points.map(p => p.is_anomaly ? 7 : 3);
  new Chart(canvas, {
    type: 'line',
    data: { labels, datasets: [{ data: values, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,.08)', pointBackgroundColor: pointColors, pointRadius, tension: .3, fill: true }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
  });
}

function renderDashboard(data) {
  dashboardRoot.innerHTML = `
  <div class="dashboard">
    <h2 class="dashboard-title">이상탐지 대시보드</h2>
    <p class="dashboard-sub">매출·구매 데이터에서 평소 패턴을 벗어난 항목을 자동으로 짚어줍니다</p>

    <div class="kpi-row">${data.kpis.map(kpiCardHtml).join('')}</div>

    <section class="domain-section">
      <h3 class="domain-title">매출 <span class="badge-count">${data.sales_anomalies.length}</span></h3>
      <div class="dashboard-chart-card">
        <div class="dashboard-chart-title">월별 매출 추이 (빨간 점 = 이동평균 ±2표준편차 이탈)</div>
        <div class="dashboard-chart-box"><canvas id="sales-trend-chart"></canvas></div>
      </div>
      <div class="anomaly-grid">${data.sales_anomalies.map(anomalyCardHtml).join('')}</div>
    </section>

    <section class="domain-section">
      <h3 class="domain-title">구매 <span class="badge-count">${data.purchase_anomalies.length}</span></h3>
      <div class="dashboard-chart-card">
        <div class="dashboard-chart-title">월별 구매액 추이</div>
        <div class="dashboard-chart-box"><canvas id="purchase-trend-chart"></canvas></div>
      </div>
      <div class="anomaly-grid">${data.purchase_anomalies.map(anomalyCardHtml).join('')}</div>
    </section>
  </div>`;

  drawTrendChart('sales-trend-chart', data.sales_trend);
  drawTrendChart('purchase-trend-chart', data.purchase_trend);
}

function renderAccessDenied() {
  dashboardRoot.innerHTML = `
  <div class="dashboard-empty-role">
    <h2>대시보드에 접근할 수 없습니다</h2>
    <p>이상탐지 대시보드는 매출·구매 데이터 접근 권한이 있는 계정만 볼 수 있습니다.</p>
  </div>`;
}

window.onAuthStateReady = async user => {
  if (!DASHBOARD_ROLES.includes(user.role)) {
    renderAccessDenied();
    return;
  }
  const data = await fetchDashboardData();
  renderDashboard(data);
};

window.onAuthStateCleared = () => {
  dashboardRoot.innerHTML = '';
};

restoreSession();
