<<<<<<< HEAD
const form = document.querySelector('#chat-form');
const input = document.querySelector('#question');
const messages = document.querySelector('#messages');

function routeBadge(route) {
  if (!route) return '';
  const labels = { GENERAL: '일반', DOCUMENT: '문서', DATABASE: 'DB', BOTH: '문서+DB' };
  return `<span class="badge badge-${route}">${labels[route] || route}</span>`;
}

function renderSources(sources) {
  if (!sources || sources.length === 0) return '';
  const items = sources.map(s => {
    const icon = s.source_type === 'document' ? '📄' : '🗄️';
    const scoreText = s.score != null ? ` (score ${s.score.toFixed(3)})` : '';
    return `<li>${icon} ${s.title}${scoreText}</li>`;
  }).join('');
  return `<details class="sources"><summary>참고 출처 (${sources.length})</summary><ul>${items}</ul></details>`;
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
    const cachedBadge = data.cached ? '<span class="badge badge-cached">캐시</span>' : '';

    document.getElementById(loadingId).outerHTML = `
      <div class="msg bot">
        <div class="meta">${routeBadge(data.route)}${cachedBadge}</div>
        <div class="answer">${data.answer.replace(/\n/g, '<br>')}</div>
        ${renderSources(data.sources)}
      </div>`;
  } catch (err) {
    document.getElementById(loadingId).outerHTML = `<div class="msg bot error">오류: ${err.message}</div>`;
  }
  messages.scrollTop = messages.scrollHeight;
});
=======
const form=document.querySelector('#chat-form'), input=document.querySelector('#question'), messages=document.querySelector('#messages');
form.addEventListener('submit', async e=>{e.preventDefault(); const question=input.value; messages.innerHTML+=`<p><b>나:</b> ${question}</p>`; input.value=''; const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})}); const d=await r.json(); messages.innerHTML+=`<p><b>봇:</b> ${d.answer} ${d.cached?'(cache)':''}</p>`;});
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0
