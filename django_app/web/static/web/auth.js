// 로그인 화면·세션 복원·로그아웃을 담당하는 공용 스크립트입니다.
// index.html(채팅)과 dashboard.html이 둘 다 이 파일을 먼저 로드하고,
// 그 다음 각자의 페이지 전용 스크립트(chat.js/dashboard.js)를 로드합니다.
// 페이지별로 로그인·로그아웃 시 초기화할 상태가 다르므로, 직접 호출하는 대신
// window.onAuthStateCleared / window.onAuthStateReady 훅을 통해 위임합니다.
const loginScreen = document.querySelector('#login-screen');
const loginForm = document.querySelector('#login-form');
const loginError = document.querySelector('#login-error');
const loginButton = document.querySelector('#login-button');
const currentUser = document.querySelector('#current-user');
const logoutButton = document.querySelector('#logout-button');

let auth_state_revision = 0;
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

function showLogin() {
  loginScreen.hidden = false;
  document.querySelector('.app-shell')?.setAttribute('aria-hidden', 'true');
  document.querySelector('#username')?.focus();
}

// sales_db/purchase_db 접근 권한이 있는 역할만 볼 수 있는 화면들의 공통 목록.
// 대시보드(이상탐지)·리포트 생성 둘 다 매출/구매 데이터를 다루므로 같은 목록을 쓴다
// (shared/auth_policy.py의 hr=document_db만 허용과 대응).
const DASHBOARD_ROLES = ['admin', 'finance'];
const RESTRICTED_TAB_IDS = ['#dashboard-tab-link', '#report-tab-link'];

function showApplication(user) {
  loginScreen.hidden = true;
  document.querySelector('.app-shell')?.removeAttribute('aria-hidden');
  currentUser.textContent = `${user.display_name} (${user.role})`;
  const allowed = DASHBOARD_ROLES.includes(user.role);
  RESTRICTED_TAB_IDS.forEach(selector => {
    const tab = document.querySelector(selector);
    if (tab) tab.hidden = !allowed;
  });
  window.onAuthStateReady?.(user);
}

async function restoreSession() {
  const revision = auth_state_revision;
  const response = await fetch('/api/auth/me');
  if (revision !== auth_state_revision) return;
  if (response.ok) showApplication(await response.json()); else showLogin();
}

loginForm.addEventListener('submit', () => { auth_state_revision += 1; }, true);
loginForm.addEventListener('submit', async event => {
  event.preventDefault();
  loginError.textContent = '';
  loginButton.disabled = true;
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: await csrfHeaders(),
      body: JSON.stringify({
        username: document.querySelector('#username').value,
        password: document.querySelector('#password').value,
      }),
    });
    if (!response.ok) throw await responseError(response, '아이디 또는 비밀번호가 올바르지 않습니다.');
    window.onAuthStateCleared?.();
    csrfTokenValue = null;
    showApplication((await response.json()).user);
    document.querySelector('#password').value = '';
  } catch (error) {
    csrfTokenValue = null;
    loginError.textContent = error.message;
  } finally {
    loginButton.disabled = false;
  }
});

logoutButton.addEventListener('click', async () => {
  auth_state_revision += 1;
  window.onAuthStateCleared?.();
  loginError.textContent = '';
  try {
    const response = await fetch('/api/auth/logout', { method: 'POST', headers: await csrfHeaders() });
    if (!response.ok && response.status !== 401) throw await responseError(response, '로그아웃하지 못했습니다.');
    csrfTokenValue = null;
    showLogin();
  } catch (error) {
    csrfTokenValue = null;
    loginError.textContent = error.message;
    await restoreSession();
  }
});
