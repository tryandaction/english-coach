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

  if (status.active) {
    const expiryWarn = status.days_left < 7
      ? `<div class="license-expiry-warn">⚠ Cloud license expires in <strong>${status.days_left}</strong> days — please renew soon</div>`
      : '';
    body.innerHTML = `
      ${expiryWarn}
      <div class="alert alert-success">
        ✓ Cloud license active — <strong>${status.days_left}</strong> days remaining
      </div>
      <div class="card">
        <p style="color:var(--text-dim);font-size:14px">Cloud license uses a built-in API key. No configuration needed — all AI features work out of the box.</p>
        <button class="btn btn-outline" id="btn-deactivate" style="margin-top:12px;color:var(--red)">Deactivate License</button>
      </div>
    `;
    body.querySelector('#btn-deactivate').addEventListener('click', async () => {
      if (!confirm('Deactivate cloud license? You will need your own API key to use AI features.')) return;
      await api.post('/api/license/deactivate', {});
      navigate('license');
    });
    return;
  }

  body.innerHTML = `
    <div class="card">
      <h3>Activate Cloud License</h3>
      <p style="color:var(--text-dim);font-size:14px;margin-bottom:16px">
        After purchase you'll receive a License Key (format: XXXX-XXXX-XXXX-XXXX).
        Enter it below to enable the built-in API — no DeepSeek key needed.
      </p>
      <div class="form-group">
        <label>License Key</label>
        <input id="inp-key" type="text" placeholder="XXXX-XXXX-XXXX-XXXX" style="font-family:monospace">
      </div>
      <div id="license-msg"></div>
      <button class="btn btn-primary" id="btn-activate" style="margin-top:8px">Activate</button>
    </div>

    <div class="card" style="margin-top:16px">
      <h3>Use Your Own API Key</h3>
      <p style="color:var(--text-dim);font-size:14px">
        Already have a DeepSeek or OpenAI key? Configure it in <a href="#" id="go-setup" style="color:var(--accent)">Setup</a> — no cloud license needed.
      </p>
    </div>

    <div class="card" style="margin-top:16px;border-color:var(--accent)">
      <h3 style="color:var(--accent)">Purchase</h3>

      <div style="font-size:12px;color:var(--text-dim);margin:10px 0 6px">First purchase (includes exe)</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
        <div style="text-align:center;padding:14px;background:var(--bg2);border-radius:8px;border:1px solid var(--border)">
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">exe only</div>
          <div style="font-size:20px;font-weight:700;color:var(--text)">¥19.9</div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:4px">one-time</div>
        </div>
        <div style="text-align:center;padding:14px;background:var(--bg2);border-radius:8px;border:1px solid var(--accent)">
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">exe + 1mo API</div>
          <div style="font-size:20px;font-weight:700;color:var(--accent)">¥29.9</div>
          <div style="font-size:11px;color:var(--green);margin-top:4px">recommended</div>
        </div>
        <div style="text-align:center;padding:14px;background:var(--bg2);border-radius:8px;border:1px solid var(--yellow)">
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">exe + 1yr API</div>
          <div style="font-size:20px;font-weight:700;color:var(--yellow)">¥109</div>
          <div style="font-size:11px;color:var(--yellow);margin-top:4px">save ¥60</div>
        </div>
      </div>

      <div style="font-size:12px;color:var(--text-dim);margin:14px 0 6px">Renew API (already have exe)</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
        <div style="text-align:center;padding:14px;background:var(--bg2);border-radius:8px;border:1px solid var(--border)">
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">1 month</div>
          <div style="font-size:20px;font-weight:700;color:var(--text)">¥19.9</div>
        </div>
        <div style="text-align:center;padding:14px;background:var(--bg2);border-radius:8px;border:1px solid var(--border)">
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">3 months</div>
          <div style="font-size:20px;font-weight:700;color:var(--text)">¥49</div>
          <div style="font-size:11px;color:var(--green);margin-top:4px">save ¥11</div>
        </div>
        <div style="text-align:center;padding:14px;background:var(--bg2);border-radius:8px;border:1px solid var(--green)">
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">1 year</div>
          <div style="font-size:20px;font-weight:700;color:var(--green)">¥149</div>
          <div style="font-size:11px;color:var(--green);margin-top:4px">save ¥90</div>
        </div>
      </div>

      <p style="font-size:13px;color:var(--text-dim);margin-top:14px">
        Search "英语教练" on Xianyu to purchase. Key sent after payment.
      </p>
    </div>
  `;

  body.querySelector('#go-setup').addEventListener('click', (e) => {
    e.preventDefault();
    navigate('setup');
  });

  body.querySelector('#btn-activate').addEventListener('click', async () => {
    const key = body.querySelector('#inp-key').value.trim();
    const msg = body.querySelector('#license-msg');
    const btn = body.querySelector('#btn-activate');
    if (!key) { msg.innerHTML = '<div class="alert alert-error">Please enter a License Key</div>'; return; }

    btn.disabled = true; btn.textContent = 'Verifying…';
    try {
      const r = await api.post('/api/license/activate', { key });
      if (r.ok) {
        msg.innerHTML = `<div class="alert alert-success">✓ Activated! ${r.days_left} days remaining</div>`;
        // Refresh nav dot
        const dot = document.querySelector('[data-page="license"] .nav-status-dot');
        if (dot) { dot.className = 'nav-status-dot active'; }
        else {
          const licLink = document.querySelector('[data-page="license"]');
          if (licLink) {
            const d = document.createElement('span');
            d.className = 'nav-status-dot active';
            licLink.appendChild(d);
          }
        }
        setTimeout(() => navigate('license'), 1200);
      } else {
        msg.innerHTML = `<div class="alert alert-error">${r.error}</div>`;
        btn.disabled = false; btn.textContent = 'Activate';
      }
    } catch (e) {
      msg.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
      btn.disabled = false; btn.textContent = 'Activate';
    }
  });
}
