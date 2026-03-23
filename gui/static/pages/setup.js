// pages/setup.js — First-run wizard OR returning-user settings panel

function _clearExamCache() {
  ['chat_current', 'writing_current', 'reading_current', 'listening_current'].forEach(k => localStorage.removeItem(k));
}

function _defaultCoachSettings() {
  return {
    preferred_study_time: '20:00',
    quiet_hours: { start: '22:30', end: '08:00' },
    reminder_level: 'basic',
    desktop_enabled: true,
    bark_enabled: false,
    webhook_enabled: false,
    bark_key: '',
    webhook_url: '',
  };
}

export async function render(el) {
  let status = {};
  try { status = await api.get('/api/setup/status'); } catch (e) {}
  const versionMode = status.version_mode || 'opensource';
  const needsDataDirReview = !!status.needs_data_dir_review;
  let licStatus = {
    active: !!status.cloud_license_active,
    days_left: Number(status.license_days_left || 0),
    activation_available: !!status.activation_available,
    activation_reason: status.activation_reason || '',
    needs_reactivation: !!status.needs_reactivation,
    server_verified: status.server_verified,
    verification_warning: status.verification_warning || '',
    ai_mode: status.ai_mode || 'none',
    ai_ready: !!status.ai_ready,
    has_self_key: !!status.has_self_key,
    self_key_backend: status.self_key_backend || '',
    error: status.license_error || '',
  };
  let coachCfg = { settings: _defaultCoachSettings(), tier: 'free', channel_capabilities: { desktop: true, bark: false, webhook: false } };
  try { coachCfg = await api.get('/api/coach/settings'); } catch (e) {}
  const activationAvailable = !!licStatus.activation_available;
  const effectiveAiMode = status.ai_mode || (licStatus.active ? 'cloud' : status.has_self_key ? 'self_key' : 'none');
  const apiHint = effectiveAiMode === 'cloud'
    ? '(当前由 Cloud License 提供 AI，可留空保留)'
    : status.has_self_key
    ? '(已配置，可留空保留)'
    : versionMode === 'cloud' && licStatus.active
    ? '(可选)'
    : '';
  const apiPlaceholder = effectiveAiMode === 'cloud'
    ? 'Cloud License 已提供 AI，可按需覆盖'
    : status.has_self_key
    ? '留空可保留当前配置'
    : 'sk-...';

  const isFirstRun = !status.configured || needsDataDirReview;

  if (!isFirstRun) {
    renderSettings(el, status, licStatus, versionMode, coachCfg);
    return;
  }

  // ── First-run wizard ──────────────────────────────────────────────────────
  // Skip license step in opensource version
  const steps = versionMode === 'opensource'
    ? ['import', 'info', 'ai', 'prefs', 'done']
    : ['import', 'info', 'license', 'ai', 'prefs', 'done'];

  el.innerHTML = `
    <div style="max-width:520px;margin:0 auto">
      <h1 style="margin-bottom:4px">${needsDataDirReview ? '确认数据文件夹' : 'Welcome to English Coach 👋'}</h1>
      <p style="margin-bottom:24px">${needsDataDirReview ? '检测到新安装版本，请先确认这次继续使用的数据存储位置。' : 'Quick setup to get started'}</p>

      <div id="step-indicator" style="display:none;gap:8px;margin-bottom:24px;align-items:center">
        <div class="step-dot active" data-s="1">1</div>
        <div class="step-line"></div>
        <div class="step-dot" data-s="2">2</div>
        <div class="step-line"></div>
        <div class="step-dot" data-s="3">3</div>
        ${versionMode === 'cloud' ? '<div class="step-line"></div><div class="step-dot" data-s="4">4</div>' : ''}
      </div>

      <div class="card" style="padding:28px">

        <!-- Step 0: Existing data? -->
        <div class="setup-step active" id="step-0">
          <div style="text-align:center;padding:8px 0 20px">
            <div style="font-size:48px;margin-bottom:12px">📦</div>
            <h2 style="margin-bottom:8px">${needsDataDirReview ? '这次继续使用哪个数据文件夹？' : 'Do you have existing data?'}</h2>
            <p style="color:var(--text-dim);margin-bottom:24px">${needsDataDirReview ? '产品已更新。请确认继续使用旧数据文件夹，或改成新的数据文件夹。系统会按你这次选择的文件夹继续读取词汇、进度和设置。' : "If you've used English Coach before, you can restore your vocabulary, progress, and settings by pointing to your old data folder."}</p>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <button class="btn btn-outline" id="btn-has-data" style="padding:16px;display:flex;flex-direction:column;align-items:center;gap:6px;height:auto">
              <span style="font-size:24px">📂</span>
              <span style="font-weight:600">${needsDataDirReview ? '选择 / 确认文件夹' : 'Yes, I have data'}</span>
              <span style="font-size:12px;color:var(--text-dim)">${needsDataDirReview ? 'Use an existing data folder' : 'Restore from existing folder'}</span>
            </button>
            <button class="btn btn-primary" id="btn-no-data" style="padding:16px;display:flex;flex-direction:column;align-items:center;gap:6px;height:auto">
              <span style="font-size:24px">✨</span>
              <span style="font-weight:600">${needsDataDirReview ? '改用新位置' : 'Start fresh'}</span>
              <span style="font-size:12px;opacity:0.8">${needsDataDirReview ? 'Choose a new storage location' : 'New user, no prior data'}</span>
            </button>
          </div>
        </div>

        <!-- Step 0b: Import existing data -->
        <div class="setup-step" id="step-0b">
          <h2 style="margin-bottom:8px">📂 ${needsDataDirReview ? '确认数据文件夹' : 'Restore Existing Data'}</h2>
          <p style="color:var(--text-dim);margin-bottom:20px">${needsDataDirReview ? '请输入你要继续使用的数据目录，或者直接粘贴 <code style="color:var(--accent)">user.db</code> 文件路径。更新后的应用会按这个位置继续读取和保存数据。' : 'Enter the path to your existing data folder. This is the folder that contains <code style="color:var(--accent)">user.db</code>.'}</p>
          <div id="data-dir-hint" style="background:var(--bg3);border-radius:8px;padding:12px;margin-bottom:16px;font-size:13px">
            <div style="color:var(--text-dim);margin-bottom:4px">Default data folder location:</div>
            <div id="default-data-path" style="font-family:monospace;color:var(--accent);word-break:break-all">Loading…</div>
          </div>
          <div class="form-group">
            <label>Data folder path</label>
            <input id="inp-restore-dir" type="text" placeholder="e.g. C:\\Users\\you\\Documents\\EnglishCoach\\data" style="font-family:monospace;font-size:13px">
            <div style="font-size:12px;color:var(--text-dim);margin-top:6px">${needsDataDirReview ? '支持填写数据目录，或直接填写 user.db 文件路径。' : 'Paste the full path to your existing data folder. The app will load your vocabulary and progress from there.'}</div>
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
          <div class="form-group">
            <label>Target exam date (optional)</label>
            <input id="inp-exam-date" type="date" value="${status.target_exam_date || ''}">
            <div style="font-size:12px;color:var(--text-dim);margin-top:6px">Set this only if you want sprint-mode recommendations in the last 30 days.</div>
          </div>
          <button class="btn btn-primary" id="btn-next-1" style="width:100%">Next →</button>
        </div>

        <!-- Step 2: License -->
        ${versionMode === 'cloud' ? `
        <div class="setup-step" id="step-2">
          <h2 style="margin-bottom:8px">Activate Cloud License</h2>
          ${licStatus.active ? `
          <div class="alert alert-success" style="margin-bottom:16px">
            ✓ Cloud license active — <strong>${licStatus.days_left}</strong> days remaining
          </div>` : activationAvailable ? `
          <p style="margin-bottom:20px">This build has a configured activation service. Enter a key like <code style="color:var(--accent);font-size:12px">XXXX-XXXX-XXXX-XXXX</code> to enable the embedded AI setup on this device.</p>

          <div class="form-group">
            <label>License Key</label>
            <input id="inp-license" type="text" placeholder="XXXX-XXXX-XXXX-XXXX" style="font-family:monospace;letter-spacing:1px">
          </div>
          <div id="lic-msg"></div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px">
            <button class="btn btn-outline" id="btn-back-2">← Back</button>
            <button class="btn btn-primary" id="btn-activate">Activate Key</button>
          </div>
          ` : `
          <div class="alert alert-info" style="margin-bottom:16px">
            当前构建未配置激活服务
          </div>
          <p style="margin-bottom:16px;color:var(--text-dim)">${licStatus.activation_reason || '没有服务器时，请直接配置你自己的 API key。'}</p>
          <div style="font-size:14px;line-height:1.7;color:var(--text);margin-bottom:8px">
            <div>• 有 API key：下一步可直接配置 DeepSeek / OpenAI / Claude / Qwen。</div>
            <div>• 没有 API key：仍可使用 Vocabulary、Grammar、Reading fallback、Listening 等离线能力。</div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px">
            <button class="btn btn-outline" id="btn-back-2">← Back</button>
            <button class="btn btn-primary" id="btn-skip-lic-direct">Continue →</button>
          </div>
          `}
          <button class="btn" id="btn-skip-lic" style="width:100%;margin-top:10px;background:transparent;color:var(--text-dim);font-size:13px">
            ${licStatus.active ? 'Continue →' : 'Skip — I have my own API key →'}
          </button>
        </div>
        ` : ''}

        <!-- Step 3: Self API Key -->
        <div class="setup-step" id="step-3">
          <h2 style="margin-bottom:8px">Configure AI</h2>

          ${versionMode === 'cloud' && licStatus.active ? `
          <div class="alert alert-success" style="margin-bottom:16px">
            ✓ Cloud license active — no API key needed (optional)
          </div>` : versionMode === 'opensource' ? `
          <p style="margin-bottom:20px">Provide your own API key to use AI features (writing feedback, reading questions, chat). You can skip this and use offline features (grammar, vocab) for free.</p>
          ` : versionMode === 'cloud' && !activationAvailable ? `
          <p style="margin-bottom:20px">当前构建没有激活服务器。要使用 AI 功能，请在这里直接配置你自己的 API key；否则也可以跳过，先使用离线主流程。</p>
          ` : `
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
            <label>API Key <span id="api-key-hint" style="color:var(--text-dim)">${apiHint}</span></label>
            <input id="inp-apikey" type="password" placeholder="${apiPlaceholder}">
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
          <div class="form-group">
            <label>Coach reminder level</label>
            <select id="inp-reminder-level" style="width:100%;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:6px 10px">
              <option value="off" ${coachCfg.settings?.reminder_level === 'off' ? 'selected' : ''}>Off</option>
              <option value="basic" ${(!coachCfg.settings?.reminder_level || coachCfg.settings?.reminder_level === 'basic') ? 'selected' : ''}>Basic</option>
              <option value="coach" ${coachCfg.settings?.reminder_level === 'coach' ? 'selected' : ''}>Coach</option>
            </select>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div class="form-group">
              <label>Preferred study time</label>
              <input id="inp-study-time" type="time" value="${coachCfg.settings?.preferred_study_time || '20:00'}">
            </div>
            <div class="form-group">
              <label>Quiet hours start</label>
              <input id="inp-quiet-start" type="time" value="${coachCfg.settings?.quiet_hours?.start || '22:30'}">
            </div>
          </div>
          <div class="form-group">
            <label>Quiet hours end</label>
            <input id="inp-quiet-end" type="time" value="${coachCfg.settings?.quiet_hours?.end || '08:00'}">
          </div>
          <div class="form-group">
            <label>Desktop reminder</label>
            <label style="display:flex;gap:8px;align-items:center;font-size:13px">
              <input id="inp-desktop-enabled" type="checkbox" ${coachCfg.settings?.desktop_enabled !== false ? 'checked' : ''}>
              Enable local desktop reminder
            </label>
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

      <div id="buy-info" style="display:none"></div>
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
  async function loadRestorePath() {
    try {
      const current = status.current_data_dir || (await api.get('/api/setup/data_dir')).data_dir;
      el.querySelector('#default-data-path').textContent = current;
      el.querySelector('#inp-restore-dir').placeholder = current;
      if (needsDataDirReview && current) {
        el.querySelector('#inp-restore-dir').value = current;
      }
    } catch {
      el.querySelector('#default-data-path').textContent = '(unavailable)';
    }
  }

  el.querySelector('#btn-no-data').addEventListener('click', () => setStep(1));
  el.querySelector('#btn-has-data').addEventListener('click', async () => {
    setStep('0b');
    await loadRestorePath();
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
          data_dir: r.data_dir || dir,
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
    // Skip to step 3 in opensource, step 2 in cloud
    setStep(versionMode === 'opensource' ? 3 : 2);
  });

  if (versionMode === 'cloud') {
    el.querySelector('#btn-back-2')?.addEventListener('click', () => setStep(1));

    el.querySelector('#btn-activate')?.addEventListener('click', async () => {
      const key = el.querySelector('#inp-license').value.trim();
      const msg = el.querySelector('#lic-msg');
      const btn = el.querySelector('#btn-activate');
      if (!key) { msg.innerHTML = '<div class="alert alert-error" style="margin-top:8px">Please enter a License Key</div>'; return; }
      btn.disabled = true; btn.textContent = 'Verifying…';
      try {
        const r = await api.post('/api/license/activate', { key });
        if (r.ok) {
          licStatus.active = true;
          licStatus.days_left = r.days_left;
          status.ai_mode = 'cloud';
          status.ai_ready = true;
          status.has_cloud_license = true;
          status.has_ai_access = true;
          status.has_api_key = true;
          const hintEl = el.querySelector('#api-key-hint');
          const keyInput = el.querySelector('#inp-apikey');
          if (hintEl) hintEl.textContent = '(当前由 Cloud License 提供 AI，可留空保留)';
          if (keyInput) keyInput.placeholder = 'Cloud License 已提供 AI，可按需覆盖';
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

    el.querySelector('#btn-skip-lic')?.addEventListener('click', () => setStep(3));
    el.querySelector('#btn-skip-lic-direct')?.addEventListener('click', () => setStep(3));
  }

  el.querySelector('#btn-back-3').addEventListener('click', () => setStep(versionMode === 'opensource' ? 1 : 2));
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
        target_exam_date: el.querySelector('#inp-exam-date')?.value || '',
        backend:     el.querySelector('#inp-backend').value,
        api_key:     el.querySelector('#inp-apikey').value.trim(),
        content_path: '',
        data_dir:    el.querySelector('#inp-datadir')?.value.trim() || 'data',
      });
      await api.post('/api/coach/settings', {
        preferred_study_time: el.querySelector('#inp-study-time')?.value || '20:00',
        quiet_hours: {
          start: el.querySelector('#inp-quiet-start')?.value || '22:30',
          end: el.querySelector('#inp-quiet-end')?.value || '08:00',
        },
        reminder_level: el.querySelector('#inp-reminder-level')?.value || 'basic',
        desktop_enabled: !!el.querySelector('#inp-desktop-enabled')?.checked,
        bark_enabled: !!el.querySelector('#inp-bark-enabled')?.checked,
        webhook_enabled: !!el.querySelector('#inp-webhook-enabled')?.checked,
        bark_key: el.querySelector('#inp-bark-key')?.value || '',
        webhook_url: el.querySelector('#inp-webhook-url')?.value || '',
      }).catch(() => {});
      _clearExamCache();
      setStep(5);
    } catch (e) {
      msg.innerHTML = `<div class="alert alert-error" style="margin-top:8px">${e.message}</div>`;
      btn.disabled = false;
    }
  }

  el.querySelector('#btn-go-home').addEventListener('click', () => navigate('home'));

  if (needsDataDirReview) {
    setStep('0b');
    loadRestorePath();
    const msg = el.querySelector('#restore-msg');
    if (msg) {
      msg.innerHTML = '<div class="alert alert-info" style="margin-bottom:0">检测到新安装版本，请确认这次继续使用的数据文件夹。</div>';
    }
  }
}

// ── Returning-user settings panel ─────────────────────────────────────────
function renderSettings(el, status, licStatus, versionMode, coachCfg) {
  const licTag = licStatus.active
    ? `<span class="tag tag-green">☁ Cloud ${licStatus.days_left}d</span>`
    : licStatus.needs_reactivation
    ? `<span class="tag" style="color:var(--red)">需重新激活</span>`
    : licStatus.activation_available
    ? `<span class="tag" style="color:var(--text-dim)">Not activated</span>`
    : `<span class="tag" style="color:var(--text-dim)">Self-key only</span>`;
  const effectiveAiMode = status.ai_mode || (licStatus.active ? 'cloud' : status.has_self_key ? 'self_key' : 'none');
  const apiHint = effectiveAiMode === 'cloud'
    ? '(当前由 Cloud License 提供 AI，可留空保留)'
    : status.has_self_key
    ? '(已配置，可留空保留)'
    : versionMode === 'cloud' && licStatus.active
    ? '(可选)'
    : '';
  const apiPlaceholder = effectiveAiMode === 'cloud'
    ? 'Cloud License 已提供 AI，可按需覆盖'
    : status.has_self_key
    ? '留空可保留当前配置'
    : 'sk-...';

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
          <div class="form-group" style="margin-top:12px;margin-bottom:0">
            <label>Target exam date (optional)</label>
            <input id="inp-exam-date" type="date" value="${status.target_exam_date || ''}">
          </div>
        </div>
      </div>

      <div class="settings-section">
        <div class="settings-section-title">AI Configuration</div>
        <div class="card">
          ${versionMode === 'cloud' ? `
          <div class="settings-row">
            <span class="settings-row-label">Cloud License</span>
            ${licTag}
            <a href="#" id="go-license" style="font-size:13px;color:var(--accent);text-decoration:none">Manage →</a>
          </div>
          ${licStatus.verification_warning ? `
          <div style="font-size:12px;color:var(--text-dim);margin-top:8px;line-height:1.6">${licStatus.verification_warning}</div>
          ` : ''}
          ${!licStatus.active && !licStatus.activation_available ? `
          <div style="font-size:12px;color:var(--text-dim);margin-top:8px">${licStatus.activation_reason || '当前构建未配置激活服务。'}</div>
          ` : ''}
          <hr class="divider" style="margin:12px 0">
          ` : ''}
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
            <label>API Key <span style="color:var(--text-dim)">${apiHint}</span></label>
            <input id="inp-apikey" type="password" placeholder="${apiPlaceholder}">
            <div style="font-size:12px;color:var(--text-dim);margin-top:6px">Stored locally in .env — never uploaded</div>
          </div>
        </div>
      </div>

      <div class="settings-section">
        <div class="settings-section-title">Coach Reminders</div>
        <div class="card">
          <div class="form-group">
            <label>Reminder level</label>
            <select id="inp-reminder-level">
              <option value="off" ${coachCfg.settings?.reminder_level === 'off' ? 'selected' : ''}>Off</option>
              <option value="basic" ${(!coachCfg.settings?.reminder_level || coachCfg.settings?.reminder_level === 'basic') ? 'selected' : ''}>Basic</option>
              <option value="coach" ${coachCfg.settings?.reminder_level === 'coach' ? 'selected' : ''}>Coach</option>
            </select>
          </div>
          <div class="settings-row">
            <span class="settings-row-label">Preferred study time</span>
            <input id="inp-study-time" type="time" value="${coachCfg.settings?.preferred_study_time || '20:00'}"
              style="background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:13px">
          </div>
          <hr class="divider" style="margin:12px 0">
          <div class="settings-row">
            <span class="settings-row-label">Quiet hours start</span>
            <input id="inp-quiet-start" type="time" value="${coachCfg.settings?.quiet_hours?.start || '22:30'}"
              style="background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:13px">
          </div>
          <hr class="divider" style="margin:12px 0">
          <div class="settings-row">
            <span class="settings-row-label">Quiet hours end</span>
            <input id="inp-quiet-end" type="time" value="${coachCfg.settings?.quiet_hours?.end || '08:00'}"
              style="background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:13px">
          </div>
          <hr class="divider" style="margin:12px 0">
          <label style="display:flex;gap:8px;align-items:center;font-size:13px">
            <input id="inp-desktop-enabled" type="checkbox" ${coachCfg.settings?.desktop_enabled !== false ? 'checked' : ''}>
            Enable local desktop reminders
          </label>
          <div style="margin-top:10px">
            <button class="btn btn-outline" id="btn-test-reminder" style="font-size:12px;padding:5px 12px">发送测试提醒</button>
          </div>
          <div style="font-size:12px;color:var(--text-dim);margin-top:8px">
            ${coachCfg.channel_capabilities?.bark ? '商业版可启用 Bark / Webhook 外部触达。' : '外部触达仅对商业版开放；当前仍可使用本地提醒。'}
          </div>
          <hr class="divider" style="margin:12px 0">
          <label style="display:flex;gap:8px;align-items:center;font-size:13px;margin-bottom:8px">
            <input id="inp-bark-enabled" type="checkbox" ${coachCfg.settings?.bark_enabled ? 'checked' : ''} ${coachCfg.channel_capabilities?.bark ? '' : 'disabled'}>
            Enable Bark push
          </label>
          <input id="inp-bark-key" type="text" placeholder="Bark device key or full URL"
            value="${coachCfg.settings?.bark_key || ''}"
            ${coachCfg.channel_capabilities?.bark ? '' : 'disabled'}
            style="width:100%;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:6px 10px;font-size:13px">
          <hr class="divider" style="margin:12px 0">
          <label style="display:flex;gap:8px;align-items:center;font-size:13px;margin-bottom:8px">
            <input id="inp-webhook-enabled" type="checkbox" ${coachCfg.settings?.webhook_enabled ? 'checked' : ''} ${coachCfg.channel_capabilities?.webhook ? '' : 'disabled'}>
            Enable Webhook
          </label>
          <input id="inp-webhook-url" type="text" placeholder="https://your-webhook-url"
            value="${coachCfg.settings?.webhook_url || ''}"
            ${coachCfg.channel_capabilities?.webhook ? '' : 'disabled'}
            style="width:100%;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:6px 10px;font-size:13px">
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

  if (versionMode === 'cloud') {
    el.querySelector('#go-license')?.addEventListener('click', (e) => {
      e.preventDefault();
      navigate('license');
    });
  }

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
  el.querySelector('#btn-test-reminder')?.addEventListener('click', async () => {
    const msg = el.querySelector('#save-msg');
    try {
      const r = await api.post('/api/coach/test-reminder', {});
      const count = (r.dispatched || []).length;
      msg.innerHTML = `<div class="alert alert-success">✓ 已触发 ${count} 条测试提醒</div>`;
      setTimeout(() => { msg.innerHTML = ''; }, 3000);
    } catch (e) {
      msg.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
  });

  el.querySelector('#btn-save').addEventListener('click', async () => {
    const btn = el.querySelector('#btn-save');
    const msg = el.querySelector('#save-msg');
    btn.disabled = true;
    try {
      await api.post('/api/setup', {
        name: el.querySelector('#inp-name').value.trim() || 'User',
        target_exam: el.querySelector('#inp-exam').value,
        target_exam_date: el.querySelector('#inp-exam-date')?.value || '',
        backend: el.querySelector('#inp-backend').value,
        api_key: el.querySelector('#inp-apikey').value.trim(),
        content_path: '',
        history_retention_days: parseInt(el.querySelector('#inp-retention').value) || 30,
        data_dir: el.querySelector('#inp-datadir').value.trim(),
      });
      await api.post('/api/coach/settings', {
        preferred_study_time: el.querySelector('#inp-study-time')?.value || '20:00',
        quiet_hours: {
          start: el.querySelector('#inp-quiet-start')?.value || '22:30',
          end: el.querySelector('#inp-quiet-end')?.value || '08:00',
        },
        reminder_level: el.querySelector('#inp-reminder-level')?.value || 'basic',
        desktop_enabled: !!el.querySelector('#inp-desktop-enabled')?.checked,
        bark_enabled: !!el.querySelector('#inp-bark-enabled')?.checked,
        webhook_enabled: !!el.querySelector('#inp-webhook-enabled')?.checked,
        bark_key: el.querySelector('#inp-bark-key')?.value || '',
        webhook_url: el.querySelector('#inp-webhook-url')?.value || '',
      }).catch(() => {});
      _clearExamCache();
      msg.innerHTML = '<div class="alert alert-success">✓ Settings saved</div>';
      setTimeout(() => { msg.innerHTML = ''; }, 3000);
    } catch (e) {
      msg.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
    btn.disabled = false;
  });
}
