// pages/license.js — Cloud license activation

export async function render(el) {
  let status = {};
  try { status = await api.get('/api/license/status'); } catch (e) {}

  el.innerHTML = `
    <h1>🔑 Cloud License</h1>
    <div id="license-body"></div>
  `;

  renderLicense(el, status);
}

function renderLicense(el, status) {
  const body = el.querySelector('#license-body');
  const selfKeySummary = status.has_self_key
    ? `当前也检测到自带 Key 模式（${escHtml((status.self_key_backend || '').toUpperCase()) || '已配置'}）。`
    : '当前没有检测到可用的自带 Key。';

  body.innerHTML = `
    <div class="card" style="margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
        <div>
          <h3 style="margin:0 0 8px 0">当前状态</h3>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
            <span class="tag">${status.active ? 'Cloud 已激活' : 'Cloud 未激活'}</span>
            <span class="tag">AI 模式 ${escHtml(status.ai_mode || 'none')}</span>
            ${status.active ? `<span class="tag tag-green">剩余 ${status.days_left || 0} 天</span>` : ''}
          </div>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.7">${escHtml(summaryLine(status, selfKeySummary))}</div>
        </div>
        <button class="btn btn-outline" id="btn-license-setup">前往 Setup</button>
      </div>
      ${status.verification_warning ? `<div class="alert alert-info" style="margin-top:12px">${escHtml(status.verification_warning)}</div>` : ''}
    </div>
  `;

  body.querySelector('#btn-license-setup')?.addEventListener('click', () => navigate('setup'));

  if (status.active) {
    renderActive(body, status);
    return;
  }

  if (status.needs_reactivation) {
    renderNeedsReactivation(body, status);
  }

  if (!status.activation_available) {
    renderUnavailable(body, status);
    return;
  }

  renderActivationForm(body, status);
}

function renderActive(body, status) {
  const expiryWarn = status.days_left < 7
    ? `<div class="license-expiry-warn">⚠ 当前 License 将在 <strong>${status.days_left}</strong> 天后到期，建议提前处理续期与云端校验。</div>`
    : '';
  body.innerHTML += `
    ${expiryWarn}
    <div class="alert ${status.ai_ready ? 'alert-success' : 'alert-warn'}">
      ${status.ai_ready ? '当前设备已激活 Cloud License，可使用内置 AI 配置。' : '当前设备已激活 Cloud License，但内置 AI 还未恢复到可用状态。'}
    </div>
    <div class="card">
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
        <span class="tag">License 格式 ${status.storage_format || 'unknown'}</span>
        <span class="tag">${status.server_verified === false ? '最近一次服务器校验未完成' : '服务器校验正常'}</span>
        <span class="tag">${status.ai_ready ? 'AI 已就绪' : 'AI 未就绪'}</span>
      </div>
      <p style="color:var(--text-dim);font-size:14px;line-height:1.7">
        若你没有自建激活服务，请保留当前数据目录中的 <code>license.key</code>。重装或迁移时，如果没有这个文件，就无法在离线状态下恢复 Cloud 模式。
      </p>
      <button class="btn btn-outline" id="btn-deactivate" style="margin-top:12px;color:var(--red)">停用当前 License</button>
    </div>
  `;
  body.querySelector('#btn-deactivate')?.addEventListener('click', async () => {
    if (!confirm('停用当前 License 后，Cloud AI 将不再可用；如有自带 Key，会回退到自带 Key 模式。是否继续？')) return;
    await api.post('/api/license/deactivate', {});
    navigate('license');
  });
}

function renderNeedsReactivation(body, status) {
  body.innerHTML += `
    <div class="alert alert-error">${escHtml(status.error || '当前 License 需要重新激活后才能恢复稳定可用。')}</div>
    <div class="card" style="margin-bottom:16px">
      <h3>为什么要重新激活</h3>
      <div style="font-size:14px;line-height:1.7;color:var(--text)">
        <div>1. 当前本地记录不是可稳定恢复 Cloud AI 的状态。</div>
        <div>2. 重新激活后会写入新的安全格式，重启后的恢复能力会更可靠。</div>
        <div>3. 如果你已经配置了自带 Key，系统会在重新激活前继续使用自带 Key 模式。</div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
        <span class="tag">当前格式 ${status.storage_format || 'unknown'}</span>
        <span class="tag">${status.has_self_key ? '自带 Key 可兜底' : '未检测到自带 Key'}</span>
      </div>
    </div>
  `;
}

function renderUnavailable(body, status) {
  body.innerHTML += `
    <div class="alert alert-info">当前构建未配置激活服务</div>
    <div class="card">
      <h3>当前建议路径</h3>
      <div style="font-size:14px;line-height:1.8;color:var(--text)">
        <div>1. 去 <a href="#" id="go-setup-unavailable" style="color:var(--accent)">Setup</a> 配置你自己的 API Key。</div>
        <div>2. 没有 API Key 时，仍可使用 Vocabulary、Grammar、Reading fallback、Listening 内置流程等离线能力。</div>
        <div>3. ${escHtml(status.activation_reason || '以后如果接入激活服务，再重新验证 Cloud 流程。')}</div>
      </div>
    </div>
  `;
  body.querySelector('#go-setup-unavailable')?.addEventListener('click', (e) => {
    e.preventDefault();
    navigate('setup');
  });
}

function renderActivationForm(body, status) {
  body.innerHTML += `
    <div class="card">
      <h3>激活 Cloud License</h3>
      <p style="color:var(--text-dim);font-size:14px;margin-bottom:16px;line-height:1.7">
        输入形如 <code>XXXX-XXXX-XXXX-XXXX</code> 的激活码，即可在当前设备上启用 Cloud AI。${status.has_self_key ? '如果你已经有自带 Key，也可以继续保留，自由切换。' : ''}
      </p>
      <div class="form-group">
        <label>License Key</label>
        <input id="inp-key" type="text" placeholder="XXXX-XXXX-XXXX-XXXX" style="font-family:monospace">
      </div>
      <div id="license-msg"></div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px">
        <button class="btn btn-primary" id="btn-activate">立即激活</button>
        ${status.has_self_key ? '<button class="btn btn-outline" id="btn-go-setup-selfkey">查看自带 Key 配置</button>' : ''}
      </div>
    </div>
  `;

  body.querySelector('#btn-go-setup-selfkey')?.addEventListener('click', () => navigate('setup'));
  body.querySelector('#btn-activate')?.addEventListener('click', async () => {
    const key = body.querySelector('#inp-key').value.trim();
    const msg = body.querySelector('#license-msg');
    const btn = body.querySelector('#btn-activate');
    if (!key) {
      msg.innerHTML = '<div class="alert alert-error">请输入 License Key</div>';
      return;
    }

    btn.disabled = true;
    btn.textContent = '正在验证…';
    try {
      const result = await api.post('/api/license/activate', { key });
      if (result.ok) {
        msg.innerHTML = `<div class="alert alert-success">激活成功，剩余 ${result.days_left} 天。应用将优先使用 Cloud AI。</div>`;
        const dot = document.querySelector('[data-page="license"] .nav-status-dot');
        if (dot) dot.className = 'nav-status-dot active';
        setTimeout(() => navigate('license'), 1200);
      } else {
        msg.innerHTML = `<div class="alert alert-error">${escHtml(result.error)}</div>`;
        btn.disabled = false;
        btn.textContent = '立即激活';
      }
    } catch (e) {
      msg.innerHTML = `<div class="alert alert-error">${escHtml(e.message)}</div>`;
      btn.disabled = false;
      btn.textContent = '立即激活';
    }
  });
}

function summaryLine(status, selfKeySummary) {
  if (status.active) {
    if (status.server_verified === false) {
      return `Cloud License 当前处于本地恢复可用状态。${selfKeySummary}`;
    }
    return `Cloud License 已激活并通过最近一次服务器校验。${selfKeySummary}`;
  }
  if (status.needs_reactivation) {
    return `当前 Cloud License 记录需要重新激活。${selfKeySummary}`;
  }
  if (!status.activation_available) {
    return `当前构建没有可用的激活服务。${selfKeySummary}`;
  }
  return `当前还没有激活 Cloud License。${selfKeySummary}`;
}

function escHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
