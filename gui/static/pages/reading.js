// pages/reading.js — Reading training hub + comprehension flow

const STORAGE_KEY = 'reading_current';
const PRACTICE_KEY = 'practice_mode';

const _store = {
  get: () => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { return null; } },
  set: (v) => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(v)); } catch {} },
  clear: () => { try { localStorage.removeItem(STORAGE_KEY); } catch {} },
};

const QUESTION_TYPE_LABELS = {
  factual: 'Factual Information',
  negative_factual: 'Negative Factual',
  inference: 'Inference',
  vocabulary: 'Vocabulary',
  rhetorical_purpose: 'Rhetorical Purpose',
  reference: 'Reference',
  sentence_simplification: 'Sentence Simplification',
  insert_text: 'Insert Text',
  prose_summary: 'Prose Summary',
  fill_table: 'Fill in a Table',
  tfng: 'True / False / Not Given',
  matching_headings: 'Matching Headings',
  summary_completion: 'Summary Completion',
  matching_information: 'Matching Information',
  short_answer: 'Short Answer',
  diagram_label: 'Diagram Label',
};

let _sid = null;
let _qTotal = 0;
let _qIndex = 0;
let _correct = 0;
let _passageData = null;
let _activePractice = null;
let _filterMeta = null;
let _filterState = {
  exam: 'toefl',
  difficultyBand: 'balanced',
  difficultyScore: 5,
  topic: '',
  subject: '',
  selectedTypes: [],
};
let _lastStart = { mode: 'filtered', request: null };

export async function render(el) {
  _activePractice = getPracticeContext();

  el.innerHTML = `
    <h1>📖 Reading Training</h1>
    <p>${_activePractice
      ? `当前为 ${escHtml(practiceSummaryText(_activePractice))}`
      : '按考试、题型、难度和主题筛选后再开始训练。'}</p>
    <div id="reading-body"></div>
  `;

  const saved = _store.get();

  if (_activePractice) {
    _store.clear();
    await startSession(el, { filtered: true, request: practiceRequest(_activePractice) });
    return;
  }

  if (saved && saved.session_id) {
    _sid = saved.session_id;
    _qTotal = saved.question_count || 0;
    _qIndex = saved.q_index || 0;
    _correct = saved.correct || 0;
    _passageData = saved;
    _lastStart = saved.last_start || _lastStart;

    if (_qIndex > 0 && _qIndex < _qTotal) {
      renderSplitLayout(el, saved);
      await loadQuestion(el);
    } else {
      renderPassage(el, saved);
    }
    return;
  }

  await renderHub(el);
}

function getPracticeContext() {
  try {
    const raw = sessionStorage.getItem(PRACTICE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.section !== 'reading') return null;
    if (parsed.started_at && Date.now() - parsed.started_at > 30 * 60 * 1000) {
      sessionStorage.removeItem(PRACTICE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function practiceRequest(practice) {
  return {
    exam: practice.exam,
    difficulty: null,
    subject: practice.subject || null,
    topic: practice.topic || null,
    question_types: practice.type ? [practice.type] : null,
    practice_mode: practice.source === 'mock_exam' ? 'mock' : 'targeted',
  };
}

async function renderHub(el) {
  const body = el.querySelector('#reading-body');
  body.innerHTML = `
    <div class="card" style="padding:18px;margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap">
        <div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:10px">EXAM</div>
          <div id="reading-exam-tabs" style="display:flex;gap:8px;flex-wrap:wrap">
            ${['toefl', 'ielts'].map(exam => `
              <button class="btn ${_filterState.exam === exam ? 'btn-primary' : 'btn-outline'} reading-exam-tab" data-exam="${exam}">
                ${exam.toUpperCase()}
              </button>
            `).join('')}
          </div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn btn-primary" id="btn-start-reading">Start Drill</button>
          <button class="btn btn-outline" id="btn-random-reading">Random Passage</button>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:16px">
        <div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">DIFFICULTY</div>
          <div id="difficulty-bands" style="display:flex;gap:8px;flex-wrap:wrap"></div>
        </div>
        <div>
          <label style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);display:block;margin-bottom:8px">THEME / TOPIC</label>
          <input id="reading-topic-input" type="text" placeholder="例如 climate / education / urbanization"
            style="width:100%;padding:10px 12px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:10px">
        </div>
        <div>
          <label style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);display:block;margin-bottom:8px">SUBJECT</label>
          <select id="reading-subject-select"
            style="width:100%;padding:10px 12px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:10px">
            <option value="">All Subjects</option>
          </select>
        </div>
      </div>

      <div style="margin-top:16px">
        <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:10px">QUESTION TYPES</div>
        <div id="reading-type-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px"></div>
      </div>
    </div>

    <div class="card" style="padding:18px">
      <div style="display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:14px">
        <div>
          <h3 style="margin:0">Passage Preview</h3>
          <div style="font-size:12px;color:var(--text-dim)">根据当前筛选预览题库素材。若没有精确命中，开始训练时会自动放宽或回退。</div>
        </div>
        <button class="btn btn-outline" id="btn-refresh-library">Refresh Preview</button>
      </div>
      <div id="reading-library-preview"><div style="text-align:center;padding:24px"><div class="spinner"></div></div></div>
    </div>
  `;

  bindHubEvents(el);
  await loadFilterMeta(el);
  await loadLibraryPreview(el);
}

function bindHubEvents(el) {
  el.querySelectorAll('.reading-exam-tab').forEach(btn => {
    btn.addEventListener('click', async () => {
      _filterState.exam = btn.dataset.exam;
      _filterState.selectedTypes = [];
      renderHub(el);
    });
  });

  el.querySelector('#btn-start-reading')?.addEventListener('click', async () => {
    await startSession(el, { filtered: true, request: currentFilterRequest(el) });
  });

  el.querySelector('#btn-random-reading')?.addEventListener('click', async () => {
    await startSession(el, { filtered: false, exam: _filterState.exam });
  });

  el.querySelector('#btn-refresh-library')?.addEventListener('click', async () => {
    await loadLibraryPreview(el);
  });
}

async function loadFilterMeta(el) {
  const bandsEl = el.querySelector('#difficulty-bands');
  const typeEl = el.querySelector('#reading-type-grid');
  const subjectEl = el.querySelector('#reading-subject-select');
  const topicInput = el.querySelector('#reading-topic-input');
  topicInput.value = _filterState.topic || '';

  try {
    _filterMeta = await api.get(`/api/reading/filters/meta?exam=${_filterState.exam}`);
  } catch {
    _filterMeta = {
      question_types: [],
      subjects: [],
      topics: [],
      difficulty_bands: [
        { id: 'easy', label: 'Easy', score: 3 },
        { id: 'balanced', label: 'Balanced', score: 5 },
        { id: 'hard', label: 'Hard', score: 8 },
      ],
    };
  }

  bandsEl.innerHTML = (_filterMeta.difficulty_bands || []).map(band => `
    <button class="btn ${band.id === _filterState.difficultyBand ? 'btn-primary' : 'btn-outline'} difficulty-band-btn"
      data-band="${band.id}" data-score="${band.score}" style="font-size:12px;padding:5px 12px">${band.label}</button>
  `).join('');

  typeEl.innerHTML = (_filterMeta.question_types || []).map(item => {
    const active = _filterState.selectedTypes.includes(item.id);
    return `
      <button class="btn ${active ? 'btn-primary' : 'btn-outline'} reading-type-btn"
        data-type="${item.id}" style="justify-content:flex-start;font-size:12px;padding:8px 10px">
        ${item.label}
      </button>
    `;
  }).join('');

  subjectEl.innerHTML = `
    <option value="">All Subjects</option>
    ${(_filterMeta.subjects || []).map(item => `
      <option value="${escHtml(item.value)}" ${item.value === _filterState.subject ? 'selected' : ''}>${escHtml(item.value)} (${item.count})</option>
    `).join('')}
  `;

  bindFilterControls(el);
}

function bindFilterControls(el) {
  const topicInput = el.querySelector('#reading-topic-input');
  const subjectEl = el.querySelector('#reading-subject-select');

  el.querySelectorAll('.difficulty-band-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      _filterState.difficultyBand = btn.dataset.band;
      _filterState.difficultyScore = Number(btn.dataset.score || 5);
      await renderHub(el);
    });
  });

  el.querySelectorAll('.reading-type-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const type = btn.dataset.type;
      if (_filterState.selectedTypes.includes(type)) {
        _filterState.selectedTypes = _filterState.selectedTypes.filter(item => item !== type);
      } else {
        _filterState.selectedTypes = [type];
      }
      await renderHub(el);
    });
  });

  topicInput?.addEventListener('change', async () => {
    _filterState.topic = topicInput.value.trim();
    await loadLibraryPreview(el);
  });

  subjectEl?.addEventListener('change', async () => {
    _filterState.subject = subjectEl.value;
    await loadLibraryPreview(el);
  });
}

function currentFilterRequest(el) {
  const topicInput = el.querySelector('#reading-topic-input');
  const subjectEl = el.querySelector('#reading-subject-select');
  _filterState.topic = topicInput?.value.trim() || '';
  _filterState.subject = subjectEl?.value || '';

  return {
    exam: _filterState.exam,
    difficulty: _filterState.difficultyScore,
    subject: _filterState.subject || null,
    topic: _filterState.topic || null,
    question_types: _filterState.selectedTypes.length ? _filterState.selectedTypes : null,
    practice_mode: 'targeted',
  };
}

async function loadLibraryPreview(el) {
  const target = el.querySelector('#reading-library-preview');
  if (!target) return;

  target.innerHTML = '<div style="text-align:center;padding:24px"><div class="spinner"></div></div>';
  const bands = (_filterMeta?.difficulty_bands || []).reduce((acc, item) => ({ ...acc, [item.id]: item }), {});
  const band = bands[_filterState.difficultyBand] || { min: 4, max: 6 };
  const params = new URLSearchParams({
    exam: _filterState.exam,
    difficulty_min: String(band.min || 4),
    difficulty_max: String(band.max || 6),
    limit: '6',
  });
  if (_filterState.subject) params.set('subject', _filterState.subject);
  if (_filterState.topic) params.set('topic', _filterState.topic);

  try {
    const data = await api.get(`/api/reading/passages/library?${params}`);
    const passages = data.passages || [];
    target.innerHTML = passages.length ? passages.map(item => `
      <div class="card" style="padding:14px;background:var(--bg2);margin-bottom:10px">
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
          <span class="tag">${escHtml(item.difficulty || '?')}</span>
          ${item.topic ? `<span class="tag">${escHtml(item.topic)}</span>` : ''}
          ${item.subject ? `<span class="tag">${escHtml(item.subject)}</span>` : ''}
          ${item.word_count ? `<span class="tag">${item.word_count} words</span>` : ''}
        </div>
        <div style="font-size:13px;color:var(--text-dim);line-height:1.5">${escHtml(item.preview || '')}</div>
      </div>
    `).join('') : '<div class="alert alert-info">当前筛选下没有精确命中的素材。开始训练时会自动尝试回退。</div>';
  } catch (e) {
    target.innerHTML = `<div class="alert alert-warn">${escHtml(e.message)}</div>`;
  }
}

async function startSession(el, options = {}) {
  const body = el.querySelector('#reading-body');
  body.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div></div>';

  try {
    let result;
    if (options.filtered) {
      const request = options.request || currentFilterRequest(el);
      _lastStart = { mode: 'filtered', request };
      result = await api.post('/api/reading/start-filtered', request);
    } else {
      _lastStart = { mode: 'random', request: { exam: options.exam || _filterState.exam } };
      result = await api.post(`/api/reading/start?exam=${encodeURIComponent(options.exam || _filterState.exam || 'toefl')}`, {});
    }

    if (window._currentAbortSignal?.aborted || !el.isConnected) return;

    if (result.error) {
      body.innerHTML = `<div class="alert alert-warn">${escHtml(result.message)}</div>`;
      return;
    }

    _sid = result.session_id;
    _qTotal = result.question_count;
    _qIndex = 0;
    _correct = 0;
    _passageData = { ...result, practice: _activePractice, last_start: _lastStart };
    _store.set({ ..._passageData, q_index: 0, correct: 0, last_start: _lastStart });
    renderPassage(el, _passageData);
  } catch (e) {
    if (e.name === 'AbortError' || !el.isConnected) return;
    const noProfile = e.message.includes('profile') || e.message.includes('Profile');
    body.innerHTML = noProfile
      ? `<div class="alert alert-warn">Please complete setup before using Reading.
          <button class="btn btn-primary" style="margin-top:12px;display:block" onclick="navigate('setup')">Go to Setup →</button>
        </div>`
      : `<div class="alert alert-error">${escHtml(e.message)}</div>`;
  }
}

function renderPassage(el, r) {
  const body = el.querySelector('#reading-body');
  body.innerHTML = `
    <div class="card">
      <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap">
        ${practiceSummaryHtml(r)}
        ${r.exam ? `<span class="tag">${escHtml(String(r.exam).toUpperCase())}</span>` : ''}
        ${r.difficulty ? `<span class="tag">${escHtml(r.difficulty)}</span>` : ''}
        ${r.topic ? `<span class="tag">${escHtml(r.topic)}</span>` : ''}
        ${r.subject ? `<span class="tag">${escHtml(r.subject)}</span>` : ''}
        ${(r.requested_question_types || []).map(type => `<span class="tag">${escHtml(typeLabel(type))}</span>`).join('')}
        <span class="tag">${r.word_count} words</span>
        ${r.ai_generated ? `<span class="tag" style="color:var(--accent);border-color:var(--accent)">AI</span>` : ''}
        <div style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap">
          <button class="tts-btn" id="tts-passage" title="Read aloud">🔊</button>
          <button class="btn btn-outline" id="btn-refine-reading" style="font-size:12px;padding:5px 10px">Refine Filters</button>
          <button class="btn btn-outline" id="btn-new-passage" style="font-size:12px;padding:5px 10px">${_activePractice ? 'Another Drill ↺' : 'New Passage ↺'}</button>
        </div>
      </div>
      ${r.fallback_reason ? `<div class="alert alert-info" style="margin-bottom:12px">${escHtml(r.fallback_reason)}</div>` : ''}
      <div class="passage-box" id="passage-text">${escHtml(r.passage)}</div>
      ${r.has_questions !== false
        ? `<button class="btn btn-primary" id="btn-start-q" style="margin-top:16px">Start Questions (${_qTotal}) →</button>`
        : `<div class="alert alert-info" style="margin-top:16px">当前没有可用题目，请调整筛选或配置 AI 后再试。</div>`
      }
    </div>
  `;

  body.querySelector('#tts-passage')?.addEventListener('click', () => {
    tts(body.querySelector('#passage-text').textContent);
  });

  body.querySelector('#btn-refine-reading')?.addEventListener('click', () => {
    _store.clear();
    renderHub(el);
  });

  body.querySelector('#btn-new-passage')?.addEventListener('click', () => {
    _store.clear();
    rerunLastStart(el);
  });

  if (r.has_questions !== false) {
    body.querySelector('#btn-start-q')?.addEventListener('click', () => {
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
            ${practiceSummaryHtml(r)}
            ${r.exam ? `<span class="tag">${escHtml(String(r.exam).toUpperCase())}</span>` : ''}
            ${r.difficulty ? `<span class="tag">${escHtml(r.difficulty)}</span>` : ''}
            ${r.topic ? `<span class="tag">${escHtml(r.topic)}</span>` : ''}
            ${r.subject ? `<span class="tag">${escHtml(r.subject)}</span>` : ''}
            <span class="tag">${r.word_count} words</span>
            <div style="margin-left:auto;display:flex;gap:8px">
              <button class="tts-btn" id="tts-passage-split" title="Read aloud">🔊</button>
              <button class="btn btn-outline" id="btn-new-passage-split" style="font-size:12px;padding:5px 10px">${_activePractice ? 'Another Drill ↺' : 'New Passage ↺'}</button>
            </div>
          </div>
          ${r.fallback_reason ? `<div class="alert alert-info" style="margin-bottom:12px">${escHtml(r.fallback_reason)}</div>` : ''}
          <div class="passage-box" id="passage-text-split">${escHtml(r.passage)}</div>
        </div>
      </div>
      <div class="reading-right" id="qa-panel">
        <div style="text-align:center;padding:40px"><div class="spinner"></div></div>
      </div>
    </div>
  `;

  body.querySelector('#tts-passage-split')?.addEventListener('click', () => {
    tts(body.querySelector('#passage-text-split').textContent);
  });

  body.querySelector('#btn-new-passage-split')?.addEventListener('click', () => {
    _store.clear();
    rerunLastStart(el);
  });
}

function practiceSummaryHtml(r) {
  const practice = r.practice || _activePractice;
  if (!practice) return '';
  return `<span class="tag" style="border-color:var(--accent);color:var(--accent)">${escHtml(practiceSummaryText(practice))}</span>`;
}

async function loadQuestion(el) {
  if (!el.querySelector('.reading-split')) renderSplitLayout(el, _passageData);
  const panel = el.querySelector('#qa-panel');
  if (panel) panel.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div></div>';

  try {
    const q = await api.get(`/api/reading/question/${_sid}/${_qIndex}`);
    renderQuestion(el, q);
  } catch (e) {
    if (e.message.includes('404') || e.message.includes('not found') || e.message.includes('Session')) {
      _store.clear();
      await rerunLastStart(el);
    } else if (panel) {
      panel.innerHTML = `<div class="alert alert-error">${escHtml(e.message)}</div>`;
    }
  }
}

function renderQuestion(el, q) {
  const panel = el.querySelector('#qa-panel');
  if (!panel) return;
  const hasMC = Array.isArray(q.options) && q.options.length > 0;

  panel.innerHTML = `
    <div class="card">
      <div style="display:flex;justify-content:space-between;margin-bottom:16px">
        <span class="tag">${escHtml(typeLabel(q.type))}</span>
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
    q.options.forEach((opt) => {
      const button = document.createElement('button');
      button.className = 'choice-btn';
      button.textContent = opt;
      button.addEventListener('click', async () => {
        choicesEl.querySelectorAll('.choice-btn').forEach(x => { x.disabled = true; });
        try {
          const result = await api.post(`/api/reading/answer/${_sid}`, {
            question_index: _qIndex,
            user_answer: opt,
          });
          choicesEl.querySelectorAll('.choice-btn').forEach(x => {
            const choiceKey = x.textContent.charAt(0);
            if (choiceKey === result.model_answer.charAt(0)) x.classList.add('correct');
            else if (x === button && !result.correct) x.classList.add('wrong');
          });
          showFeedback(el, result);
        } catch {}
      });
      choicesEl.appendChild(button);
    });
    return;
  }

  const input = panel.querySelector('#ans-input');
  input.focus();
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') panel.querySelector('#btn-submit-ans').click();
  });
  panel.querySelector('#btn-submit-ans')?.addEventListener('click', async () => {
    const answer = input.value.trim();
    if (!answer) return;
    panel.querySelector('#btn-submit-ans').disabled = true;
    try {
      const result = await api.post(`/api/reading/answer/${_sid}`, {
        question_index: _qIndex,
        user_answer: answer,
      });
      showFeedback(el, result);
    } catch {
      panel.querySelector('#btn-submit-ans').disabled = false;
    }
  });
}

function showFeedback(el, result) {
  const panel = el.querySelector('#qa-panel');
  if (!panel) return;

  const feedback = panel.querySelector('#ans-feedback');
  feedback.classList.remove('hidden');
  feedback.innerHTML = result.correct
    ? `<div class="alert alert-success">✓ Correct! ${escHtml(result.explanation)}</div>`
    : `<div class="alert alert-warn"><strong>Model answer:</strong> ${escHtml(result.model_answer)}<br><span style="font-size:13px">${escHtml(result.explanation)}</span></div>`;

  if (result.correct) _correct++;
  _qIndex++;

  const saved = _store.get() || {};
  saved.q_index = _qIndex;
  saved.correct = _correct;
  _store.set(saved);

  const nextBtn = panel.querySelector('#btn-next-q');
  nextBtn.classList.remove('hidden');
  if (result.session_complete) {
    nextBtn.textContent = 'See Results';
    nextBtn.addEventListener('click', () => showResults(el, result.stats));
  } else {
    nextBtn.addEventListener('click', () => loadQuestion(el));
  }
}

function showResults(el, stats) {
  _store.clear();
  const body = el.querySelector('#reading-body');
  const acc = Math.round((stats.correct / Math.max(stats.answered, 1)) * 100);
  const color = acc >= 67 ? 'var(--green)' : 'var(--yellow)';
  const recommendation = readingRecommendation(acc, stats);
  body.innerHTML = `
    <div class="card" style="text-align:center;padding:40px">
      <div style="font-size:48px;margin-bottom:16px">📖</div>
      <h2>Reading Complete!</h2>
      ${_activePractice ? `<p style="color:var(--text-dim);margin-top:-4px">${escHtml(practiceSummaryText(_activePractice))}</p>` : ''}
      <div style="font-size:36px;font-weight:700;color:${color};margin:16px 0">${acc}%</div>
      <p>${stats.correct} / ${stats.answered} questions correct</p>
      <div class="card" style="margin:20px auto 0;max-width:560px;text-align:left;background:var(--bg2);padding:16px">
        <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">结果解读</div>
        <div style="font-size:14px;line-height:1.7">${escHtml(recommendation)}</div>
      </div>
      <div style="display:flex;gap:12px;justify-content:center;margin-top:24px;flex-wrap:wrap">
        <button class="btn btn-primary" id="btn-read-another">${_activePractice ? 'Try Same Type Again' : 'Read Another'}</button>
        <button class="btn btn-outline" id="btn-refine-after-reading">Refine Filters</button>
        ${isMockSection() ? '<button class="btn btn-outline" id="btn-complete-reading-mock">Complete Mock Section</button>' : ''}
        <button class="btn btn-outline" onclick="navigate('practice')">← Practice</button>
      </div>
    </div>
  `;
  body.querySelector('#btn-read-another')?.addEventListener('click', () => rerunLastStart(el));
  body.querySelector('#btn-refine-after-reading')?.addEventListener('click', () => renderHub(el));
  body.querySelector('#btn-complete-reading-mock')?.addEventListener('click', async () => {
    await completeMockSection(stats);
  });
}

async function rerunLastStart(el) {
  if (_activePractice) {
    await startSession(el, { filtered: true, request: practiceRequest(_activePractice) });
    return;
  }
  if (_lastStart.mode === 'random') {
    await startSession(el, { filtered: false, exam: _lastStart.request?.exam || _filterState.exam });
    return;
  }
  await startSession(el, { filtered: true, request: _lastStart.request || currentFilterRequest(el) });
}

function typeLabel(type) {
  return QUESTION_TYPE_LABELS[type] || String(type || '').replace(/_/g, ' ');
}

function practiceSummaryText(practice) {
  if (!practice) return '';
  const exam = (practice.exam || 'general').toUpperCase();
  if (practice.source === 'mock_exam') return `${exam} Mock Section`;
  const type = practice.type ? ` · ${typeLabel(practice.type)}` : '';
  return `${exam} Drill${type}`;
}

function isMockSection() {
  return _activePractice?.source === 'mock_exam' && _activePractice?.mock_session_id;
}

async function completeMockSection(stats) {
  if (!isMockSection()) return;
  await api.post(`/api/mock-exam/complete-section/${_activePractice.mock_session_id}`, {
    section_index: _activePractice.mock_section_index,
    result: {
      correct: stats.correct,
      total: stats.answered,
      source: 'reading',
    },
  });
  navigate('mock-exam');
}

function readingRecommendation(acc, stats) {
  if (acc >= 85) {
    return `这轮阅读表现稳定，已经能较好抓住关键信息。建议继续保持同难度，或切到更难题型做专项训练。`;
  }
  if (acc >= 60) {
    return `这轮已经具备基本稳定性，但仍有 ${Math.max((stats.answered || 0) - (stats.correct || 0), 0)} 题失分。建议再做一轮同题型，重点关注解释里暴露出的定位和推断问题。`;
  }
  return `这轮失分偏多，建议先降低筛选难度或改做更基础的题型，再逐步回到当前难度。先保证做得稳，再追求做得难。`;
}

function escHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
