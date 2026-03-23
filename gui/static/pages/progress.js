// pages/progress.js — Progress dashboard with coach metrics

export async function render(el) {
  el.innerHTML = `
    <h1>📊 学习进度</h1>
    <div id="progress-body"><div style="text-align:center;padding:40px"><div class="spinner"></div></div></div>
  `;

  try {
    const [data, coach] = await Promise.all([
      api.get('/api/progress'),
      api.get('/api/coach/status').catch(() => ({})),
    ]);
    if (window._currentAbortSignal?.aborted || !el.isConnected) return;
    if (!data.has_profile || data.error === 'no_profile') {
      renderEmptyState(el);
      return;
    }
    renderDashboard(el, data, coach);
  } catch (e) {
    if (e.name === 'AbortError' || !el.isConnected) return;
    const body = el.querySelector('#progress-body');
    if (body) body.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

function renderEmptyState(el) {
  const body = el.querySelector('#progress-body');
  body.innerHTML = `
    <div class="card" style="padding:28px;max-width:760px">
      <div style="font-size:42px;margin-bottom:12px">🧭</div>
      <h2 style="margin-bottom:8px">还没有可展示的学习进度</h2>
      <p style="color:var(--text-dim);margin-bottom:18px;line-height:1.7">
        当前还没有用户档案或已完成训练记录。完成 Setup 并做一次 Vocabulary / Reading / Listening / Writing / Speaking 练习后，这里会开始显示连续学习、正确率和弱项趋势。
      </p>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn btn-primary" id="btn-progress-setup">前往 Setup</button>
        <button class="btn btn-outline" id="btn-progress-home">返回 Home</button>
      </div>
    </div>
  `;
  body.querySelector('#btn-progress-setup')?.addEventListener('click', () => navigate('setup'));
  body.querySelector('#btn-progress-home')?.addEventListener('click', () => navigate('home'));
}

function renderDashboard(el, d, coach) {
  const body = el.querySelector('#progress-body');
  const coachSummary = d.coach_summary || coach.coach_summary || {};
  const today = d.today_summary || { sessions: 0, minutes: 0, items: 0 };
  const weakAreas = d.weak_areas || [];

  body.innerHTML = `
    <div class="stats-row">
      <div class="stat-badge"><div class="val">${d.cefr_level || '?'}</div><div class="lbl">当前 CEFR</div></div>
      <div class="stat-badge"><div class="val">${d.streak_days ? `🔥 ${d.streak_days}` : '0'}</div><div class="lbl">连续天数</div></div>
      <div class="stat-badge"><div class="val">${d.total_sessions || 0}</div><div class="lbl">累计训练次数</div></div>
      <div class="stat-badge"><div class="val">${d.avg_accuracy || 0}%</div><div class="lbl">平均正确率</div></div>
      <div class="stat-badge"><div class="val">${coachSummary.plan_completion_rate_7d || 0}%</div><div class="lbl">7 日计划完成率</div></div>
      <div class="stat-badge"><div class="val">${coachSummary.study_consistency_7d || 0}%</div><div class="lbl">7 日稳定度</div></div>
    </div>

    <div class="card" style="margin-bottom:20px">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
        <div>
          <h3 style="margin:0 0 8px 0">监督型指标</h3>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <span class="tag">今日待复习 ${coachSummary.review_due_today ?? d.srs_due ?? 0}</span>
            <span class="tag">今日 ${today.sessions || 0} 次训练</span>
            <span class="tag">今日 ${today.minutes || 0} 分钟</span>
            <span class="tag">阶段 ${coachSummary.plan_stage || 'growth'}</span>
          </div>
        </div>
        <div style="min-width:220px">
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">这次做了什么</div>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.6">${escHtml(coachSummary.today_result_card || '完成今日计划后，这里会显示结果感。')}</div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin:12px 0 8px">哪一点进步了</div>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.6">${escHtml(coachSummary.today_improved_point || '完成一次训练后，这里会显示最值得复用的进步。')}</div>
        </div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
      <div class="card">
        <h3>技能雷达</h3>
        <div class="chart-wrap"><canvas id="radar-chart"></canvas></div>
      </div>
      <div class="card">
        <h3>近 14 天练习频次</h3>
        <div class="chart-wrap"><canvas id="bar-chart"></canvas></div>
      </div>
    </div>

    <div class="card" style="margin-bottom:20px">
      <h3 style="margin-bottom:8px">复习债务趋势</h3>
      ${renderDueTrend(coachSummary.review_due_trend || [])}
    </div>

    <div class="card" style="margin-bottom:20px">
      <h3 style="margin-bottom:8px">弱项修复进展</h3>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
        ${(coachSummary.weak_area_progress?.current || weakAreas).length
          ? (coachSummary.weak_area_progress?.current || weakAreas).map(item => `<span class="tag">${escHtml(item)}</span>`).join('')
          : '<span class="tag">暂无明显弱项</span>'}
      </div>
      <div style="font-size:13px;color:var(--text-dim)">
        ${coachSummary.weak_area_progress?.today_focused
          ? '今天已经针对弱项做了修复动作，建议保持这个节奏。'
          : '今天还没有命中弱项修复，建议优先完成系统推荐任务。'}
      </div>
    </div>

    <div class="card" style="margin-bottom:20px">
      <h3 style="margin-bottom:8px">下一步建议</h3>
      ${renderRecommendations(d, coachSummary, weakAreas)}
    </div>

    <div class="card" style="margin-bottom:20px">
      <h3 style="margin-bottom:8px">最近完成的训练</h3>
      ${(d.recent_sessions || []).length
        ? d.recent_sessions.map(recentRow).join('')
        : '<div style="font-size:13px;color:var(--text-dim)">最近还没有可展示的已完成训练。</div>'}
    </div>

    <div class="card">
      <h3>技能分数</h3>
      <div id="skill-table"></div>
    </div>
  `;

  renderCharts(d);
  renderSkillTable(body.querySelector('#skill-table'), d.skill_scores || {});
  body.querySelectorAll('.progress-next[data-page]').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.page));
  });
}

function renderCharts(d) {
  const skills = d.skill_scores || {};
  const labels = Object.keys(skills).map(k => k.replace(/_/g, ' '));
  const values = Object.values(skills).map(v => Math.round(v * 100));
  const radarLabels = labels.length ? labels : ['no data'];
  const radarValues = values.length ? values : [0];

  new Chart(document.getElementById('radar-chart'), {
    type: 'radar',
    data: {
      labels: radarLabels,
      datasets: [{
        label: 'Score %',
        data: radarValues,
        backgroundColor: 'rgba(79,142,247,0.15)',
        borderColor: '#4f8ef7',
        pointBackgroundColor: '#4f8ef7',
        pointRadius: 3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          min: 0,
          max: 100,
          ticks: { color: '#7b82a8', stepSize: 25, font: { size: 10 } },
          grid: { color: '#2e3250' },
          pointLabels: { color: '#e8eaf6', font: { size: 10 } },
          angleLines: { color: '#2e3250' },
        },
      },
      plugins: { legend: { display: false } },
    },
  });

  const history = d.history || [];
  const last14 = getLast14Days();
  const histMap = {};
  history.forEach(item => { histMap[item.day] = item.sessions; });
  const barData = last14.map(day => histMap[day] || 0);

  new Chart(document.getElementById('bar-chart'), {
    type: 'bar',
    data: {
      labels: last14.map(day => day.slice(5)),
      datasets: [{
        label: 'Sessions',
        data: barData,
        backgroundColor: barData.map(value => value > 0 ? '#4f8ef7' : '#2e3250'),
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: '#7b82a8', font: { size: 10 } }, grid: { color: '#2e3250' } },
        y: { ticks: { color: '#7b82a8', stepSize: 1 }, grid: { color: '#2e3250' }, min: 0 },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function renderSkillTable(container, skills) {
  const entries = Object.entries(skills).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    container.innerHTML = '<div style="font-size:13px;color:var(--text-dim)">还没有足够的样本来形成技能分数。</div>';
    return;
  }
  container.innerHTML = entries.map(([skill, score]) => {
    const pct = Math.round(score * 100);
    const color = pct >= 75 ? 'var(--green)' : pct >= 55 ? 'var(--yellow)' : 'var(--red)';
    const filled = Math.round(pct / 10);
    const bar = '█'.repeat(filled) + '░'.repeat(10 - filled);
    return `
      <div style="display:flex;align-items:center;gap:12px;padding:6px 0;border-bottom:1px solid var(--border)">
        <span style="flex:1;font-size:13px">${skill.replace(/_/g, ' ')}</span>
        <span style="color:${color};font-weight:600;width:40px;text-align:right">${pct}%</span>
        <span style="color:${color};font-family:monospace;font-size:12px">${bar}</span>
      </div>
    `;
  }).join('');
}

function renderDueTrend(values) {
  if (!values.length) {
    return '<div style="font-size:13px;color:var(--text-dim)">积累更多天的数据后，这里会开始显示复习债务变化。</div>';
  }
  const max = Math.max(...values, 1);
  return `
    <div style="display:flex;gap:10px;align-items:flex-end;height:120px">
      ${values.slice().reverse().map((value, index) => `
        <div style="flex:1;text-align:center">
          <div style="height:${Math.max(12, Math.round(value / max * 100))}px;background:${value > 10 ? 'var(--yellow)' : 'var(--accent)'};border-radius:8px 8px 0 0"></div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:6px">D-${values.length - index - 1}</div>
          <div style="font-size:11px">${value}</div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderRecommendations(d, coachSummary, weakAreas) {
  const items = [];
  if ((d.srs_due || 0) > 0) {
    items.push({ page: 'vocab', text: `先完成今天的 ${d.srs_due} 张词汇复习，最容易形成稳定连续学习。` });
  }
  if ((coachSummary.weak_area_progress?.current || weakAreas).some(item => String(item).startsWith('grammar'))) {
    items.push({ page: 'grammar', text: '语法仍是当前薄弱项，建议先做一次短练习拉回正确率。' });
  } else if ((coachSummary.weak_area_progress?.current || weakAreas).some(item => String(item).startsWith('reading'))) {
    items.push({ page: 'reading', text: '阅读相关分项偏弱，建议做一篇定向阅读训练。' });
  }
  items.push({ page: 'home', text: coachSummary.tomorrow_reason || '先把今天任务做完，明天系统会自动刷新下一步。' });
  return `
    <div style="display:flex;flex-direction:column;gap:10px">
      ${items.slice(0, 4).map(item => `
        <button class="btn btn-outline progress-next" data-page="${item.page}" style="justify-content:flex-start">
          ${item.text}
        </button>
      `).join('')}
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

function getLast14Days() {
  const days = [];
  for (let i = 13; i >= 0; i--) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    days.push(date.toISOString().slice(0, 10));
  }
  return days;
}

function escHtml(value) {
  return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
