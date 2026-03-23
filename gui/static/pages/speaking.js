const STORAGE_KEY = 'speaking_current';
const PRACTICE_KEY = 'practice_mode';

const _store = {
  get: () => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { return null; } },
  set: (v) => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(v)); } catch {} },
  clear: () => { try { localStorage.removeItem(STORAGE_KEY); } catch {} },
};

const TASKS = {
  toefl: [
    { id: 'independent', name: 'Independent', desc: 'Personal opinion with reasons and examples' },
    { id: 'listen_repeat', name: 'Listen & Repeat', desc: 'Repeat short to advanced academic sentences' },
    { id: 'virtual_interview', name: 'Virtual Interview', desc: 'Answer interview-style speaking questions' },
  ],
  ielts: [
    { id: 'part1', name: 'Part 1', desc: 'Short personal interview answers' },
    { id: 'part2', name: 'Part 2', desc: 'Cue card monologue with structure' },
    { id: 'part3', name: 'Part 3', desc: 'Extended discussion and analysis' },
  ],
};

let _activePractice = null;
let _state = null;

function ensureSpeakingShell(el) {
  let body = el.querySelector('#speaking-body');
  if (body) return body;
  el.innerHTML = `
    <h1>🗣 Speaking Practice</h1>
    <p>${_activePractice ? escHtml(practiceSummaryText(_activePractice)) : 'Generate a speaking task, type your response, and get AI scoring feedback.'}</p>
    <div id="speaking-body"></div>
  `;
  return el.querySelector('#speaking-body');
}

function markStartedAt() {
  if (!_state) return;
  _state.started_at = Date.now();
  _store.set(_state);
}

function elapsedSeconds() {
  if (!_state?.started_at) return 0;
  return Math.max(0, Math.round((Date.now() - _state.started_at) / 1000));
}

export async function render(el) {
  _activePractice = getPracticeContext();
  const saved = _store.get();

  el.innerHTML = `
    <h1>🗣 Speaking Practice</h1>
    <p>${_activePractice ? escHtml(practiceSummaryText(_activePractice)) : 'Generate a speaking task, type your response, and get AI scoring feedback.'}</p>
    <div id="speaking-body"></div>
  `;

  if (_activePractice) {
    _store.clear();
    await renderTaskView(el, normalizePracticeContext(_activePractice));
    return;
  }

  if (saved?.exam && saved?.task_type && saved?.prompt) {
    _state = saved;
    if (!_state.started_at) {
      _state.started_at = Date.now();
      _store.set(_state);
    }
    renderPromptShell(el, _state);
    return;
  }

  await renderTaskView(el, { exam: 'toefl', task_type: 'independent' });
}

async function renderTaskView(el, preferred) {
  const body = ensureSpeakingShell(el);
  if (!body) return;
  const exam = preferred?.exam || 'toefl';
  const taskType = preferred?.task_type || defaultTask(exam);

  body.innerHTML = `
    ${practiceBannerHtml()}
    <div class="card" style="padding:18px;margin-bottom:16px">
      <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:10px">EXAM</div>
      <div id="speaking-exam-tabs" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
        ${['toefl', 'ielts'].map(item => `
          <button class="btn ${item === exam ? 'btn-primary' : 'btn-outline'} speaking-exam-tab" data-exam="${item}">
            ${item.toUpperCase()}
          </button>
        `).join('')}
      </div>
      <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:10px">TASK TYPE</div>
      <div id="speaking-task-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">
        ${renderTaskCards(exam, taskType)}
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:16px">
        <button class="btn btn-primary" id="btn-load-speaking">Load Task</button>
        ${_activePractice?.source === 'mock_exam' ? '<button class="btn btn-outline" id="btn-back-mock">Back to Mock Exam</button>' : ''}
      </div>
    </div>
    <div id="speaking-task-panel"></div>
  `;

  let selectedExam = exam;
  let selectedTask = taskType;

  body.querySelectorAll('.speaking-exam-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      selectedExam = btn.dataset.exam;
      selectedTask = defaultTask(selectedExam);
      renderTaskView(el, { exam: selectedExam, task_type: selectedTask });
    });
  });

  body.querySelectorAll('.speaking-task-card').forEach(card => {
    card.addEventListener('click', () => {
      selectedTask = card.dataset.taskType;
      body.querySelectorAll('.speaking-task-card').forEach(node => {
        node.style.borderColor = node === card ? 'var(--accent)' : 'var(--border)';
        node.style.background = node === card ? 'var(--bg3)' : 'var(--bg)';
      });
    });
  });

  body.querySelector('#btn-load-speaking')?.addEventListener('click', async () => {
    await loadPrompt(el, selectedExam, selectedTask);
  });
  body.querySelector('#btn-back-mock')?.addEventListener('click', () => navigate('mock-exam'));

  await loadPrompt(el, exam, taskType);
}

function renderTaskCards(exam, activeTask) {
  return (TASKS[exam] || []).map(task => `
    <div class="speaking-task-card" data-task-type="${task.id}" style="border:1px solid ${task.id === activeTask ? 'var(--accent)' : 'var(--border)'};background:${task.id === activeTask ? 'var(--bg3)' : 'var(--bg)'};border-radius:12px;padding:14px;cursor:pointer">
      <div style="font-weight:700;margin-bottom:6px">${task.name}</div>
      <div style="font-size:12px;color:var(--text-dim);line-height:1.5">${task.desc}</div>
    </div>
  `).join('');
}

async function loadPrompt(el, exam, taskType) {
  const panel = el.querySelector('#speaking-task-panel');
  if (!panel) return;
  panel.innerHTML = '<div style="text-align:center;padding:30px"><div class="spinner"></div></div>';

  try {
    const params = new URLSearchParams({ exam, task_type: taskType });
    const result = await api.get(`/api/speaking/prompt?${params}`);
    if (window._currentAbortSignal?.aborted || !el.isConnected) return;
    _state = { ...result, practice: _activePractice || null };
    _state.started_at = Date.now();
    _store.set(_state);
    renderPromptShell(el, _state);
  } catch (e) {
    if (e.name === 'AbortError' || !el.isConnected) return;
    panel.innerHTML = `<div class="alert alert-error">${escHtml(e.message)}</div>`;
  }
}

function renderPromptShell(el, state) {
  const body = el.querySelector('#speaking-task-panel');
  if (!body) return;
  const exam = state.exam || 'toefl';
  const taskLabel = state.task_label || state.task_type;
  const criteria = state.scoring_criteria || 'Delivery, structure, vocabulary';

  body.innerHTML = `
    <div class="card" style="padding:18px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:14px">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          ${state.practice ? `<span class="tag" style="border-color:var(--accent);color:var(--accent)">${escHtml(practiceSummaryText(state.practice))}</span>` : ''}
          ${state.practice?.source === 'coach_plan' && practiceCategoryLabel(state.practice) ? `<span class="tag">${escHtml(practiceCategoryLabel(state.practice))}</span>` : ''}
          <span class="exam-badge exam-${exam}">${String(exam).toUpperCase()}</span>
          <span class="tag">${escHtml(taskLabel)}</span>
          <span class="tag">${state.prep_seconds || 0}s prep</span>
          <span class="tag">${state.speak_seconds || 0}s speak</span>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn btn-outline" id="btn-new-speaking">New Task ↺</button>
          ${state.practice?.source === 'mock_exam' ? '<button class="btn btn-outline" id="btn-return-mock">Return to Mock</button>' : ''}
        </div>
      </div>
      <div style="font-size:13px;color:var(--text-dim);margin-bottom:12px">${escHtml(state.instructions || '')}</div>
      <div class="writing-prompt" style="margin-bottom:14px">${renderPromptContent(state)}</div>
      <div style="font-size:12px;color:var(--text-dim);margin-bottom:14px">Scoring focus: ${escHtml(criteria)}</div>
      <textarea class="essay-input" id="speaking-response" placeholder="Type your spoken response transcript here..."></textarea>
      <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-top:10px">
        <div id="speaking-word-count" style="font-size:12px;color:var(--text-dim)">0 words</div>
        <button class="btn btn-primary" id="btn-submit-speaking">Submit for Scoring</button>
      </div>
      <div id="speaking-feedback" style="margin-top:16px"></div>
    </div>
  `;

  const ta = body.querySelector('#speaking-response');
  const wc = body.querySelector('#speaking-word-count');
  ta.addEventListener('input', () => {
    const count = countWords(ta.value);
    wc.textContent = `${count} words`;
  });

  body.querySelector('#btn-new-speaking')?.addEventListener('click', () => {
    _store.clear();
    renderTaskView(el, { exam: exam, task_type: state.task_type });
  });
  body.querySelector('#btn-return-mock')?.addEventListener('click', () => navigate('mock-exam'));
  body.querySelector('#btn-submit-speaking')?.addEventListener('click', () => submitResponse(el));
}

function renderPromptContent(state) {
  if (Array.isArray(state.sentences) && state.sentences.length) {
    return `
      <div style="font-weight:700;margin-bottom:8px">${escHtml(state.prompt || 'Repeat the following sentences')}</div>
      <div style="display:flex;flex-direction:column;gap:8px">
        ${state.sentences.map(item => `
          <div style="display:flex;gap:10px;align-items:flex-start;background:var(--bg2);border-radius:10px;padding:10px 12px">
            <span class="tag">L${item.level || ''}</span>
            <div style="flex:1">${escHtml(item.text || '')}</div>
            <button class="tts-btn" onclick="tts(${JSON.stringify(item.text || '')})">🔊</button>
          </div>
        `).join('')}
      </div>
    `;
  }
  if (Array.isArray(state.questions) && state.questions.length) {
    return `
      <div style="font-weight:700;margin-bottom:8px">${escHtml(state.prompt || 'Answer the following questions')}</div>
      <div style="display:flex;flex-direction:column;gap:8px">
        ${state.questions.map((item, index) => `
          <div style="background:var(--bg2);border-radius:10px;padding:10px 12px">
            <div style="font-weight:600;margin-bottom:4px">Q${index + 1}</div>
            <div>${escHtml(item.question || '')}</div>
          </div>
        `).join('')}
      </div>
    `;
  }
  return escHtml(state.prompt || '');
}

async function submitResponse(el) {
  const body = el.querySelector('#speaking-task-panel');
  if (!body) return;
  const ta = body.querySelector('#speaking-response');
  const feedback = body.querySelector('#speaking-feedback');
  if (!ta || !feedback) return;
  const transcript = ta.value.trim();
  if (countWords(transcript) < 20) {
    feedback.innerHTML = '<div class="alert alert-warn">Please enter at least 20 words before submitting.</div>';
    ta.focus();
    return;
  }

  body.querySelector('#btn-submit-speaking').disabled = true;
  feedback.innerHTML = '<div style="text-align:center;padding:18px"><div class="spinner"></div></div>';

  try {
    const result = await api.post('/api/speaking/submit', {
      transcript,
      task_type: _state.task_type,
      exam: _state.exam,
      prompt: _state.prompt,
      sample_response: _state.sample_response || null,
      duration_sec: elapsedSeconds(),
    });
    if (window._currentAbortSignal?.aborted || !el.isConnected) return;
    renderFeedback(feedback, result);
    _store.clear();
  } catch (e) {
    if (e.name === 'AbortError' || !el.isConnected) return;
    feedback.innerHTML = `<div class="alert alert-error">${escHtml(e.message)}</div>`;
  } finally {
    const submitBtn = body.querySelector('#btn-submit-speaking');
    if (submitBtn) submitBtn.disabled = false;
  }
}

function renderFeedback(container, result) {
  const overall = result.overall || 0;
  const color = overall >= 3 ? 'var(--green)' : overall >= 2 ? 'var(--yellow)' : 'var(--red)';
  const strengths = (result.strengths || []).map(item => `<li>${escHtml(item)}</li>`).join('');
  const improvements = (result.improvements || []).map(item => `<li>${escHtml(item)}</li>`).join('');
  const phrases = (result.key_phrases_to_add || []).map(item => `<span class="tag">${escHtml(item)}</span>`).join(' ');
  const scores = result.scores || {};

  container.innerHTML = `
    <div class="card" style="background:var(--bg2);padding:16px">
      <div style="text-align:center;margin-bottom:14px">
        <div style="font-size:12px;color:var(--text-dim)">Overall Speaking Score</div>
        <div style="font-size:36px;font-weight:700;color:${color}">${overall}<span style="font-size:18px;color:var(--text-dim)"> / 4</span></div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:14px">
        ${Object.entries(scores).map(([key, val]) => `
          <div class="card" style="padding:12px;text-align:center">
            <div style="font-size:12px;color:var(--text-dim)">${escHtml(key.replace(/_/g, ' '))}</div>
            <div style="font-size:22px;font-weight:700">${val}/4</div>
          </div>
        `).join('')}
      </div>
      ${strengths ? `<h3 style="margin-bottom:8px">Strengths</h3><ul style="margin-top:0">${strengths}</ul>` : ''}
      ${improvements ? `<h3 style="margin-bottom:8px">Improvements</h3><ul style="margin-top:0">${improvements}</ul>` : ''}
      ${phrases ? `<h3 style="margin-bottom:8px">Phrases To Add</h3><div style="display:flex;gap:8px;flex-wrap:wrap">${phrases}</div>` : ''}
      <div class="card" style="margin-top:14px;background:var(--bg3);padding:14px;text-align:left">
        <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">下一步建议</div>
        <div style="font-size:14px;line-height:1.7">${escHtml(speakingRecommendation(overall))}</div>
      </div>
      ${isMockSection() ? '<div style="margin-top:14px;text-align:center"><button class="btn btn-outline" id="btn-complete-speaking-mock">Complete Mock Section</button></div>' : ''}
    </div>
  `;
  container.querySelector('#btn-complete-speaking-mock')?.addEventListener('click', async () => {
    await completeMockSection(overall);
  });
}

function getPracticeContext() {
  try {
    const raw = sessionStorage.getItem(PRACTICE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.section !== 'speaking') return null;
    if (parsed.started_at && Date.now() - parsed.started_at > 30 * 60 * 1000) {
      sessionStorage.removeItem(PRACTICE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function normalizePracticeContext(practice) {
  const exam = ['toefl', 'ielts'].includes(practice.exam) ? practice.exam : 'toefl';
  const valid = (TASKS[exam] || []).map(item => item.id);
  const fallback = defaultTask(exam);
  const taskType = valid.includes(practice.type) ? practice.type : fallback;
  return { exam, task_type: taskType };
}

function practiceBannerHtml() {
  if (!_activePractice) return '';
  return `
    <div class="card" style="margin-bottom:16px;padding:14px 16px;border-color:var(--accent);background:var(--bg2)">
      <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--accent);margin-bottom:6px">
        ${_activePractice.source === 'mock_exam' ? 'MOCK EXAM' : 'PRACTICE MODE'}
      </div>
      <div style="font-size:14px">${escHtml(practiceSummaryText(_activePractice))}</div>
    </div>
  `;
}

function practiceSummaryText(practice) {
  const exam = (practice.exam || 'toefl').toUpperCase();
  const mode = practice.source === 'mock_exam' ? 'Mock Section' : 'Speaking Drill';
  const task = practice.type ? ` · ${String(practice.type).replace(/_/g, ' ')}` : '';
  return `${exam} ${mode}${task}`;
}

function practiceCategoryLabel(practice) {
  return {
    core: '核心内容',
    growth: '成长内容',
    sprint: '冲刺内容',
    ai_enhanced: 'AI 增强',
  }[practice?.category] || '';
}

function isMockSection() {
  return _activePractice?.source === 'mock_exam' && _activePractice?.mock_session_id;
}

async function completeMockSection(overall) {
  if (!isMockSection()) return;
  await api.post(`/api/mock-exam/complete-section/${_activePractice.mock_session_id}`, {
    section_index: _activePractice.mock_section_index,
    result: {
      correct: Number(overall >= 2.5),
      total: 1,
      source: 'speaking',
      overall,
    },
  });
  navigate('mock-exam');
}

function defaultTask(exam) {
  return exam === 'ielts' ? 'part1' : 'independent';
}

function speakingRecommendation(overall) {
  if (overall >= 3.5) {
    return '这轮口语已经比较稳定，下一轮建议缩短犹豫时间，进一步提升表达自然度和句式变化。';
  }
  if (overall >= 2.5) {
    return '这轮口语具备基本完成度，建议下一轮只盯住一个问题，比如结构更清楚，或例子更具体。';
  }
  return '这轮口语还不够稳定，建议先把回答拆成“观点 + 两个支撑点”的固定骨架，再逐步提升词汇和流畅度。';
}

function countWords(text) {
  return String(text || '').trim().split(/\s+/).filter(Boolean).length;
}

function escHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
