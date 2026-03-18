// pages/chat.js — Conversation practice UI + exam mode header

const STORAGE_KEY = 'chat_current';

// Use localStorage so content persists across app restarts
const _store = {
  get: () => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { return null; } },
  set: (v) => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(v)); } catch {} },
  clear: () => { try { localStorage.removeItem(STORAGE_KEY); } catch {} },
};

let _sid = null;
let _currentBackend = 'deepseek';
let _voices = [];
let _voiceCallWs = null;
let _mediaRecorder = null;
let _inCall = false;
let _exam = 'general';
let _displayHistory = []; // [{role, text}]

export async function render(el) {
  _sid = null;
  _inCall = false;
  _voiceCallWs = null;
  _displayHistory = [];

  el.innerHTML = `
    <h1>💬 Chat Practice</h1>
    <p>Free conversation with your AI English coach. Press Enter to send.</p>
    <div id="chat-body"></div>
  `;

  api.get('/api/voice/voices').then(r => {
    _voices = r.voices || [];
    window._ttsVoice = r.default || 'en-US-AriaNeural';
  }).catch(() => {});

  // Try restore from localStorage
  try {
    const saved = _store.get();
    if (saved && saved.session_id) {
      _sid = saved.session_id;
      _exam = saved.exam || 'general';
      _currentBackend = saved.backend || 'deepseek';
      _displayHistory = saved.display_history || [];
      renderChat(el, saved);
      return;
    }
  } catch {}

  await startChat(el);
}

async function startChat(el) {
  const body = el.querySelector('#chat-body');
  body.innerHTML = '<div style="text-align:center;padding:20px"><div class="spinner"></div></div>';

  try {
    const r = await api.post('/api/chat/start', {});
    _sid = r.session_id;
    _exam = r.exam || 'general';
    _currentBackend = r.backend || 'deepseek';
    _displayHistory = [{ role: 'ai', text: r.opener }];
    const sessionData = {
      session_id: _sid,
      exam: _exam,
      backend: _currentBackend,
      mode_name: r.mode_name || 'Free Conversation',
      mode_description: r.mode_description || '',
      mode_tips: r.mode_tips || [],
      display_history: _displayHistory,
    };
    _store.set(sessionData);
    renderChat(el, sessionData);
  } catch (e) {
    const noProfile = e.message.includes('profile') || e.message.includes('Profile');
    const noKey = e.message.includes('API key') || e.message.includes('api_key');
    if (noProfile) {
      body.innerHTML = `<div class="alert alert-warn">
        Please complete setup before using Chat.
        <button class="btn btn-primary" style="margin-top:12px;display:block" onclick="navigate('setup')">Go to Setup →</button>
      </div>`;
    } else if (noKey) {
      let licStatus = {};
      try { licStatus = await api.get('/api/license/status'); } catch {}
      body.innerHTML = `<div class="alert alert-warn">
        ${licStatus.activation_available
          ? 'Chat requires an API key or an active cloud license.'
          : 'Chat requires an API key. 当前构建未配置激活服务。'}
        <div style="display:flex;gap:10px;margin-top:12px">
          <button class="btn btn-primary" onclick="navigate('setup')">Configure API Key</button>
          ${licStatus.activation_available ? '<button class="btn btn-outline" onclick="navigate(\'license\')">Activate License</button>' : ''}
        </div>
      </div>`;
    } else {
      body.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
  }
}

function renderChat(el, sessionData) {
  const body = el.querySelector('#chat-body');
  const examKey = _exam || 'general';
  const examUpper = examKey.toUpperCase();
  const modeName = sessionData.mode_name || 'Free Conversation';
  const modeDesc = sessionData.mode_description || '';
  const tips = sessionData.mode_tips || [];

  body.innerHTML = `
    <div class="card" style="padding:0;overflow:hidden">
      <div style="padding:12px 16px;border-bottom:1px solid var(--border);background:var(--bg2)">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
          <span class="exam-badge exam-${examKey}">${examUpper}</span>
          <span style="font-weight:600;font-size:14px">${escHtml(modeName)}</span>
        </div>
        ${modeDesc ? `<div style="font-size:12px;color:var(--text-dim);margin-bottom:${tips.length ? '6px' : '0'}">${escHtml(modeDesc)}</div>` : ''}
        ${tips.length ? `<div style="display:flex;gap:6px;flex-wrap:wrap">${tips.map(t => `<span style="font-size:11px;background:var(--bg3);color:var(--text-dim);padding:2px 8px;border-radius:10px">${escHtml(t)}</span>`).join('')}</div>` : ''}
      </div>
      <div style="padding:10px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
        <span style="font-size:13px;color:var(--text-dim)">AI Coach</span>
        <div style="display:flex;align-items:center;gap:8px;margin-left:auto;flex-wrap:wrap">
          <select id="voice-selector" title="TTS Voice" style="font-size:12px;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:3px 8px;cursor:pointer">
            <option value="en-US-AriaNeural">Aria (US♀)</option>
            <option value="en-US-JennyNeural">Jenny (US♀)</option>
            <option value="en-US-GuyNeural">Guy (US♂)</option>
            <option value="en-US-EricNeural">Eric (US♂)</option>
            <option value="en-GB-SoniaNeural">Sonia (UK♀)</option>
            <option value="en-GB-RyanNeural">Ryan (UK♂)</option>
            <option value="en-AU-NatashaNeural">Natasha (AU♀)</option>
          </select>
          <select id="api-selector" title="Switch AI provider" style="font-size:12px;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:3px 8px;cursor:pointer">
            <option value="deepseek">DeepSeek</option>
            <option value="qwen">Qwen</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Claude</option>
          </select>
          <button class="btn btn-outline" id="btn-voice-call" style="font-size:12px;padding:5px 10px" title="Start voice call">🎙 Voice Call</button>
          <button class="btn btn-outline" id="btn-new-topic" style="font-size:12px;padding:5px 10px">New Topic ↺</button>
        </div>
      </div>
      <div class="chat-messages" id="msgs"></div>
      <div id="voice-call-bar" style="display:none;padding:10px 16px;border-top:1px solid var(--border);background:var(--bg3);text-align:center">
        <span id="call-status" style="font-size:13px;color:var(--accent)">🎙 Listening...</span>
        <button class="btn btn-outline" id="btn-end-call" style="margin-left:12px;font-size:12px;color:var(--red);border-color:var(--red)">End Call</button>
      </div>
      <div id="text-input-area" style="padding:12px 16px;border-top:1px solid var(--border)">
        <div class="chat-input-row">
          <input id="chat-input" type="text" placeholder="Type your message..." autocomplete="off">
          <button class="btn btn-primary" id="btn-send">Send</button>
        </div>
      </div>
    </div>
    <div style="margin-top:12px;text-align:right">
      <button class="btn btn-outline" id="btn-end-chat" style="font-size:12px">End Session</button>
    </div>
  `;

  // Restore display history
  const msgs = body.querySelector('#msgs');
  for (const { role, text } of _displayHistory) {
    _appendMsg(msgs, text, role);
  }

  // Voice selector
  const voiceSel = body.querySelector('#voice-selector');
  voiceSel.value = window._ttsVoice || 'en-US-AriaNeural';
  voiceSel.addEventListener('change', () => { window._ttsVoice = voiceSel.value; });

  // API selector
  const sel = body.querySelector('#api-selector');
  sel.value = _currentBackend;
  sel.addEventListener('change', async () => {
    const prev = _currentBackend;
    try {
      const r = await api.post(`/api/chat/config/${_sid}`, { backend: sel.value });
      if (r.ok) {
        _currentBackend = sel.value;
        _saveSession();
      } else {
        sel.value = prev;
        _appendMsg(msgs, `⚠ ${r.error}`, 'ai');
      }
    } catch { sel.value = prev; }
  });

  const input = body.querySelector('#chat-input');
  const sendBtn = body.querySelector('#btn-send');
  input.focus();
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendBtn.click(); } });
  sendBtn.addEventListener('click', () => sendMessage(el));

  body.querySelector('#btn-new-topic').addEventListener('click', async () => {
    try {
      const r = await api.get(`/api/chat/topic?exam=${_exam}`);
      _appendMsg(msgs, r.topic, 'ai');
      _displayHistory.push({ role: 'ai', text: r.topic });
      _saveSession();
    } catch {}
  });

  body.querySelector('#btn-voice-call').addEventListener('click', () => {
    if (_inCall) stopVoiceCall(body); else startVoiceCall(body);
  });
  body.querySelector('#btn-end-call').addEventListener('click', () => stopVoiceCall(body));

  body.querySelector('#btn-end-chat').addEventListener('click', async () => {
    stopVoiceCall(body);
    _store.clear();
    try { await api.post(`/api/chat/end/${_sid}`, {}); } catch {}
    navigate('home');
  });
}

function _saveSession() {
  try {
    const saved = _store.get() || {};
    saved.display_history = _displayHistory;
    saved.backend = _currentBackend;
    _store.set(saved);
  } catch {}
}

// ── Voice Call ────────────────────────────────────────────────────────────────

async function startVoiceCall(body) {
  if (_inCall) return;
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    _appendMsg(body.querySelector('#msgs'), '⚠ Microphone access denied. Please allow microphone in browser settings.', 'ai');
    return;
  }

  const wsUrl = `ws://${location.host}/api/voice/call/${_sid}`;
  const ws = new WebSocket(wsUrl);
  _voiceCallWs = ws;

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: 'set_voice', voice: window._ttsVoice || 'en-US-AriaNeural' }));
  };

  let isPlayingTTS = false;
  let ttsQueue = [];

  ws.onmessage = async (e) => {
    if (e.data instanceof Blob) {
      ttsQueue.push(e.data);
      if (!isPlayingTTS) playNextTTSChunk();
      return;
    }
    const msg = JSON.parse(e.data);
    const msgs = body.querySelector('#msgs');
    if (msg.type === 'transcript') {
      _appendMsg(msgs, msg.text, 'user');
      setCallStatus('🤔 Thinking...');
    } else if (msg.type === 'response') {
      _appendMsg(msgs, msg.text, 'ai');
      _displayHistory.push({ role: 'ai', text: msg.text });
      _saveSession();
      setCallStatus('🔊 Speaking...');
    } else if (msg.type === 'done') {
      setCallStatus('🎙 Listening...');
    } else if (msg.type === 'error') {
      _appendMsg(msgs, `⚠ ${msg.text}`, 'ai');
    }
  };

  async function playNextTTSChunk() {
    if (ttsQueue.length === 0) { isPlayingTTS = false; return; }
    isPlayingTTS = true;
    const blob = new Blob(ttsQueue.splice(0), { type: 'audio/mpeg' });
    ttsQueue = [];
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    window._ttsAudio = audio;
    audio.onended = () => { URL.revokeObjectURL(url); playNextTTSChunk(); };
    await audio.play().catch(() => {});
  }

  ws.onerror = () => stopVoiceCall(body);
  ws.onclose = () => { if (_inCall) stopVoiceCall(body); };

  const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
  _mediaRecorder = recorder;
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
      e.data.arrayBuffer().then(buf => ws.send(buf));
    }
  };
  recorder.start(2000);

  _inCall = true;
  body.querySelector('#voice-call-bar').style.display = 'block';
  body.querySelector('#text-input-area').style.display = 'none';
  body.querySelector('#btn-voice-call').textContent = '⏹ Stop Call';
  body.querySelector('#btn-voice-call').style.color = 'var(--red)';
  setCallStatus('🎙 Listening...');
}

function stopVoiceCall(body) {
  _inCall = false;
  if (_mediaRecorder) { try { _mediaRecorder.stop(); _mediaRecorder.stream.getTracks().forEach(t => t.stop()); } catch {} _mediaRecorder = null; }
  if (_voiceCallWs) { try { _voiceCallWs.close(); } catch {} _voiceCallWs = null; }
  if (window._ttsAudio) { window._ttsAudio.pause(); window._ttsAudio = null; }
  body.querySelector('#voice-call-bar').style.display = 'none';
  body.querySelector('#text-input-area').style.display = 'block';
  body.querySelector('#btn-voice-call').textContent = '🎙 Voice Call';
  body.querySelector('#btn-voice-call').style.color = '';
}

function setCallStatus(text) {
  const el = document.getElementById('call-status');
  if (el) el.textContent = text;
}

// ── Text chat ─────────────────────────────────────────────────────────────────

async function sendMessage(el) {
  const body = el.querySelector('#chat-body');
  const input = body.querySelector('#chat-input');
  const sendBtn = body.querySelector('#btn-send');
  const msgs = body.querySelector('#msgs');

  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  input.disabled = true;
  sendBtn.disabled = true;

  _appendMsg(msgs, text, 'user');
  _displayHistory.push({ role: 'user', text });

  const typing = document.createElement('div');
  typing.className = 'typing-indicator';
  typing.textContent = 'Coach is typing...';
  msgs.appendChild(typing);
  msgs.scrollTop = msgs.scrollHeight;

  try {
    let response = '';
    await api.stream(`/api/chat/message/${_sid}`, { message: text }, (type, data) => {
      if (type === 'token') response = data;
    });
    typing.remove();
    if (response) {
      _appendMsg(msgs, response, 'ai');
      _displayHistory.push({ role: 'ai', text: response });
      if (_displayHistory.length > 40) _displayHistory = _displayHistory.slice(-40);
      _saveSession();
    }
  } catch (e) {
    typing.remove();
    // Server restarted — session lost, transparently create new one and resend
    if (e.message.includes('404') || e.message.includes('not found') || e.message.includes('Session')) {
      _store.clear();
      input.disabled = false;
      sendBtn.disabled = false;
      input.value = text;
      await startChat(el);
      return;
    }
    _appendMsg(msgs, `Error: ${e.message}`, 'ai');
  }

  input.disabled = false;
  sendBtn.disabled = false;
  input.focus();
}

function _appendMsg(msgs, text, role) {
  const wrap = document.createElement('div');
  wrap.className = `msg msg-${role}`;
  wrap.textContent = text;
  if (role === 'ai') {
    const btn = document.createElement('button');
    btn.className = 'tts-btn';
    btn.title = 'Read aloud';
    btn.textContent = '🔊';
    btn.style.display = 'block';
    btn.style.marginTop = '4px';
    btn.addEventListener('click', () => tts(text));
    wrap.appendChild(btn);
  }
  msgs.appendChild(wrap);
  msgs.scrollTop = msgs.scrollHeight;
}

function escHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

