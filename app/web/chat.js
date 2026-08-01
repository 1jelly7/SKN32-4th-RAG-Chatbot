// ChatResponse를 답변·출처·표·차트로 변환하는 vanilla UI 경계입니다.
// 서버가 제거한 내부 경로와 자격증명을 별도 endpoint에서 다시 조회하지 않습니다.
const form = document.querySelector('#chat-form');
const input = document.querySelector('#question');
const messages = document.querySelector('#messages');

let chartCounter = 0;

function routeBadge(route) {
  if (!route) return '';
  const labels = { GENERAL: '일반', DOCUMENT: '문서', DATABASE: 'DB', BOTH: '문서+DB' };
  return `<span class="badge badge-${route}">${labels[route] || route}</span>`;
}

// 공개 Source 필드만 사용하며 document/database provenance를 아이콘으로 구분합니다.
function renderSources(sources) {
  if (!sources || sources.length === 0) return '';
  const items = sources.map(s => {
    const icon = s.source_type === 'document' ? '📄' : '🗄️';
    const scoreText = s.score != null ? ` (score ${s.score.toFixed(3)})` : '';
    return `<li>${icon} ${s.title}${scoreText}</li>`;
  }).join('');
  return `<details class="sources"><summary>참고 출처 (${sources.length})</summary><ul>${items}</ul></details>`;
}

// DB 조회 결과를 표(<table>)로 렌더링합니다.
function renderTable(table) {
  const headerHtml = table.columns.map(c => `<th>${c}</th>`).join('');
  const rowsHtml = table.rows.map(row =>
    `<tr>${row.map(cell => `<td>${cell ?? ''}</td>`).join('')}</tr>`
  ).join('');
  return `
    <div class="table-wrap">
      <div class="table-meta">${table.domain} 데이터 · ${table.rows.length}건</div>
      <table class="data-table">
        <thead><tr>${headerHtml}</tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
      <details class="sql-detail"><summary>생성된 SQL 보기</summary><pre>${table.sql}</pre></details>
    </div>`;
}

// label_column/value_column이 있으면 막대그래프용 <canvas>를 만들고, 삽입 직후 Chart.js로 그립니다.
function renderChartPlaceholder(table) {
  if (!table.chartable) return '';
  chartCounter += 1;
  const canvasId = `chart-${Date.now()}-${chartCounter}`;
  // 다음 tick에 실제 차트를 그리도록 id만 먼저 반환하고, 호출부에서 drawChart를 실행합니다.
  return { html: `<div class="chart-wrap"><canvas id="${canvasId}"></canvas></div>`, canvasId };
}

// 서버가 지정한 label/value 컬럼이 모두 있을 때만 제한된 행으로 차트를 그립니다.
function drawChart(canvasId, table) {
  const labelIdx = table.columns.indexOf(table.label_column);
  const valueIdx = table.columns.indexOf(table.value_column);
  const labels = table.rows.map(r => String(r[labelIdx]));
  const values = table.rows.map(r => Number(r[valueIdx]) || 0);

  const ctx = document.getElementById(canvasId);
  if (!ctx || typeof Chart === 'undefined') return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ label: table.value_column, data: values, backgroundColor: '#285E45' }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { autoSkip: false, maxRotation: 60, minRotation: 30 } } },
    },
  });
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const question = input.value;
  if (!question.trim()) return;

  messages.innerHTML += `<div class="msg user"><b>나</b>${question}</div>`;
  input.value = '';

  const loadingId = `loading-${Date.now()}`;
  messages.innerHTML += `<div class="msg bot" id="${loadingId}">답변 생성 중...</div>`;
  messages.scrollTop = messages.scrollHeight;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();

    if (!res.ok) {
      document.getElementById(loadingId).outerHTML = `<div class="msg bot error">서버 오류: ${data.detail || res.status}</div>`;
      return;
    }

    const cachedBadge = data.cached ? '<span class="badge badge-cached">캐시</span>' : '';

    const tables = data.tables || [];
    const chartPlaceholders = [];
    const tablesHtml = tables.map(t => {
      const tableHtml = renderTable(t);
      const chart = renderChartPlaceholder(t);
      if (chart) {
        chartPlaceholders.push({ canvasId: chart.canvasId, table: t });
        return tableHtml + chart.html;
      }
      return tableHtml;
    }).join('');

    document.getElementById(loadingId).outerHTML = `
      <div class="msg bot">
        <div class="meta">${routeBadge(data.route)}${cachedBadge}</div>
        <div class="answer">${data.answer.replace(/\n/g, '<br>')}</div>
        ${renderSources(data.sources)}
        ${tablesHtml}
      </div>`;

    // DOM에 canvas가 실제로 삽입된 뒤에 Chart.js를 실행해야 합니다.
    chartPlaceholders.forEach(({ canvasId, table }) => drawChart(canvasId, table));
  } catch (err) {
    document.getElementById(loadingId).outerHTML = `<div class="msg bot error">오류: ${err.message}</div>`;
  }
  messages.scrollTop = messages.scrollHeight;
});
