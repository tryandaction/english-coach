// pages/home.js — Dashboard

export async function render(el) {
  let data = {};
  let licStatus = {};
  try { data = await api.get('/api/progress'); } catch {}
  try { licStatus = await api.get('/api/license/status'); } catch {}

  const cefr     = data.cefr_level || '?';
  const streak   = data.streak_days || 0;
  const due      = data.srs_due ?? 0;
  const sessions = data.total_sessions || 0;
  const exam     = (data.target_exam || 'general').toUpperCase();
  const needsApi = !licStatus.active && !data.has_api_key;
  const isNew    = sessions < 3;

  const licBadge = licStatus.active
    ? `&nbsp;·&nbsp;<span class="tag tag-green">☁ Cloud ${licStatus.days_left}d</span>`
    : `&nbsp;·&nbsp;<span class="tag" style="color:var(--text-dim)">Offline</span>`;

  const vocabDesc = due > 0
    ? `${due} cards due`
    : (data.srs_total > 0 ? 'All done today ✓' : 'No words yet');

  // Onboarding dismissed?
  const onboardingDone = localStorage.getItem('onboarding_done') === '1';

  el.innerHTML = `
    <h1>Welcome back${data.name ? ', ' + data.name : ''} 👋</h1>
    <p style="margin-bottom:20px">CEFR <span class="tag">${cefr}</span> &nbsp;·&nbsp; Target: <span class="tag">${exam}</span>${streak ? `&nbsp;·&nbsp;<span class="tag tag-yellow">🔥 ${streak}d streak</span>` : ''}${licBadge}</p>

    <div class="stats-row">
      <div class="stat-badge"><div class="val">${due || '—'}</div><div class="lbl">Cards Due</div></div>
      <div class="stat-badge"><div class="val">${data.srs_total ?? '—'}</div><div class="lbl">Total Words</div></div>
      <div class="stat-badge"><div class="val">${sessions}</div><div class="lbl">Sessions</div></div>
      <div class="stat-badge"><div class="val">${data.avg_accuracy ?? 0}%</div><div class="lbl">Avg Accuracy</div></div>
    </div>

    ${isNew && !onboardingDone ? renderOnboarding(data, needsApi) : ''}

    ${renderExamProgress(data)}

    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <h2 style="margin:0">Today's Plan</h2>
    </div>
    <div class="daily-loop" style="margin-bottom:24px">
      ${planItem('vocab',   '🃏', 'Vocabulary',  due > 0 ? `${due} cards due` : 'All done ✓', due === 0 && data.srs_total > 0, false)}
      ${planItem('grammar', '✏️', 'Grammar',     'Fill-in-the-blank drills', false, false)}
      ${planItem('reading', '📖', 'Reading',     'Comprehension + AI questions', false, needsApi)}
      ${planItem('chat',    '💬', 'Chat',        'Free conversation practice', false, needsApi)}
    </div>

    <h2>All Modes</h2>
    <div class="card-grid">
      ${modeCard('vocab',   '🃏', 'Vocabulary',  vocabDesc,                     false)}
      ${modeCard('grammar', '✏️', 'Grammar',     'Fill-in-the-blank drills',    false)}
      ${modeCard('reading', '📖', 'Reading',     'Comprehension + AI questions', needsApi)}
      ${modeCard('writing', '📝', 'Writing',     'Essay feedback & scoring',     needsApi)}
      ${modeCard('chat',    '💬', 'Chat',        'Free conversation practice',   needsApi)}
      ${modeCard('progress','📊', 'Progress',    'Skills & session history',     false)}
    </div>

    ${needsApi ? `
    <div class="alert alert-info" style="margin-top:4px">
      Reading, Writing and Chat require an API key or cloud license.
      <a href="#" id="go-setup-api" style="color:var(--accent);margin-left:6px">Configure API →</a>
      &nbsp;or&nbsp;
      <a href="#" id="go-license-buy" style="color:var(--accent)">Get Cloud License →</a>
    </div>` : ''}
  `;

  // Daily plan clicks
  el.querySelectorAll('.plan-item:not(.plan-item-locked)').forEach(item => {
    item.addEventListener('click', () => navigate(item.dataset.page));
  });

  // Mode card clicks
  el.querySelectorAll('.mode-card:not(.mode-card-locked)').forEach(card => {
    card.addEventListener('click', () => navigate(card.dataset.page));
  });

  if (needsApi) {
    el.querySelector('#go-setup-api')?.addEventListener('click', e => { e.preventDefault(); navigate('setup'); });
    el.querySelector('#go-license-buy')?.addEventListener('click', e => { e.preventDefault(); navigate('license'); });
  }

  // Onboarding dismiss
  el.querySelector('#btn-dismiss-onboarding')?.addEventListener('click', () => {
    localStorage.setItem('onboarding_done', '1');
    el.querySelector('#onboarding-guide')?.remove();
  });

  // Onboarding step clicks
  el.querySelectorAll('.onboard-step[data-page]').forEach(step => {
    step.addEventListener('click', () => navigate(step.dataset.page));
  });
}

function renderExamProgress(data) {
  const examKey = (data.target_exam || 'general').toLowerCase();
  const examUpper = examKey.toUpperCase();
  const scores = data.skill_scores || {};

  // Vocab
  const vocabTotal = data.srs_total || 0;
  const vocabTargets = { toefl: 570, gre: 500, ielts: 500, cet: 600, general: 300 };
  const vocabTarget = vocabTargets[examKey] || 300;
  const vocabPct = Math.min(100, Math.round(vocabTotal / vocabTarget * 100));

  // Grammar — average of all grammar skill scores
  const grammarKeys = Object.keys(scores).filter(k => k.startsWith('grammar'));
  const grammarAvg = grammarKeys.length
    ? Math.round(grammarKeys.reduce((s, k) => s + (scores[k] || 0), 0) / grammarKeys.length * 100)
    : 0;

  // Session counts (may be absent from older API versions)
  const readingSessions  = data.reading_sessions  || 0;
  const writingSessions  = data.writing_sessions  || 0;
  const chatSessions     = data.chat_sessions     || 0;

  const rows = [
    { label: 'Vocabulary', pct: vocabPct,                          detail: `${vocabTotal} / ${vocabTarget} words` },
    { label: 'Grammar',    pct: grammarAvg,                        detail: grammarAvg ? `${grammarAvg}% accuracy` : 'Not started' },
    { label: 'Reading',    pct: Math.min(100, readingSessions * 7), detail: readingSessions ? `${readingSessions} passages` : 'Not started' },
    { label: 'Writing',    pct: Math.min(100, writingSessions * 10), detail: writingSessions ? `${writingSessions} essays` : 'Not started' },
    { label: 'Chat',       pct: Math.min(100, chatSessions * 5),   detail: chatSessions ? `${chatSessions} sessions` : 'Not started' },
  ];

  const rowsHtml = rows.map(r => {
    const color = r.pct >= 70 ? 'var(--green)' : r.pct >= 40 ? 'var(--accent)' : 'var(--text-dim)';
    return `
    <div style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px">
        <span>${r.label}</span>
        <span style="color:var(--text-dim)">${r.detail}</span>
      </div>
      <div style="height:6px;background:var(--bg3);border-radius:3px;overflow:hidden">
        <div style="height:100%;width:${r.pct}%;background:${color};border-radius:3px;transition:width 0.4s"></div>
      </div>
    </div>`;
  }).join('');

  return `
    <div class="card" style="margin-bottom:24px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <span class="exam-badge exam-${examKey}">${examUpper}</span>
        <h3 style="margin:0">Exam Prep Progress</h3>
      </div>
      ${rowsHtml}
    </div>`;
}

function renderOnboarding(data, needsApi) {
  const steps = [
    { page: 'vocab',   icon: '🃏', label: 'Add a word to your vocab deck',    done: (data.srs_total || 0) > 0 },
    { page: 'grammar', icon: '✏️', label: 'Complete a grammar drill',          done: false },
    { page: 'reading', icon: '📖', label: 'Read a passage',                    done: false, locked: needsApi },
    { page: 'chat',    icon: '💬', label: 'Have a conversation with your coach', done: false, locked: needsApi },
  ];
  const stepsHtml = steps.map(s => `
    <div class="onboard-step${s.done ? ' onboard-done' : ''}${s.locked ? ' onboard-locked' : ''}" ${!s.done && !s.locked ? `data-page="${s.page}"` : ''}>
      <span class="onboard-check">${s.done ? '✓' : s.locked ? '🔒' : '○'}</span>
      <span>${s.label}</span>
    </div>`).join('');
  return `
    <div id="onboarding-guide" class="card" style="margin-bottom:24px;border-color:var(--accent);padding:20px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h3 style="margin:0;color:var(--accent)">🚀 Getting Started</h3>
        <button class="btn" id="btn-dismiss-onboarding" style="font-size:12px;padding:3px 10px;background:transparent;color:var(--text-dim)">Dismiss</button>
      </div>
      <p style="font-size:13px;color:var(--text-dim);margin-bottom:14px">Complete these steps to get the most out of English Coach.</p>
      <div style="display:flex;flex-direction:column;gap:8px">${stepsHtml}</div>
    </div>`;
}

function planItem(page, icon, label, desc, done, locked) {
  if (locked) {
    return `<div class="plan-item plan-item-locked" data-page="${page}">
      <span style="font-size:20px">${icon}</span>
      <div style="flex:1"><div style="font-weight:600;font-size:14px">${label}</div><div style="font-size:12px;color:var(--text-dim)">${desc}</div></div>
      <span style="font-size:12px;color:var(--text-dim)">🔒</span>
    </div>`;
  }
  return `<div class="plan-item${done ? ' plan-item-done' : ''}" data-page="${page}">
    <span style="font-size:20px">${icon}</span>
    <div style="flex:1"><div style="font-weight:600;font-size:14px">${label}</div><div style="font-size:12px;color:var(--text-dim)">${desc}</div></div>
    <span style="font-size:16px">${done ? '✓' : '›'}</span>
  </div>`;
}

function modeCard(page, icon, label, desc, locked) {
  if (locked) {
    return `<div class="mode-card mode-card-locked" data-page="${page}">
      <span class="lock-badge">🔒</span>
      <div class="icon">${icon}</div>
      <div class="label">${label}</div>
      <div class="desc">${desc}</div>
      <div class="lock-hint">Requires API Key or Cloud License</div>
    </div>`;
  }
  return `<div class="mode-card" data-page="${page}">
    <div class="icon">${icon}</div>
    <div class="label">${label}</div>
    <div class="desc">${desc}</div>
  </div>`;
}
