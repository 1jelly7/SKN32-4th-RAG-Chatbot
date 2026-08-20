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
const loginScreen = document.querySelector('#login-screen');
const loginForm = document.querySelector('#login-form');
const loginError = document.querySelector('#login-error');
const loginButton = document.querySelector('#login-button');
const currentUser = document.querySelector('#current-user');
const logoutButton = document.querySelector('#logout-button');

let chartCounter = 0;
let auth_state_revision = 0;
let activeRequestController = null;

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
}
function showLogin() { loginScreen.hidden = false; document.querySelector('.app-shell').setAttribute('aria-hidden', 'true'); document.querySelector('#username').focus(); }
function showApplication(user) { loginScreen.hidden = true; document.querySelector('.app-shell').removeAttribute('aria-hidden'); currentUser.textContent = `${user.display_name} (${user.role})`; }
async function restoreSession() { const response = await fetch('/api/auth/me'); if (response.ok) showApplication(await response.json()); else showLogin(); }
loginForm.addEventListener('submit', async event => { event.preventDefault(); loginError.textContent = ''; loginButton.disabled = true; try { const response = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: document.querySelector('#username').value, password: document.querySelector('#password').value }) }); if (!response.ok) throw new Error('아이디 또는 비밀번호가 올바르지 않습니다.'); clearApplicationState(); showApplication((await response.json()).user); document.querySelector('#password').value = ''; } catch (error) { loginError.textContent = error.message; } finally { loginButton.disabled = false; } });
logoutButton.addEventListener('click', async () => { auth_state_revision += 1; clearApplicationState(); try { await fetch('/api/auth/logout', { method: 'POST' }); } finally { showLogin(); } });

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
      return `
      <article class="source-card">
        <div class="source-card-main">
          <div class="source-title-row">
            <span class="source-icon" aria-hidden="true">🌐</span>
            <h3 class="source-title">${escapeHtml(title)}</h3>
          </div>
          ${source.url ? `<p class="source-meta"><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.url)}</a></p>` : ''}
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
    const downloadButton = source.download_url ? `<button class="source-download" type="button" data-download-url="${escapeHtml(source.download_url)}" data-file-name="${escapeHtml(fileName)}" aria-label="${escapeHtml(fileName)} 다운로드">다운로드</button>` : '';
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
    const data = await response.json();
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
    const evidenceLabel = data.evidence_status === 'SUPPORTED' ? '검증된 근거를 바탕으로 답변했습니다.' : data.evidence_status ? `근거 상태: ${escapeHtml(data.evidence_status)}` : '';
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