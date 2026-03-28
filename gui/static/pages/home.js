// pages/home.js — Coach-first dashboard

async function getWithRetry(requestFn, { attempts = 3, delayMs = 350 } = {}) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      return await requestFn();
    } catch (error) {
      lastError = error;
      const msg = String(error?.message || '');
      const retryable = msg.includes('API error 500') || msg.includes('Failed to fetch');
      if (!retryable || attempt === attempts) break;
      await new Promise(resolve => setTimeout(resolve, delayMs));
    }
  }
  throw lastError;
}

export async function render(el) {
  let setupStatus = {};
  let progress = {};
  let coach = {};
  let licStatus = {};

  try {
    const setupPromise = api.get('/api/setup/status');
    const progressPromise = getWithRetry(() => api.get('/api/progress'));
    const coachPromise = api.get('/api/coach/status').catch(() => ({}));
    setupStatus = await setupPromise;
    if (window._currentAbortSignal?.aborted || !el.isConnected) return;
    const licensePromise = (setupStatus.version_mode || 'opensource') === 'cloud'
      ? api.get('/api/license/status').catch(() => ({}))
      : Promise.resolve({});
    [progress, coach, licStatus] = await Promise.all([progressPromise, coachPromise, licensePromise]);
    if (window._currentAbortSignal?.aborted || !el.isConnected) return;
  } catch (e) {
    if (e.name === 'AbortError' || !el.isConnected) return;
    renderError(el, e.message, () => render(el));
    return;
  }

  const runtime = buildRuntime(setupStatus, licStatus);
  if (!setupStatus.has_profile || progress.error === 'no_profile') {
    renderSetupRequired(el, runtime);
    return;
  }

  renderDashboard(el, progress, runtime, coach);
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

function renderDashboard(el, data, runtime, coach) {
  const coachPlan = coach.plan || { tasks: [], summary: {} };
  const coachSummary = coach.coach_summary || data.coach_summary || {};
  const memorySummary = data.memory_summary || {};
  const actionCandidates = coach.action_candidates || coachSummary.action_candidates || [];
  const counts = data.mode_counts || {};
  const streak = data.streak_days || 0;
  const exam = (data.target_exam || 'general').toUpperCase();
  const examDate = data.target_exam_date || '';
  const today = data.today_summary || { sessions: 0, minutes: 0, items: 0 };
  const aiSummary = runtime.cloudActive && !runtime.aiReady
    ? 'Cloud 已激活，但 AI 当前未就绪'
    : runtime.aiMode === 'cloud'
    ? `Cloud AI 已就绪${runtime.licenseDaysLeft ? ` · 剩余 ${runtime.licenseDaysLeft} 天` : ''}`
    : runtime.aiMode === 'self_key'
    ? `自带 Key 模式${runtime.selfKeyBackend ? ` · ${runtime.selfKeyBackend}` : ''}`
    : 'AI 未配置';

  el.innerHTML = `
    <h1>欢迎回来${data.name ? `，${escHtml(data.name)}` : ''}</h1>
    ${renderWarnings(data.warning_codes || [], coach.warning_codes || [], { coachSummary, memorySummary })}
    <p style="margin-bottom:18px">
      CEFR <span class="tag">${escHtml(data.cefr_level || '?')}</span>
      &nbsp;·&nbsp; 目标考试 <span class="tag">${escHtml(exam)}</span>
      ${examDate ? `&nbsp;·&nbsp;<span class="tag">考试日期 ${escHtml(examDate)}</span>` : ''}
      ${streak ? `&nbsp;·&nbsp;<span class="tag tag-yellow">🔥 连续 ${streak} 天</span>` : ''}
    </p>

    <div class="card" style="margin-bottom:18px">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
        <div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:6px">运行状态</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
            <span class="tag">${runtime.versionMode === 'cloud' ? 'Cloud 版本' : 'Open Source 版本'}</span>
            <span class="tag">${escHtml(aiSummary)}</span>
            <span class="tag">${tierLabel(coach.tier || coachSummary.tier || 'free')}</span>
            <span class="tag">${stageLabel(coach.stage || coachSummary.plan_stage || 'growth')}</span>
            ${runtime.cloudActive ? '<span class="tag tag-green">License 已激活</span>' : ''}
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
      <div class="stat-badge"><div class="val">${data.srs_due ?? 0}</div><div class="lbl">今日待复习</div></div>
      <div class="stat-badge"><div class="val">${coachPlan.summary?.completion_rate ?? 0}%</div><div class="lbl">今日计划完成率</div></div>
      <div class="stat-badge"><div class="val">${today.sessions || 0}</div><div class="lbl">今日练习次数</div></div>
      <div class="stat-badge"><div class="val">${today.minutes || 0}</div><div class="lbl">今日学习分钟</div></div>
      <div class="stat-badge"><div class="val">${data.total_study_minutes || 0}</div><div class="lbl">累计学习分钟</div></div>
      <div class="stat-badge"><div class="val">${data.avg_accuracy ?? 0}%</div><div class="lbl">平均正确率</div></div>
    </div>

    ${renderMemoryAndActions(memorySummary, actionCandidates)}
    ${renderCoachPanel(coachPlan, coach, data)}
    ${renderExamProgress(data)}
    ${renderRecentActivity(data.recent_sessions || [])}
    ${renderModeCards(data, runtime, counts)}
  `;

  el.querySelector('#btn-home-setup')?.addEventListener('click', () => navigate('setup'));
  el.querySelector('#btn-home-license')?.addEventListener('click', () => navigate('license'));
  el.querySelectorAll('.plan-item[data-task]').forEach(item => {
    item.addEventListener('click', () => {
      const task = parseTask(item.dataset.task);
      openCoachTask(task);
    });
  });
  el.querySelectorAll('.coach-dismiss[data-event]').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await api.post('/api/coach/dismiss', { event_id: btn.dataset.event }).catch(() => {});
      render(el);
    });
  });
  el.querySelectorAll('.mode-card[data-page]').forEach(card => {
    card.addEventListener('click', () => navigate(card.dataset.page));
  });
}

function hasCoachSummaryData(summary) {
  if (!summary || typeof summary !== 'object') return false;
  return !!(
    summary.today_result_card ||
    summary.today_improved_point ||
    summary.tomorrow_reason ||
    summary.plan_stage ||
    (Array.isArray(summary.action_candidates) && summary.action_candidates.length) ||
    typeof summary.review_due_today === 'number'
  );
}

function hasMemorySummaryData(summary) {
  if (!summary || typeof summary !== 'object') return false;
  return !!(
    typeof summary.review_due_count === 'number' ||
    typeof summary.facts_count === 'number' ||
    typeof summary.known_words === 'number'
  );
}

function renderWarnings(progressWarnings, coachWarnings, availability = {}) {
  let warnings = [...new Set([...(progressWarnings || []), ...(coachWarnings || [])])];
  if (hasCoachSummaryData(availability.coachSummary)) {
    warnings = warnings.filter(item => item !== 'coach_summary_unavailable');
  }
  if (hasMemorySummaryData(availability.memorySummary)) {
    warnings = warnings.filter(item => item !== 'memory_summary_unavailable');
  }
  if (!warnings.length) return '';
  return `
    <div class="alert alert-warn" style="margin-bottom:14px">
      当前部分教练数据已降级显示：${warnings.map(item => escHtml(item)).join(' / ')}
    </div>
  `;
}

function renderMemoryAndActions(memorySummary, actionCandidates) {
  return `
    <div class="card" style="margin:18px 0 24px">
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px">
        <div class="card" style="background:var(--bg2);padding:16px">
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">长期记忆摘要</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
            <span class="tag">Facts ${memorySummary.facts_count || 0}</span>
            <span class="tag">待复习 ${memorySummary.review_due_count || 0}</span>
            <span class="tag">高错词 ${memorySummary.frequent_forgetting_count || 0}</span>
          </div>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.6">
            已知 ${memorySummary.known_words || 0} · 犹豫 ${memorySummary.unsure_words || 0} · 未掌握 ${memorySummary.unknown_words || 0}
          </div>
        </div>
        <div class="card" style="background:var(--bg2);padding:16px">
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">候选下一步</div>
          ${(actionCandidates || []).length
            ? actionCandidates.slice(0, 3).map(item => `
                <div style="padding:8px 0;border-bottom:1px solid var(--border)">
                  <div style="font-size:13px;font-weight:600">${escHtml(item.title)}</div>
                  <div style="font-size:12px;color:var(--text-dim);line-height:1.5">${escHtml(item.reason || '')}</div>
                </div>
              `).join('')
            : '<div style="font-size:13px;color:var(--text-dim)">当前没有额外候选动作。</div>'}
        </div>
      </div>
    </div>
  `;
}

function renderCoachPanel(plan, coach, data) {
  const tasks = plan.tasks || [];
  const summary = plan.summary || {};
  const recentNotifications = coach.recent_notifications || [];
  const nextNotification = coach.next_notification;

  return `
    <div class="card" style="margin:18px 0 24px">
      <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap;margin-bottom:14px">
        <div>
          <h2 style="margin:0 0 6px 0">今天该做什么</h2>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.6">${escHtml(summary.if_skip || '系统会根据复习到期、弱项和考试目标给出每天最该做的事。')}</div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <span class="tag">完成 ${summary.tasks_done || 0} / ${summary.tasks_total || 0}</span>
          ${nextNotification ? `<span class="tag">下一次提醒 ${formatShortTime(nextNotification.scheduled_for)}</span>` : '<span class="tag">暂无待发提醒</span>'}
        </div>
      </div>

      <div class="daily-loop" style="margin-bottom:14px">
        ${tasks.length
          ? tasks.map(task => planItem(task)).join('')
          : '<div class="alert alert-info">今天还没有生成 coach 计划，先去做一次练习，系统会开始跟踪你的节奏。</div>'}
      </div>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:14px">
        <div class="card" style="background:var(--bg2);padding:16px">
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:6px">这次做了什么</div>
          <div style="font-size:14px;line-height:1.7">${escHtml(summary.result_card || '完成任意一个任务后，这里会显示当天结果感。')}</div>
        </div>
        <div class="card" style="background:var(--bg2);padding:16px">
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:6px">哪一点进步了</div>
          <div style="font-size:14px;line-height:1.7">${escHtml(summary.improved_point || '完成一次训练后，这里会显示今天最值得保留的进步。')}</div>
        </div>
        <div class="card" style="background:var(--bg2);padding:16px">
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:6px">明天为什么还要回来</div>
          <div style="font-size:14px;line-height:1.7">${escHtml(summary.tomorrow_reason || '明天系统会根据你今天的完成情况自动刷新下一步。')}</div>
        </div>
      </div>

      ${coach.catch_up ? `<div class="alert alert-warn" style="margin-bottom:14px">${escHtml(coach.catch_up)}</div>` : ''}

      <div class="card" style="background:var(--bg2);padding:16px">
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:8px">
          <strong>最近提醒</strong>
          <span style="font-size:12px;color:var(--text-dim)">提醒不会超过必要频率</span>
        </div>
        ${recentNotifications.length
          ? recentNotifications.slice(0, 4).map(item => `
              <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding:10px 0;border-bottom:1px solid var(--border)">
                <div>
                  <div style="font-size:13px;font-weight:600">${escHtml(item.title)}</div>
                  <div style="font-size:12px;color:var(--text-dim);line-height:1.5">${escHtml(item.body || '')}</div>
                  <div style="font-size:11px;color:var(--text-dim);margin-top:4px">${escHtml(item.channel)} · ${item.state === 'sent' ? '已发送' : item.state}</div>
                </div>
                <button class="btn btn-outline coach-dismiss" data-event="${item.event_id}" style="font-size:12px;padding:3px 10px">隐藏</button>
              </div>
            `).join('')
          : '<div style="font-size:13px;color:var(--text-dim)">提醒中心还没有记录。启用提醒并运行应用后，这里会显示最近的督促记录。</div>'}
      </div>
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
      ${rows.map(progressRow).join('')}
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
        ? recentSessions.map(recentRow).join('')
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
      ${cards.map(([page, icon, label, desc]) => `
        <div class="mode-card" data-page="${page}">
          <div class="icon">${icon}</div>
          <div class="label">${label}</div>
          <div class="desc">${desc}</div>
        </div>
      `).join('')}
    </div>
  `;
}

function planItem(task) {
  return `
    <div class="plan-item" data-task="${escAttr(JSON.stringify(task))}">
      <span style="font-size:20px">${categoryIcon(task.category)}</span>
      <div style="flex:1">
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <div style="font-weight:600;font-size:14px">${escHtml(task.title)}</div>
          <span class="tag">${categoryLabel(task.category)}</span>
          <span class="tag">${stateLabel(task.state)}</span>
        </div>
        <div style="font-size:12px;color:var(--text-dim);margin-top:4px">${escHtml(task.reason || task.description || '')}</div>
        <div style="font-size:11px;color:var(--text-dim);margin-top:4px">${escHtml(task.risk_text || '')}</div>
      </div>
      <span style="font-size:16px">›</span>
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
  const labelMap = { vocab: '词汇', grammar: '语法', reading: '阅读', listening: '听力', writing: '写作', speaking: '口语', chat: 'Chat', mock: 'Mock Exam' };
  const label = labelMap[item.mode] || item.mode;
  return `
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)">
      <div>
        <div style="font-weight:600">${label}</div>
        <div style="font-size:12px;color:var(--text-dim)">${item.items_done || 0} 项 · ${Math.round((item.duration_sec || 0) / 60)} 分钟</div>
      </div>
      <span class="tag">${item.accuracy || 0}%</span>
    </div>
  `;
}

function openCoachTask(task) {
  if (!task) return;
  sessionStorage.setItem('coach_task_context', JSON.stringify(task));
  if (['reading', 'listening', 'writing', 'speaking'].includes(task.route_page)) {
    sessionStorage.setItem('practice_mode', JSON.stringify({
      section: task.route_page,
      type: task.task_type || null,
      exam: task.exam || 'general',
      started_at: Date.now(),
      source: 'coach_plan',
      task_key: task.task_key || '',
      category: task.category || '',
    }));
    navigate(task.route_page);
    return;
  }
  navigate(task.route_page || 'practice');
}

function parseTask(value) {
  try { return JSON.parse(value); } catch { return null; }
}

function tierLabel(tier) {
  return { free: '免费教练', self_key: '自带 Key 教练', premium: '商业版教练' }[tier] || tier;
}

function stageLabel(stage) {
  return { core: 'Core 阶段', growth: 'Growth 阶段', sprint: 'Sprint 阶段' }[stage] || stage;
}

function categoryLabel(category) {
  return {
    core: '核心内容',
    growth: '成长内容',
    sprint: '冲刺内容',
    ai_enhanced: 'AI 增强',
  }[category] || category;
}

function categoryIcon(category) {
  return { core: '✅', growth: '📈', sprint: '⏱', ai_enhanced: '🤖' }[category] || '•';
}

function stateLabel(state) {
  return { done: '已完成', in_progress: '进行中', pending: '待完成' }[state] || '待完成';
}

function runtimeLine(runtime) {
  if (runtime.cloudActive && !runtime.aiReady) {
    return '当前 Cloud License 记录仍在，但内置 AI 尚未恢复。建议先检查 License 状态，必要时重新激活。';
  }
  if (runtime.needsReactivation) {
    return '当前 Cloud License 记录需要重新激活后，内置 AI 才能恢复稳定可用。';
  }
  if (runtime.aiMode === 'cloud') {
    return runtime.serverVerified === false
      ? '当前使用本地 Cloud License 恢复 AI；最近一次服务器校验未完成，但本地记录仍可工作。'
      : '当前优先使用 Cloud 激活后的内置 AI 配置。';
  }
  if (runtime.aiMode === 'self_key') {
    return '当前使用你自己的 API Key。Cloud 激活不会影响本地离线数据。';
  }
  if (runtime.versionMode === 'cloud' && runtime.activationAvailable) {
    return '当前未配置 AI。你可以去 Setup 配置自己的 API Key，或去 License 页面激活 Cloud 许可。';
  }
  return '当前未配置 AI，但 Vocabulary / Grammar / Reading / Listening 的离线主路径仍可继续使用。';
}

function formatShortTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function escAttr(value) {
  return escHtml(value).replace(/"/g, '&quot;');
}

function escHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
