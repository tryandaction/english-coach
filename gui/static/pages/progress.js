// pages/progress.js — Progress dashboard with Chart.js charts

export async function render(el) {
  el.innerHTML = `
    <h1>📊 学习进度</h1>
    <div id="progress-body"><div style="text-align:center;padding:40px"><div class="spinner"></div></div></div>
  `;

  try {
    const [data, setup] = await Promise.all([
      api.get('/api/progress'),
      api.get('/api/setup/status').catch(() => ({})),
    ]);
    if (window._currentAbortSignal?.aborted || !el.isConnected) return;
    if (!data.has_profile || data.error === 'no_profile') {
      renderEmptyState(el);
      return;
    }
    renderDashboard(el, data, setup);
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

function renderDashboard(el, d, setup) {
  const body = el.querySelector('#progress-body');
  const streak = d.streak_days || 0;
  const counts = d.mode_counts || {};
  const recentSessions = d.recent_sessions || [];
  const today = d.today_summary || { sessions: 0, minutes: 0, items: 0 };
  const weakAreas = d.weak_areas || [];
  const totalMinutes = d.total_study_minutes || 0;

  body.innerHTML = `
    <div class="stats-row">
      <div class="stat-badge"><div class="val">${d.cefr_level || '?'}</div><div class="lbl">当前 CEFR</div></div>
      <div class="stat-badge"><div class="val" style="color:var(--yellow)">${streak ? `🔥 ${streak}` : '0'}</div><div class="lbl">连续天数</div></div>
      <div class="stat-badge"><div class="val">${d.total_sessions || 0}</div><div class="lbl">累计训练次数</div></div>
      <div class="stat-badge"><div class="val">${d.avg_accuracy || 0}%</div><div class="lbl">平均正确率</div></div>
      <div class="stat-badge"><div class="val">${d.srs_total || 0}</div><div class="lbl">累计词汇</div></div>
      <div class="stat-badge"><div class="val">${totalMinutes}</div><div class="lbl">累计学习分钟</div></div>
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
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
        <div>
          <h3 style="margin:0 0 8px 0">累计成果</h3>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <span class="tag">学习 ${d.learning_days || 0} 天</span>
            <span class="tag">今日 ${today.sessions || 0} 次训练</span>
            <span class="tag">今日 ${today.minutes || 0} 分钟</span>
            <span class="tag">今日 ${today.items || 0} 项</span>
            <span class="tag">熟词 ${d.srs_mature || 0}</span>
          </div>
        </div>
        <div style="min-width:220px">
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">训练分布</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            ${modeTags(counts)}
          </div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom:20px">
      <h3 style="margin-bottom:8px">下一步建议</h3>
      ${renderRecommendations(d, weakAreas, counts, setup)}
    </div>

    <div class="card" style="margin-bottom:20px">
      <h3 style="margin-bottom:8px">最近完成的训练</h3>
      ${recentSessions.length ? recentSessions.map(recentRow).join('') : '<div style="font-size:13px;color:var(--text-dim)">最近还没有可展示的已完成训练。</div>'}
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

function renderRecommendations(d, weakAreas, counts, setup) {
  const items = [];
  const aiReady = !!setup.ai_ready;
  if ((d.srs_due || 0) > 0) {
    items.push({ page: 'vocab', text: `先完成今天的 ${d.srs_due} 张词汇复习，最容易形成稳定连续学习。` });
  }
  if (weakAreas.some(item => item.startsWith('grammar'))) {
    items.push({ page: 'grammar', text: '语法是当前薄弱项，建议先做一次短练习拉回正确率。' });
  } else if (weakAreas.some(item => item.startsWith('reading'))) {
    items.push({ page: 'reading', text: '阅读相关分项偏弱，建议做一篇定向阅读训练。' });
  }
  if (aiReady && (counts.writing || 0) === 0) {
    items.push({ page: 'writing', text: '你还没有形成写作反馈记录，建议完成一次写作以建立闭环。' });
  }
  if (aiReady && (counts.speaking || 0) === 0) {
    items.push({ page: 'speaking', text: '口语还没有形成样本，建议至少完成一次任务并查看评分建议。' });
  }
  if (!aiReady) {
    items.push({ page: 'setup', text: '当前 AI 还未就绪。先去 Setup 补齐配置，再解锁写作反馈、口语评分与 Chat。' });
  }
  if (!items.length) {
    items.push({ page: 'practice', text: '基础项目已有积累，可以进入 Practice 做更有针对性的专项训练。' });
  }

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

function modeTags(counts) {
  const labels = {
    vocab: '词汇',
    grammar: '语法',
    reading: '阅读',
    listening: '听力',
    writing: '写作',
    speaking: '口语',
    chat: 'Chat',
    mock: 'Mock',
  };
  return Object.entries(labels).map(([key, label]) => `<span class="tag">${label} ${counts[key] || 0}</span>`).join('');
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
