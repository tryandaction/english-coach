// pages/writing.js — Essay writing with SSE feedback + exam task types

const STORAGE_KEY = 'writing_current';
const POOL_KEY = 'writing_pool';
const PRACTICE_KEY = 'practice_mode';

const _store = {
  get: () => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { return null; } },
  set: (v) => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(v)); } catch {} },
  clear: () => { try { localStorage.removeItem(STORAGE_KEY); } catch {} },
};

const _pool = {
  get: () => { try { return JSON.parse(localStorage.getItem(POOL_KEY)) || []; } catch { return []; } },
  set: (v) => { try { localStorage.setItem(POOL_KEY, JSON.stringify(v)); } catch {} },
  pop: () => {
    const items = _pool.get();
    if (!items.length) return null;
    const item = items.shift();
    _pool.set(items);
    return item;
  },
  refill: async (exam, task_type) => {
    try {
      const params = new URLSearchParams({ n: 3 });
      if (exam) params.set('exam', exam);
      if (task_type) params.set('task_type', task_type);
      const r = await api.get('/api/writing/pool?' + params);
      _pool.set(r.prompts || []);
    } catch {}
  },
};

let _state = null; // {exam, task_types, tasks: {task1: {prompt, ...}, task2: {prompt, ...}}, current_task}
let _activePractice = null;

export async function render(el) {
  _activePractice = getPracticeContext();

  el.innerHTML = `
    <h1>📝 Writing Practice</h1>
    <p>${_activePractice ? escHtml(practiceSummaryText(_activePractice)) : 'Write an essay response. AI will score and give detailed feedback.'}</p>
    <div id="writing-body"></div>
  `;

  if (_activePractice) {
    _store.clear();
    await loadAllPrompts(el, _activePractice);
    return;
  }

  // Restore active session
  const saved = _store.get();
  if (saved && saved.tasks) {
    _state = saved;
    _activePractice = saved.practice || null;
    renderEditor(el, _state);
    return;
  }

  // Load prompts for all task types
  await loadAllPrompts(el);
}

async function loadAllPrompts(el, context = _activePractice) {
  const body = el.querySelector('#writing-body');
  body.innerHTML = '<div style="text-align:center;padding:20px"><div class="spinner"></div><p style="margin-top:12px;color:var(--text-dim)">Loading writing tasks...</p></div>';

  try {
    // Get first prompt to determine exam and task_types
    const initialParams = getPromptParams(context);
    const r1 = await api.get('/api/writing/prompt' + (initialParams ? `?${initialParams}` : ''));
    const exam = r1.exam;
    const task_types = r1.task_types || [];
    const preferredTask = resolvePreferredTask(context, task_types, r1.task_type);

    if (!task_types || task_types.length <= 1) {
      // Single task type - use old behavior
      _state = { ...r1, current_task: preferredTask, practice: context || null };
      _store.set(_state);
      renderEditor(el, _state);
      return;
    }

    // Multiple task types - load all
    const tasks = {};
    tasks[r1.task_type] = {
      prompt: r1.prompt,
      word_target: r1.word_target,
      score_max: r1.score_max,
      score_label: r1.score_label,
    };

    // Load other task types
    for (const [tt_key, tt_label] of task_types) {
      if (tt_key !== r1.task_type) {
        const r = await api.get(`/api/writing/prompt?exam=${exam}&task_type=${tt_key}`);
        tasks[tt_key] = {
          prompt: r.prompt,
          word_target: r.word_target,
          score_max: r.score_max,
          score_label: r.score_label,
        };
      }
    }

    _state = {
      exam,
      task_types,
      tasks,
      current_task: preferredTask,
      practice: context || null,
    };
    _store.set(_state);
    renderEditor(el, _state);

  } catch (e) {
    const noProfile = e.message.includes('profile') || e.message.includes('Profile');
    if (noProfile) {
      body.innerHTML = `<div class="alert alert-warn">
        Please complete setup before using Writing.
        <button class="btn btn-primary" style="margin-top:12px;display:block" onclick="navigate('setup')">Go to Setup →</button>
      </div>`;
    } else {
      body.innerHTML = `<div class="alert alert-error">${e.message}
        <button class="btn btn-outline" style="margin-top:8px;display:block" id="retry-btn">Retry</button>
      </div>`;
      body.querySelector('#retry-btn').addEventListener('click', () => loadAllPrompts(el));
    }
  }
}

async function loadPrompt(el, task_type) {
  const body = el.querySelector('#writing-body');
  body.innerHTML = '<div style="text-align:center;padding:20px"><div class="spinner"></div></div>';
  try {
    const exam = _state?.exam || _activePractice?.exam || '';
    const tt = task_type || _state?.current_task || _state?.task_type || _activePractice?.type || '';
    const params = getPromptParams({ exam, type: tt });
    const r = await api.get('/api/writing/prompt' + (params ? `?${params}` : ''));
    _state = { ...r, practice: _activePractice || _state?.practice || null };
    _state.current_task = r.task_type;
    _store.set(_state);
    renderEditor(el, _state);
  } catch (e) {
    const noProfile = e.message.includes('profile') || e.message.includes('Profile');
    if (noProfile) {
      body.innerHTML = `<div class="alert alert-warn">
        Please complete setup before using Writing.
        <button class="btn btn-primary" style="margin-top:12px;display:block" onclick="navigate('setup')">Go to Setup →</button>
      </div>`;
    } else {
      body.innerHTML = `<div class="alert alert-error">${e.message}
        <button class="btn btn-outline" style="margin-top:8px;display:block" onclick="">Retry</button>
      </div>`;
      body.querySelector('button').addEventListener('click', () => loadPrompt(el, task_type));
    }
  }
}

function renderEditor(el, state) {
  const body = el.querySelector('#writing-body');
  const practice = state.practice || _activePractice;

  // Handle both old and new state formats
  let exam, task_types, current_task, current_data;
  if (state.tasks) {
    // New format: multiple tasks
    exam = state.exam;
    task_types = state.task_types;
    current_task = state.current_task;
    current_data = state.tasks[current_task];
  } else {
    // Old format: single task (backward compatibility)
    exam = state.exam;
    task_types = state.task_types;
    current_task = state.task_type;
    current_data = {
      prompt: state.prompt,
      word_target: state.word_target,
      score_max: state.score_max,
      score_label: state.score_label,
    };
  }

  const { prompt, word_target, score_max, score_label } = current_data;
  const examUpper = (exam || 'general').toUpperCase();

  // Build task type tabs
  const taskTabsHtml = (task_types && task_types.length > 1)
    ? `<div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
        ${task_types.map(([key, label]) =>
          `<button class="btn ${key === current_task ? 'btn-primary' : 'btn-outline'} task-tab"
            data-tt="${key}" style="font-size:12px;padding:5px 12px">${label}</button>`
        ).join('')}
       </div>` : '';

  body.innerHTML = `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        <div style="display:flex;align-items:center;gap:8px">
          ${practice ? `<span class="tag" style="border-color:var(--accent);color:var(--accent)">${escHtml(practiceSummaryText(practice))}</span>` : ''}
          <span class="exam-badge exam-${exam || 'general'}">${examUpper}</span>
          ${current_task ? `<span style="font-size:12px;color:var(--text-dim)">${_taskLabel(task_types, current_task)}</span>` : ''}
        </div>
        <button class="btn btn-outline" id="btn-new-prompt" style="font-size:12px;padding:5px 12px">New Prompt ↺</button>
      </div>
      ${taskTabsHtml}
      <div class="writing-prompt">${escHtml(prompt)}</div>
      <textarea class="essay-input" id="essay-ta" placeholder="Write your response here..."></textarea>
      <div class="word-count" id="wc-div"><span id="wc">0</span> words
        <span id="wc-target" style="color:var(--text-dim);margin-left:6px">(target: ${word_target}+ words)</span>
      </div>
      <div style="margin-top:16px;display:flex;gap:10px">
        <button class="btn btn-primary" id="btn-submit">Submit for Feedback</button>
      </div>
    </div>
    <div id="feedback-area" class="hidden">
      <div class="card feedback-stream" id="feedback-stream">
        <div style="color:var(--text-dim);font-size:14px"><div class="spinner" style="display:inline-block;margin-right:8px"></div>Analyzing your essay...</div>
      </div>
    </div>
  `;

  // Task type tab switching - just switch display, don't reload
  body.querySelectorAll('.task-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      if (state.tasks) {
        // New format: switch to different task
        _state.current_task = btn.dataset.tt;
        _store.set(_state);
        renderEditor(el, _state);
      } else {
        // Old format: reload prompt
        _store.clear();
        loadPrompt(el, btn.dataset.tt);
      }
    });
  });

  const ta = body.querySelector('#essay-ta');
  const wcDiv = body.querySelector('#wc-div');

  ta.addEventListener('input', () => {
    const count = ta.value.trim().split(/\s+/).filter(Boolean).length;
    const target = word_target || 200;
    if (count >= target) {
      wcDiv.innerHTML = `<span style="color:var(--green)">${count} words ✓</span>`;
    } else if (count >= target * 0.7) {
      wcDiv.innerHTML = `<span style="color:var(--yellow)">${count} words</span> <span style="color:var(--text-dim)">(${target - count} more to reach target)</span>`;
    } else {
      wcDiv.innerHTML = `<span>${count} words</span> <span id="wc-target" style="color:var(--text-dim);margin-left:6px">(target: ${target}+ words)</span>`;
    }
  });

  body.querySelector('#btn-new-prompt').addEventListener('click', () => {
    _store.clear();
    _state = null;
    loadAllPrompts(el, practice ? { ...practice, type: current_task } : null);
  });

  body.querySelector('#btn-submit').addEventListener('click', async () => {
    const essay = ta.value.trim();
    const count = essay.split(/\s+/).filter(Boolean).length;
    const minWords = Math.min(50, (word_target || 200) * 0.3);
    if (count < minWords) {
      wcDiv.innerHTML = `<span style="color:var(--red)">Please write at least ${Math.round(minWords)} words before submitting.</span>`;
      ta.focus();
      return;
    }
    body.querySelector('#btn-submit').disabled = true;
    body.querySelector('#feedback-area').classList.remove('hidden');
    await streamFeedback(el, essay, prompt, exam, current_task, score_max, score_label);
  });
}

function _taskLabel(task_types, key) {
  if (!task_types) return key;
  const found = task_types.find(([k]) => k === key);
  return found ? found[1] : key;
}

async function streamFeedback(el, essay, prompt, exam, task_type, score_max, score_label) {
  const stream = el.querySelector('#feedback-stream');
  stream.innerHTML = '';

  const scores = {};
  const strengths = [];
  const improvements = [];
  let overallScore = null;

  try {
    await api.stream('/api/writing/submit', { essay, prompt, exam, task_type }, (type, data) => {
      if (type === 'scores') {
        Object.assign(scores, data);
        renderScores(stream, scores, score_max);
      } else if (type === 'overall') {
        overallScore = data.data !== undefined ? data.data : data;
        renderOverall(stream, data.data !== undefined ? data.data : data, data.score_max || score_max, data.score_label || score_label);
      } else if (type === 'strength') {
        strengths.push(data);
        renderStrengths(stream, strengths);
      } else if (type === 'improvement') {
        improvements.push(data);
        renderImprovements(stream, improvements);
      } else if (type === 'revised_intro') {
        renderRevised(stream, data);
      } else if (type === 'error') {
        stream.innerHTML += `<div class="alert alert-error">${escHtml(data)}</div>`;
      }
    });
  } catch (e) {
    stream.innerHTML += `<div class="alert alert-error">${e.message}</div>`;
  }

  el.querySelector('#btn-submit').disabled = false;
  _store.clear();
  _pool.refill(exam, task_type); // refill pool in background after submission
  stream.innerHTML += `
    <div class="card" style="margin-top:16px;background:var(--bg2);padding:16px">
      <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">下一步建议</div>
      <div style="font-size:14px;line-height:1.7">${escHtml(writingRecommendation(overallScore, score_max, task_type))}</div>
    </div>`;
  stream.innerHTML += `
    <hr class="divider">
    <div style="display:flex;gap:10px;margin-top:8px">
      <button class="btn btn-primary" id="btn-write-another">Write Another</button>
      ${isMockSection() ? '<button class="btn btn-outline" id="btn-complete-writing-mock">Complete Mock Section</button>' : ''}
      <button class="btn btn-outline" onclick="navigate('home')">← Home</button>
    </div>`;
  stream.querySelector('#btn-write-another').addEventListener('click', () => {
    _store.clear();
    if (_activePractice) {
      loadAllPrompts(el, { ..._activePractice, type: task_type });
      return;
    }
    const pooled = _pool.pop();
    if (pooled) {
      _state = pooled;
      _store.set(_state);
      el.querySelector('#writing-body').innerHTML = '';
      renderEditor(el, _state);
      if (_pool.get().length === 0) _pool.refill(pooled.exam, pooled.task_type);
    } else {
      loadPrompt(el, task_type);
    }
  });
  stream.querySelector('#btn-complete-writing-mock')?.addEventListener('click', async () => {
    await completeMockSection(overallScore);
  });
}

function renderScores(el, scores, score_max) {
  const max = score_max || 5;
  let html = '<h3>Scores</h3><div class="score-grid">';
  for (const [k, v] of Object.entries(scores)) {
    const label = k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    const color = v >= max * 0.7 ? 'var(--green)' : v >= max * 0.5 ? 'var(--yellow)' : 'var(--red)';
    html += `<div class="score-item"><div class="s-label">${label}</div><div class="s-val" style="color:${color}">${v}/${max}</div></div>`;
  }
  html += '</div>';
  let el2 = el.querySelector('#scores-section');
  if (!el2) { el2 = document.createElement('div'); el2.id = 'scores-section'; el.appendChild(el2); }
  el2.innerHTML = html;
}

function renderOverall(el, overall, score_max, score_label) {
  const max = score_max || 5;
  const label = score_label || `/ ${max}`;
  const color = overall >= max * 0.7 ? 'var(--green)' : overall >= max * 0.5 ? 'var(--yellow)' : 'var(--red)';
  let el2 = el.querySelector('#overall-section');
  if (!el2) { el2 = document.createElement('div'); el2.id = 'overall-section'; el.appendChild(el2); }
  el2.innerHTML = `<div style="text-align:center;margin:16px 0">
    <span style="font-size:13px;color:var(--text-dim)">Overall Score</span>
    <div style="font-size:40px;font-weight:700;color:${color}">${overall} <span style="font-size:20px;color:var(--text-dim)">${label}</span></div>
  </div>`;
}

function renderStrengths(el, strengths) {
  let el2 = el.querySelector('#strengths-section');
  if (!el2) { el2 = document.createElement('div'); el2.id = 'strengths-section'; el.appendChild(el2); }
  el2.innerHTML = '<h3>Strengths</h3>' + strengths.map(s => `<div class="strength-item">${escHtml(s)}</div>`).join('');
}

function renderImprovements(el, items) {
  let el2 = el.querySelector('#improve-section');
  if (!el2) { el2 = document.createElement('div'); el2.id = 'improve-section'; el.appendChild(el2); }
  el2.innerHTML = '<h3>Improvements</h3>' + items.map(item => `
    <div class="improve-item">
      <div class="improve-issue">${escHtml(item.issue || '')}</div>
      ${item.original ? `<div class="improve-orig">✗ ${escHtml(item.original)}</div>` : ''}
      ${item.correction ? `<div class="improve-fix">✓ ${escHtml(item.correction)}</div>` : ''}
      ${item.explanation ? `<div class="improve-exp">${escHtml(item.explanation)}</div>` : ''}
    </div>`).join('');
}

function renderRevised(el, text) {
  let el2 = el.querySelector('#revised-section');
  if (!el2) { el2 = document.createElement('div'); el2.id = 'revised-section'; el.appendChild(el2); }
  el2.innerHTML = `<h3>Suggested Opening</h3><div class="writing-prompt" style="border-color:var(--green)">${escHtml(text)}</div>`;
}

function writingRecommendation(overallScore, scoreMax, taskType) {
  const max = scoreMax || 5;
  const normalized = max ? Number(overallScore || 0) / max : 0;
  const label = taskType ? String(taskType).replace(/_/g, ' ') : '当前任务';
  if (normalized >= 0.75) {
    return `${label} 这轮整体比较稳，可以在下一轮主动提高论证深度或句式复杂度，而不是只追求“写得更多”。`;
  }
  if (normalized >= 0.5) {
    return `${label} 已经具备基本完成度，下一轮建议只盯住 1-2 个高频问题反复修正，比如结构衔接或语法准确度。`;
  }
  return `${label} 这一轮还不够稳定，建议先缩小目标：先把开头、主论点和每段一句核心支撑写清楚，再逐步补细节。`;
}

function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function getPracticeContext() {
  try {
    const raw = sessionStorage.getItem(PRACTICE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.section !== 'writing') return null;
    if (parsed.started_at && Date.now() - parsed.started_at > 30 * 60 * 1000) {
      sessionStorage.removeItem(PRACTICE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function getPromptParams(context) {
  if (!context) return '';
  const params = new URLSearchParams();
  if (context.exam) params.set('exam', context.exam);
  if (context.type) params.set('task_type', context.type);
  return params.toString();
}

function resolvePreferredTask(context, taskTypes, fallback) {
  if (!context?.type || !Array.isArray(taskTypes)) return fallback;
  return taskTypes.some(([key]) => key === context.type) ? context.type : fallback;
}

function practiceSummaryText(practice) {
  if (!practice) return '';
  const exam = (practice.exam || 'general').toUpperCase();
  const mode = practice.source === 'mock_exam' ? 'Mock Section' : 'Writing Drill';
  const task = practice.type ? ` · ${String(practice.type).replace(/_/g, ' ')}` : '';
  return `${exam} ${mode}${task}`;
}

function isMockSection() {
  return _activePractice?.source === 'mock_exam' && _activePractice?.mock_session_id;
}

async function completeMockSection(overallScore) {
  if (!isMockSection()) return;
  await api.post(`/api/mock-exam/complete-section/${_activePractice.mock_session_id}`, {
    section_index: _activePractice.mock_section_index,
    result: {
      correct: Number((overallScore || 0) >= 3),
      total: 1,
      source: 'writing',
      overall: overallScore,
    },
  });
  navigate('mock-exam');
}
