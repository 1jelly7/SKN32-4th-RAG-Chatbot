// ChatResponse를 대화·출처·표 UI로 변환하는 vanilla JavaScript 경계입니다.
const form = document.querySelector('#chat-form');
const input = document.querySelector('#question');
const messages = document.querySelector('#messages');
const sendButton = document.querySelector('#send-button');
const sourcesPanel = document.querySelector('#sources-panel');
const sourcesList = document.querySelector('#sources-list');
const sourcesSummary = document.querySelector('#sources-summary');
const sourcesToggle = document.querySelector('#sources-toggle');
const sourcesClose = document.querySelector('#sources-close');
const sourcesBackdrop = document.querySelector('#sources-backdrop');
// 추가: 리포트(POST /api/reports/generate) 확인용 임시 다운로드 버튼 참조.
const reportToggle = document.querySelector('#report-toggle');
const reportPanel = document.querySelector('#report-panel');
const reportStart = document.querySelector('#report-start');
const reportEnd = document.querySelector('#report-end');
const reportDownloadButton = document.querySelector('#report-download');
const reportStatus = document.querySelector('#report-status');
const loginScreen = document.querySelector('#login-screen');
const loginForm = document.querySelector('#login-form');
const loginError = document.querySelector('#login-error');
const loginButton = document.querySelector('#login-button');
const currentUser = document.querySelector('#current-user');
const logoutButton = document.querySelector('#logout-button');

let chartCounter = 0;
let auth_state_revision = 0;
let activeRequestController = null;
let csrfTokenValue = null;

async function csrfHeaders() {
  if (!csrfTokenValue) {
    const response = await fetch('/api/auth/csrf');
    if (!response.ok) throw new Error('로그인 보안 토큰을 발급받지 못했습니다.');
    csrfTokenValue = (await response.json()).csrf_token;
  }
  return { 'Content-Type': 'application/json', 'X-CSRFToken': csrfTokenValue };
}

async function responseError(response, fallbackMessage) {
  try {
    const payload = await response.json();
    return new Error(payload.detail || fallbackMessage);
  } catch (_) {
    return new Error(fallbackMessage);
  }
}

async function chatResponsePayload(response) {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('application/json')) {
    if (response.status >= 500) {
      throw new Error('채팅 서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.');
    }
    throw new Error(`요청에 실패했습니다 (${response.status})`);
  }
  try {
    return await response.json();
  } catch (_) {
    throw new Error('채팅 서버가 올바른 응답을 반환하지 않았습니다. 잠시 후 다시 시도해 주세요.');
  }
}

function clearApplicationState() {
  activeRequestController?.abort();
  activeRequestController = null;
  messages.replaceChildren();
  input.value = '';
  autoResize();
  sendButton.disabled = false;
  currentUser.textContent = '';
  renderSources([], null);
  setSourcesOpen(false);
  // TEMP: 로그아웃 시 이전 사용자의 이상탐지 결과가 잠깐이라도 남아있지 않게 초기화.
  // loadAnomalies()/anomalyBody는 파일 맨 아래 TEMP 블록에 정의돼 있다(호이스팅으로
  // 여기서도 참조 가능).
  if (typeof anomalyBody !== 'undefined') anomalyBody.innerHTML = '<p class="anomaly-loading">불러오는 중...</p>';
}
function showLogin() { loginScreen.hidden = false; document.querySelector('.app-shell').setAttribute('aria-hidden', 'true'); document.querySelector('#username').focus(); }
// TEMP: showApplication()은 로그인 성공/세션 복원 성공 양쪽에서 호출되는 유일한
// 지점이라, 여기서 이상탐지를 불러오면 restoreSession() 성공 직후뿐 아니라 방금
// 로그인한 경우에도 바로 채워진다. 파일 맨 아래 TEMP 블록을 지울 때 이 줄도
// 함께 지워야 한다(안 지우면 loadAnomalies is not defined 에러가 난다).
function showApplication(user) { loginScreen.hidden = true; document.querySelector('.app-shell').removeAttribute('aria-hidden'); currentUser.textContent = `${user.display_name} (${user.role})`; loadAnomalies(); }
async function restoreSession() { const response = await fetch('/api/auth/me'); if (response.ok) showApplication(await response.json()); else showLogin(); }
loginForm.addEventListener('submit', async event => { event.preventDefault(); loginError.textContent = ''; loginButton.disabled = true; try { const response = await fetch('/api/auth/login', { method: 'POST', headers: await csrfHeaders(), body: JSON.stringify({ username: document.querySelector('#username').value, password: document.querySelector('#password').value }) }); if (!response.ok) throw await responseError(response, '아이디 또는 비밀번호가 올바르지 않습니다.'); clearApplicationState(); csrfTokenValue = null; showApplication((await response.json()).user); document.querySelector('#password').value = ''; } catch (error) { csrfTokenValue = null; loginError.textContent = error.message; } finally { loginButton.disabled = false; } });
logoutButton.addEventListener('click', async () => { auth_state_revision += 1; clearApplicationState(); loginError.textContent = ''; try { const response = await fetch('/api/auth/logout', { method: 'POST', headers: await csrfHeaders() }); if (!response.ok && response.status !== 401) throw await responseError(response, '로그아웃하지 못했습니다.'); csrfTokenValue = null; showLogin(); } catch (error) { csrfTokenValue = null; loginError.textContent = error.message; await restoreSession(); } });

loginForm.addEventListener('submit', () => { auth_state_revision += 1; }, true);

restoreSession = async function restore_session_with_revision() {
  const revision = auth_state_revision;
  const response = await fetch('/api/auth/me');
  if (revision !== auth_state_revision) return;
  if (response.ok) showApplication(await response.json()); else showLogin();
};

const robotIcon = '<svg viewBox="0 0 24 24" class="svg-icon"><path d="M5 10h14v9H5zM12 4v3M9 14h.01M15 14h.01M8 19v2M16 19v2M3 12h2M19 12h2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/></svg>';
const documentIcon = '<svg viewBox="0 0 24 24" class="svg-icon"><path d="M6 3h8l4 4v14H6zM14 3v5h5M9 12h6M9 16h6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"/></svg>';

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function formatAnswer(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

function userFriendlyError(error) {
  const message = String(error?.message || '');
  if (message === 'Failed to fetch' || error instanceof TypeError) {
    return '서버에 연결하지 못했습니다. 연결 상태를 확인한 뒤 다시 시도해 주세요.';
  }
  return message || '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.';
}

function routeBadge(route) {
  const labels = { GENERAL: '일반 지식', DOCUMENT: '사내 문서', DATABASE: '업무 데이터', BOTH: '문서 + 데이터' };
  return labels[route] ? `<span class="badge badge-${route}">${labels[route]}</span>` : '';
}

function evidenceStatusNote(status) {
  const labels = {
    SUPPORTED: '검증된 근거를 바탕으로 답변했습니다.',
    PARTIALLY_SUPPORTED: '일부 조회 결과를 확인할 수 없어, 확인된 근거만 바탕으로 답변했습니다.',
    INSUFFICIENT: '답변에 필요한 근거가 부족합니다. 다른 표현으로 다시 질문해 주세요.',
    CONTRADICTED: '조회된 근거 사이에 차이가 있어 답변을 확정하지 않았습니다.',
  };
  return labels[status] || (status ? `근거 상태: ${escapeHtml(status)}` : '');
}

function formatScore(score) {
  if (typeof score !== 'number') return '근거 확인';
  if (score >= 0.7) return '높은 관련성';
  if (score >= 0.35) return '관련성 있음';
  return '참고 근거';
}

function formatPages(pages) {
  if (!pages?.length) return '참조 페이지 정보 없음';
  return `${pages.join(', ')}페이지 참조`;
}

function safeWebUrl(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch (_) {
    return null;
  }
}

function safeDownloadUrl(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin || url.pathname !== '/api/documents/download') return null;
    return `${url.pathname}${url.search}`;
  } catch (_) {
    return null;
  }
}

function showDownloadError(message) {
  let toast = document.querySelector('#download-toast');
  if (!toast) {
    toast = document.createElement('p');
    toast.id = 'download-toast';
    toast.className = 'download-toast';
    toast.setAttribute('role', 'alert');
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.hidden = false;
  window.setTimeout(() => { toast.hidden = true; }, 4000);
}

function downloadFileName(response, fallbackFileName) {
  const disposition = response.headers.get('content-disposition') || '';
  const utf8Match = disposition.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
  const legacyMatch = disposition.match(/filename\s*=\s*(?:"([^"]+)"|([^;\s]+))/i);
  const encodedName = utf8Match?.[1] || legacyMatch?.[1] || legacyMatch?.[2];
  if (!encodedName) return fallbackFileName;
  try {
    return decodeURIComponent(encodedName.replace(/^"|"$/g, '')).split(/[\\/]/).pop() || fallbackFileName;
  } catch (_) {
    return fallbackFileName;
  }
}

async function handleDownload(button) {
  const downloadUrl = button.dataset.downloadUrl;
  const fileName = button.dataset.fileName || 'document';
  if (!downloadUrl) return;

  button.disabled = true;
  button.classList.add('is-loading');
  button.setAttribute('aria-label', '다운로드 중');
  try {
    const response = await fetch(downloadUrl);
    if (!response.ok) throw new Error(response.status === 404 ? '문서를 찾을 수 없습니다.' : '문서를 다운로드하지 못했습니다.');
    const blob = await response.blob();
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = downloadFileName(response, fileName);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
  } catch (error) {
    showDownloadError(userFriendlyError(error));
  } finally {
    button.disabled = false;
    button.classList.remove('is-loading');
    button.setAttribute('aria-label', `${fileName} 다운로드`);
  }
}

function renderSources(sources, route) {
  const documentSources = (sources || []).filter(source => source.source_type === 'document');
  const webSources = (sources || []).filter(source => source.source_type === 'web');
  const label = documentSources.length
    ? `문서 근거 ${documentSources.length}건`
    : webSources.length
      ? `웹 검색 근거 ${webSources.length}건`
      : route === 'DOCUMENT' ? '관련 문서를 찾지 못했습니다' : '문서 검색 결과가 여기에 표시됩니다';
  sourcesSummary.textContent = label;

  if (webSources.length) {
    sourcesList.innerHTML = webSources.map(source => {
      const title = source.title || source.url || '웹 출처';
      const sourceUrl = safeWebUrl(source.url);
      return `
      <article class="source-card">
        <div class="source-card-main">
          <div class="source-title-row">
            <span class="source-icon" aria-hidden="true">🌐</span>
            <h3 class="source-title">${escapeHtml(title)}</h3>
          </div>
          ${sourceUrl ? `<p class="source-meta"><a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(sourceUrl)}</a></p>` : ''}
        </div>
      </article>`;
    }).join('');
    return;
  }

  if (!documentSources.length) {
    sourcesList.innerHTML = `<div class="source-empty"><span aria-hidden="true">▤</span><p>${route === 'DOCUMENT' ? '관련 문서를 찾지 못했습니다. 다른 표현으로 다시 질문해 주세요.' : '사내 문서 검색을 실행하면 근거 문서와 관련도가 표시됩니다.'}</p></div>`;
    return;
  }

  sourcesList.innerHTML = documentSources.map(source => {
    const excerpts = (source.chunks || []).map(chunk => `
      <details class="source-excerpt">
        <summary>${chunk.page ? `${chunk.page}페이지 발췌` : '발췌 내용'}</summary>
        <p>${escapeHtml(chunk.text)}</p>
      </details>`).join('');
    const fileName = source.file_name || source.title || '문서';
    const downloadUrl = safeDownloadUrl(source.download_url);
    const downloadButton = downloadUrl ? `<button class="source-download" type="button" data-download-url="${escapeHtml(downloadUrl)}" data-file-name="${escapeHtml(fileName)}" aria-label="${escapeHtml(fileName)} 다운로드">다운로드</button>` : '';
    return `
    <article class="source-card">
      <div class="source-card-main">
        <div class="source-title-row">
          <span class="source-icon" aria-hidden="true">${documentIcon}</span>
          <h3 class="source-title">${escapeHtml(fileName)}</h3>
          ${downloadButton}
        </div>
        <p class="source-meta">${formatPages(source.pages)}${source.updated_at ? ` · 갱신 ${escapeHtml(source.updated_at)}` : ''}</p>
        <div class="source-excerpts">${excerpts}</div>
      </div>
    </article>`;
  }).join('');
}

function renderTable(table) {
  const headerHtml = table.columns.map(column => `<th>${escapeHtml(column)}</th>`).join('');
  const rowsHtml = table.rows.map(row => `<tr>${row.map((cell, index) => `<td${typeof cell === 'number' ? ' class="numeric"' : ''}>${escapeHtml(formatCell(cell, table.domain, table.columns[index]))}</td>`).join('')}</tr>`).join('');
  return `<div class="table-wrap"><div class="table-meta">${escapeHtml(table.domain)} 데이터 · ${table.rows.length}건</div><table class="data-table"><thead><tr>${headerHtml}</tr></thead><tbody>${rowsHtml}</tbody></table><details class="sql-detail"><summary>생성된 SQL 보기</summary><pre>${escapeHtml(table.sql)}</pre></details></div>`;
}

function formatCell(value, domain, column) {
  if (typeof value !== 'number') return value;
  const formatted = value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const isCurrencyColumn = /revenue|amount|sales|total|spend|price|cost/i.test(column || '');
  return domain === 'sales' && isCurrencyColumn ? `${formatted} JOD` : formatted;
}

function renderChartPlaceholder(table) {
  if (!table.chartable) return null;
  chartCounter += 1;
  const canvasId = `chart-${Date.now()}-${chartCounter}`;
  return { html: `<div class="chart-wrap"><canvas id="${canvasId}"></canvas></div>`, id: canvasId };
}

function drawChart(canvasId, table) {
  const labelIndex = table.columns.indexOf(table.label_column);
  const valueIndex = table.columns.indexOf(table.value_column);
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined' || labelIndex < 0 || valueIndex < 0) return;
  const chartType = table.chart_type || 'bar';
  const currencySuffix = table.domain === 'sales' ? ' JOD' : '';
  new Chart(canvas, { type: chartType, data: { labels: table.rows.map(row => String(row[labelIndex])), datasets: [{ label: table.value_column, data: table.rows.map(row => Number(row[valueIndex]) || 0), backgroundColor: '#2563eb', borderColor: '#2563eb', borderRadius: chartType === 'bar' ? 5 : 0, tension: chartType === 'line' ? 0.25 : 0, fill: false }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => `${context.dataset.label}: ${Number(context.parsed.y).toLocaleString()}${currencySuffix}` } } }, scales: { x: { ticks: { autoSkip: false, maxRotation: 50 } }, y: { beginAtZero: true, ticks: { callback: value => Number(value).toLocaleString() } } } } });
}

function scrollToLatest() {
  messages.scrollTop = messages.scrollHeight;
}

function setSourcesOpen(isOpen) {
  sourcesPanel.classList.toggle('is-open', isOpen);
  sourcesToggle.setAttribute('aria-expanded', String(isOpen));
  sourcesBackdrop.hidden = !isOpen;
}

function autoResize() {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
}

sourcesToggle.addEventListener('click', () => setSourcesOpen(!sourcesPanel.classList.contains('is-open')));
sourcesClose.addEventListener('click', () => setSourcesOpen(false));
sourcesBackdrop.addEventListener('click', () => setSourcesOpen(false));
sourcesList.addEventListener('click', event => {
  const button = event.target.closest('.source-download');
  if (button) handleDownload(button);
});

// 추가: 리포트 다운로드 임시 버튼. handleDownload()와 동일한 fetch → blob →
// objectURL → 링크 클릭 패턴을 재사용한다(documentIcon 다운로드 버튼과 같은 방식).
// 템플릿은 지금 하나(sales_monthly)뿐이라 하드코딩했다 — 여러 템플릿을 고를 수
// 있게 하려면 GET /api/reports/templates로 목록을 받아 <select>로 바꿔야 한다.
function setReportOpen(isOpen) {
  reportPanel.hidden = !isOpen;
  reportToggle.setAttribute('aria-expanded', String(isOpen));
}

reportToggle.addEventListener('click', () => setReportOpen(reportPanel.hidden));

reportDownloadButton.addEventListener('click', async () => {
  const startDate = reportStart.value;
  const endDate = reportEnd.value;
  reportStatus.classList.remove('is-error');
  if (!startDate || !endDate) {
    reportStatus.textContent = '시작일과 종료일을 모두 입력하세요.';
    reportStatus.classList.add('is-error');
    return;
  }

  reportDownloadButton.disabled = true;
  reportStatus.textContent = '리포트를 만드는 중입니다...';
  try {
    const response = await fetch('/api/reports/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id: 'sales_monthly', start_date: startDate, end_date: endDate }),
    });
    if (response.status === 401) { showLogin(); throw new Error('세션이 만료되었습니다. 다시 로그인하세요.'); }
    if (!response.ok) throw await responseError(response, '리포트를 생성하지 못했습니다.');

    const blob = await response.blob();
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = downloadFileName(response, 'report.docx');
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
    reportStatus.textContent = '다운로드가 시작됐습니다.';
  } catch (error) {
    reportStatus.textContent = userFriendlyError(error);
    reportStatus.classList.add('is-error');
  } finally {
    reportDownloadButton.disabled = false;
  }
});

input.addEventListener('input', autoResize);
input.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question || sendButton.disabled) return;

  messages.insertAdjacentHTML('beforeend', `<div class="msg-row user"><div class="msg"><span class="msg-label">나</span><div class="answer">${formatAnswer(question)}</div></div></div>`);
  input.value = '';
  autoResize();
  sendButton.disabled = true;
  const requestRevision = auth_state_revision;
  activeRequestController = new AbortController();

  const loadingId = `loading-${Date.now()}`;
  messages.insertAdjacentHTML('beforeend', `<div class="msg-row assistant loading-row" id="${loadingId}"><span class="avatar" aria-hidden="true">${robotIcon}</span><div class="msg"><span class="msg-label">사내 지식 챗봇</span><span class="loading">답변을 준비하고 있습니다</span></div></div>`);
  scrollToLatest();

  try {
    const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: activeRequestController.signal, body: JSON.stringify({ question }) });
    const data = await chatResponsePayload(response);
    if (requestRevision !== auth_state_revision) return;
    if (response.status === 401) { showLogin(); throw new Error('세션이 만료되었습니다. 다시 로그인하세요.'); }
    if (!response.ok) throw new Error(data.detail || `요청에 실패했습니다 (${response.status})`);

    const chartPlaceholders = [];
    const tablesHtml = (data.tables || []).map(table => {
      const chart = renderChartPlaceholder(table);
      if (chart) chartPlaceholders.push({ id: chart.id, table });
      return renderTable(table) + (chart?.html || '');
    }).join('');
    const cacheBadge = data.cached ? '<span class="badge badge-cached">캐시됨</span>' : '';
    const evidenceLabel = evidenceStatusNote(data.evidence_status);
    document.getElementById(loadingId).outerHTML = `<div class="msg-row assistant"><span class="avatar" aria-hidden="true">${robotIcon}</span><div class="msg"><span class="msg-label">사내 지식 챗봇</span><div class="meta">${routeBadge(data.route)}${cacheBadge}</div><div class="answer">${formatAnswer(data.answer)}</div>${tablesHtml}${evidenceLabel ? `<p class="evidence-note">${evidenceLabel}</p>` : ''}</div></div>`;
    chartPlaceholders.forEach(({ id, table }) => drawChart(id, table));
    renderSources(data.sources, data.route);
  } catch (error) {
    if (requestRevision !== auth_state_revision || error.name === 'AbortError') return;
    document.getElementById(loadingId).outerHTML = `<div class="msg-row assistant"><span class="avatar" aria-hidden="true">!</span><div class="msg error"><span class="msg-label">요청 오류</span><div class="answer">${escapeHtml(userFriendlyError(error))}</div></div></div>`;
  } finally {
    if (requestRevision !== auth_state_revision) return;
    activeRequestController = null;
    sendButton.disabled = false;
    scrollToLatest();
    input.focus();
  }
});

restoreSession();

// --- TEMP: 이상탐지 임시 대시보드 (GET /api/anomalies) ---------------------------
// 다른 팀원이 실제 이상탐지 대시보드를 완성하면 이 블록 전체를 지운다. 단, 이 블록
// 밖에서 이 블록을 참조하는 곳이 두 군데 있으니 같이 지워야 한다:
//   1) clearApplicationState() 안의 anomalyBody.innerHTML 초기화 줄
//   2) showApplication() 끝의 loadAnomalies() 호출 줄
// (둘 다 해당 함수 옆에 "TEMP" 주석을 남겨뒀다 — 1단계 삭제 체크리스트 참고)
const anomalyBody = document.querySelector('#anomaly-body');

function renderAnomalies(rows) {
  if (!rows || rows.length === 0) {
    anomalyBody.innerHTML = '<p class="anomaly-empty">이상 징후가 발견되지 않았습니다.</p>';
    return;
  }
  const typeLabels = { amount_outlier: '금액 이상치', overdue: '연체 과다', spike: '거래 급증' };
  const domainLabels = { sales: '판매', purchase: '구매' };
  const rowsHtml = rows.map(row => `
    <tr title="${escapeHtml(row.detail)}">
      <td><span class="anomaly-badge anomaly-badge-${row.domain}">${escapeHtml(domainLabels[row.domain] || row.domain)}</span></td>
      <td>${escapeHtml(typeLabels[row.type] || row.type)}</td>
      <td>${escapeHtml(row.entity)}</td>
      <td class="numeric">${Number(row.amount).toLocaleString()}</td>
    </tr>`).join('');
  anomalyBody.innerHTML = `
    <table class="anomaly-table">
      <thead><tr><th>도메인</th><th>유형</th><th>거래처</th><th>금액</th></tr></thead>
      <tbody>${rowsHtml}</tbody>
    </table>`;
}

async function loadAnomalies() {
  anomalyBody.innerHTML = '<p class="anomaly-loading">불러오는 중...</p>';
  try {
    const response = await fetch('/api/anomalies');
    if (!response.ok) throw await responseError(response, '이상탐지 데이터를 불러오지 못했습니다.');
    renderAnomalies(await response.json());
  } catch (error) {
    anomalyBody.innerHTML = `<p class="anomaly-empty">${escapeHtml(userFriendlyError(error))}</p>`;
  }
}
// --- // TEMP: 이상탐지 끝 -------------------------------------------------------
