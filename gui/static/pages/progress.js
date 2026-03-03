// pages/progress.js — Progress dashboard with Chart.js charts

export async function render(el) {
  el.innerHTML = `
    <h1>📊 Progress Dashboard</h1>
    <div id="progress-body"><div style="text-align:center;padding:40px"><div class="spinner"></div></div></div>
  `;

  try {
    const data = await api.get('/api/progress');
    renderDashboard(el, data);
  } catch (e) {
    el.querySelector('#progress-body').innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

function renderDashboard(el, d) {
  const body = el.querySelector('#progress-body');

  const streak = d.streak_days || 0;
  body.innerHTML = `
    <div class="stats-row">
      <div class="stat-badge"><div class="val">${d.cefr_level || '?'}</div><div class="lbl">CEFR Level</div></div>
      <div class="stat-badge"><div class="val" style="color:var(--yellow)">${streak ? '🔥 ' + streak : '0'}</div><div class="lbl">Day Streak</div></div>
      <div class="stat-badge"><div class="val">${d.total_sessions || 0}</div><div class="lbl">Sessions</div></div>
      <div class="stat-badge"><div class="val">${d.avg_accuracy || 0}%</div><div class="lbl">Avg Accuracy</div></div>
      <div class="stat-badge"><div class="val">${d.srs_total || 0}</div><div class="lbl">Words</div></div>
      <div class="stat-badge"><div class="val" style="color:var(--green)">${d.srs_mature || 0}</div><div class="lbl">Mature</div></div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
      <div class="card">
        <h3>Skill Radar</h3>
        <div class="chart-wrap"><canvas id="radar-chart"></canvas></div>
      </div>
      <div class="card">
        <h3>14-Day Activity</h3>
        <div class="chart-wrap"><canvas id="bar-chart"></canvas></div>
      </div>
    </div>

    ${d.weak_areas && d.weak_areas.length ? `
    <div class="card" style="margin-bottom:20px">
      <h3 style="margin-bottom:8px">Areas to Improve</h3>
      <p style="margin-bottom:14px">${d.weak_areas.map(w => `<span class="tag tag-yellow" style="margin-right:6px">${w.replace(/_/g,' ')}</span>`).join('')}</p>
      <div style="display:flex;gap:10px">
        <button class="btn btn-outline" onclick="navigate('grammar')">✏️ Practice Grammar</button>
        <button class="btn btn-outline" onclick="navigate('vocab')">🃏 Review Vocab</button>
      </div>
    </div>` : ''}

    <div class="card">
      <h3>Skill Scores</h3>
      <div id="skill-table"></div>
    </div>
  `;

  // Radar chart
  const skills = d.skill_scores || {};
  const labels = Object.keys(skills).map(k => k.replace(/_/g,' '));
  const values = Object.values(skills).map(v => Math.round(v * 100));

  new Chart(document.getElementById('radar-chart'), {
    type: 'radar',
    data: {
      labels,
      datasets: [{
        label: 'Score %',
        data: values,
        backgroundColor: 'rgba(79,142,247,0.15)',
        borderColor: '#4f8ef7',
        pointBackgroundColor: '#4f8ef7',
        pointRadius: 3,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { r: {
        min: 0, max: 100,
        ticks: { color: '#7b82a8', stepSize: 25, font: { size: 10 } },
        grid: { color: '#2e3250' },
        pointLabels: { color: '#e8eaf6', font: { size: 10 } },
        angleLines: { color: '#2e3250' },
      }},
      plugins: { legend: { display: false } },
    },
  });

  // Bar chart — 14-day history
  const history = d.history || [];
  const last14 = getLast14Days();
  const histMap = {};
  history.forEach(h => { histMap[h.day] = h.sessions; });
  const barData = last14.map(day => histMap[day] || 0);

  new Chart(document.getElementById('bar-chart'), {
    type: 'bar',
    data: {
      labels: last14.map(d => d.slice(5)), // MM-DD
      datasets: [{
        label: 'Sessions',
        data: barData,
        backgroundColor: barData.map(v => v > 0 ? '#4f8ef7' : '#2e3250'),
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: '#7b82a8', font: { size: 10 } }, grid: { color: '#2e3250' } },
        y: { ticks: { color: '#7b82a8', stepSize: 1 }, grid: { color: '#2e3250' }, min: 0 },
      },
      plugins: { legend: { display: false } },
    },
  });

  // Skill table
  const table = body.querySelector('#skill-table');
  const sorted = Object.entries(skills).sort((a, b) => b[1] - a[1]);
  table.innerHTML = sorted.map(([skill, score]) => {
    const pct = Math.round(score * 100);
    const color = pct >= 75 ? 'var(--green)' : pct >= 55 ? 'var(--yellow)' : 'var(--red)';
    const filled = Math.round(pct / 10);
    const bar = '█'.repeat(filled) + '░'.repeat(10 - filled);
    return `<div style="display:flex;align-items:center;gap:12px;padding:6px 0;border-bottom:1px solid var(--border)">
      <span style="flex:1;font-size:13px">${skill.replace(/_/g,' ')}</span>
      <span style="color:${color};font-weight:600;width:40px;text-align:right">${pct}%</span>
      <span style="color:${color};font-family:monospace;font-size:12px">${bar}</span>
    </div>`;
  }).join('');
}

function getLast14Days() {
  const days = [];
  for (let i = 13; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(d.toISOString().slice(0, 10));
  }
  return days;
}
