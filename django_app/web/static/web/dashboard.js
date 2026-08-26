// 이상탐지 대시보드. GET /api/anomalies(이상 신호 목록)와
// GET /api/dashboard/monthly-trends(월별 매출·구매 추이)를 함께 불러와
// KPI 카드·추이 차트·이상탐지 카드로 구성한다.
// DASHBOARD_ROLES는 auth.js가 이미 선언한다(탭 숨김 판단에도 같은 목록을 씀).
const dashboardRoot = document.querySelector('#dashboard-root');

const TYPE_LABEL = { amount_outlier: '금액 이상치', overdue: '연체 과다', spike: '거래 급증' };
let charts = {};

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
}

function formatAmount(n) {
  return `${Number(n).toLocaleString()} KRW`;
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`request_failed:${response.status}`);
  return response.json();
}

async function fetchDashboardData() {
  const year = new Date().getFullYear();
  const [anomalies, trends] = await Promise.all([
    fetchJson('/api/anomalies'),
    fetchJson(`/api/dashboard/monthly-trends?year=${year}`),
  ]);
  return { anomalies, trends };
}

function deltaHtml(points) {
  if (points.length < 2) return `<div class="kpi-sub">전월 비교 불가</div>`;
  const last = points[points.length - 1];
  const prev = points[points.length - 2];
  if (prev.amount === 0) return `<div class="kpi-sub">전월 비교 불가</div>`;
  const pct = ((last.amount - prev.amount) / Math.abs(prev.amount)) * 100;
  const cls = pct >= 0 ? 'up' : 'down';
  const arrow = pct >= 0 ? '▲' : '▼';
  return `<div class="kpi-sub kpi-delta ${cls}">${arrow} 전월 대비 ${Math.abs(pct).toFixed(1)}%</div>`;
}

function kpiRowHtml(trends, anomalies) {
  const salesLast = trends.sales.at(-1) ?? null;
  const purchaseLast = trends.purchase.at(-1) ?? null;
  const overdueTotal = anomalies.filter(a => a.type === 'overdue').reduce((sum, a) => sum + a.amount, 0);

  return `
  <div class="kpi-card">
    <div class="kpi-label">최근 달 매출${salesLast ? ` (${escapeHtml(salesLast.month)})` : ''}</div>
    <div class="kpi-value">${salesLast ? formatAmount(salesLast.amount) : '데이터 없음'}</div>
    ${salesLast ? deltaHtml(trends.sales) : ''}
  </div>
  <div class="kpi-card">
    <div class="kpi-label">최근 달 구매액${purchaseLast ? ` (${escapeHtml(purchaseLast.month)})` : ''}</div>
    <div class="kpi-value">${purchaseLast ? formatAmount(purchaseLast.amount) : '데이터 없음'}</div>
    ${purchaseLast ? deltaHtml(trends.purchase) : ''}
  </div>
  <div class="kpi-card${overdueTotal > 0 ? ' is-alert' : ''}">
    <div class="kpi-label">연체 총액</div>
    <div class="kpi-value">${overdueTotal > 0 ? formatAmount(overdueTotal) : '연체 없음'}</div>
  </div>
  <div class="kpi-card${anomalies.length ? ' is-alert' : ''}">
    <div class="kpi-label">이상 신호</div>
    <div class="kpi-value">${anomalies.length}건</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">데이터 기준</div>
    <div class="kpi-value" style="font-size:13px">${escapeHtml(salesLast?.month || purchaseLast?.month || '-')}</div>
  </div>`;
}

function anomalyCardHtml(a) {
  return `
  <div class="anomaly-card">
    <div class="anomaly-head">
      <span class="anomaly-entity">${escapeHtml(a.entity)}</span>
      <span class="anomaly-type">${escapeHtml(TYPE_LABEL[a.type] || a.type)}</span>
    </div>
    <div class="anomaly-amount">${formatAmount(a.amount)}</div>
    <div class="anomaly-detail">${escapeHtml(a.detail)}</div>
    <div class="anomaly-time">감지 시각 ${new Date(a.detected_at).toLocaleString('ko-KR')}</div>
  </div>`;
}

function drawTrendChart(canvasId, points) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined') return;
  if (charts[canvasId]) charts[canvasId].destroy();
  charts[canvasId] = new Chart(canvas, {
    type: 'line',
    data: {
      labels: points.map(p => p.month),
      datasets: [{ data: points.map(p => p.amount), borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,.08)', pointBackgroundColor: '#3b82f6', pointRadius: 3, tension: .3, fill: true }],
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
  });
}

function domainSectionHtml(label, trendPoints, canvasId, rows) {
  const ANOMALY_DISPLAY_LIMIT = 4;
  const shown = rows.slice().sort((a, b) => b.amount - a.amount).slice(0, ANOMALY_DISPLAY_LIMIT);
  return `
  <section class="domain-section">
    <h3 class="domain-title">${escapeHtml(label)} <span class="badge-count">${rows.length}</span></h3>
    <div class="dashboard-chart-card">
      <div class="dashboard-chart-title">월별 ${escapeHtml(label)} 추이</div>
      <div class="dashboard-chart-box"><canvas id="${canvasId}"></canvas></div>
    </div>
    ${shown.length
      ? `<div class="anomaly-grid">${shown.map(anomalyCardHtml).join('')}</div>`
      : `<div class="empty-note">현재 감지된 이상 신호가 없습니다.</div>`}
    ${rows.length > shown.length ? `<p class="anomaly-truncated-note">금액이 큰 상위 ${shown.length}건만 표시합니다 (전체 ${rows.length}건).</p>` : ''}
  </section>`;
}

function renderDashboard({ anomalies, trends }) {
  const salesAnomalies = anomalies.filter(a => a.domain === 'sales');
  const purchaseAnomalies = anomalies.filter(a => a.domain === 'purchase');
  const fewDataPoints = trends.sales.length < 2 && trends.purchase.length < 2;

  dashboardRoot.innerHTML = `
  <div class="dashboard">
    <h2 class="dashboard-title">이상탐지 대시보드</h2>
    <p class="dashboard-sub">월별 매출·구매 추이와 고정 규칙 기반 이상 신호를 함께 보여줍니다.</p>
    <div class="kpi-row">${kpiRowHtml(trends, anomalies)}</div>
    ${fewDataPoints ? `<div class="note-banner">이번 연도 데이터가 아직 1개월뿐이라 추이·전월대비 비교가 제한적입니다.</div>` : ''}
    ${domainSectionHtml('매출', trends.sales, 'sales-trend-chart', salesAnomalies)}
    ${domainSectionHtml('구매', trends.purchase, 'purchase-trend-chart', purchaseAnomalies)}
  </div>`;

  drawTrendChart('sales-trend-chart', trends.sales);
  drawTrendChart('purchase-trend-chart', trends.purchase);
}

function renderAccessDenied() {
  dashboardRoot.innerHTML = `
  <div class="dashboard-empty-role">
    <h2>대시보드에 접근할 수 없습니다</h2>
    <p>이상탐지 대시보드는 매출·구매 데이터 접근 권한이 있는 계정만 볼 수 있습니다.</p>
  </div>`;
}

function renderLoadError() {
  dashboardRoot.innerHTML = `
  <div class="dashboard-empty-role">
    <h2>대시보드를 불러오지 못했습니다</h2>
    <p>잠시 후 다시 시도해 주세요.</p>
  </div>`;
}

window.onAuthStateReady = async user => {
  if (!DASHBOARD_ROLES.includes(user.role)) {
    renderAccessDenied();
    return;
  }
  try {
    const data = await fetchDashboardData();
    renderDashboard(data);
  } catch (_) {
    renderLoadError();
  }
};

window.onAuthStateCleared = () => {
  Object.values(charts).forEach(chart => chart.destroy());
  charts = {};
  dashboardRoot.innerHTML = '';
};

restoreSession();
