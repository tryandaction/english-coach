// pages/grammar.js — Grammar drill UI

const _GRAMMAR_POOL_KEY = 'grammar_pool';
const _qPool = {
  get: () => { try { return JSON.parse(localStorage.getItem(_GRAMMAR_POOL_KEY)) || []; } catch { return []; } },
  set: (v) => { try { localStorage.setItem(_GRAMMAR_POOL_KEY, JSON.stringify(v)); } catch {} },
  pop: () => {
    const items = _qPool.get();
    if (!items.length) return null;
    const item = items.shift();
    _qPool.set(items);
    return item;
  },
  refill: async (category, exam) => {
    try {
      const params = new URLSearchParams({ n: 5 });
      if (category) params.set('category', category);
      else if (exam && exam !== 'general') params.set('exam', exam);
      const r = await api.get('/api/grammar/pool?' + params);
      _qPool.set(r.questions || []);
    } catch {}
  },
};

let _session = { correct: 0, total: 0, current: null, category: null, exam: 'general' };
let _categories = [];

export async function render(el) {
  _session = { correct: 0, total: 0, current: null, category: null, exam: 'general' };

  el.innerHTML = `
    <h1>✏️ Grammar Drills</h1>
    <p>Fill-in-the-blank exercises targeting common error patterns.</p>

    <div class="card" style="margin-bottom:16px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
        <label style="font-size:13px;color:var(--text-dim)">Category</label>
        <span id="exam-badge-grammar"></span>
      </div>
      <div id="cat-groups"></div>
    </div>

    <div id="drill-area" class="card">
      <div id="drill-loading" style="text-align:center;padding:20px"><div class="spinner"></div></div>
    </div>

    <div id="session-stats" class="hidden" style="text-align:center;margin-top:8px">
      Score: <span id="stat-correct">0</span> / <span id="stat-total">0</span>
    </div>
  `;

  // Load categories with exam context
  let exam = 'general';
  try {
    const prog = await api.get('/api/progress');
    if (api.isAborted() || !el.isConnected) return;
    exam = prog.target_exam || 'general';
  } catch {}
  _session.exam = exam;

  const badge = el.querySelector('#exam-badge-grammar');
  if (badge && exam && exam !== 'general') {
    badge.innerHTML = `<span class="exam-badge exam-${exam}">${exam.toUpperCase()}</span>`;
  }

  try {
    const r = await api.get(`/api/grammar/categories?exam=${exam}`);
    if (api.isAborted() || !el.isConnected) return;
    _categories = r.categories || [];
  } catch {}

  _renderCategoryButtons(el);
  // Seed pool in background, then load first question (may hit pool on 2nd+ visit)
  if (_qPool.get().length < 2) _qPool.refill(_session.category, exam);
  loadQuestion(el);
}

function _renderCategoryButtons(el) {
  const groups = el.querySelector('#cat-groups');
  groups.innerHTML = '';

  // Group by general vs exam-specific
  const general = _categories.filter(c => c.group === 'General');
  const examSpecific = _categories.filter(c => c.group !== 'General');

  const makeBtn = (label, catKey, isActive) => {
    const b = document.createElement('button');
    b.className = 'btn btn-outline' + (isActive ? ' btn-primary' : '');
    b.textContent = label;
    b.dataset.cat = catKey;
    b.addEventListener('click', () => {
      groups.querySelectorAll('.btn').forEach(x => x.classList.remove('btn-primary'));
      b.classList.add('btn-primary');
      _session.category = catKey || null;
      _qPool.set([]); // clear pool when category changes
      _qPool.refill(_session.category, _session.exam);
      loadQuestion(el);
    });
    return b;
  };

  // Random button
  const row1 = document.createElement('div');
  row1.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px';
  row1.appendChild(makeBtn('Random', '', true));
  general.forEach(c => row1.appendChild(makeBtn(c.label, c.key, false)));
  groups.appendChild(row1);

  if (examSpecific.length > 0) {
    const divider = document.createElement('div');
    divider.style.cssText = 'font-size:11px;color:var(--text-dim);margin:6px 0 4px';
    divider.textContent = `${_session.exam.toUpperCase()} Specific`;
    groups.appendChild(divider);
    const row2 = document.createElement('div');
    row2.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap';
    examSpecific.forEach(c => row2.appendChild(makeBtn(c.label, c.key, false)));
    groups.appendChild(row2);
  }
}

async function loadQuestion(el) {
  const area = el.querySelector('#drill-area');
  if (!area) return;

  // Try pool first — instant, no spinner
  const pooled = _qPool.pop();
  if (pooled) {
    _session.current = pooled;
    renderQuestion(el, pooled);
    ttsPreload && ttsPreload(pooled.sentence.replace('___', 'blank'));
    if (_qPool.get().length < 2) _qPool.refill(_session.category, _session.exam);
    return;
  }

  // Pool empty — fetch with spinner
  area.innerHTML = '<div style="text-align:center;padding:20px"><div class="spinner"></div></div>';
  try {
    let url = '/api/grammar/question';
    const params = [];
    if (_session.category) params.push(`category=${_session.category}`);
    else if (_session.exam && _session.exam !== 'general') params.push(`exam=${_session.exam}`);
    if (params.length) url += '?' + params.join('&');
    const q = await api.get(url);

    if (api.isAborted() || !el.isConnected) return;

    _session.current = q;
    renderQuestion(el, q);
    ttsPreload && ttsPreload(q.sentence.replace('___', 'blank'));
    _qPool.refill(_session.category, _session.exam);
  } catch (e) {
    if (api.isAborted() || !el.isConnected) return;
    if (area) area.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

function renderQuestion(el, q) {
  const area = el.querySelector('#drill-area');
  const sentence = q.sentence.replace('___', '<span class="blank">___</span>');
  const examBadge = q.category && !['articles','prepositions','tense','subject_verb','passive'].includes(q.category)
    ? `<span class="exam-badge exam-${_session.exam}" style="font-size:10px">${q.category_label || q.category}</span>` : '';

  area.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:8px">
        <span class="tag">${q.category_label || q.category.replace('_',' ')}</span>
        ${examBadge}
      </div>
      <div style="display:flex;align-items:center;gap:10px">
        <button class="tts-btn" id="tts-sentence" title="Read aloud">🔊</button>
        <span style="font-size:13px;color:var(--text-dim)">Q${_session.total + 1}</span>
      </div>
    </div>
    <div class="sentence-display">${sentence}</div>
    <div class="choices" id="choices"></div>
    <div class="explanation-box" id="expl">${q.explanation}</div>
    <button class="btn btn-primary hidden" id="btn-next">Next Question →</button>
  `;

  const choicesEl = area.querySelector('#choices');
  q.choices.forEach((choice, i) => {
    const b = document.createElement('button');
    b.className = 'choice-btn';
    b.textContent = `${String.fromCharCode(65 + i)}. ${choice}`;
    b.addEventListener('click', () => selectAnswer(el, q, i, b));
    choicesEl.appendChild(b);
  });

  area.querySelector('#btn-next').addEventListener('click', () => loadQuestion(el));
  area.querySelector('#tts-sentence').addEventListener('click', () => {
    tts(q.sentence.replace('___', 'blank'));
  });
}

async function selectAnswer(el, q, idx, btn) {
  el.querySelectorAll('.choice-btn').forEach(b => b.disabled = true);

  try {
    const result = await api.post('/api/grammar/answer', {
      category: q.category,
      sentence: q.sentence,
      user_index: idx,
      correct_index: q.correct_index,
      explanation: q.explanation,
    });

    if (api.isAborted() || !el.isConnected) return;

    _session.total++;
    if (result.correct) {
      _session.correct++;
      btn.classList.add('correct');
    } else {
      btn.classList.add('wrong');
      const correctBtn = el.querySelectorAll('.choice-btn')[result.correct_index];
      if (correctBtn) correctBtn.classList.add('correct');
    }

    const explEl = el.querySelector('#expl');
    const nextBtn = el.querySelector('#btn-next');
    if (explEl) explEl.classList.add('show');
    if (nextBtn) nextBtn.classList.remove('hidden');

    const stats = el.querySelector('#session-stats');
    const correctEl = el.querySelector('#stat-correct');
    const totalEl = el.querySelector('#stat-total');
    if (stats) stats.classList.remove('hidden');
    if (correctEl) correctEl.textContent = _session.correct;
    if (totalEl) totalEl.textContent = _session.total;

    if (_session.total >= 5 && !el.querySelector('#btn-finish') && stats) {
      const finishBtn = document.createElement('button');
      finishBtn.id = 'btn-finish';
      finishBtn.className = 'btn btn-outline';
      finishBtn.style.marginLeft = '12px';
      finishBtn.textContent = 'Finish Round ✓';
      finishBtn.addEventListener('click', () => showSummary(el));
      stats.appendChild(finishBtn);
    }
  } catch (e) {
    if (api.isAborted() || !el.isConnected) return;
    console.error(e);
  }
}

function showSummary(el) {
  const pct = _session.total ? Math.round((_session.correct / _session.total) * 100) : 0;
  const color = pct >= 80 ? 'var(--green)' : pct >= 60 ? 'var(--yellow)' : 'var(--red)';
  const emoji = pct >= 80 ? '🎉' : pct >= 60 ? '👍' : '💪';
  el.querySelector('#drill-area').innerHTML = `
    <div style="text-align:center;padding:32px 20px">
      <div style="font-size:48px;margin-bottom:12px">${emoji}</div>
      <h2 style="margin-bottom:8px">Round Complete</h2>
      <div style="font-size:40px;font-weight:700;color:${color};margin:12px 0">${pct}%</div>
      <p>${_session.correct} / ${_session.total} correct</p>
      <div style="display:flex;gap:12px;justify-content:center;margin-top:24px">
        <button class="btn btn-primary" id="btn-again">Try Again ↺</button>
        <button class="btn btn-outline" onclick="navigate('home')">← Home</button>
      </div>
    </div>
  `;
  el.querySelector('#session-stats').classList.add('hidden');
  el.querySelector('#btn-again').addEventListener('click', () => {
    _session = { correct: 0, total: 0, current: null, category: _session.category, exam: _session.exam };
    el.querySelector('#session-stats').classList.add('hidden');
    loadQuestion(el);
  });
}
