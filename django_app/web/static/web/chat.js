// ChatResponse를 대화·출처·표 UI로 변환하는 vanilla JavaScript 경계입니다.
// 로그인·세션·로그아웃은 auth.js가 담당하며(이 파일보다 먼저 로드됨), 이 파일은
// window.onAuthStateCleared/onAuthStateReady 훅으로 필요한 시점에 반응합니다.
const form = document.querySelector('#chat-form');
const input = document.querySelector('#question');
const messages = document.querySelector('#messages');
const sendButton = document.querySelector('#send-button');
const sourcesPanel = document.querySelector('#sources-panel');
const sourcesList = document.querySelector('#sources-list');
const sourcesSummary = document.querySelector('#sources-summary');
const sourcesClose = document.querySelector('#sources-close');
const sourcesBackdrop = document.querySelector('#sources-backdrop');
const jumpBanner = document.querySelector('#jump-banner');
const jumpButton = document.querySelector('#jump-button');

let currentUserRole = null;

const EXAMPLE_QUESTIONS = {
  hr: ['법인카드 발급 방법 알려줘'],
  finance: ['2026년 1분기 매출을 2025년 1분기와 비교해줘'],
  admin: ['법인카드 발급 방법 알려줘', '2026년 1분기 매출을 2025년 1분기와 비교해줘'],
};
let activeRequestController = null;

// 답변별 출처: answerId -> { sources, route, index, question }
let answerCounter = 0;
const answerSources = new Map();
let selectedAnswerId = null;
let latestAnswerId = null;
const DEFAULT_SOURCES_SUMMARY = '문서 검색 결과가 여기에 표시됩니다';

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
  answerSources.clear();
  selectedAnswerId = null;
  latestAnswerId = null;
  answerCounter = 0;
  jumpBanner.classList.remove('is-visible');
  sourcesSummary.textContent = DEFAULT_SOURCES_SUMMARY;
  renderSources([], null);
  setSourcesOpen(false);
}

window.onAuthStateCleared = clearApplicationState;
window.onAuthStateReady = user => { currentUserRole = user.role; renderWelcomeIfEmpty(); };

function renderWelcomeIfEmpty() {
  if (messages.children.length > 0) return;
  const questions = EXAMPLE_QUESTIONS[currentUserRole] || EXAMPLE_QUESTIONS.admin;
  const chipsHtml = questions.map(q => `<button type="button" class="example-chip" data-question="${escapeHtml(q)}">${escapeHtml(q)}</button>`).join('');
  messages.innerHTML = `
    <div class="welcome-screen">
      <div class="welcome-icon">${robotIcon}</div>
      <h2 class="welcome-title">사내 지식 챗봇에게 물어보세요</h2>
      <p class="welcome-sub">문서 검색과 업무 데이터 조회를 도와드립니다</p>
      <div class="example-questions">${chipsHtml}</div>
    </div>`;
}
const chatbotIconUrl = document.body.dataset.chatbotIcon;
const robotIcon = `<img src="${chatbotIconUrl}" class="avatar-icon" alt="">`;
const documentIcon = '<svg viewBox="0 0 24 24" class="svg-icon"><path d="M6 3h8l4 4v14H6zM14 3v5h5M9 12h6M9 16h6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"/></svg>';
const databaseIcon = '<svg viewBox="0 0 24 24" class="svg-icon"><path d="M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3Zm0 0v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"/></svg>';

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

function formatFreshness(seconds) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds)) return null;
  if (seconds < 60) return `${Math.round(seconds)}초 전 기준 데이터`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}분 전 기준 데이터`;
  return `${Math.round(seconds / 3600)}시간 전 기준 데이터`;
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

function sourceChipHtml(sources, route, answerId) {
  const documentSources = (sources || []).filter(source => source.source_type === 'document');
  const databaseSources = (sources || []).filter(source => source.source_type === 'database');
  const webSources = (sources || []).filter(source => source.source_type === 'web');

  const parts = [];
  if (documentSources.length) parts.push(`문서 ${documentSources.length}건`);
  if (databaseSources.length) parts.push(`데이터 ${databaseSources.length}건`);
  if (parts.length) {
    const total = documentSources.length + databaseSources.length;
    return `<button class="source-chip" type="button" data-target="${answerId}">${documentIcon}<span>${parts.join(' · ')} 근거 보기</span><span class="count">${total}</span></button>`;
  }
  if (webSources.length) {
    return `<button class="source-chip" type="button" data-target="${answerId}">🌐<span>웹 출처 ${webSources.length}건 보기</span><span class="count">${webSources.length}</span></button>`;
  }
  if (route === 'DOCUMENT' || route === 'DATABASE' || route === 'BOTH') {
    return `<button class="source-chip is-empty" type="button" data-target="${answerId}">${documentIcon}<span>근거 0건</span><span class="count">0</span></button>`;
  }
  return '';
}

function selectAnswer(answerId) {
  const entry = answerSources.get(answerId);
  if (!entry) return;
  selectedAnswerId = answerId;
  document.querySelectorAll('.msg-row.assistant[data-answer-id]').forEach(row => {
    row.classList.toggle('is-selected', row.dataset.answerId === answerId);
  });
  sourcesSummary.textContent = `${entry.index}번째 답변 · "${entry.question}"의 근거`;
  renderSources(entry.sources, entry.route);
  if (answerId === latestAnswerId) jumpBanner.classList.remove('is-visible');
}

function documentCardHtml(source) {
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
}

function databaseCardHtml(source) {
  const title = source.title || '업무 데이터 조회';
  const metaParts = [];
  if (source.table_name) metaParts.push(`테이블 ${source.table_name}`);
  const freshness = formatFreshness(source.freshness_seconds);
  if (freshness) metaParts.push(freshness);
  if (source.source_version) metaParts.push(`버전 ${source.source_version}`);
  return `
  <article class="source-card">
    <div class="source-card-main">
      <div class="source-title-row">
        <span class="source-icon" aria-hidden="true">${databaseIcon}</span>
        <h3 class="source-title">${escapeHtml(title)}</h3>
      </div>
      ${metaParts.length ? `<p class="source-meta">${metaParts.map(escapeHtml).join(' · ')}</p>` : ''}
    </div>
  </article>`;
}

function webCardHtml(source) {
  // 서버 Source 스키마에 url 필드가 없어 응답 직렬화 시 사라지는 경우가 있다
  // (app/schemas/chat.py 확인 필요). 웹 출처는 id에 항상 같은 URL이 들어있어
  // 임시로 id를 대체 값으로 쓴다.
  const sourceUrl = safeWebUrl(source.url) || safeWebUrl(source.id);
  const title = source.title || sourceUrl || '웹 출처';
  const tag = sourceUrl ? 'a' : 'div';
  const linkAttrs = sourceUrl ? ` href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer"` : '';
  return `
  <${tag} class="source-card"${linkAttrs}>
    <div class="source-card-main">
      <div class="source-title-row">
        <span class="source-icon" aria-hidden="true">🌐</span>
        <h3 class="source-title">${escapeHtml(title)}</h3>
      </div>
      ${sourceUrl ? `<p class="source-meta">${escapeHtml(sourceUrl)}</p><p class="source-card-web-hint">새 창에서 열기 ↗</p>` : ''}
    </div>
  </${tag}>`;
}

function renderSources(sources, route) {
  const documentSources = (sources || []).filter(source => source.source_type === 'document');
  const databaseSources = (sources || []).filter(source => source.source_type === 'database');
  const webSources = (sources || []).filter(source => source.source_type === 'web');

  if (documentSources.length || databaseSources.length) {
    sourcesList.innerHTML = documentSources.map(documentCardHtml).join('') + databaseSources.map(databaseCardHtml).join('');
    return;
  }

  if (webSources.length) {
    sourcesList.innerHTML = webSources.map(webCardHtml).join('');
    return;
  }

  sourcesList.innerHTML = `<div class="source-empty"><span aria-hidden="true">▤</span><p>${route === 'DOCUMENT' || route === 'DATABASE' || route === 'BOTH' ? '관련 근거를 찾지 못했습니다. 다른 표현으로 다시 질문해 주세요.' : '사내 문서 검색을 실행하면 근거 문서와 관련도가 표시됩니다.'}</p></div>`;
}

function formatCell(value, domain, column) {
  if (typeof value !== 'number') return value;
  const formatted = value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const isCurrencyColumn = /revenue|amount|sales|total|spend|price|cost/i.test(column || '');
  return domain === 'sales' && isCurrencyColumn ? `${formatted} JOD` : formatted;
}

// ------------------------------------------------------------
// CSV 다운로드: 화면에 보이는 현재 상태(정렬·상위N 반영)를 그대로 내보낸다.
// 숫자는 화면 표시용 포맷(콤마·통화기호) 대신 원본 값으로 내보내 재계산 가능하게 한다.
// ------------------------------------------------------------
function csvEscape(value) {
  const s = String(value ?? '');
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function downloadCsv(columns, rows, fileNameBase) {
  const lines = [columns.map(csvEscape).join(',')];
  rows.forEach(row => lines.push(row.map(csvEscape).join(',')));
  const csv = '﻿' + lines.join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${fileNameBase}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ------------------------------------------------------------
// 기간 대비 요약: 서버가 기간 컬럼을 명시하지 않으므로 컬럼명·값 형식 패턴으로
// 추정한다. 추정에 실패하면 전월·전년 대비는 조용히 생략하고 최고/최저만 보여준다.
// ------------------------------------------------------------
const PERIOD_NAME_PATTERN = /(월|년|기간|date|month|year|period)/i;

function parsePeriod(value) {
  const s = String(value ?? '').trim();
  let m = s.match(/^(\d{4})[-/](\d{1,2})(?:[-/]\d{1,2})?$/);
  if (m) return { year: +m[1], month: +m[2] };
  m = s.match(/^(\d{4})년\s*(\d{1,2})월$/);
  if (m) return { year: +m[1], month: +m[2] };
  m = s.match(/^(\d{4})년?$/);
  if (m) return { year: +m[1], month: null };
  return null;
}

function detectPeriodColumnIndex(columns) {
  return columns.findIndex(c => PERIOD_NAME_PATTERN.test(c));
}

function computeSummary(table, rows) {
  const valueIdx = table.columns.indexOf(table.value_column);
  if (valueIdx < 0 || !rows.length) return null;
  let maxRow = rows[0], minRow = rows[0], sum = 0;
  for (const row of rows) {
    const value = Number(row[valueIdx]);
    if (value > Number(maxRow[valueIdx])) maxRow = row;
    if (value < Number(minRow[valueIdx])) minRow = row;
    sum += value;
  }
  const fmt = value => formatCell(value, table.domain, table.value_column);
  const summary = {
    max: { label: maxRow[0], text: fmt(maxRow[valueIdx]) },
    min: { label: minRow[0], text: fmt(minRow[valueIdx]) },
    avg: fmt(sum / rows.length),
    yoy: null,
  };

  const periodIdx = detectPeriodColumnIndex(table.columns);
  if (periodIdx < 0) return summary;

  const parsed = rows
    .map(row => ({ period: parsePeriod(row[periodIdx]), value: Number(row[valueIdx]) }))
    .filter(p => p.period && p.period.month != null && Number.isFinite(p.value));
  if (parsed.length < 2) return summary;

  // 같은 월이 두 번 이상 나오면(월×제품 등 다차원 표) 어느 행끼리 비교해야 할지
  // 알 수 없어 전년 대비를 계산하지 않는다. "월 하나당 행 하나"인 단일
  // 시계열일 때만 신뢰할 수 있는 비교다.
  const periodKeys = parsed.map(p => `${p.period.year}-${p.period.month}`);
  const hasDuplicatePeriod = new Set(periodKeys).size !== periodKeys.length;
  if (hasDuplicatePeriod) return summary;

  parsed.sort((a, b) => (a.period.year - b.period.year) || (a.period.month - b.period.month));
  const latest = parsed[parsed.length - 1];

  const prevYear = parsed.find(p => p.period.year === latest.period.year - 1 && p.period.month === latest.period.month);
  if (prevYear && prevYear.value !== 0) {
    summary.yoy = ((latest.value - prevYear.value) / Math.abs(prevYear.value)) * 100;
  }

  return summary;
}

function deltaSpan(pct) {
  const cls = pct >= 0 ? 'delta-up' : 'delta-down';
  const arrow = pct >= 0 ? '▲' : '▼';
  return `<span class="${cls}">${arrow} ${Math.abs(pct).toFixed(1)}%</span>`;
}

function summaryHtml(summary) {
  if (!summary) return '';
  const parts = [
    `최고 <strong>${escapeHtml(summary.max.label)}</strong> (${escapeHtml(summary.max.text)})`,
    `최저 <strong>${escapeHtml(summary.min.label)}</strong> (${escapeHtml(summary.min.text)})`,
    `평균 <strong>${escapeHtml(summary.avg)}</strong>`,
  ];
  if (summary.yoy !== null) parts.push(`전년 동월 대비 ${deltaSpan(summary.yoy)}`);
  return parts.map(p => `<span>${p}</span>`).join('');
}

// ------------------------------------------------------------
// 표+차트 블록: 정렬·상위N 상태와 Chart 인스턴스를 테이블별로 독립적으로 갖는다.
// ------------------------------------------------------------
function mountTableBlock(container, table, blockId) {
  const state = { sortCol: -1, sortDir: 0, topN: 'all' };
  let chartInstance = null;

  function currentRows() {
    let rows = table.rows.slice();
    if (state.sortCol >= 0 && state.sortDir !== 0) {
      rows.sort((a, b) => {
        const av = a[state.sortCol], bv = b[state.sortCol];
        const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv));
        return state.sortDir === 1 ? cmp : -cmp;
      });
    }
    if (state.topN !== 'all') rows = rows.slice(0, Number(state.topN));
    return rows;
  }

  function render() {
    const rows = currentRows();
    const headerHtml = table.columns.map((column, index) => {
      const active = state.sortCol === index && state.sortDir !== 0;
      const arrow = active ? (state.sortDir === 1 ? '▲' : '▼') : '▲▼';
      return `<th class="sortable" data-col="${index}">${escapeHtml(column)}<span class="sort-arrow${active ? ' is-active' : ''}">${arrow}</span></th>`;
    }).join('');
    const rowsHtml = rows.map(row => `<tr>${row.map((cell, index) => `<td${typeof cell === 'number' ? ' class="numeric"' : ''}>${escapeHtml(formatCell(cell, table.domain, table.columns[index]))}</td>`).join('')}</tr>`).join('');
    const summary = table.value_column ? computeSummary(table, rows) : null;

    container.innerHTML = `
      <div class="table-wrap">
        <div class="table-meta">
          <span class="table-meta-label">${escapeHtml(table.domain)} 데이터 · ${rows.length}건${rows.length !== table.rows.length ? ` (전체 ${table.rows.length}건 중)` : ''}</span>
          <div class="table-controls">
            <select class="topn-select">
              <option value="all">전체 보기</option>
              <option value="5">상위 5개</option>
              <option value="10">상위 10개</option>
            </select>
            <button type="button" class="csv-button">⭳ CSV 다운로드</button>
          </div>
        </div>
        <table class="data-table"><thead><tr>${headerHtml}</tr></thead><tbody>${rowsHtml}</tbody></table>
        <details class="sql-detail"><summary>생성된 SQL 보기</summary><pre>${escapeHtml(table.sql)}</pre></details>
      </div>
      <div class="period-summary${summary ? '' : ' is-empty'}">${summaryHtml(summary)}</div>
      ${table.chartable ? `
      <div class="chart-wrap">
        <div class="chart-wrap-header"><button type="button" class="chart-save-button">🖼 이미지 저장</button></div>
        <div class="chart-canvas-box"><canvas id="${blockId}-canvas"></canvas></div>
      </div>` : ''}
    `;

    container.querySelector('.topn-select').value = state.topN;
    container.querySelectorAll('th.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const col = Number(th.dataset.col);
        if (state.sortCol !== col) { state.sortCol = col; state.sortDir = 1; }
        else if (state.sortDir === 1) state.sortDir = -1;
        else if (state.sortDir === -1) { state.sortCol = -1; state.sortDir = 0; }
        else state.sortDir = 1;
        render();
      });
    });
    container.querySelector('.topn-select').addEventListener('change', event => {
      state.topN = event.target.value;
      render();
    });
    container.querySelector('.csv-button').addEventListener('click', () => {
      downloadCsv(table.columns, currentRows(), `${table.domain}_${blockId}`);
    });

    if (table.chartable) {
      const labelIndex = table.columns.indexOf(table.label_column);
      const valueIndex = table.columns.indexOf(table.value_column);
      const canvas = container.querySelector(`#${blockId}-canvas`);
      if (chartInstance) chartInstance.destroy();
      if (canvas && typeof Chart !== 'undefined' && labelIndex >= 0 && valueIndex >= 0) {
        const chartType = table.chart_type || 'bar';
        const currencySuffix = table.domain === 'sales' ? ' JOD' : '';
        chartInstance = new Chart(canvas, {
          type: chartType,
          data: {
            labels: rows.map(row => String(row[labelIndex])),
            datasets: [{ label: table.value_column, data: rows.map(row => Number(row[valueIndex]) || 0), backgroundColor: '#2563eb', borderColor: '#2563eb', borderRadius: chartType === 'bar' ? 5 : 0, tension: chartType === 'line' ? 0.25 : 0, fill: false }],
          },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => `${context.dataset.label}: ${Number(context.parsed.y).toLocaleString()}${currencySuffix}` } } }, scales: { x: { ticks: { autoSkip: false, maxRotation: 50 } }, y: { beginAtZero: true, ticks: { callback: value => Number(value).toLocaleString() } } } },
        });
      }
      const saveButton = container.querySelector('.chart-save-button');
      if (saveButton) {
        saveButton.addEventListener('click', () => {
          if (!chartInstance) return;
          const a = document.createElement('a');
          a.href = chartInstance.toBase64Image();
          a.download = `${table.domain}_${blockId}_chart.png`;
          document.body.appendChild(a);
          a.click();
          a.remove();
        });
      }
    }
  }

  render();
}

function scrollToLatest() {
  messages.scrollTop = messages.scrollHeight;
}

function setSourcesOpen(isOpen) {
  sourcesPanel.classList.toggle('is-open', isOpen);
  sourcesBackdrop.hidden = !isOpen;
}

function autoResize() {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
}

sourcesClose.addEventListener('click', () => setSourcesOpen(false));
sourcesBackdrop.addEventListener('click', () => setSourcesOpen(false));
sourcesList.addEventListener('click', event => {
  const button = event.target.closest('.source-download');
  if (button) handleDownload(button);
});
messages.addEventListener('click', event => {
  const chip = event.target.closest('.source-chip');
  if (chip) { selectAnswer(chip.dataset.target); setSourcesOpen(true); return; }
  const example = event.target.closest('.example-chip');
  if (example) { input.value = example.dataset.question; autoResize(); form.requestSubmit(); }
});
jumpButton.addEventListener('click', () => selectAnswer(latestAnswerId));
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

  document.querySelector('.welcome-screen')?.remove();
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

    answerCounter += 1;
    const answerId = `ans-${answerCounter}`;
    const tableBlocks = (data.tables || []).map((table, index) => ({ id: `${answerId}-table-${index}`, table }));
    const tablesHtml = tableBlocks.map(({ id }) => `<div class="table-block" id="${id}"></div>`).join('');
    const cacheBadge = data.cached ? '<span class="badge badge-cached">캐시됨</span>' : '';
    const evidenceLabel = evidenceStatusNote(data.evidence_status);
    const chipHtml = sourceChipHtml(data.sources, data.route, answerId);
    document.getElementById(loadingId).outerHTML = `<div class="msg-row assistant" data-answer-id="${answerId}"><span class="avatar" aria-hidden="true">${robotIcon}</span><div class="msg"><span class="msg-label">사내 지식 챗봇</span><div class="meta">${routeBadge(data.route)}${cacheBadge}</div><div class="answer">${formatAnswer(data.answer)}</div>${tablesHtml}${evidenceLabel ? `<p class="evidence-note">${evidenceLabel}</p>` : ''}${chipHtml}</div></div>`;
    tableBlocks.forEach(({ id, table }) => mountTableBlock(document.getElementById(id), table, id));

    if (chipHtml) {
      const wasFollowingLatest = selectedAnswerId === null || selectedAnswerId === latestAnswerId;
      answerSources.set(answerId, { sources: data.sources || [], route: data.route, index: answerCounter, question });
      latestAnswerId = answerId;
      if (wasFollowingLatest) {
        selectAnswer(answerId);
      } else {
        jumpBanner.classList.add('is-visible');
      }
    }
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
