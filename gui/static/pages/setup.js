// pages/setup.js — First-run wizard OR returning-user settings panel

function _clearExamCache() {
  ['chat_current', 'writing_current', 'reading_current', 'listening_current'].forEach(k => localStorage.removeItem(k));
}

export async function render(el) {
  let status = {};
  try { status = await api.get('/api/setup/status'); } catch (e) {}
  let licStatus = {};
  try { licStatus = await api.get('/api/license/status'); } catch (e) {}

  const isFirstRun = !status.configured;

  if (!isFirstRun) {
    renderSettings(el, status, licStatus);
    return;
  }

  // ── First-run wizard ──────────────────────────────────────────────────────
  el.innerHTML = `
    <div style="max-width:520px;margin:0 auto">
      <h1 style="margin-bottom:4px">Welcome to English Coach 👋</h1>
      <p style="margin-bottom:24px">Quick setup to get started</p>

      <div id="step-indicator" style="display:none;gap:8px;margin-bottom:24px;align-items:center">
        <div class="step-dot active" data-s="1">1</div>
        <div class="step-line"></div>
        <div class="step-dot" data-s="2">2</div>
        <div class="step-line"></div>
        <div class="step-dot" data-s="3">3</div>
        <div class="step-line"></div>
        <div class="step-dot" data-s="4">4</div>
      </div>

      <div class="card" style="padding:28px">

        <!-- Step 0: Existing data? -->
        <div class="setup-step active" id="step-0">
          <div style="text-align:center;padding:8px 0 20px">
            <div style="font-size:48px;margin-bottom:12px">📦</div>
            <h2 style="margin-bottom:8px">Do you have existing data?</h2>
            <p style="color:var(--text-dim);margin-bottom:24px">If you've used English Coach before, you can restore your vocabulary, progress, and settings by pointing to your old data folder.</p>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <button class="btn btn-outline" id="btn-has-data" style="padding:16px;display:flex;flex-direction:column;align-items:center;gap:6px;height:auto">
              <span style="font-size:24px">📂</span>
              <span style="font-weight:600">Yes, I have data</span>
              <span style="font-size:12px;color:var(--text-dim)">Restore from existing folder</span>
            </button>
            <button class="btn btn-primary" id="btn-no-data" style="padding:16px;display:flex;flex-direction:column;align-items:center;gap:6px;height:auto">
              <span style="font-size:24px">✨</span>
              <span style="font-weight:600">Start fresh</span>
              <span style="font-size:12px;opacity:0.8">New user, no prior data</span>
            </button>
          </div>
        </div>

        <!-- Step 0b: Import existing data -->
        <div class="setup-step" id="step-0b">
          <h2 style="margin-bottom:8px">📂 Restore Existing Data</h2>
          <p style="color:var(--text-dim);margin-bottom:20px">Enter the path to your existing data folder. This is the folder that contains <code style="color:var(--accent)">user.db</code>.</p>
          <div id="data-dir-hint" style="background:var(--bg3);border-radius:8px;padding:12px;margin-bottom:16px;font-size:13px">
            <div style="color:var(--text-dim);margin-bottom:4px">Default data folder location:</div>
            <div id="default-data-path" style="font-family:monospace;color:var(--accent);word-break:break-all">Loading…</div>
          </div>
          <div class="form-group">
            <label>Data folder path</label>
            <input id="inp-restore-dir" type="text" placeholder="e.g. C:\\Users\\you\\Documents\\EnglishCoach\\data" style="font-family:monospace;font-size:13px">
            <div style="font-size:12px;color:var(--text-dim);margin-top:6px">Paste the full path to your existing data folder. The app will load your vocabulary and progress from there.</div>
          </div>
          <div id="restore-msg" style="min-height:20px;margin-bottom:8px"></div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
            <button class="btn btn-outline" id="btn-back-0b">← Back</button>
            <button class="btn btn-primary" id="btn-restore">✓ Restore & Continue</button>
          </div>
        </div>

        <!-- Step 1: Profile -->
        <div class="setup-step" id="step-1">
          <h2 style="margin-bottom:20px">Basic Info</h2>
          <div class="form-group">
            <label>Your name</label>
            <input id="inp-name" type="text" placeholder="e.g. Alex" value="${status.name || ''}">
          </div>
          <div class="form-group">
            <label>Target exam</label>
            <select id="inp-exam">
              <option value="toefl"   ${status.target_exam==='toefl'  ?'selected':''}>TOEFL</option>
              <option value="ielts"   ${status.target_exam==='ielts'  ?'selected':''}>IELTS</option>
              <option value="gre"     ${status.target_exam==='gre'    ?'selected':''}>GRE</option>
              <option value="cet"     ${status.target_exam==='cet'    ?'selected':''}>CET-4/6</option>
              <option value="general" ${(!status.target_exam||status.target_exam==='general')?'selected':''}>General English</option>
            </select>
          </div>
          <button class="btn btn-primary" id="btn-next-1" style="width:100%">Next →</button>
        </div>

        <!-- Step 2: License -->
        <div class="setup-step" id="step-2">
          <h2 style="margin-bottom:8px">Activate Cloud License</h2>
          <p style="margin-bottom:20px">After purchase you'll receive a key like <code style="color:var(--accent);font-size:12px">XXXX-XXXX-XXXX-XXXX</code></p>

          ${licStatus.active ? `
          <div class="alert alert-success" style="margin-bottom:16px">
            ✓ Cloud license active — <strong>${licStatus.days_left}</strong> days remaining
          </div>` : ''}

          <div class="form-group">
            <label>License Key</label>
            <input id="inp-license" type="text" placeholder="XXXX-XXXX-XXXX-XXXX" style="font-family:monospace;letter-spacing:1px">
          </div>
          <div id="lic-msg"></div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px">
            <button class="btn btn-outline" id="btn-back-2">← Back</button>
            <button class="btn btn-primary" id="btn-activate">Activate Key</button>
          </div>
          <button class="btn" id="btn-skip-lic" style="width:100%;margin-top:10px;background:transparent;color:var(--text-dim);font-size:13px">
            ${licStatus.active ? 'Continue →' : 'Skip — I have my own API key →'}
          </button>
        </div>

        <!-- Step 3: Self API Key -->
        <div class="setup-step" id="step-3">
          <h2 style="margin-bottom:8px">Configure AI</h2>

          ${licStatus.active ? `
          <div class="alert alert-success" style="margin-bottom:16px">
            ✓ Cloud license active — no API key needed (optional)
          </div>` : `
          <p style="margin-bottom:20px">Used for writing feedback, reading questions, and chat. You can skip this and use offline features (grammar, vocab) for free.</p>
          `}

          <div class="form-group">
            <label>AI Provider</label>
            <select id="inp-backend">
              <option value="deepseek" ${status.backend==='deepseek'?'selected':''}>DeepSeek (recommended, affordable)</option>
              <option value="qwen"     ${status.backend==='qwen'    ?'selected':''}>Qwen / DashScope</option>
              <option value="openai"   ${status.backend==='openai'  ?'selected':''}>OpenAI</option>
              <option value="anthropic"${status.backend==='anthropic'?'selected':''}>Anthropic Claude</option>
            </select>
          </div>
          <div class="form-group">
            <label>API Key <span style="color:var(--text-dim)">${status.has_api_key ? '(set — leave blank to keep)' : licStatus.active ? '(optional)' : ''}</span></label>
            <input id="inp-apikey" type="password" placeholder="${status.has_api_key ? 'Leave blank to keep current' : 'sk-...'}">
            <div style="font-size:12px;color:var(--text-dim);margin-top:6px">Stored locally in .env — never uploaded</div>
          </div>
          <div id="api-msg"></div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px">
            <button class="btn btn-outline" id="btn-back-3">← Back</button>
            <button class="btn btn-primary" id="btn-next-3">Next →</button>
          </div>
          <button class="btn" id="btn-skip-3" style="width:100%;margin-top:10px;background:transparent;color:var(--text-dim);font-size:13px">
            Skip — use defaults →
          </button>
        </div>

        <!-- Step 4: Preferences -->
        <div class="setup-step" id="step-4">
          <h2 style="margin-bottom:20px">Preferences</h2>
          <div class="form-group">
            <label>Data Storage Location</label>
            <input id="inp-datadir" type="text"
              value="${status.data_dir || 'data'}"
              placeholder="data  or  C:\\Users\\you\\Documents\\EnglishCoach"
              style="font-family:monospace;font-size:13px">
            <div style="font-size:12px;color:var(--text-dim);margin-top:6px">Where to save vocabulary, progress, and AI cache. Supports absolute paths. Default: <code>data/</code> next to the exe.</div>
          </div>
          <div class="form-group">
            <label>Voice Speed</label>
            <select id="inp-tts-rate" style="width:100%;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:6px 10px">
              <option value="-30%">Slow</option>
              <option value="-10%" selected>Normal</option>
              <option value="+0%">Standard</option>
              <option value="+20%">Fast</option>
            </select>
          </div>
          <div class="form-group">
            <label>TTS Voice</label>
            <select id="inp-tts-voice" style="width:100%;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:6px 10px">
              <option value="en-US-AriaNeural">Aria (US Female)</option>
              <option value="en-US-JennyNeural">Jenny (US Female)</option>
              <option value="en-US-GuyNeural">Guy (US Male)</option>
              <option value="en-US-EricNeural">Eric (US Male)</option>
              <option value="en-GB-SoniaNeural">Sonia (UK Female)</option>
              <option value="en-GB-RyanNeural">Ryan (UK Male)</option>
              <option value="en-AU-NatashaNeural">Natasha (AU Female)</option>
            </select>
          </div>
          <div id="pref-msg"></div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px">
            <button class="btn btn-outline" id="btn-back-4">← Back</button>
            <button class="btn btn-success" id="btn-save">✓ Save & Start</button>
          </div>
        </div>

        <!-- Done -->
        <div class="setup-step" id="step-done">
          <div style="text-align:center;padding:20px 0">
            <div style="font-size:48px;margin-bottom:16px">🎉</div>
            <h2 style="margin-bottom:8px">Setup Complete!</h2>
            <p style="margin-bottom:24px">You're all set. Let's start learning.</p>
            <button class="btn btn-primary" id="btn-go-home" style="width:100%;justify-content:center;font-size:16px;padding:14px">
              Go to Home →
            </button>
          </div>
        </div>

      </div>

      <!-- Purchase info -->
      <div id="buy-info" style="margin-top:16px">
        <details>
          <summary style="cursor:pointer;color:var(--text-dim);font-size:13px;padding:8px 0">Buy Cloud License (optional) ▸</summary>
          <div class="card" style="margin-top:8px;padding:20px">
            <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px">First purchase (includes exe)</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:14px">
              ${priceBox('exe only','¥19.9','one-time','var(--border)','var(--text)')}
              ${priceBox('exe + 1mo API','¥29.9','recommended','var(--accent)','var(--accent)')}
              ${priceBox('exe + 1yr API','¥109','save ¥60','var(--yellow)','var(--yellow)')}
            </div>
            <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px">Renew API (already have exe)</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
              ${priceBox('1 month','¥19.9','','var(--border)','var(--text)')}
              ${priceBox('3 months','¥49','save ¥11','var(--border)','var(--text)')}
              ${priceBox('1 year','¥149','save ¥90','var(--green)','var(--green)')}
            </div>
            <p style="margin-top:12px;font-size:12px">Search "英语教练" on Xianyu to purchase. Key sent after payment.</p>
          </div>
        </details>
      </div>
    </div>
  `;

  // Step indicator helper
  function setStep(n) {
    el.querySelectorAll('.setup-step').forEach(s => s.classList.remove('active'));
    const stepId = n === 5 ? 'done' : n === '0b' ? '0b' : n;
    el.querySelector(`#step-${stepId}`).classList.add('active');
    // Hide step dots on pre-wizard steps
    const showDots = typeof n === 'number' && n >= 1 && n <= 5;
    el.querySelector('#step-indicator').style.display = showDots ? 'flex' : 'none';
    el.querySelectorAll('.step-dot').forEach(d => {
      const s = parseInt(d.dataset.s);
      const cur = typeof n === 'number' ? n : 0;
      d.classList.toggle('active', s === cur);
      d.classList.toggle('done', s < cur);
    });
    el.querySelector('#buy-info').style.display = (n === 5 || n === '0b' || n === 0) ? 'none' : '';
  }

  // Step 0: existing data choice
  el.querySelector('#btn-no-data').addEventListener('click', () => setStep(1));
  el.querySelector('#btn-has-data').addEventListener('click', async () => {
    setStep('0b');
    try {
      const r = await api.get('/api/setup/data_dir');
      el.querySelector('#default-data-path').textContent = r.data_dir;
      el.querySelector('#inp-restore-dir').placeholder = r.data_dir;
    } catch { el.querySelector('#default-data-path').textContent = '(unavailable)'; }
  });

  el.querySelector('#btn-back-0b').addEventListener('click', () => setStep(0));
  el.querySelector('#btn-restore').addEventListener('click', async () => {
    const dir = el.querySelector('#inp-restore-dir').value.trim();
    const msg = el.querySelector('#restore-msg');
    if (!dir) { msg.innerHTML = '<div class="alert alert-error" style="margin-bottom:0">Please enter the data folder path</div>'; return; }
    const btn = el.querySelector('#btn-restore');
    btn.disabled = true;
    // Check if user.db exists at that path
    try {
      const r = await api.post('/api/setup/check_data_dir', { data_dir: dir });
      if (r.valid) {
        // Save data_dir and reload — skip full wizard
        await api.post('/api/setup', {
          name: r.name || 'User',
          target_exam: r.target_exam || 'general',
          backend: r.backend || 'deepseek',
          api_key: '',
          content_path: '',
          data_dir: dir,
        });
        _clearExamCache();
        setStep(5);
      } else {
        msg.innerHTML = `<div class="alert alert-error" style="margin-bottom:0">${r.error || 'No valid data found at that path'}</div>`;
        btn.disabled = false;
      }
    } catch (e) {
      msg.innerHTML = `<div class="alert alert-error" style="margin-bottom:0">${e.message}</div>`;
      btn.disabled = false;
    }
  });

  el.querySelector('#btn-next-1').addEventListener('click', () => {
    if (!el.querySelector('#inp-name').value.trim()) {
      el.querySelector('#inp-name').focus(); return;
    }
    setStep(2);
  });

  el.querySelector('#btn-back-2').addEventListener('click', () => setStep(1));

  el.querySelector('#btn-activate').addEventListener('click', async () => {
    const key = el.querySelector('#inp-license').value.trim();
    const msg = el.querySelector('#lic-msg');
    const btn = el.querySelector('#btn-activate');
    if (!key) { msg.innerHTML = '<div class="alert alert-error" style="margin-top:8px">Please enter a License Key</div>'; return; }
    btn.disabled = true; btn.textContent = 'Verifying…';
    try {
      const r = await api.post('/api/license/activate', { key });
      if (r.ok) {
        msg.innerHTML = `<div class="alert alert-success" style="margin-top:8px">✓ Activated! ${r.days_left} days remaining</div>`;
        setTimeout(() => setStep(3), 1000);
      } else {
        msg.innerHTML = `<div class="alert alert-error" style="margin-top:8px">${r.error}</div>`;
        btn.disabled = false; btn.textContent = 'Activate Key';
      }
    } catch (e) {
      msg.innerHTML = `<div class="alert alert-error" style="margin-top:8px">${e.message}</div>`;
      btn.disabled = false; btn.textContent = 'Activate Key';
    }
  });

  el.querySelector('#btn-skip-lic').addEventListener('click', () => setStep(3));
  el.querySelector('#btn-back-3').addEventListener('click', () => setStep(2));
  el.querySelector('#btn-next-3').addEventListener('click', () => setStep(4));
  el.querySelector('#btn-skip-3').addEventListener('click', () => setStep(4));
  el.querySelector('#btn-back-4').addEventListener('click', () => setStep(3));
  el.querySelector('#btn-save').addEventListener('click', () => doSave());

  async function doSave() {
    const btn = el.querySelector('#btn-save');
    const msg = el.querySelector('#pref-msg');
    btn.disabled = true;
    const ttsRate  = el.querySelector('#inp-tts-rate')?.value  || '-10%';
    const ttsVoice = el.querySelector('#inp-tts-voice')?.value || 'en-US-AriaNeural';
    localStorage.setItem('ttsRate',  ttsRate);
    localStorage.setItem('ttsVoice', ttsVoice);
    window._ttsRate  = ttsRate;
    window._ttsVoice = ttsVoice;
    try {
      await api.post('/api/setup', {
        name:        el.querySelector('#inp-name').value.trim() || 'User',
        target_exam: el.querySelector('#inp-exam').value,
        backend:     el.querySelector('#inp-backend').value,
        api_key:     el.querySelector('#inp-apikey').value.trim(),
        content_path: '',
        data_dir:    el.querySelector('#inp-datadir')?.value.trim() || 'data',
      });
      _clearExamCache();
      setStep(5);
    } catch (e) {
      msg.innerHTML = `<div class="alert alert-error" style="margin-top:8px">${e.message}</div>`;
      btn.disabled = false;
    }
  }

  el.querySelector('#btn-go-home').addEventListener('click', () => navigate('home'));
}

// ── Returning-user settings panel ─────────────────────────────────────────
function renderSettings(el, status, licStatus) {
  const licTag = licStatus.active
    ? `<span class="tag tag-green">☁ Cloud ${licStatus.days_left}d</span>`
    : `<span class="tag" style="color:var(--text-dim)">Not activated</span>`;

  el.innerHTML = `
    <div style="max-width:520px;margin:0 auto">
      <h1 style="margin-bottom:4px">⚙️ Settings</h1>
      <p style="margin-bottom:24px">Update your configuration anytime</p>

      <div class="settings-section">
        <div class="settings-section-title">Personal Info</div>
        <div class="card">
          <div class="form-group">
            <label>Your name</label>
            <input id="inp-name" type="text" value="${status.name || ''}">
          </div>
          <div class="form-group" style="margin-bottom:0">
            <label>Target exam</label>
            <select id="inp-exam">
              <option value="toefl"   ${status.target_exam==='toefl'  ?'selected':''}>TOEFL</option>
              <option value="ielts"   ${status.target_exam==='ielts'  ?'selected':''}>IELTS</option>
              <option value="gre"     ${status.target_exam==='gre'    ?'selected':''}>GRE</option>
              <option value="cet"     ${status.target_exam==='cet'    ?'selected':''}>CET-4/6</option>
              <option value="general" ${(!status.target_exam||status.target_exam==='general')?'selected':''}>General English</option>
            </select>
          </div>
        </div>
      </div>

      <div class="settings-section">
        <div class="settings-section-title">AI Configuration</div>
        <div class="card">
          <div class="settings-row">
            <span class="settings-row-label">Cloud License</span>
            ${licTag}
            <a href="#" id="go-license" style="font-size:13px;color:var(--accent);text-decoration:none">Manage →</a>
          </div>
          <hr class="divider" style="margin:12px 0">
          <div class="form-group">
            <label>AI Provider</label>
            <select id="inp-backend">
              <option value="deepseek" ${status.backend==='deepseek'?'selected':''}>DeepSeek (recommended, affordable)</option>
              <option value="qwen"     ${status.backend==='qwen'    ?'selected':''}>Qwen / DashScope</option>
              <option value="openai"   ${status.backend==='openai'  ?'selected':''}>OpenAI</option>
              <option value="anthropic"${status.backend==='anthropic'?'selected':''}>Anthropic Claude</option>
            </select>
          </div>
          <div class="form-group" style="margin-bottom:0">
            <label>API Key <span style="color:var(--text-dim)">${status.has_api_key ? '(set — leave blank to keep)' : licStatus.active ? '(optional)' : ''}</span></label>
            <input id="inp-apikey" type="password" placeholder="${status.has_api_key ? 'Leave blank to keep current' : 'sk-...'}">
            <div style="font-size:12px;color:var(--text-dim);margin-top:6px">Stored locally in .env — never uploaded</div>
          </div>
          <hr class="divider" style="margin:16px 0">
          <div class="form-group" style="margin-bottom:0">
            <label>Data Storage Location <span style="color:var(--text-dim)">(optional)</span></label>
            <input id="inp-datadir" type="text"
              value="${status.data_dir || 'data'}"
              placeholder="data  or  C:\\Users\\you\\Documents\\EnglishCoach"
              style="font-family:monospace;font-size:13px">
            <div style="font-size:12px;color:var(--text-dim);margin-top:6px">Where to save your vocabulary, progress, and AI cache. Default: <code>data/</code> next to the exe.</div>
          </div>
        </div>
      </div>

      <div class="settings-section">
        <div class="settings-section-title">Text-to-Speech</div>
        <div class="card">
          <div class="settings-row">
            <span class="settings-row-label">Speed</span>
            <select id="inp-tts-rate" style="background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:13px">
              <option value="-30%">Slow</option>
              <option value="-10%">Normal</option>
              <option value="+0%">Standard</option>
              <option value="+20%">Fast</option>
            </select>
          </div>
          <hr class="divider" style="margin:12px 0">
          <div class="settings-row">
            <span class="settings-row-label">Voice</span>
            <select id="inp-tts-voice" style="background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:13px">
              <option value="en-US-AriaNeural">Aria (US Female)</option>
              <option value="en-US-JennyNeural">Jenny (US Female)</option>
              <option value="en-US-GuyNeural">Guy (US Male)</option>
              <option value="en-US-EricNeural">Eric (US Male)</option>
              <option value="en-GB-SoniaNeural">Sonia (UK Female)</option>
              <option value="en-GB-RyanNeural">Ryan (UK Male)</option>
              <option value="en-AU-NatashaNeural">Natasha (AU Female)</option>
            </select>
          </div>
          <div style="margin-top:12px">
            <button class="btn btn-outline" id="btn-tts-test" style="font-size:13px;padding:5px 14px">🔊 Test Voice</button>
          </div>
        </div>
      </div>

      <div class="settings-section">
        <div class="settings-section-title">History</div>
        <div class="card">
          <div class="settings-row">
            <span class="settings-row-label">Auto-clean retention</span>
            <input id="inp-retention" type="number" min="0" step="1"
              value="${status.history_retention_days ?? 30}"
              style="width:80px;text-align:center;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 8px">
            <span style="font-size:13px;color:var(--text-dim)">days (0 = never, starred records excluded)</span>
          </div>
        </div>
      </div>

      <div class="settings-section">
        <div class="settings-section-title">Data Storage</div>
        <div class="card">
          <div class="settings-row" style="flex-wrap:wrap;gap:8px">
            <span class="settings-row-label">Data directory</span>
            <input id="inp-datadir" type="text"
              value="${status.data_dir || 'data'}"
              placeholder="data  or  C:\\Users\\you\\Documents\\EnglishCoach"
              style="flex:1;min-width:200px;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:5px 10px;font-size:13px;font-family:monospace">
          </div>
          <div style="font-size:12px;color:var(--text-dim);margin-top:6px">Relative paths are resolved next to the exe. Move existing data manually if you change this.</div>
        </div>
      </div>

      <button class="btn btn-success" id="btn-save" style="width:100%;justify-content:center;font-size:15px;padding:12px">✓ Save Settings</button>
      <div id="save-msg" style="margin-top:12px"></div>
    </div>
  `;

  el.querySelector('#go-license').addEventListener('click', (e) => {
    e.preventDefault();
    navigate('license');
  });

  // TTS settings — restore from localStorage and wire up live changes
  const rateEl  = el.querySelector('#inp-tts-rate');
  const voiceEl = el.querySelector('#inp-tts-voice');
  rateEl.value  = localStorage.getItem('ttsRate')  || '-10%';
  voiceEl.value = localStorage.getItem('ttsVoice') || 'en-US-AriaNeural';
  rateEl.addEventListener('change', () => {
    localStorage.setItem('ttsRate', rateEl.value);
    window._ttsRate = rateEl.value;
    window._ttsCache && window._ttsCache.clear();
  });
  voiceEl.addEventListener('change', () => {
    localStorage.setItem('ttsVoice', voiceEl.value);
    window._ttsVoice = voiceEl.value;
    window._ttsCache && window._ttsCache.clear();
  });
  el.querySelector('#btn-tts-test').addEventListener('click', () => {
    window.tts && window.tts('The quick brown fox jumps over the lazy dog.');
  });

  el.querySelector('#btn-save').addEventListener('click', async () => {
    const btn = el.querySelector('#btn-save');
    const msg = el.querySelector('#save-msg');
    btn.disabled = true;
    try {
      await api.post('/api/setup', {
        name: el.querySelector('#inp-name').value.trim() || 'User',
        target_exam: el.querySelector('#inp-exam').value,
        backend: el.querySelector('#inp-backend').value,
        api_key: el.querySelector('#inp-apikey').value.trim(),
        content_path: '',
        history_retention_days: parseInt(el.querySelector('#inp-retention').value) || 30,
        data_dir: el.querySelector('#inp-datadir').value.trim(),
      });
      _clearExamCache();
      msg.innerHTML = '<div class="alert alert-success">✓ Settings saved</div>';
      setTimeout(() => { msg.innerHTML = ''; }, 3000);
    } catch (e) {
      msg.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
    btn.disabled = false;
  });
}

function priceBox(label, price, sub, borderColor, textColor) {
  return `<div style="text-align:center;padding:10px 6px;background:var(--bg3);border-radius:8px;border:1px solid ${borderColor}">
    <div style="font-size:10px;color:var(--text-dim);margin-bottom:3px">${label}</div>
    <div style="font-size:17px;font-weight:700;color:${textColor}">${price}</div>
    ${sub ? `<div style="font-size:10px;color:var(--text-dim);margin-top:2px">${sub}</div>` : ''}
  </div>`;
}
