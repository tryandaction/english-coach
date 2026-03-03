// app.js — client-side router and page loader

const pages = {};
let currentPage = null;

async function loadPage(name) {
  if (!pages[name]) {
    const mod = await import(`/static/pages/${name}.js`);
    pages[name] = mod;
  }
  return pages[name];
}

async function navigate(name) {
  const container = document.getElementById('page-container');
  container.innerHTML = '<div style="padding:40px;text-align:center"><div class="spinner"></div></div>';

  // Update desktop sidebar nav
  document.querySelectorAll('.nav-link').forEach(a => {
    a.classList.toggle('active', a.dataset.page === name);
  });

  // Update mobile bottom nav
  document.querySelectorAll('#mobile-nav .mnav-btn[data-page]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.page === name);
  });
  // Update more drawer items
  document.querySelectorAll('#mobile-more-drawer .more-item').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.page === name);
  });

  try {
    const mod = await loadPage(name);
    container.innerHTML = '';
    await mod.render(container);
    currentPage = name;
    // Scroll content to top on page change
    const content = document.getElementById('content');
    if (content) content.scrollTop = 0;
  } catch (e) {
    container.innerHTML = `<div class="alert alert-error">Failed to load page: ${e.message}</div>`;
    console.error(e);
  }
}

// Desktop sidebar nav click handler
document.querySelectorAll('.nav-link[data-page]').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    navigate(a.dataset.page);
  });
});

// Mobile bottom nav click handler
document.querySelectorAll('#mobile-nav .mnav-btn[data-page]').forEach(btn => {
  btn.addEventListener('click', () => navigate(btn.dataset.page));
});

// Mobile "More" drawer toggle
const _moreBtn     = document.getElementById('mnav-more-btn');
const _moreDrawer  = document.getElementById('mobile-more-drawer');
const _moreOverlay = document.getElementById('mobile-more-drawer-overlay');

function _openMoreDrawer() {
  _moreDrawer.style.display  = 'block';
  _moreOverlay.style.display = 'block';
}
function _closeMoreDrawer() {
  _moreDrawer.style.display  = 'none';
  _moreOverlay.style.display = 'none';
}

if (_moreBtn) {
  _moreBtn.addEventListener('click', () => {
    _moreDrawer.style.display === 'block' ? _closeMoreDrawer() : _openMoreDrawer();
  });
}
if (_moreOverlay) _moreOverlay.addEventListener('click', _closeMoreDrawer);

document.querySelectorAll('#mobile-more-drawer .more-item').forEach(btn => {
  btn.addEventListener('click', () => {
    _closeMoreDrawer();
    navigate(btn.dataset.page);
  });
});

// API helpers
window.api = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `API error ${r.status}`);
    }
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `API error ${r.status}`);
    }
    return r.json();
  },
  // SSE helper: calls onEvent(type, data) for each event, returns when done
  async stream(path, body, onEvent) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`API error ${r.status}`);
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const { type, data } = JSON.parse(line.slice(6));
            onEvent(type, data);
            if (type === 'done' || type === 'error') return;
          } catch {}
        }
      }
    }
  },
};

// Global TTS helper — uses edge-tts backend for quality, falls back to Web Speech API
window._ttsVoice = localStorage.getItem('ttsVoice') || 'en-US-AriaNeural';
window._ttsRate  = localStorage.getItem('ttsRate')  || '-10%';
window._ttsAudio = null;
window._ttsCache = new Map();

// Preload audio for short texts to eliminate click-to-play latency
window.ttsPreload = function(text) {
  if (!text || text.length > 200) return;
  if (window._ttsCache.has(text)) return;
  const url = `/api/voice/tts?text=${encodeURIComponent(text)}&voice=${encodeURIComponent(window._ttsVoice)}&rate=${encodeURIComponent(window._ttsRate)}`;
  const audio = new Audio(url);
  audio.preload = 'auto';
  window._ttsCache.set(text, audio);
};

window.tts = function(text, lang = 'en-US') {
  // Stop any playing audio
  if (window._ttsAudio) { window._ttsAudio.pause(); window._ttsAudio = null; }
  if (window.speechSynthesis) window.speechSynthesis.cancel();

  // Check preload cache first
  const cached = window._ttsCache.get(text);
  if (cached) {
    cached.currentTime = 0;
    window._ttsAudio = cached;
    cached.play().catch(() => {});
    return;
  }

  // Try edge-tts backend
  const url = `/api/voice/tts?text=${encodeURIComponent(text)}&voice=${encodeURIComponent(window._ttsVoice)}&rate=${encodeURIComponent(window._ttsRate)}`;
  const audio = new Audio(url);
  window._ttsAudio = audio;
  audio.play().catch(() => {
    // Fallback to Web Speech API
    if (!window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang; u.rate = 0.9;
    window.speechSynthesis.speak(u);
  });
};

// Global error helper with optional retry button
window.renderError = function(container, message, retryFn) {
  container.innerHTML = `
    <div class="error-with-retry">
      <span>${message}</span>
      ${retryFn ? '<button class="retry-btn" id="err-retry">Retry ↺</button>' : ''}
    </div>`;
  if (retryFn) container.querySelector('#err-retry').addEventListener('click', retryFn);
};

function setStartupMsg(msg) {
  const el = document.getElementById('startup-msg');
  if (el) el.textContent = msg;
}

function hideOverlay() {
  const overlay = document.getElementById('startup-overlay');
  if (!overlay) return;
  overlay.classList.add('hidden');
  setTimeout(() => overlay.remove(), 450);
}

// Check setup on load
async function init() {
  setStartupMsg('Checking configuration…');
  let licStatus = { active: false };
  try {
    const status = await api.get('/api/setup/status');
    if (!status.configured) {
      hideOverlay();
      navigate('setup');
      return;
    }
  } catch (e) {}
  try {
    licStatus = await api.get('/api/license/status');
    const licLink = document.querySelector('[data-page="license"]');
    if (licLink) {
      const dot = document.createElement('span');
      dot.className = `nav-status-dot ${licStatus.active ? 'active' : 'inactive'}`;
      licLink.appendChild(dot);
    }
  } catch {}
  // Hide overlay and navigate immediately — don't wait for preload
  hideOverlay();
  navigate('home');
  // Defer all background work well after UI is visible
  setTimeout(() => _preloadContent(licStatus), 3000);
  if (licStatus.active) {
    setTimeout(() => {
      fetch('/api/warehouse/populate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).catch(() => {});
    }, 15000);
  }
}

// Pre-load reading and writing content into localStorage so pages open instantly
async function _preloadContent(licStatus) {
  // Reading — pre-load a passage if none cached
  if (!localStorage.getItem('reading_current')) {
    try {
      const r = await fetch('/api/reading/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (r.ok) {
        const data = await r.json();
        if (data.session_id) {
          localStorage.setItem('reading_current', JSON.stringify({ ...data, q_index: 0, correct: 0 }));
        }
      }
    } catch {}
  }
  // Writing — pre-load a prompt if none cached
  if (!localStorage.getItem('writing_current')) {
    try {
      const r = await fetch('/api/writing/prompt');
      if (r.ok) {
        const data = await r.json();
        if (data.prompt) localStorage.setItem('writing_current', JSON.stringify(data));
      }
    } catch {}
  }
  // Chat — pre-load a session if AI is available and none cached
  if (!localStorage.getItem('chat_current') && licStatus.active) {
    try {
      const r = await fetch('/api/chat/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (r.ok) {
        const data = await r.json();
        if (data.session_id) {
          localStorage.setItem('chat_current', JSON.stringify({
            session_id: data.session_id,
            exam: data.exam,
            backend: data.backend,
            display_history: [{ role: 'ai', text: data.opener }],
          }));
        }
      }
    } catch {}
  }
}

init();
