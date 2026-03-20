// pages/listening.js — Listening comprehension with rich audio player + karaoke transcript

const STORAGE_KEY = 'listening_current';
const PRACTICE_KEY = 'practice_mode';

const _store = {
  get: () => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { return null; } },
  set: (v) => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(v)); } catch {} },
  clear: () => { try { localStorage.removeItem(STORAGE_KEY); } catch {} },
};

let _sid = null;
let _qTotal = 0;
let _qIndex = 0;
let _answers = {};
let _info = null;
let _timestamps = []; // [{index, speaker, text, start_ms, end_ms}]
let _audioEl = null;  // shared <audio> element reference
let _activePractice = null;

export async function render(el) {
  const saved = _store.get();
  const incomingPractice = getPracticeContext();

  if (incomingPractice) {
    _activePractice = incomingPractice;
    _store.clear();
    renderStart(el);
    return;
  }

  if (saved && saved.session_id) {
    _activePractice = saved.practice || null;
    _sid = saved.session_id; _qTotal = saved.question_count;
    _qIndex = saved.q_index || 0; _answers = saved.answers || {};
    _info = saved; _timestamps = saved.timestamps || [];
    renderShell(el, saved);
    if (_qIndex > 0 && _qIndex < _qTotal) {
      renderQA(el); loadQuestion(el);
    } else if (_qIndex >= _qTotal && _qTotal > 0) {
      showResults(el);
    }
    return;
  }

  _activePractice = null;
  renderStart(el);
}

function saveSession() {
  if (!_sid) return;
  _store.set({ session_id: _sid, question_count: _qTotal,
    q_index: _qIndex, answers: _answers, timestamps: _timestamps, ..._info });
}

// ── Start screen ──────────────────────────────────────────────────────────────
function renderStart(el) {
  const preset = getListeningPreset();
  const startLabel = _activePractice?.source === 'mock_exam' ? '▶ Start Mock Section' : '▶ Start Listening';

  el.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
      <h1 style="margin:0">🎧 Listening Practice</h1>
    </div>
    <p style="margin-bottom:16px;color:var(--text-dim)">
      ${_activePractice
        ? `${escHtml((preset.exam || 'general').toUpperCase())} ${_activePractice.source === 'mock_exam' ? '模考分节' : '专项训练'}已预选`
        : 'Simulates real exam listening conditions. Audio plays up to 3 times, transcript revealed after completion.'}
    </p>
    ${practiceBannerHtml()}
    <div class="card" style="margin-bottom:16px;padding:16px">
      <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:flex-end">
        <div>
          <label style="font-size:12px;color:var(--text-dim);display:block;margin-bottom:6px">EXAM</label>
          <div id="exam-tabs" style="display:flex;gap:6px;flex-wrap:wrap">
            ${['general','toefl','ielts','cet','gre'].map((e,i) =>
              `<button class="btn ${e===preset.exam?'btn-primary':'btn-outline'} exam-tab" data-exam="${e}" style="font-size:13px;padding:5px 12px">${e.toUpperCase()}</button>`
            ).join('')}
          </div>
        </div>
        <div>
          <label style="font-size:12px;color:var(--text-dim);display:block;margin-bottom:6px">TYPE</label>
          <div id="type-tabs" style="display:flex;gap:6px">
            <button class="btn ${preset.dtype === 'conversation' ? 'btn-primary' : 'btn-outline'} type-tab" data-type="conversation" style="font-size:13px;padding:5px 12px">Conversation</button>
            <button class="btn ${preset.dtype === 'monologue' ? 'btn-primary' : 'btn-outline'} type-tab" data-type="monologue" style="font-size:13px;padding:5px 12px">Lecture / Talk</button>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
          <button class="btn btn-success" id="btn-begin" style="padding:8px 24px;font-size:14px">${startLabel}</button>
          <div id="pool-status" style="font-size:11px;color:var(--text-dim);text-align:center"></div>
        </div>
      </div>
    </div>
    <div id="listening-body"></div>
  `;
  el.querySelectorAll('.exam-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      el.querySelectorAll('.exam-tab').forEach(b => {
        b.className = `btn ${b === btn ? 'btn-primary' : 'btn-outline'} exam-tab`;
      });
      updatePoolStatus(el);
    });
  });
  el.querySelectorAll('.type-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      el.querySelectorAll('.type-tab').forEach(b => {
        b.className = `btn ${b === btn ? 'btn-primary' : 'btn-outline'} type-tab`;
      });
      updatePoolStatus(el);
    });
  });
  el.querySelector('#btn-begin').addEventListener('click', () => startSession(el));
  updatePoolStatus(el);
}

async function updatePoolStatus(el) {
  const statusEl = el.querySelector('#pool-status');
  if (!statusEl) return;
  try {
    const r = await api.get('/api/listening/pool/status');

    // Check if navigation was aborted while waiting
    if (window._currentAbortSignal?.aborted || !el.isConnected) {
      return; // User navigated away
    }

    const examBtn = el.querySelector('.exam-tab.btn-primary');
    const typeBtn = el.querySelector('.type-tab.btn-primary');
    const exam  = examBtn ? examBtn.dataset.exam  : 'general';
    const dtype = typeBtn ? typeBtn.dataset.type  : 'conversation';
    const entry = (r.pool || []).find(p => p.exam === exam && p.type === dtype);
    const count = entry ? entry.count : 0;
    if (count > 0) {
      statusEl.innerHTML = `<span style="color:var(--green)">✓ ${count} session${count>1?'s':''} ready</span>`;
    } else {
      statusEl.innerHTML = `<span style="color:var(--yellow)">⏳ Preparing…</span>`;
    }
  } catch (e) {
    // Don't show error if request was aborted
    if (e.name === 'AbortError' || !el.isConnected) return;
    statusEl.innerHTML = '';
  }
}

// ── Session start ─────────────────────────────────────────────────────────────
async function startSession(el) {
  // Show a lightweight inline spinner inside the button, not a full-page loader
  const btnBegin = el.querySelector('#btn-begin');
  if (btnBegin) { btnBegin.disabled = true; btnBegin.textContent = '⏳ Loading…'; }

  const examBtn = el.querySelector('.exam-tab.btn-primary') || document.querySelector('.exam-tab.btn-primary');
  const typeBtn = el.querySelector('.type-tab.btn-primary') || document.querySelector('.type-tab.btn-primary');
  const exam  = examBtn ? examBtn.dataset.exam  : 'general';
  const dtype = typeBtn ? typeBtn.dataset.type  : 'conversation';
  const requestedType = _activePractice?.type || '';

  try {
    const params = new URLSearchParams({ exam, dialogue_type: dtype });
    if (requestedType) params.set('question_type', requestedType);
    const r = await api.post(`/api/listening/start?${params}`, {});

    // Check if navigation was aborted while waiting for response
    if (window._currentAbortSignal?.aborted || !el.isConnected) {
      return; // User navigated away, don't render
    }

    _sid = r.session_id; _qTotal = r.question_count;
    _qIndex = 0; _answers = {}; _info = { ...r, practice: _activePractice };
    _timestamps = r.timestamps || [];
    saveSession();
    renderShell(el, r);
  } catch (e) {
    // Don't show error if request was aborted (user navigated away)
    if (e.name === 'AbortError' || !el.isConnected) return;

    if (btnBegin) { btnBegin.disabled = false; btnBegin.textContent = '▶ Start Listening'; }
    const body = el.querySelector('#listening-body') || el;
    const errDiv = document.createElement('div');
    errDiv.className = 'alert alert-error';
    errDiv.style.marginTop = '12px';
    errDiv.innerHTML = `${e.message} <button class="btn btn-outline" style="margin-left:8px" id="btn-retry">↺ Retry</button>`;
    body.appendChild(errDiv);
    errDiv.querySelector('#btn-retry').addEventListener('click', () => renderStart(el));
  }
}

// ── Main shell ────────────────────────────────────────────────────────────────
function renderShell(el, info) {
  const exam = (info.exam || 'general').toLowerCase();
  const examLabel = {toefl:'TOEFL',ielts:'IELTS',gre:'GRE',cet:'CET-4/6',general:'General'}[exam] || exam.toUpperCase();
  const dialogueLabel = info.type === 'monologue' ? 'Lecture / Talk' : 'Conversation';
  const questionTypeLabel = info.question_type_label || (info.question_type ? typeLabel(info.question_type) : '');

  el.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <h1 style="margin:0">🎧 Listening Practice</h1>
      <div style="display:flex;gap:8px;align-items:center">
        ${practiceTagHtml()}
        <span class="tag">${examLabel}</span>
        <span class="tag">${info.difficulty || 'B1'}</span>
        ${questionTypeLabel ? `<span class="tag">${escHtml(questionTypeLabel)}</span>` : ''}
        <span class="tag" style="color:var(--text-dim)">${dialogueLabel}</span>
        <button class="btn btn-outline" id="btn-new" style="font-size:12px;padding:4px 10px">New ↺</button>
      </div>
    </div>

    <!-- Rich audio player -->
    <div class="card" id="audio-bar" style="margin-bottom:12px;padding:16px 18px;background:var(--bg2)">
      ${info.topic ? `<div style="font-size:13px;font-weight:600;margin-bottom:10px;color:var(--text-dim)">📌 Topic: <span style="color:var(--text)">${info.topic}</span></div>` : ''}
      <audio id="listen-audio" style="display:none"></audio>

      <!-- Seekable progress bar -->
      <div id="progress-track" style="background:var(--bg3);border-radius:6px;height:12px;cursor:pointer;position:relative;margin-bottom:8px;user-select:none;-webkit-user-select:none">
        <div id="audio-progress" style="background:var(--accent);height:12px;border-radius:6px;width:0%;pointer-events:none"></div>
        <div id="seek-thumb" style="position:absolute;top:50%;transform:translate(-50%,-50%);width:16px;height:16px;border-radius:50%;background:#fff;box-shadow:0 0 4px rgba(0,0,0,.6);left:0%;pointer-events:none"></div>
      </div>

      <!-- Time row -->
      <div style="display:flex;justify-content:space-between;margin-bottom:10px">
        <span id="time-current" style="font-size:11px;color:var(--text-dim)">0:00</span>
        <span id="time-total" style="font-size:11px;color:var(--text-dim)">--:--</span>
      </div>

      <!-- Controls row -->
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <!-- Skip back -->
        <button class="btn btn-outline" id="btn-skip-back" title="Back 10s" style="font-size:13px;padding:5px 10px">⏮ 10s</button>
        <!-- Play/Pause -->
        <button class="btn btn-primary" id="btn-play" style="min-width:90px;font-size:14px">▶ Play</button>
        <!-- Skip forward -->
        <button class="btn btn-outline" id="btn-skip-fwd" title="Forward 10s" style="font-size:13px;padding:5px 10px">10s ⏭</button>

        <!-- Speed selector -->
        <div style="display:flex;align-items:center;gap:6px;margin-left:4px">
          <span style="font-size:12px;color:var(--text-dim)">Speed</span>
          <div id="speed-btns" style="display:flex;gap:4px">
            ${[0.5,0.75,1.0,1.25,1.5].map(s =>
              `<button class="btn ${s===1.0?'btn-primary':'btn-outline'} speed-btn" data-speed="${s}" style="font-size:11px;padding:3px 7px">${s}×</button>`
            ).join('')}
          </div>
        </div>

        <!-- Play count dots -->
        <div style="margin-left:auto;text-align:center">
          <div id="play-count-dots" style="display:flex;gap:4px;justify-content:center;margin-bottom:3px">
            <span class="play-dot" style="width:8px;height:8px;border-radius:50%;background:var(--border);display:inline-block"></span>
            <span class="play-dot" style="width:8px;height:8px;border-radius:50%;background:var(--border);display:inline-block"></span>
            <span class="play-dot" style="width:8px;height:8px;border-radius:50%;background:var(--border);display:inline-block"></span>
          </div>
          <span id="play-count-label" style="font-size:11px;color:var(--text-dim)">0 / 3 plays</span>
        </div>
      </div>
      <div id="player-msg" style="font-size:12px;color:var(--yellow);margin-top:6px;text-align:center;min-height:16px"></div>
    </div>

    <!-- Question area -->
    <div id="qa-area">
      <div class="card" style="text-align:center;padding:32px;color:var(--text-dim)">
        <div style="font-size:32px;margin-bottom:12px">🎧</div>
        <div style="font-size:14px">Listen to the audio first, then click <strong>Start Questions</strong></div>
        <button class="btn btn-primary" id="btn-start-q" style="margin-top:20px;padding:10px 28px;font-size:14px">
          Start Questions (${_qTotal}) →
        </button>
      </div>
    </div>
  `;

  wireAudioPlayer(el, info);
  el.querySelector('#btn-new').addEventListener('click', () => { _store.clear(); renderStart(el); });
  el.querySelector('#btn-start-q').addEventListener('click', () => { renderQA(el); loadQuestion(el); });
}

// ── Audio player wiring ───────────────────────────────────────────────────────
function wireAudioPlayer(el, info) {
  const audio = el.querySelector('#listen-audio');
  _audioEl = audio;
  const btnPlay    = el.querySelector('#btn-play');
  const progressEl = el.querySelector('#audio-progress');
  const thumbEl    = el.querySelector('#seek-thumb');
  const timeCurrent = el.querySelector('#time-current');
  const timeTotal   = el.querySelector('#time-total');
  const countLabel  = el.querySelector('#play-count-label');
  const playerMsg   = el.querySelector('#player-msg');
  const dots        = el.querySelectorAll('.play-dot');
  let playCount = 0;
  let currentSpeed = 1.0;

  function fmt(s) {
    const m = Math.floor(s / 60), sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2,'0')}`;
  }

  let _rafId = null;
  function updateProgress() {
    if (!audio.duration) return;
    const pct = (audio.currentTime / audio.duration) * 100;
    const pctStr = pct.toFixed(2) + '%';
    progressEl.style.width = pctStr;
    thumbEl.style.left = pctStr;
    timeCurrent.textContent = fmt(audio.currentTime);
    highlightTranscriptLine(audio.currentTime * 1000);
  }

  function rafLoop() {
    updateProgress();
    _rafId = requestAnimationFrame(rafLoop);
  }

  audio.addEventListener('loadedmetadata', () => { timeTotal.textContent = fmt(audio.duration); });
  audio.addEventListener('play',  () => { if (_rafId) cancelAnimationFrame(_rafId); rafLoop(); });
  audio.addEventListener('pause', () => { if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; } updateProgress(); });
  audio.addEventListener('ended', () => {
    if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
    progressEl.style.width = '100%'; thumbEl.style.left = '100%';
    btnPlay.textContent = playCount < 3 ? '↺ Replay' : '✓ Done';
    if (playCount >= 3) { btnPlay.disabled = true; playerMsg.textContent = 'Maximum plays reached — proceed to questions.'; }
  });
  audio.addEventListener('seeked', updateProgress);

  // Seekable progress bar — use pointer events for reliability in WebView2
  const track = el.querySelector('#progress-track');
  let seeking = false;
  function seekTo(clientX) {
    if (!audio.duration) return;
    const rect = track.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    audio.currentTime = pct * audio.duration;
    updateProgress();
  }
  track.addEventListener('pointerdown', (e) => {
    e.preventDefault(); track.setPointerCapture(e.pointerId);
    seeking = true; seekTo(e.clientX);
  });
  track.addEventListener('pointermove', (e) => { if (seeking) seekTo(e.clientX); });
  track.addEventListener('pointerup',   (e) => { seeking = false; seekTo(e.clientX); });
  track.addEventListener('pointercancel', () => { seeking = false; });

  // Skip ±10s
  el.querySelector('#btn-skip-back').addEventListener('click', () => {
    if (audio.src) audio.currentTime = Math.max(0, audio.currentTime - 10);
  });
  el.querySelector('#btn-skip-fwd').addEventListener('click', () => {
    if (audio.src) audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 10);
  });

  // Speed buttons
  el.querySelectorAll('.speed-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      currentSpeed = parseFloat(btn.dataset.speed);
      audio.playbackRate = currentSpeed;
      el.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('btn-primary'));
      btn.classList.add('btn-primary');
    });
  });

  // Play / Pause / Replay
  btnPlay.addEventListener('click', async () => {
    if (playCount >= 3) return;
    if (!audio.paused && !audio.ended) {
      audio.pause(); btnPlay.textContent = '▶ Resume'; return;
    }
    if (audio.src && !audio.ended) {
      audio.play(); btnPlay.textContent = '⏸ Pause'; return;
    }
    btnPlay.disabled = true; btnPlay.textContent = '⏳ Loading…';
    try {
      audio.src = `/api/listening/audio/${_sid}?_t=${Date.now()}`;
      audio.playbackRate = currentSpeed;
      await audio.play();
      playCount++;
      dots.forEach((d, i) => { d.style.background = i < playCount ? 'var(--accent)' : 'var(--border)'; });
      countLabel.textContent = `${playCount} / 3 plays`;
      btnPlay.textContent = '⏸ Pause'; btnPlay.disabled = false;
      audio.onpause = () => { if (!audio.ended) btnPlay.textContent = '▶ Resume'; };
      audio.onplay  = () => { btnPlay.textContent = '⏸ Pause'; };
    } catch (e) {
      playerMsg.textContent = e.message;
      btnPlay.disabled = false; btnPlay.textContent = '▶ Play';
    }
  });
}

// ── Karaoke highlight ─────────────────────────────────────────────────────────
function highlightTranscriptLine(currentMs) {
  const lines = document.querySelectorAll('.transcript-line');
  if (!lines.length || !_timestamps.length) return;
  let activeIdx = -1;
  for (let i = 0; i < _timestamps.length; i++) {
    if (currentMs >= _timestamps[i].start_ms && currentMs <= _timestamps[i].end_ms) {
      activeIdx = i; break;
    }
    if (currentMs > _timestamps[i].end_ms) activeIdx = i;
  }
  lines.forEach((line, i) => {
    const isActive = i === activeIdx;
    line.style.background = isActive ? 'var(--bg3)' : '';
    line.style.borderLeftColor = isActive ? 'var(--accent)' : 'transparent';
    line.style.color = isActive ? 'var(--text)' : '';
    if (isActive) line.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  });
}

// ── QA area ───────────────────────────────────────────────────────────────────
function renderQA(el) {
  el.querySelector('#qa-area').innerHTML =
    '<div style="text-align:center;padding:20px"><div class="spinner"></div></div>';
}

async function loadQuestion(el) {
  const qaArea = el.querySelector('#qa-area');
  if (!qaArea) return;
  qaArea.innerHTML = '<div style="text-align:center;padding:20px"><div class="spinner"></div></div>';
  try {
    const q = await api.get(`/api/listening/question/${_sid}/${_qIndex}`);

    // Check if navigation was aborted while waiting
    if (window._currentAbortSignal?.aborted || !el.isConnected) {
      return; // User navigated away
    }

    renderQuestion(el, q);
  } catch (e) {
    // Don't show error if request was aborted
    if (e.name === 'AbortError' || !el.isConnected) return;

    qaArea.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

function renderQuestion(el, q) {
  const qaArea = el.querySelector('#qa-area');
  const exam = (_info && _info.exam || 'general').toLowerCase();
  const opts = exam === 'cet' ? q.options.slice(0, 3) : q.options;
  const letters = ['A','B','C','D'];

  qaArea.innerHTML = `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:10px">
          <span style="font-size:13px;font-weight:600">Question ${q.index + 1}</span>
          <span style="font-size:12px;color:var(--text-dim)">of ${q.total}</span>
        </div>
        <div style="display:flex;gap:6px">
          ${Array.from({length: q.total}, (_,i) => `
            <span style="width:8px;height:8px;border-radius:50%;display:inline-block;
              background:${i < q.index ? 'var(--green)' : i === q.index ? 'var(--accent)' : 'var(--border)'}"></span>
          `).join('')}
        </div>
      </div>
      <div style="background:var(--bg2);border-left:3px solid var(--accent);padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:18px">
        <p style="font-size:15px;font-weight:500;margin:0;line-height:1.6">${q.question}</p>
      </div>
      <div id="options" style="display:flex;flex-direction:column;gap:8px">
        ${opts.map((opt, i) => `
          <button class="choice-btn" data-letter="${letters[i]}"
            style="text-align:left;padding:10px 14px;border-radius:8px;display:flex;align-items:flex-start;gap:10px">
            <span style="font-weight:700;color:var(--accent);min-width:20px">${letters[i]}.</span>
            <span>${opt.replace(/^[A-D]\.\s*/,'')}</span>
          </button>`).join('')}
      </div>
      <div id="q-feedback" style="margin-top:14px"></div>
      <button class="btn btn-primary hidden" id="btn-next-q"
        style="margin-top:14px;width:100%;justify-content:center;font-size:14px">
        ${q.index + 1 < q.total ? `Next Question (${q.index + 2}/${q.total}) →` : 'See Results →'}
      </button>
    </div>
  `;

  qaArea.querySelectorAll('.choice-btn').forEach(btn => {
    btn.addEventListener('click', () => submitAnswer(el, q, btn.dataset.letter));
  });
}

async function submitAnswer(el, q, letter) {
  el.querySelectorAll('.choice-btn').forEach(b => b.disabled = true);
  const feedback = el.querySelector('#q-feedback');
  const btnNext  = el.querySelector('#btn-next-q');
  try {
    const r = await api.post(`/api/listening/answer/${_sid}`, { question_index: q.index, answer: letter });

    // Check if navigation was aborted while waiting
    if (window._currentAbortSignal?.aborted || !el.isConnected) {
      return; // User navigated away
    }

    _answers[q.index] = r; saveSession();
    el.querySelectorAll('.choice-btn').forEach(btn => {
      if (btn.dataset.letter === r.correct_answer) btn.classList.add('correct');
      else if (btn.dataset.letter === letter && !r.correct) btn.classList.add('wrong');
    });
    feedback.innerHTML = `
      <div class="explanation-box show" style="margin-top:0">
        ${r.correct ? '✅' : '❌'} <strong>${r.correct ? 'Correct!' : `Incorrect — Answer: ${r.correct_answer}`}</strong><br>
        <span style="font-size:13px">${r.explanation}</span>
      </div>`;
    btnNext.classList.remove('hidden');
    btnNext.addEventListener('click', () => {
      if (r.session_complete) { _qIndex = _qTotal; saveSession(); showResults(el); }
      else { _qIndex++; saveSession(); loadQuestion(el); }
    });
  } catch (e) {
    // Don't show error if request was aborted
    if (e.name === 'AbortError' || !el.isConnected) return;

    feedback.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

// ── Results + karaoke transcript ──────────────────────────────────────────────
async function showResults(el) {
  const qaArea = el.querySelector('#qa-area');
  const correct = Object.values(_answers).filter(a => a.correct).length;
  const pct = Math.round((correct / _qTotal) * 100);
  const color = pct >= 80 ? 'var(--green)' : pct >= 60 ? 'var(--yellow)' : 'var(--red)';
  const recommendation = listeningRecommendation(pct, correct, _qTotal);

  qaArea.innerHTML = `
    <div class="card" style="text-align:center;padding:32px">
      <div style="font-size:40px;margin-bottom:12px">${pct>=80?'🎉':pct>=60?'👍':'💪'}</div>
      <h2 style="margin-bottom:8px">Listening Complete</h2>
      ${_activePractice ? `<p style="color:var(--text-dim);margin-top:-4px">${escHtml(practiceSummaryText())}</p>` : ''}
      <div style="font-size:36px;font-weight:700;color:${color};margin:12px 0">${pct}%</div>
      <p style="color:var(--text-dim)">${correct} / ${_qTotal} correct</p>
      <div class="card" style="margin:18px auto 0;max-width:560px;text-align:left;background:var(--bg2);padding:16px">
        <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">结果解读</div>
        <div style="font-size:14px;line-height:1.7">${escHtml(recommendation)}</div>
      </div>
      <div style="display:flex;gap:10px;justify-content:center;margin-top:20px;flex-wrap:wrap">
        <button class="btn btn-outline" id="btn-transcript">📄 Show Transcript</button>
        <button class="btn btn-primary" id="btn-new-listen">${_activePractice ? 'Another Drill ↺' : 'New Listening ↺'}</button>
        ${isMockSection() ? '<button class="btn btn-outline" id="btn-complete-listening-mock">Complete Mock Section</button>' : ''}
      </div>
      <div id="transcript-area" style="margin-top:16px;text-align:left"></div>
    </div>
  `;

  qaArea.querySelector('#btn-new-listen').addEventListener('click', () => { _store.clear(); renderStart(el); });
  qaArea.querySelector('#btn-complete-listening-mock')?.addEventListener('click', async () => {
    await completeMockSection(correct, _qTotal);
  });
  qaArea.querySelector('#btn-transcript').addEventListener('click', async () => {
    const area = qaArea.querySelector('#transcript-area');
    if (area.innerHTML) { area.innerHTML = ''; return; }
    try {
      const r = await api.get(`/api/listening/transcript/${_sid}`);
      const ts = r.timestamps || _timestamps || [];
      area.innerHTML = `
        <div class="card" style="background:var(--bg2);padding:16px;max-height:400px;overflow-y:auto" id="transcript-scroll">
          <div style="font-size:12px;font-weight:600;margin-bottom:12px;color:var(--text-dim);letter-spacing:1px">
            TRANSCRIPT ${ts.length ? '<span style="font-weight:400;font-size:11px">(click a line to jump to that position)</span>' : ''}
          </div>
          ${r.script.map((line, i) => {
            const t = ts[i];
            const startSec = t ? (t.start_ms / 1000).toFixed(1) : null;
            return `
            <div class="transcript-line" data-idx="${i}" data-start-ms="${t ? t.start_ms : ''}"
              style="margin-bottom:8px;display:flex;gap:8px;align-items:flex-start;padding:6px 10px;
                     border-radius:6px;border-left:3px solid transparent;cursor:${t ? 'pointer' : 'default'};
                     transition:background .15s,border-color .15s">
              <span style="font-weight:700;color:var(--accent);min-width:20px;flex-shrink:0">${line.speaker}:</span>
              <span style="flex:1;line-height:1.7">${line.text}</span>
              <div style="display:flex;align-items:center;gap:6px;flex-shrink:0">
                ${startSec !== null ? `<span style="font-size:10px;color:var(--text-dim)">${startSec}s</span>` : ''}
                <button class="tts-btn" onclick="event.stopPropagation();tts('${line.text.replace(/'/g,"\\'").replace(/"/g,'&quot;')}')">🔊</button>
              </div>
            </div>`;
          }).join('')}
        </div>`;

      // Wire click-to-seek on transcript lines
      area.querySelectorAll('.transcript-line[data-start-ms]').forEach(lineEl => {
        const startMs = parseInt(lineEl.dataset.startMs);
        if (!startMs && startMs !== 0) return;
        lineEl.addEventListener('click', () => {
          if (_audioEl && _audioEl.duration) {
            _audioEl.currentTime = startMs / 1000;
            if (_audioEl.paused) _audioEl.play().catch(() => {});
          }
        });
        lineEl.addEventListener('mouseenter', () => { lineEl.style.background = 'var(--bg3)'; });
        lineEl.addEventListener('mouseleave', () => {
          // keep highlight if it's the active line
          const currentMs = _audioEl ? _audioEl.currentTime * 1000 : -1;
          const t = ts[parseInt(lineEl.dataset.idx)];
          if (!t || currentMs < t.start_ms || currentMs > t.end_ms) lineEl.style.background = '';
        });
      });

      // Store timestamps for karaoke
      if (ts.length) _timestamps = ts;
    } catch (e) {
      area.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
  });
}

function getPracticeContext() {
  try {
    const raw = sessionStorage.getItem(PRACTICE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.section !== 'listening') return null;
    if (parsed.started_at && Date.now() - parsed.started_at > 30 * 60 * 1000) {
      sessionStorage.removeItem(PRACTICE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function getListeningPreset() {
  const practice = _activePractice || {};
  const exam = ['general', 'toefl', 'ielts', 'cet', 'gre'].includes(practice.exam) ? practice.exam : 'general';
  return {
    exam,
    dtype: mapListeningType(practice.type),
  };
}

function mapListeningType(type) {
  return ['organization', 'lecture', 'talk', 'monologue'].includes(type) ? 'monologue' : 'conversation';
}

function practiceBannerHtml() {
  if (!_activePractice) return '';
  return `
    <div class="card" style="margin-bottom:16px;padding:14px 16px;border-color:var(--accent);background:var(--bg2)">
      <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--accent);margin-bottom:6px">
        ${_activePractice.source === 'mock_exam' ? 'MOCK EXAM' : 'PRACTICE MODE'}
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:14px">
        ${escHtml(practiceSummaryText())}
        ${_activePractice.source === 'coach_plan' && _activePractice.category ? `<span class="tag">${escHtml(practiceCategoryLabel(_activePractice.category))}</span>` : ''}
      </div>
    </div>
  `;
}

function practiceTagHtml() {
  if (!_activePractice) return '';
  return `<span class="tag" style="border-color:var(--accent);color:var(--accent)">${escHtml(practiceSummaryText())}</span>`;
}

function practiceSummaryText() {
  if (!_activePractice) return '';
  const exam = (_activePractice.exam || 'general').toUpperCase();
  const label = _activePractice.source === 'mock_exam' ? 'Mock Section' : 'Drill';
  const type = _activePractice.type ? ` · ${typeLabel(_activePractice.type)}` : '';
  return `${exam} ${label}${type}`;
}

function practiceCategoryLabel(category) {
  return { core: '核心内容', growth: '成长内容', sprint: '冲刺内容', ai_enhanced: 'AI 增强' }[category] || category || '';
}

function isMockSection() {
  return _activePractice?.source === 'mock_exam' && _activePractice?.mock_session_id;
}

async function completeMockSection(correct, total) {
  if (!isMockSection()) return;
  await api.post(`/api/mock-exam/complete-section/${_activePractice.mock_session_id}`, {
    section_index: _activePractice.mock_section_index,
    result: {
      correct,
      total,
      source: 'listening',
    },
  });
  navigate('mock-exam');
}

function typeLabel(type) {
  return {
    detail: 'Detail',
    inference: 'Inference',
    organization: 'Organization',
    attitude: 'Attitude',
    multiple_choice: 'Multiple Choice',
    form_completion: 'Form Completion',
    matching: 'Matching',
  }[type] || String(type || '').replace(/_/g, ' ');
}

function listeningRecommendation(pct, correct, total) {
  if (pct >= 85) {
    return '这轮听力表现稳定，建议继续做同考试下更高难度或更长材料，保持对结构与细节的双重把握。';
  }
  if (pct >= 60) {
    return `这轮已经具备基本稳定性，但还有 ${Math.max(total - correct, 0)} 题失分。建议看完 transcript 后再做一轮同类型材料，重点复盘漏听和误判。`;
  }
  return '这轮失分偏多，建议先降低难度或改做更短的对话/讲座，再逐步提升长度与速度。先把听懂主线建立起来。';
}

function escHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
