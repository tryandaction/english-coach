// pages/home.js — Dashboard

export async function render(el) {
  let setupStatus = {};
  let data = {};
  let licStatus = {};

  try {
    setupStatus = await api.get('/api/setup/status');
    if (window._currentAbortSignal?.aborted || !el.isConnected) return;
  } catch (e) {
    if (e.name === 'AbortError' || !el.isConnected) return;
  }

  try {
    data = await api.get('/api/progress');
    if (window._currentAbortSignal?.aborted || !el.isConnected) return;
  } catch (e) {
    if (e.name === 'AbortError' || !el.isConnected) return;
  }

  if ((setupStatus.version_mode || 'opensource') === 'cloud') {
    try {
      licStatus = await api.get('/api/license/status');
      if (window._currentAbortSignal?.aborted || !el.isConnected) return;
    } catch (e) {
      if (e.name === 'AbortError' || !el.isConnected) return;
    }
  }

  const runtime = buildRuntime(setupStatus, licStatus);
  if (!setupStatus.has_profile || data.error === 'no_profile') {
    renderSetupRequired(el, runtime);
    return;
  }

  renderDashboard(el, data, runtime);
}

function buildRuntime(setupStatus, licStatus) {
  const versionMode = setupStatus.version_mode || 'opensource';
  const cloudActive = !!(setupStatus.cloud_license_active || licStatus.active);
  const activationAvailable = !!(setupStatus.activation_available || licStatus.activation_available);
  const aiMode = setupStatus.ai_mode || licStatus.ai_mode || 'none';
  const aiReady = !!(setupStatus.ai_ready || licStatus.ai_ready);
  const selfKeyBackend = setupStatus.self_key_backend || licStatus.self_key_backend || '';
  const licenseDaysLeft = setupStatus.license_days_left ?? licStatus.days_left ?? 0;
  const verificationWarning = setupStatus.verification_warning || licStatus.verification_warning || '';

  return {
    versionMode,
    cloudActive,
    activationAvailable,
    aiMode,
    aiReady,
    selfKeyBackend,
    licenseDaysLeft,
    needsReactivation: !!(setupStatus.needs_reactivation || licStatus.needs_reactivation),
    activationReason: setupStatus.activation_reason || licStatus.activation_reason || '',
    serverVerified: licStatus.server_verified ?? setupStatus.server_verified,
    verificationWarning,
  };
}

function renderSetupRequired(el, runtime) {
  const aiLine = runtime.versionMode === 'cloud'
    ? runtime.activationAvailable
      ? 'Cloud 版可通过激活码启用内置 AI，也可以直接配置你自己的 API Key。'
      : '当前 Cloud 构建未配置激活服务；你仍可先配置自己的 API Key，或先使用离线能力。'
    : '先完成基础设置；如果要使用 AI 功能，再配置你自己的 API Key。';

  el.innerHTML = `
    <div class="card" style="max-width:760px;margin:0 auto;padding:28px">
      <div style="font-size:46px;margin-bottom:14px">🚀</div>
      <h1 style="margin-bottom:8px">先完成设置，再开始学习</h1>
      <p style="color:var(--text-dim);margin-bottom:20px;line-height:1.7">
        当前还没有学习档案，所以首页、进度和学习记录都不会生效。完成 Setup 后，应用才能正确保存你的学习数据、Cloud 激活状态和 AI 配置。
      </p>
      <div class="card" style="background:var(--bg2);padding:16px;margin-bottom:20px">
        <div style="font-size:13px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">当前状态</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
          <span class="tag">学习档案未创建</span>
          <span class="tag">${runtime.versionMode === 'cloud' ? 'Cloud 版本' : 'Open Source 版本'}</span>
          <span class="tag">${runtime.aiMode === 'none' ? 'AI 未就绪' : `AI 模式 ${escHtml(runtime.aiMode)}`}</span>
        </div>
        <div style="font-size:13px;color:var(--text-dim);line-height:1.7">${escHtml(aiLine)}</div>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn btn-primary" id="btn-go-setup">前往 Setup</button>
        ${runtime.versionMode === 'cloud' && runtime.activationAvailable ? '<button class="btn btn-outline" id="btn-go-license">查看 License</button>' : ''}
      </div>
    </div>
  `;

  el.querySelector('#btn-go-setup')?.addEventListener('click', () => navigate('setup'));
  el.querySelector('#btn-go-license')?.addEventListener('click', () => navigate('license'));
}

function renderDashboard(el, data, runtime) {
  const counts = data.mode_counts || {};
  const cefr = data.cefr_level || '?';
  const streak = data.streak_days || 0;
  const due = data.srs_due ?? 0;
  const sessions = data.total_sessions || 0;
  const exam = (data.target_exam || 'general').toUpperCase();
  const today = data.today_summary || { sessions: 0, minutes: 0, items: 0 };
  const recentSessions = data.recent_sessions || [];
  const onboardingDone = localStorage.getItem('onboarding_done') === '1';
  const isNew = sessions < 3;
  const aiSummary = runtime.cloudActive && !runtime.aiReady
    ? 'Cloud 已激活，但 AI 当前未就绪'
    : runtime.aiMode === 'cloud'
    ? `Cloud AI 已就绪${runtime.licenseDaysLeft ? ` · 剩余 ${runtime.licenseDaysLeft} 天` : ''}`
    : runtime.aiMode === 'self_key'
    ? `自带 Key 模式${runtime.selfKeyBackend ? ` · ${runtime.selfKeyBackend}` : ''}`
    : 'AI 未配置';

  el.innerHTML = `
    <h1>欢迎回来${data.name ? `，${escHtml(data.name)}` : ''}</h1>
    <p style="margin-bottom:18px">
      CEFR <span class="tag">${cefr}</span>
      &nbsp;·&nbsp; 目标考试 <span class="tag">${exam}</span>
      ${streak ? `&nbsp;·&nbsp;<span class="tag tag-yellow">🔥 连续 ${streak} 天</span>` : ''}
    </p>

    <div class="card" style="margin-bottom:18px">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
        <div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:6px">运行状态</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
            <span class="tag">${runtime.versionMode === 'cloud' ? 'Cloud 版本' : 'Open Source 版本'}</span>
            <span class="tag">${escHtml(aiSummary)}</span>
            ${runtime.cloudActive ? '<span class="tag tag-green">License 已激活</span>' : ''}
            ${runtime.needsReactivation ? '<span class="tag" style="color:var(--red)">需要重新激活</span>' : ''}
          </div>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.7">${escHtml(runtimeLine(runtime))}</div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn btn-outline" id="btn-home-setup">Setup</button>
          ${runtime.versionMode === 'cloud' ? '<button class="btn btn-outline" id="btn-home-license">License</button>' : ''}
        </div>
      </div>
      ${runtime.verificationWarning ? `<div class="alert alert-info" style="margin-top:12px">${escHtml(runtime.verificationWarning)}</div>` : ''}
    </div>

    <div class="stats-row">
      <div class="stat-badge"><div class="val">${due}</div><div class="lbl">今日待复习</div></div>
      <div class="stat-badge"><div class="val">${data.srs_total ?? 0}</div><div class="lbl">累计词汇</div></div>
      <div class="stat-badge"><div class="val">${today.sessions || 0}</div><div class="lbl">今日练习次数</div></div>
      <div class="stat-badge"><div class="val">${data.total_study_minutes || 0}</div><div class="lbl">累计学习分钟</div></div>
      <div class="stat-badge"><div class="val">${data.learning_days || 0}</div><div class="lbl">累计学习天数</div></div>
      <div class="stat-badge"><div class="val">${data.avg_accuracy ?? 0}%</div><div class="lbl">平均正确率</div></div>
    </div>

    ${isNew && !onboardingDone ? renderOnboarding(data, runtime) : ''}
    ${renderTodayPlan(data, runtime)}
    ${renderExamProgress(data)}
    ${renderRecentActivity(recentSessions)}
    ${renderModeCards(data, runtime, counts)}
  `;

  el.querySelector('#btn-home-setup')?.addEventListener('click', () => navigate('setup'));
  el.querySelector('#btn-home-license')?.addEventListener('click', () => navigate('license'));
  el.querySelectorAll('.plan-item[data-page]').forEach(item => {
    item.addEventListener('click', () => navigate(item.dataset.page));
  });
  el.querySelectorAll('.mode-card[data-page]').forEach(card => {
    card.addEventListener('click', () => navigate(card.dataset.page));
  });
  el.querySelector('#btn-dismiss-onboarding')?.addEventListener('click', () => {
    localStorage.setItem('onboarding_done', '1');
    el.querySelector('#onboarding-guide')?.remove();
  });
  el.querySelectorAll('.onboard-step[data-page]').forEach(step => {
    step.addEventListener('click', () => navigate(step.dataset.page));
  });
}

function runtimeLine(runtime) {
  if (runtime.cloudActive && !runtime.aiReady) {
    return '当前 Cloud License 记录仍在，但内置 AI 尚未恢复。建议先检查 License 状态，必要时重新激活。';
  }
  if (runtime.needsReactivation) {
    return '当前 Cloud License 记录需要重新激活后，内置 AI 才能恢复稳定可用。';
  }
  if (runtime.aiMode === 'cloud') {
    if (runtime.serverVerified === false) {
      return '当前使用本地 Cloud License 恢复 AI；最近一次服务器校验未完成，但本地记录仍可工作。';
    }
    return '当前优先使用 Cloud 激活后的内置 AI 配置。';
  }
  if (runtime.aiMode === 'self_key') {
    return '当前使用你自己的 API Key。Cloud 激活不会影响本地离线数据。';
  }
  if (runtime.versionMode === 'cloud' && runtime.activationAvailable) {
    return '当前未配置 AI。你可以去 Setup 配置自己的 API Key，或去 License 页面激活 Cloud 许可。';
  }
  return '当前未配置 AI，但 Vocabulary / Grammar / Reading / Listening 的离线主路径仍可继续使用。';
}

function renderTodayPlan(data, runtime) {
  const counts = data.mode_counts || {};
  const weakAreas = data.weak_areas || [];
  const items = [];

  if ((data.srs_due || 0) > 0) {
    items.push({
      page: 'vocab',
      icon: '🃏',
      title: '先清今天的词汇复习',
      desc: `还有 ${data.srs_due} 张卡片待复习，这是最稳的今日起点。`,
    });
  }

  if (!items.length && (counts.reading || 0) === 0) {
    items.push({
      page: 'reading',
      icon: '📖',
      title: '做一篇阅读，建立今天的进度',
      desc: '阅读页支持离线题库与 fallback，不依赖 AI 也能直接开始。',
    });
  }

  if (weakAreas.some(item => item.startsWith('grammar'))) {
    items.push({
      page: 'grammar',
      icon: '✏️',
      title: '补一下语法短板',
      desc: '你最近的薄弱项集中在语法，适合先做短练习拉回正确率。',
    });
  } else if (weakAreas.some(item => item.startsWith('reading'))) {
    items.push({
      page: 'reading',
      icon: '📖',
      title: '强化阅读理解',
      desc: '最近阅读相关分项偏弱，建议做一轮定向训练。',
    });
  }

  if (!runtime.aiReady) {
    items.push({
      page: runtime.versionMode === 'cloud' && runtime.activationAvailable ? 'license' : 'setup',
      icon: runtime.versionMode === 'cloud' ? '☁' : '⚙️',
      title: runtime.versionMode === 'cloud' && runtime.activationAvailable ? '补齐 AI 能力' : '配置 AI',
      desc: runtime.versionMode === 'cloud' && runtime.activationAvailable
        ? '激活 Cloud License 或配置自带 Key 后，Chat / 写作 / 口语反馈会更完整。'
        : '配置自带 Key 后可启用 Chat、写作反馈和口语评分。',
    });
  } else if ((counts.writing || 0) === 0) {
    items.push({
      page: 'writing',
      icon: '📝',
      title: '完成一次带反馈的写作',
      desc: '你当前 AI 已就绪，建议利用反馈闭环积累可见成果。',
    });
  }

  if (!items.length) {
    items.push({
      page: 'practice',
      icon: '🎯',
      title: '进入专项训练',
      desc: '今天的基础任务已清完，可以按考试题型做更有针对性的练习。',
    });
  }

  return `
    <div style="display:flex;align-items:center;justify-content:space-between;margin:18px 0 12px">
      <h2 style="margin:0">今天该做什么</h2>
      <span style="font-size:12px;color:var(--text-dim)">系统基于你的进度自动建议</span>
    </div>
    <div class="daily-loop" style="margin-bottom:24px">
      ${items.slice(0, 4).map(item => planItem(item.page, item.icon, item.title, item.desc)).join('')}
    </div>
  `;
}

function renderExamProgress(data) {
  const examKey = (data.target_exam || 'general').toLowerCase();
  const examUpper = examKey.toUpperCase();
  const scores = data.skill_scores || {};
  const counts = data.mode_counts || {};

  const vocabTotal = data.srs_total || 0;
  const vocabTargets = { toefl: 570, gre: 500, ielts: 500, cet: 600, general: 300 };
  const vocabTarget = vocabTargets[examKey] || 300;
  const vocabPct = Math.min(100, Math.round(vocabTotal / Math.max(vocabTarget, 1) * 100));

  const grammarKeys = Object.keys(scores).filter(k => k.startsWith('grammar'));
  const grammarAvg = grammarKeys.length
    ? Math.round(grammarKeys.reduce((sum, key) => sum + (scores[key] || 0), 0) / grammarKeys.length * 100)
    : 0;

  const rows = [
    { label: 'Vocabulary', pct: vocabPct, detail: `${vocabTotal} / ${vocabTarget} words` },
    { label: 'Grammar', pct: grammarAvg, detail: grammarAvg ? `${grammarAvg}% accuracy` : '尚未形成稳定记录' },
    { label: 'Reading', pct: Math.min(100, (counts.reading || 0) * 12), detail: counts.reading ? `${counts.reading} 次训练` : '尚未开始' },
    { label: 'Listening', pct: Math.min(100, (counts.listening || 0) * 12), detail: counts.listening ? `${counts.listening} 次训练` : '尚未开始' },
    { label: 'Writing', pct: Math.min(100, (counts.writing || 0) * 18), detail: counts.writing ? `${counts.writing} 次反馈` : '尚未开始' },
  ];

  return `
    <div class="card" style="margin-bottom:24px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <span class="exam-badge exam-${examKey}">${examUpper}</span>
        <h3 style="margin:0">考试准备进度</h3>
      </div>
      ${rows.map(row => progressRow(row)).join('')}
    </div>
  `;
}

function renderRecentActivity(recentSessions) {
  return `
    <div class="card" style="margin-bottom:24px">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px">
        <h3 style="margin:0">最近完成的训练</h3>
        <button class="btn btn-outline" onclick="navigate('history')" style="font-size:12px;padding:5px 12px">查看 History</button>
      </div>
      ${recentSessions.length
        ? recentSessions.map(item => recentRow(item)).join('')
        : '<div style="font-size:13px;color:var(--text-dim)">还没有已完成训练记录。完成任意一次练习后，这里会显示最近成果。</div>'}
    </div>
  `;
}

function renderModeCards(data, runtime, counts) {
  const aiLocked = !runtime.aiReady;
  const cards = [
    ['practice', '🎯', 'Practice', '按题型进入专项训练'],
    ['mock-exam', '⏱', 'Mock Exam', '连续完成多 section 流程'],
    ['vocab', '🃏', 'Vocabulary', `${data.srs_due || 0} 张今日待复习`],
    ['grammar', '✏️', 'Grammar', '短练习，适合快速拉回正确率'],
    ['reading', '📖', 'Reading', '离线可练，AI 仅用于增强'],
    ['listening', '🎧', 'Listening', counts.listening ? `已完成 ${counts.listening} 次` : '内置内容可直接开始'],
    ['speaking', '🗣', 'Speaking', aiLocked ? '可练题面，评分需 AI' : '题面与评分都已就绪'],
    ['writing', '📝', 'Writing', aiLocked ? '可练题面，反馈需 AI' : '题面与反馈都已就绪'],
    ['progress', '📊', 'Progress', '查看累计成果与弱项'],
  ];

  return `
    <h2>全部功能</h2>
    <div class="card-grid">
      ${cards.map(([page, icon, label, desc]) => modeCard(page, icon, label, desc)).join('')}
    </div>
  `;
}

function renderOnboarding(data, runtime) {
  const counts = data.mode_counts || {};
  const steps = [
    { page: 'vocab', icon: '🃏', label: '加入第一批词汇并完成一次复习', done: (data.srs_total || 0) > 0 },
    { page: 'grammar', icon: '✏️', label: '完成一次语法练习', done: (counts.grammar || 0) > 0 },
    { page: 'reading', icon: '📖', label: '完成一篇阅读', done: (counts.reading || 0) > 0 },
    { page: runtime.aiReady ? 'writing' : 'setup', icon: runtime.aiReady ? '📝' : '⚙️', label: runtime.aiReady ? '做一次带反馈的写作' : '补齐 AI 配置', done: runtime.aiReady ? (counts.writing || 0) > 0 : false, locked: false },
  ];

  return `
    <div id="onboarding-guide" class="card" style="margin-bottom:24px;border-color:var(--accent);padding:20px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h3 style="margin:0;color:var(--accent)">新用户建议路径</h3>
        <button class="btn" id="btn-dismiss-onboarding" style="font-size:12px;padding:3px 10px;background:transparent;color:var(--text-dim)">关闭</button>
      </div>
      <p style="font-size:13px;color:var(--text-dim);margin-bottom:14px">先跑完这几步，你会更容易看到真实进度与 AI 能力差异。</p>
      <div style="display:flex;flex-direction:column;gap:8px">
        ${steps.map(step => `
          <div class="onboard-step${step.done ? ' onboard-done' : ''}${step.locked ? ' onboard-locked' : ''}" ${!step.done && !step.locked ? `data-page="${step.page}"` : ''}>
            <span class="onboard-check">${step.done ? '✓' : step.locked ? '🔒' : '○'}</span>
            <span>${step.label}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function progressRow(row) {
  const color = row.pct >= 70 ? 'var(--green)' : row.pct >= 40 ? 'var(--accent)' : 'var(--text-dim)';
  return `
    <div style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px">
        <span>${row.label}</span>
        <span style="color:var(--text-dim)">${row.detail}</span>
      </div>
      <div style="height:6px;background:var(--bg3);border-radius:3px;overflow:hidden">
        <div style="height:100%;width:${row.pct}%;background:${color};border-radius:3px;transition:width 0.4s"></div>
      </div>
    </div>
  `;
}

function recentRow(item) {
  const labelMap = {
    vocab: '词汇',
    grammar: '语法',
    reading: '阅读',
    listening: '听力',
    writing: '写作',
    speaking: '口语',
    chat: 'Chat',
    mock: 'Mock Exam',
  };
  const label = labelMap[item.mode] || item.mode;
  return `
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)">
      <div>
        <div style="font-weight:600">${label}</div>
        <div style="font-size:12px;color:var(--text-dim)">
          ${item.items_done || 0} 项 · ${Math.round((item.duration_sec || 0) / 60)} 分钟
        </div>
      </div>
      <span class="tag">${item.accuracy || 0}%</span>
    </div>
  `;
}

function planItem(page, icon, label, desc) {
  return `
    <div class="plan-item" data-page="${page}">
      <span style="font-size:20px">${icon}</span>
      <div style="flex:1">
        <div style="font-weight:600;font-size:14px">${label}</div>
        <div style="font-size:12px;color:var(--text-dim)">${desc}</div>
      </div>
      <span style="font-size:16px">›</span>
    </div>
  `;
}

function modeCard(page, icon, label, desc) {
  return `
    <div class="mode-card" data-page="${page}">
      <div class="icon">${icon}</div>
      <div class="label">${label}</div>
      <div class="desc">${desc}</div>
    </div>
  `;
}

function escHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
