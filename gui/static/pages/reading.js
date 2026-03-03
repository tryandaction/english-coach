// pages/reading.js — Reading comprehension with split-pane layout

const STORAGE_KEY = 'reading_current';

// Use localStorage so content persists across app restarts
const _store = {
  get: () => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { return null; } },
  set: (v) => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(v)); } catch {} },
  clear: () => { try { localStorage.removeItem(STORAGE_KEY); } catch {} },
};

let _sid = null;
let _qTotal = 0;
let _qIndex = 0;
let _correct = 0;
let _passageData = null;

export async function render(el) {
  el.innerHTML = `
    <h1>📖 Reading Comprehension</h1>
    <p>Read the passage carefully, then answer the questions.</p>
    <div id="reading-body"></div>
  `;

  // Try to restore saved session from localStorage
  const saved = _store.get();

  if (saved && saved.session_id) {
    _sid = saved.session_id;
    _qTotal = saved.question_count || 0;
    _qIndex = saved.q_index || 0;
    _correct = saved.correct || 0;
    _passageData = saved;

    if (_qIndex > 0 && _qIndex < _qTotal) {
      // Was mid-questions — restore split layout and resume
      renderSplitLayout(el, saved);
      await loadQuestion(el);
    } else {
      renderPassage(el, saved);
    }
    return;
  }

  await startSession(el);
}

async function startSession(el) {
  const body = el.querySelector('#reading-body');
  body.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div></div>';

  try {
    const r = await api.post('/api/reading/start', {});
    if (r.error) {
      body.innerHTML = `<div class="alert alert-warn">${r.message}</div>`;
      return;
    }
    _sid = r.session_id;
    _qTotal = r.question_count;
    _qIndex = 0; _correct = 0;
    _passageData = r;

    // Persist to localStorage
    _store.set({...r, q_index: 0, correct: 0});

    renderPassage(el, r);
  } catch (e) {
    const noProfile = e.message.includes('profile') || e.message.includes('Profile');
    if (noProfile) {
      body.innerHTML = `<div class="alert alert-warn">
        Please complete setup before using Reading.
        <button class="btn btn-primary" style="margin-top:12px;display:block" onclick="navigate('setup')">Go to Setup →</button>
      </div>`;
    } else {
      body.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
  }
}

function renderPassage(el, r) {
  const body = el.querySelector('#reading-body');
  body.innerHTML = `
    <div class="card">
      <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap">
        ${r.difficulty ? `<span class="tag">${r.difficulty}</span>` : ''}
        ${r.topic ? `<span class="tag">${r.topic}</span>` : ''}
        <span class="tag">${r.word_count} words</span>
        ${r.ai_generated ? `<span class="tag" style="color:var(--accent);border-color:var(--accent)">AI</span>` : ''}
        <div style="margin-left:auto;display:flex;gap:8px">
          <button class="tts-btn" id="tts-passage" title="Read aloud">🔊</button>
          <button class="btn btn-outline" id="btn-new-passage" style="font-size:12px;padding:5px 10px">New Passage ↺</button>
        </div>
      </div>
      <div class="passage-box" id="passage-text">${escHtml(r.passage)}</div>
      ${r.has_questions
        ? `<button class="btn btn-primary" id="btn-start-q" style="margin-top:16px">Start Questions (${_qTotal}) →</button>`
        : `<div class="alert alert-info" style="margin-top:16px">No API key — questions unavailable.
            <button class="btn btn-outline" style="margin-left:8px" onclick="navigate('home')">← Home</button></div>`
      }
    </div>
  `;

  body.querySelector('#tts-passage').addEventListener('click', () => {
    tts(body.querySelector('#passage-text').textContent);
  });

  body.querySelector('#btn-new-passage').addEventListener('click', () => {
    _store.clear();
    startSession(el);
  });

  if (r.has_questions) {
    body.querySelector('#btn-start-q').addEventListener('click', () => {
      renderSplitLayout(el, r);
      loadQuestion(el);
    });
  }
}

function renderSplitLayout(el, r) {
  const body = el.querySelector('#reading-body');
  body.innerHTML = `
    <div class="reading-split">
      <div class="reading-left">
        <div class="card">
          <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap">
            ${r.difficulty ? `<span class="tag">${r.difficulty}</span>` : ''}
            ${r.topic ? `<span class="tag">${r.topic}</span>` : ''}
            <span class="tag">${r.word_count} words</span>
            <div style="margin-left:auto;display:flex;gap:8px">
              <button class="tts-btn" id="tts-passage-split" title="Read aloud">🔊</button>
              <button class="btn btn-outline" id="btn-new-passage-split" style="font-size:12px;padding:5px 10px">New Passage ↺</button>
            </div>
          </div>
          <div class="passage-box" id="passage-text-split">${escHtml(r.passage)}</div>
        </div>
      </div>
      <div class="reading-right" id="qa-panel">
        <div style="text-align:center;padding:40px"><div class="spinner"></div></div>
      </div>
    </div>
  `;

  body.querySelector('#tts-passage-split').addEventListener('click', () => {
    tts(body.querySelector('#passage-text-split').textContent);
  });

  body.querySelector('#btn-new-passage-split').addEventListener('click', () => {
    _store.clear();
    startSession(el);
  });
}

async function loadQuestion(el) {
  // If split layout not yet rendered, render it first
  if (!el.querySelector('.reading-split')) {
    renderSplitLayout(el, _passageData);
  }

  const panel = el.querySelector('#qa-panel');
  if (panel) panel.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div></div>';

  try {
    const q = await api.get(`/api/reading/question/${_sid}/${_qIndex}`);
    renderQuestion(el, q);
  } catch (e) {
    if (e.message.includes('404') || e.message.includes('not found') || e.message.includes('Session')) {
      // Session expired — start fresh
      _store.clear();
      await startSession(el);
    } else {
      const panel = el.querySelector('#qa-panel');
      if (panel) panel.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
  }
}

function renderQuestion(el, q) {
  const panel = el.querySelector('#qa-panel');
  if (!panel) return;

  const typeLabel = {
    factual: 'Factual', negative_factual: 'Negative Factual', inference: 'Inference',
    vocabulary: 'Vocabulary', rhetorical: 'Rhetorical Purpose', tfng: 'True/False/Not Given',
    mc: 'Multiple Choice', purpose: 'Author\'s Purpose', argument: 'Argument',
    main_idea: 'Main Idea', detail: 'Detail', fill: 'Fill in Blank',
  }[q.type] || q.type;

  const hasMC = Array.isArray(q.options) && q.options.length > 0;

  panel.innerHTML = `
    <div class="card">
      <div style="display:flex;justify-content:space-between;margin-bottom:16px">
        <span class="tag">${escHtml(typeLabel)}</span>
        <span style="font-size:13px;color:var(--text-dim)">Q${q.index + 1} / ${q.total}</span>
      </div>
      <div class="sentence-display" style="font-size:16px;line-height:1.6">${escHtml(q.question)}</div>
      ${hasMC
        ? `<div class="choices" id="choices" style="margin-top:16px"></div>`
        : `<div class="form-group" style="margin-top:16px">
            <input id="ans-input" type="text" placeholder="Type your answer..."
              style="width:100%;padding:10px 14px;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:8px;font-size:15px;outline:none">
           </div>
           <button class="btn btn-primary" id="btn-submit-ans" style="margin-top:8px">Submit</button>`
      }
      <div id="ans-feedback" class="hidden" style="margin-top:16px"></div>
      <button class="btn btn-outline hidden" id="btn-next-q" style="margin-top:12px">Next →</button>
    </div>
  `;

  if (hasMC) {
    const choicesEl = panel.querySelector('#choices');
    q.options.forEach((opt, i) => {
      const b = document.createElement('button');
      b.className = 'choice-btn';
      b.textContent = opt;
      b.addEventListener('click', async () => {
        choicesEl.querySelectorAll('.choice-btn').forEach(x => x.disabled = true);
        try {
          const r = await api.post(`/api/reading/answer/${_sid}`, {
            question_index: _qIndex,
            user_answer: opt,
          });
          // Highlight correct/wrong
          const letter = opt.charAt(0);
          choicesEl.querySelectorAll('.choice-btn').forEach(x => {
            const xl = x.textContent.charAt(0);
            if (xl === r.model_answer.charAt(0)) x.classList.add('correct');
            else if (x === b && !r.correct) x.classList.add('wrong');
          });
          showFeedback(el, r, q);
        } catch {}
      });
      choicesEl.appendChild(b);
    });
  } else {
    const input = panel.querySelector('#ans-input');
    input.focus();
    input.addEventListener('keydown', e => { if (e.key === 'Enter') panel.querySelector('#btn-submit-ans').click(); });
    panel.querySelector('#btn-submit-ans').addEventListener('click', async () => {
      const ans = input.value.trim();
      if (!ans) return;
      panel.querySelector('#btn-submit-ans').disabled = true;
      try {
        const r = await api.post(`/api/reading/answer/${_sid}`, {
          question_index: _qIndex,
          user_answer: ans,
        });
        showFeedback(el, r, q);
      } catch (e) {
        panel.querySelector('#btn-submit-ans').disabled = false;
      }
    });
  }
}

function showFeedback(el, r, q) {
  const panel = el.querySelector('#qa-panel');
  if (!panel) return;

  const fb = panel.querySelector('#ans-feedback');
  fb.classList.remove('hidden');
  fb.innerHTML = r.correct
    ? `<div class="alert alert-success">✓ Correct! ${escHtml(r.explanation)}</div>`
    : `<div class="alert alert-warn">
        <strong>Model answer:</strong> ${escHtml(r.model_answer)}<br>
        <span style="font-size:13px">${escHtml(r.explanation)}</span>
       </div>`;

  if (r.correct) _correct++;
  _qIndex++;

  // Update localStorage progress
  try {
    const saved = _store.get() || {};
    saved.q_index = _qIndex;
    saved.correct = _correct;
    _store.set(saved);
  } catch {}

  const nextBtn = panel.querySelector('#btn-next-q');
  nextBtn.classList.remove('hidden');

  if (r.session_complete) {
    nextBtn.textContent = 'See Results';
    nextBtn.addEventListener('click', () => showResults(el, r.stats));
  } else {
    nextBtn.addEventListener('click', () => loadQuestion(el));
  }
}

function showResults(el, stats) {
  _store.clear();
  const body = el.querySelector('#reading-body');
  const acc = Math.round((stats.correct / Math.max(stats.answered, 1)) * 100);
  const color = acc >= 67 ? 'var(--green)' : 'var(--yellow)';
  body.innerHTML = `
    <div class="card" style="text-align:center;padding:40px">
      <div style="font-size:48px;margin-bottom:16px">📖</div>
      <h2>Reading Complete!</h2>
      <div style="font-size:36px;font-weight:700;color:${color};margin:16px 0">${acc}%</div>
      <p>${stats.correct} / ${stats.answered} questions correct</p>
      <div style="display:flex;gap:12px;justify-content:center;margin-top:24px">
        <button class="btn btn-primary" id="btn-read-another">Read Another</button>
        <button class="btn btn-outline" onclick="navigate('home')">← Home</button>
      </div>
    </div>
  `;
  body.querySelector('#btn-read-another').addEventListener('click', () => startSession(el));
}

function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
