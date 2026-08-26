// 리포트 생성 화면. 템플릿 목록을 불러와 보여주고, 기간을 받아 .docx를 생성해
// 바로 다운로드한다. DASHBOARD_ROLES/showApplication의 탭 숨김은 auth.js가 담당하고,
// 이 파일은 hr이 URL로 직접 들어왔을 때의 화면 내용만 방어적으로 처리한다.
const reportRoot = document.querySelector('#report-root');

let templates = [];
let selectedTemplateId = null;
let isGenerating = false;
let statusKind = null;
let statusText = '';

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
}

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function templateCardHtml(template) {
  const selected = template.id === selectedTemplateId;
  return `
  <label class="template-card${selected ? ' is-selected' : ''}">
    <input type="radio" name="template" value="${escapeHtml(template.id)}" ${selected ? 'checked' : ''}>
    <div>
      <div class="template-name">${escapeHtml(template.name)}</div>
      <div class="template-desc">${escapeHtml(template.description)}</div>
    </div>
  </label>`;
}

function render() {
  if (!templates.length) {
    reportRoot.innerHTML = `
    <div class="dashboard">
      <h2 class="dashboard-title">리포트 생성</h2>
      <div class="empty-note">등록된 리포트 템플릿이 없습니다.</div>
    </div>`;
    return;
  }

  reportRoot.innerHTML = `
  <div class="dashboard">
    <h2 class="dashboard-title">리포트 생성</h2>
    <p class="dashboard-sub">템플릿과 조회 기간을 선택하면 .docx 문서로 만들어 바로 다운로드합니다.</p>
    <div class="template-list">${templates.map(templateCardHtml).join('')}</div>
    <div class="date-row">
      <div class="date-field"><label for="start-date">시작일</label><input type="date" id="start-date" value="${todayIsoDate()}" max="${todayIsoDate()}"></div>
      <div class="date-field"><label for="end-date">종료일</label><input type="date" id="end-date" value="${todayIsoDate()}" max="${todayIsoDate()}"></div>
    </div>
    <button type="button" class="generate-button" id="generate-button" ${isGenerating ? 'disabled' : ''}>${isGenerating ? '생성 중…' : '리포트 생성'}</button>
    <div id="report-status" class="report-status${statusKind ? ` status-${statusKind} is-visible` : ''}">${escapeHtml(statusText)}</div>
  </div>`;

  reportRoot.querySelectorAll('input[name="template"]').forEach(input => {
    input.addEventListener('change', () => {
      selectedTemplateId = input.value;
      render();
    });
  });
  reportRoot.querySelector('#generate-button').addEventListener('click', handleGenerate);
}

function setStatus(kind, text) {
  statusKind = kind;
  statusText = text || '';
  const el = reportRoot.querySelector('#report-status');
  if (!el) return;
  el.className = `report-status${kind ? ` status-${kind} is-visible` : ''}`;
  el.textContent = statusText;
}

function reportErrorMessage(status, detail) {
  const fallback = {
    400: '요청 형식이 올바르지 않습니다. 기간을 다시 확인해 주세요.',
    403: '요청한 데이터베이스에 접근할 권한이 없습니다.',
    404: '등록되지 않은 리포트 템플릿입니다.',
    422: '리포트를 만들기에 근거가 부족합니다.',
    502: '리포트 조회 중 오류가 발생했습니다.',
    503: '리포트 서비스를 사용할 수 없습니다.',
  }[status];
  return detail || fallback || '리포트 생성 중 오류가 발생했습니다.';
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

async function handleGenerate() {
  if (isGenerating) return;
  const startInput = reportRoot.querySelector('#start-date');
  const endInput = reportRoot.querySelector('#end-date');
  const startDate = startInput.value;
  const endDate = endInput.value;
  if (!startDate || !endDate) {
    setStatus('error', '시작일과 종료일을 모두 선택해 주세요.');
    return;
  }
  if (endDate < startDate) {
    setStatus('error', '종료일은 시작일보다 앞설 수 없습니다.');
    return;
  }

  isGenerating = true;
  render();
  setStatus('loading', '리포트를 생성하는 중입니다…');

  try {
    const response = await fetch('/api/reports/generate', {
      method: 'POST',
      headers: await csrfHeaders(),
      body: JSON.stringify({ template_id: selectedTemplateId, start_date: startDate, end_date: endDate }),
    });
    if (response.status === 401) {
      showLogin();
      throw new Error('세션이 만료되었습니다. 다시 로그인하세요.');
    }
    if (!response.ok) {
      let detail = null;
      try { detail = (await response.json()).detail; } catch (_) { /* 본문이 JSON이 아닐 수 있음 */ }
      throw new Error(reportErrorMessage(response.status, detail));
    }
    const blob = await response.blob();
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = downloadFileName(response, `${selectedTemplateId}.docx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
    setStatus('success', '리포트 생성이 완료되어 다운로드를 시작합니다.');
  } catch (error) {
    setStatus('error', error.message || '리포트 생성 중 오류가 발생했습니다.');
  } finally {
    isGenerating = false;
    render();
  }
}

async function loadTemplates() {
  try {
    const response = await fetch('/api/reports/templates');
    if (!response.ok) throw new Error('템플릿 목록을 불러오지 못했습니다.');
    templates = await response.json();
    selectedTemplateId = templates[0]?.id ?? null;
  } catch (_) {
    templates = [];
  }
  render();
}

function renderAccessDenied() {
  reportRoot.innerHTML = `
  <div class="dashboard-empty-role">
    <h2>리포트 생성에 접근할 수 없습니다</h2>
    <p>리포트는 매출·구매 데이터 접근 권한이 있는 계정만 만들 수 있습니다.</p>
  </div>`;
}

window.onAuthStateReady = user => {
  if (!DASHBOARD_ROLES.includes(user.role)) {
    renderAccessDenied();
    return;
  }
  loadTemplates();
};

window.onAuthStateCleared = () => {
  reportRoot.innerHTML = '';
  templates = [];
  selectedTemplateId = null;
  isGenerating = false;
};

restoreSession();
