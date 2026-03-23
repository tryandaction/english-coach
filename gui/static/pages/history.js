// pages/history.js — Daily review history

export async function render(el) {
  el.innerHTML = `
    <h1>📋 History</h1>
    <div id="history-list"><div style="text-align:center;padding:40px"><div class="spinner"></div></div></div>
  `;
  await loadDaily(el);
}

async function loadDaily(el) {
  const list = el.querySelector('#history-list');
  try {
    const data = await api.get('/api/history/daily?limit_days=14');
    if (!data.days.length) {
      list.innerHTML = '<div class="alert alert-info">还没有可展示的学习复盘。完成一次训练后，这里会开始按天记录。</div>';
      return;
    }
    list.innerHTML = data.days.map(dayCard).join('');
    list.querySelectorAll('.history-open-task[data-task]').forEach(btn => {
      btn.addEventListener('click', () => {
        const task = parseTask(btn.dataset.task);
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
      });
    });
    list.querySelectorAll('.history-toggle[data-day]').forEach(btn => {
      btn.addEventListener('click', () => {
        const body = list.querySelector(`.history-detail[data-day="${btn.dataset.day}"]`);
        if (!body) return;
        body.style.display = body.style.display === 'none' ? 'block' : 'none';
      });
    });
  } catch (e) {
    renderError(list, e.message, () => loadDaily(el));
  }
}

function dayCard(day) {
  const summary = day.plan?.summary || {};
  const tasks = day.plan?.tasks || [];
  const done = summary.tasks_done || 0;
  const total = summary.tasks_total || 0;
  return `
    <div class="card" style="margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap">
        <div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px">
            <strong>${escHtml(day.day)}</strong>
            <span class="tag">${stageLabel(day.stage)}</span>
            <span class="tag">${statusLabel(day.status)}</span>
            <span class="tag">计划 ${done}/${total}</span>
            <span class="tag">提醒 ${day.notification_count || 0}</span>
          </div>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.6">${escHtml(summary.result_card || '当天完成任意训练后，这里会显示结果感。')}</div>
        </div>
        <button class="btn btn-outline history-toggle" data-day="${day.day}" style="font-size:12px;padding:5px 12px">展开复盘</button>
      </div>

      <div class="history-detail" data-day="${day.day}" style="display:none;margin-top:14px">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:14px">
          <div class="card" style="background:var(--bg2);padding:14px">
            <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">当天任务</div>
            ${tasks.length
              ? tasks.map(task => `
                  <div style="padding:8px 0;border-bottom:1px solid var(--border)">
                    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:4px">
                      <strong style="font-size:13px">${escHtml(task.title)}</strong>
                      <span class="tag">${categoryLabel(task.category)}</span>
                      <span class="tag">${taskStateLabel(task.state)}</span>
                      ${task.route_page ? `<button class="btn btn-outline history-open-task" data-task="${escAttr(JSON.stringify(task))}" style="font-size:11px;padding:3px 8px">再做一次</button>` : ''}
                    </div>
                    <div style="font-size:12px;color:var(--text-dim);line-height:1.5">${escHtml(task.reason || task.description || '')}</div>
                  </div>
                `).join('')
              : '<div style="font-size:13px;color:var(--text-dim)">当天没有生成 coach 计划。</div>'}
          </div>
          <div class="card" style="background:var(--bg2);padding:14px">
            <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">当天结果</div>
            <div style="font-size:13px;color:var(--text-dim);line-height:1.7;margin-bottom:10px">${escHtml(summary.result_card || '')}</div>
            ${summary.improved_point ? `<div style="font-size:13px;color:var(--text-dim);line-height:1.7;margin-bottom:10px">进步点：${escHtml(summary.improved_point)}</div>` : ''}
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <span class="tag">训练 ${summary.today_sessions || 0} 次</span>
              <span class="tag">学习 ${summary.today_minutes || 0} 分钟</span>
              <span class="tag">完成率 ${summary.completion_rate || 0}%</span>
              <span class="tag">剩余复习 ${summary.due_now || 0}</span>
            </div>
            ${summary.tomorrow_reason ? `<div style="font-size:12px;color:var(--text-dim);margin-top:10px">明天理由：${escHtml(summary.tomorrow_reason)}</div>` : ''}
          </div>
        </div>

        <div class="card" style="background:var(--bg2);padding:14px">
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">当天训练明细</div>
          ${day.sessions.length
            ? day.sessions.map(sessionRow).join('')
            : '<div style="font-size:13px;color:var(--text-dim)">当天没有已完成训练。</div>'}
        </div>
      </div>
    </div>
  `;
}

function sessionRow(session) {
  const labelMap = { vocab: '词汇', grammar: '语法', reading: '阅读', listening: '听力', writing: '写作', speaking: '口语', chat: 'Chat', mock: 'Mock Exam' };
  const label = labelMap[session.mode] || session.mode;
  const detail = renderSessionDetail(session.mode, session.content);
  return `
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding:10px 0;border-bottom:1px solid var(--border)">
      <div style="flex:1">
        <div style="font-weight:600">${session.icon || '📋'} ${label}</div>
        <div style="font-size:12px;color:var(--text-dim)">
          ${fmtDate(session.started_at)} · ${session.items_done || 0} 项 · ${Math.round((session.duration_sec || 0) / 60)} 分钟
        </div>
        ${detail}
      </div>
      <span class="tag">${session.accuracy_pct || 0}%</span>
    </div>
  `;
}

function renderSessionDetail(mode, content) {
  if (!content) return '';
  const recap = renderRecap(content);
  if (mode === 'writing' || mode === 'speaking') {
    const preview = mode === 'writing'
      ? (content.essay_preview ? escHtml(String(content.essay_preview).slice(0, 120)) : '')
      : (content.transcript_preview ? escHtml(String(content.transcript_preview).slice(0, 120)) : '');
    const prompt = content.prompt ? escHtml(String(content.prompt).slice(0, 60)) : '';
    return `
      <div style="font-size:12px;color:var(--text-dim);margin-top:6px;line-height:1.5">
        ${recap}
        ${content.task_type ? `<span class="tag">${escHtml(String(content.task_type).replace(/_/g, ' '))}</span> ` : ''}
        ${content.word_count ? `<span class="tag">${content.word_count} words</span> ` : ''}
        ${preview || prompt}${(preview && String(preview).length >= 120) || (content.prompt && String(content.prompt).length > 60) ? '...' : ''}
      </div>
    `;
  }
  if (mode === 'reading') {
    return `
      <div style="font-size:12px;color:var(--text-dim);margin-top:6px;line-height:1.5">
        ${recap}
        ${content.topic ? `<span class="tag">${escHtml(content.topic)}</span> ` : ''}
        ${Array.isArray(content.question_types) ? content.question_types.slice(0, 2).map(type => `<span class="tag">${escHtml(String(type).replace(/_/g, ' '))}</span>`).join(' ') : ''}
        ${content.passage_preview ? `<div style="margin-top:4px">${escHtml(String(content.passage_preview).slice(0, 120))}${String(content.passage_preview).length > 120 ? '...' : ''}</div>` : ''}
      </div>
    `;
  }
  if (mode === 'listening') {
    return `
      <div style="font-size:12px;color:var(--text-dim);margin-top:6px;line-height:1.5">
        ${recap}
        ${content.topic ? `<span class="tag">${escHtml(content.topic)}</span> ` : ''}
        ${content.dialogue_type ? `<span class="tag">${escHtml(content.dialogue_type)}</span> ` : ''}
        ${content.question_type ? `<span class="tag">${escHtml(content.question_type)}</span> ` : ''}
        ${content.question_count ? `<span class="tag">${content.correct || 0}/${content.question_count}</span>` : ''}
      </div>
    `;
  }
  return recap;
}

function renderRecap(content) {
  const headline = content?.result_headline || content?.result_card || '';
  const improved = content?.improved_point || '';
  const nextStep = content?.next_step || content?.tomorrow_reason || '';
  if (!headline && !improved && !nextStep) return '';
  return `
    ${headline ? `<div style="margin-bottom:4px;color:var(--text)">${escHtml(headline)}</div>` : ''}
    ${improved ? `<div style="margin-bottom:4px">进步点：${escHtml(improved)}</div>` : ''}
    ${nextStep ? `<div style="margin-bottom:6px">下一步：${escHtml(nextStep)}</div>` : ''}
  `;
}

function statusLabel(status) {
  return { planned: '未完成', in_progress: '进行中', done: '已完成', expired: '已过期' }[status] || status;
}

function stageLabel(stage) {
  return { core: 'Core', growth: 'Growth', sprint: 'Sprint' }[stage] || stage;
}

function categoryLabel(category) {
  return { core: '核心', growth: '成长', sprint: '冲刺', ai_enhanced: 'AI 增强' }[category] || category;
}

function taskStateLabel(state) {
  return { done: '已完成', in_progress: '进行中', pending: '待完成' }[state] || '待完成';
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function parseTask(value) {
  try { return JSON.parse(value); } catch { return null; }
}

function escAttr(value) {
  return escHtml(value).replace(/"/g, '&quot;');
}

function escHtml(value) {
  return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
