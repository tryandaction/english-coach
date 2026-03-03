// pages/vocab.js — Unified Vocabulary: flashcards + word books

// ── Shared state ──────────────────────────────────────────────────
let _sid = null, _total = 0, _remaining = 0, _revealed = false;
let _keyHandler = null;
let _exam = 'general', _wordListLabel = '';
let _currentTab = 'study';
let _currentBook = null;
let _allWords = [];
let _searchTimeout = null;
let _autoTts = localStorage.getItem('autoTts') !== 'false';
let _cardContainer = null;

const _vocabStore = {
  get: () => { try { return JSON.parse(localStorage.getItem('vocab_session')); } catch { return null; } },
  set: (v) => { try { localStorage.setItem('vocab_session', JSON.stringify(v)); } catch {} },
  clear: () => { try { localStorage.removeItem('vocab_session'); } catch {} },
};

function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Entry point ───────────────────────────────────────────────────

export async function render(el) {
  _sid = null; _revealed = false; _currentBook = null;
  _currentTab = 'study';
  renderShell(el);
  api.post('/api/vocab/ingest_builtin', {}).catch(() => {});
  await showTab(el, 'study');
}

function renderShell(el) {
  el.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <h1 style="margin:0">🃏 Vocabulary</h1>
    </div>
    <div class="tab-bar" style="display:flex;gap:4px;margin-bottom:20px;border-bottom:1px solid var(--border);padding-bottom:0">
      <button class="tab-btn active" data-tab="study" style="padding:8px 18px;border:none;background:none;cursor:pointer;font-size:14px;border-bottom:2px solid var(--accent);color:var(--accent);font-weight:600">▶ Study</button>
      <button class="tab-btn" data-tab="books" style="padding:8px 18px;border:none;background:none;cursor:pointer;font-size:14px;border-bottom:2px solid transparent;color:var(--text-dim)">📚 My Books</button>
      <button class="tab-btn" data-tab="add" style="padding:8px 18px;border:none;background:none;cursor:pointer;font-size:14px;border-bottom:2px solid transparent;color:var(--text-dim)">+ Add Word</button>
    </div>
    <div id="vocab-tab-content"></div>
  `;
  el.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.tab === _currentTab) return;
      showTab(el, btn.dataset.tab);
    });
  });
}

function setActiveTab(el, tab) {
  _currentTab = tab;
  el.querySelectorAll('.tab-btn').forEach(btn => {
    const active = btn.dataset.tab === tab;
    btn.style.borderBottomColor = active ? 'var(--accent)' : 'transparent';
    btn.style.color = active ? 'var(--accent)' : 'var(--text-dim)';
    btn.style.fontWeight = active ? '600' : '400';
  });
}

async function showTab(el, tab) {
  if (_keyHandler) { document.removeEventListener('keydown', _keyHandler); _keyHandler = null; }
  setActiveTab(el, tab);
  const content = el.querySelector('#vocab-tab-content');
  if (tab === 'study') await renderStudyTab(el, content);
  else if (tab === 'books') await renderBooksTab(el, content);
  else if (tab === 'add') renderAddTab(el, content);
}

// ── STUDY TAB ─────────────────────────────────────────────────────

async function renderStudyTab(el, content) {
  content.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div></div>';

  // If user has a recently studied book, go straight into it
  const lastBookId = localStorage.getItem('lastStudiedBookId');
  if (lastBookId) {
    try {
      const books = await api.get('/api/wordbooks');
      const book = books.find(b => b.book_id === lastBookId);
      if (book) { await startBookSession(el, content, book); return; }
    } catch {}
  }

  // Restore in-progress session (navigate-back)
  const saved = _vocabStore.get();
  if (saved && saved.session_id) {
    _sid = saved.session_id;
    _total = saved.total;
    _remaining = saved.remaining;
    _exam = saved.exam || 'general';
    _wordListLabel = saved.word_list_label || '';

    const ttsToggle = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;font-size:13px;color:var(--text-dim)">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
          <input type="checkbox" id="auto-tts-toggle" ${_autoTts ? 'checked' : ''} style="width:auto">
          🔊 Auto-read word on flip
        </label>
      </div>`;
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = ttsToggle;
    content.innerHTML = '';
    content.appendChild(tempDiv);
    const cardDiv = document.createElement('div');
    _cardContainer = cardDiv;
    content.appendChild(cardDiv);
    renderCard(el, cardDiv, saved.card, false);
    content.querySelector('#auto-tts-toggle')?.addEventListener('change', e => {
      _autoTts = e.target.checked;
      localStorage.setItem('autoTts', _autoTts);
    });
    if (saved.card) { ttsPreload && ttsPreload(saved.card.word); }
    return;
  }

  try {
    const r = await api.post('/api/vocab/start', { max_cards: 20 });
    if (r.empty) {
      let stats = {};
      try { stats = await api.get('/api/vocab/stats'); } catch {}
      content.innerHTML = `
        <div class="alert alert-success">🎉 No cards due today! Come back tomorrow.</div>
        ${stats.total === 0 ? `
        <div class="card" style="text-align:center;padding:32px;margin-top:16px">
          <div style="font-size:40px;margin-bottom:12px">📭</div>
          <h3 style="margin-bottom:8px">Your deck is empty</h3>
          <p style="color:var(--text-dim);margin-bottom:20px">Add words or browse a word book to get started.</p>
          <div style="display:flex;gap:10px;justify-content:center">
            <button class="btn btn-primary" id="btn-go-add">+ Add Word</button>
            <button class="btn btn-outline" id="btn-go-books">📚 My Books</button>
          </div>
        </div>` : `
        <div style="display:flex;gap:16px;margin-top:16px;flex-wrap:wrap">
          <div class="card" style="flex:1;min-width:100px;text-align:center;padding:16px">
            <div style="font-size:24px;font-weight:700">${stats.total || 0}</div>
            <div style="font-size:12px;color:var(--text-dim)">Total words</div>
          </div>
          <div class="card" style="flex:1;min-width:100px;text-align:center;padding:16px">
            <div style="font-size:24px;font-weight:700">${stats.mature || 0}</div>
            <div style="font-size:12px;color:var(--text-dim)">Mature</div>
          </div>
        </div>`}
        <button class="btn btn-outline" onclick="navigate('home')" style="margin-top:16px">← Back to Home</button>
      `;
      content.querySelector('#btn-go-add')?.addEventListener('click', () => showTab(el, 'add'));
      content.querySelector('#btn-go-books')?.addEventListener('click', () => showTab(el, 'books'));
      return;
    }
    _sid = r.session_id; _total = r.total; _remaining = r.remaining;
    _exam = r.exam || 'general'; _wordListLabel = r.word_list_label || '';
    // Save session for navigate-back restore
    _vocabStore.set({ session_id: _sid, total: _total, remaining: _remaining,
                      exam: _exam, word_list_label: _wordListLabel, card: r.card });

    const ttsToggle = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;font-size:13px;color:var(--text-dim)">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
          <input type="checkbox" id="auto-tts-toggle" ${_autoTts ? 'checked' : ''} style="width:auto">
          🔊 Auto-read word on flip
        </label>
      </div>`;

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = ttsToggle;
    content.innerHTML = '';
    content.appendChild(tempDiv);

    const cardDiv = document.createElement('div');
    _cardContainer = cardDiv;
    content.appendChild(cardDiv);
    renderCard(el, cardDiv, r.card, false);

    content.querySelector('#auto-tts-toggle')?.addEventListener('change', e => {
      _autoTts = e.target.checked;
      localStorage.setItem('autoTts', _autoTts);
    });

    if (r.card) { ttsPreload && ttsPreload(r.card.word); }
  } catch (e) {
    if (e.message.includes('profile') || e.message.includes('Profile') || e.message.includes('No profile')) {
      content.innerHTML = `
        <div class="card" style="text-align:center;padding:40px">
          <div style="font-size:40px;margin-bottom:12px">⚙️</div>
          <h3 style="margin-bottom:8px">Setup Required</h3>
          <p style="color:var(--text-dim);margin-bottom:20px">Please complete setup before using Vocabulary.</p>
          <button class="btn btn-primary" onclick="navigate('setup')">Go to Setup →</button>
        </div>`;
    } else {
      content.innerHTML = `<div class="alert alert-error">${e.message} <button class="btn btn-outline" style="margin-left:8px" id="btn-retry">Retry ↺</button></div>`;
      content.querySelector('#btn-retry')?.addEventListener('click', () => renderStudyTab(el, content));
    }
  }
}

function renderCard(el, content, card, revealed) {
  _revealed = revealed;
  const done = _total - _remaining;
  const pct = Math.round((done / _total) * 100);
  const sourceLabel = card.source_label || _wordListLabel || '';
  const examBadge = _exam && _exam !== 'general'
    ? `<span class="exam-badge exam-${_exam}">${_exam.toUpperCase()}</span>` : '';

  content.innerHTML = `
    <div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:${pct}%"></div></div>
    <div style="display:flex;align-items:center;justify-content:space-between;font-size:13px;color:var(--text-dim);margin-bottom:16px">
      <span>${done} / ${_total} cards</span>
      ${sourceLabel ? `<span style="font-size:12px">${examBadge} ${escHtml(sourceLabel)}</span>` : examBadge}
    </div>
    <div class="flashcard-wrap">
      <div class="flashcard${revealed ? ' flipped' : ''}" id="fc">
        <div class="flashcard-front">
          <div style="position:absolute;top:12px;right:12px">${examBadge}</div>
          <div class="flashcard-word">${escHtml(card.word)} <button class="tts-btn" onclick="event.stopPropagation();tts('${card.word.replace(/'/g,"\\'")}')">🔊</button></div>
          ${card.part_of_speech ? `<div class="flashcard-pos">${escHtml(card.part_of_speech)}</div>` : ''}
          ${card.pronunciation ? `<div class="flashcard-pron">${escHtml(card.pronunciation)}</div>` : ''}
          ${card.is_new ? '<div class="tag tag-green" style="margin-top:12px">NEW</div>' : ''}
          <div class="flashcard-hint">Click or Space to flip · Click again to flip back</div>
        </div>
        <div class="flashcard-back" id="fc-back">
          <div class="def-en">${escHtml(card.definition_en || '')}</div>
          <div class="def-zh">${escHtml(card.definition_zh || '')}</div>
          ${card.example ? `<div class="example">"${escHtml(card.example)}" <button class="tts-btn" onclick="tts('${card.example.replace(/'/g,"\\'").replace(/"/g,'&quot;')}')">🔊</button></div>` : ''}
        </div>
      </div>
    </div>
    <div id="rating-area" class="${revealed ? '' : 'hidden'}" style="text-align:center">
      <p style="margin-bottom:8px;font-size:13px;color:var(--text-dim)">How well did you know it?</p>
      <div class="rating-bar">
        <button class="rating-btn" data-q="1" title="Forgot">1</button>
        <button class="rating-btn" data-q="2" title="Hard">2</button>
        <button class="rating-btn" data-q="3" title="OK">3</button>
        <button class="rating-btn" data-q="4" title="Good">4</button>
        <button class="rating-btn" data-q="5" title="Easy">5</button>
      </div>
      <div style="display:flex;justify-content:center;gap:20px;margin-top:8px;font-size:11px;color:var(--text-dim)">
        <span>1=Forgot</span><span>3=OK</span><span>5=Easy</span><span style="margin-left:8px">Keys 1–5 to rate</span>
      </div>
      <div id="tag-bar" style="display:flex;justify-content:center;gap:8px;margin-top:12px;flex-wrap:wrap"></div>
    </div>
  `;

  const fc = content.querySelector('#fc');
  fc.addEventListener('click', async () => {
    if (_revealed) {
      // flip back to front
      fc.classList.remove('flipped');
      _revealed = false;
      content.querySelector('#rating-area').classList.add('hidden');
      return;
    }
    fc.classList.add('flipped'); _revealed = true;
    try {
      const detail = await api.post(`/api/vocab/reveal/${_sid}`, {});
      const back = content.querySelector('#fc-back');
      const sl = detail.source_label || sourceLabel;
      back.innerHTML = `
        <div class="def-en">${escHtml(detail.definition_en || '')}</div>
        <div class="def-zh">${escHtml(detail.definition_zh || '')}</div>
        ${detail.example ? `<div class="example">"${escHtml(detail.example)}" <button class="tts-btn" onclick="tts('${detail.example.replace(/'/g,"\\'").replace(/"/g,'&quot;')}')">🔊</button></div>` : ''}
        ${detail.context_sentence ? `<div class="field"><span class="tag" style="margin-bottom:4px">Context</span><br>${escHtml(detail.context_sentence)}</div>` : ''}
        ${detail.synonyms ? `<div class="field" style="margin-top:8px"><span style="color:var(--text-dim)">Synonyms: </span>${escHtml(detail.synonyms)}</div>` : ''}
        ${detail.antonyms ? `<div class="field"><span style="color:var(--text-dim)">Antonyms: </span>${escHtml(detail.antonyms)}</div>` : ''}
        ${detail.collocations ? `<div class="field"><span style="color:var(--text-dim)">Collocations: </span>${escHtml(detail.collocations)}</div>` : ''}
        ${detail.derivatives ? `<div class="field"><span style="color:var(--text-dim)">Derivatives: </span>${escHtml(detail.derivatives)}</div>` : ''}
        ${sl ? `<div style="margin-top:12px;font-size:11px;color:var(--text-dim);text-align:right">${escHtml(sl)}</div>` : ''}
      `;
      if (_autoTts && detail.word) tts(detail.word);
      else if (detail.example) ttsPreload && ttsPreload(detail.example);
      if (detail.word_id) renderTagBar(content.querySelector('#tag-bar'), detail.word_id);
    } catch {}
    content.querySelector('#rating-area').classList.remove('hidden');
  });

  content.querySelectorAll('.rating-btn').forEach(btn => {
    btn.addEventListener('click', () => rateCard(el, content, parseInt(btn.dataset.q)));
  });

  if (_keyHandler) document.removeEventListener('keydown', _keyHandler);
  _keyHandler = (e) => {
    if (e.code === 'Space') { e.preventDefault(); content.querySelector('#fc')?.click(); }
    else if (_revealed && e.key >= '1' && e.key <= '5') {
      const btn = content.querySelector(`.rating-btn[data-q="${e.key}"]`);
      if (btn && !btn.disabled) btn.click();
    }
  };
  document.addEventListener('keydown', _keyHandler);
}

// ── Tag bar ───────────────────────────────────────────────────────

const _TAG_DEFS = [
  { tag: 'star',      label: '⭐ Star',      title: 'Favourite' },
  { tag: 'error',     label: '❌ Error',     title: 'Error-prone' },
  { tag: 'writing',   label: '✍️ Writing',   title: 'Writing collection' },
  { tag: 'listening', label: '🎧 Listen',    title: 'Listening collection' },
];

async function renderTagBar(barEl, wordId) {
  if (!barEl || !wordId) return;
  let activeTags = new Set();
  try {
    const r = await api.get(`/api/vocab/tags/${wordId}`);
    activeTags = new Set(r.tags || []);
  } catch {}

  barEl.innerHTML = _TAG_DEFS.map(t => `
    <button class="tag-toggle-btn" data-tag="${t.tag}" data-word-id="${wordId}"
      title="${t.title}"
      style="padding:4px 10px;border-radius:20px;border:1px solid var(--border);
             background:${activeTags.has(t.tag) ? 'var(--accent)' : 'var(--bg3)'};
             color:${activeTags.has(t.tag) ? '#fff' : 'var(--text-dim)'};
             font-size:12px;cursor:pointer;transition:all .15s">
      ${t.label}
    </button>`).join('');

  barEl.querySelectorAll('.tag-toggle-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const tag = btn.dataset.tag;
      const wid = btn.dataset.wordId;
      const isActive = btn.style.background.includes('accent') || activeTags.has(tag);
      const newActive = !isActive;
      try {
        await api.post('/api/vocab/tag', { word_id: wid, tag, active: newActive });
        if (newActive) activeTags.add(tag); else activeTags.delete(tag);
        btn.style.background = newActive ? 'var(--accent)' : 'var(--bg3)';
        btn.style.color = newActive ? '#fff' : 'var(--text-dim)';
      } catch {}
    });
  });
}

async function rateCard(el, content, quality) {
  content.querySelectorAll('.rating-btn').forEach(b => b.disabled = true);
  try {
    const r = await api.post(`/api/vocab/rate/${_sid}`, { quality });
    if (r.complete) {
      _vocabStore.clear();
      showComplete(el, content, r.stats);
    } else {
      _remaining = r.remaining;
      _vocabStore.set({ session_id: _sid, total: _total, remaining: _remaining,
                        exam: _exam, word_list_label: _wordListLabel, card: r.card });
      renderCard(el, content, r.card, false);
      if (r.card) { ttsPreload && ttsPreload(r.card.word); if (r.card.example) ttsPreload && ttsPreload(r.card.example); }
    }
  } catch (e) { console.error(e); }
}

function showComplete(el, content, stats) {
  if (_keyHandler) { document.removeEventListener('keydown', _keyHandler); _keyHandler = null; }
  const color = stats.accuracy >= 80 ? 'var(--green)' : stats.accuracy >= 60 ? 'var(--yellow)' : 'var(--red)';
  content.innerHTML = `
    <div class="card" style="text-align:center;padding:40px">
      <div style="font-size:48px;margin-bottom:16px">🎉</div>
      <h2>Session Complete!</h2>
      <div style="font-size:36px;font-weight:700;color:${color};margin:16px 0">${stats.accuracy}%</div>
      <p>${stats.correct} / ${stats.reviewed} correct</p>
      <div style="display:flex;gap:12px;justify-content:center;margin-top:24px">
        <button class="btn btn-primary" id="btn-again">Study Again</button>
        <button class="btn btn-outline" onclick="navigate('home')">← Home</button>
      </div>
    </div>
  `;
  content.querySelector('#btn-again').addEventListener('click', () => renderStudyTab(el, content));
}

// ── BOOKS TAB ─────────────────────────────────────────────────────

const ICONS  = ['📖','📝','🧠','⭐','🔥','💡','🎯','🌟','📌','🏆','🌈','🔬','🎓','💬','🗂'];
const COLORS = ['#4f8ef7','#7c5cfc','#3ecf8e','#f5c842','#f26b6b','#f97316','#06b6d4','#ec4899','#a855f7','#84cc16'];

async function renderBooksTab(el, content) {
  _currentBook = null;
  content.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
      <span style="color:var(--text-dim);font-size:14px">Custom vocabulary collections with spaced repetition</span>
      <button class="btn btn-primary" id="btn-create-book">+ New Book</button>
    </div>
    <div id="books-list"><div style="text-align:center;padding:40px"><div class="spinner"></div></div></div>
  `;
  content.querySelector('#btn-create-book').addEventListener('click', () => showBookModal(el, content, null));
  await loadBookList(el, content);
}

async function loadBookList(el, content) {
  const container = content.querySelector('#books-list');
  if (!container) return;
  try {
    const books = await api.get('/api/wordbooks');
    if (!books.length) {
      container.innerHTML = `
        <div class="card" style="text-align:center;padding:40px">
          <div style="font-size:48px;margin-bottom:12px">📭</div>
          <h3 style="margin-bottom:8px">No word books yet</h3>
          <p style="color:var(--text-dim);margin-bottom:20px">Create custom collections — like Anki decks — with AI enrichment.</p>
          <button class="btn btn-primary" id="btn-create-first">+ Create Word Book</button>
        </div>`;
      container.querySelector('#btn-create-first').addEventListener('click', () => showBookModal(el, content, null));
      return;
    }
    container.innerHTML = `<div class="book-grid">${books.map(b => bookCard(b)).join('')}</div>`;
    container.querySelectorAll('.book-card').forEach(card => {
      const book = books.find(b => b.book_id === card.dataset.bookId);
      card.querySelector('.btn-book-open').addEventListener('click', () => showBookDetail(el, content, book));
      card.querySelector('.btn-book-edit').addEventListener('click', e => { e.stopPropagation(); showBookModal(el, content, book); });
      card.querySelector('.btn-book-delete').addEventListener('click', e => { e.stopPropagation(); confirmDeleteBook(el, content, book); });
      card.querySelector('.btn-book-study').addEventListener('click', e => { e.stopPropagation(); startBookSession(el, content, book); });
    });
  } catch (e) {
    if (e.message.includes('profile') || e.message.includes('No profile')) {
      container.innerHTML = `<div class="card" style="text-align:center;padding:40px"><div style="font-size:40px;margin-bottom:12px">⚙️</div><h3>Setup Required</h3><button class="btn btn-primary" onclick="navigate('setup')">Go to Setup →</button></div>`;
    } else {
      container.innerHTML = `<div class="alert alert-error">${e.message} <button class="btn btn-outline" style="margin-left:8px" id="btn-retry-wb">Retry ↺</button></div>`;
      container.querySelector('#btn-retry-wb')?.addEventListener('click', () => loadBookList(el, content));
    }
  }
}

function bookCard(b) {
  const due = b.due_today || 0;
  const dueBadge = due > 0
    ? `<span style="background:var(--accent);color:#fff;border-radius:12px;padding:2px 8px;font-size:11px;font-weight:700">${due} due</span>`
    : `<span style="color:var(--text-dim);font-size:11px">0 due</span>`;
  return `
    <div class="book-card card" data-book-id="${b.book_id}" style="padding:20px;position:relative">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px">
        <div style="display:flex;align-items:center;gap:10px">
          <span style="font-size:28px">${b.icon}</span>
          <div>
            <div style="font-weight:700;font-size:15px">${escHtml(b.name)}</div>
            ${b.description ? `<div style="font-size:12px;color:var(--text-dim);margin-top:2px">${escHtml(b.description)}</div>` : ''}
          </div>
        </div>
        <div style="display:flex;gap:6px">
          <button class="btn btn-outline btn-book-edit" style="font-size:11px;padding:3px 8px">✏️</button>
          <button class="btn btn-outline btn-book-delete" style="font-size:11px;padding:3px 8px;color:var(--red)">🗑</button>
        </div>
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;gap:12px;font-size:13px">
          <span><strong>${b.word_count || 0}</strong> <span style="color:var(--text-dim)">words</span></span>
          ${dueBadge}
        </div>
        <div style="display:flex;gap:6px">
          <button class="btn btn-outline btn-book-open" style="font-size:12px;padding:4px 10px">Browse</button>
          <button class="btn btn-primary btn-book-study" style="font-size:12px;padding:4px 10px">Study ▶</button>
        </div>
      </div>
      <div style="position:absolute;bottom:0;left:0;right:0;height:3px;border-radius:0 0 var(--radius) var(--radius);background:${b.color}"></div>
    </div>`;
}

// ── Book Modal (create/edit) ───────────────────────────────────────

function showBookModal(el, content, book, onSave) {
  const isEdit = !!book;
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal-box" style="max-width:440px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
        <h3 style="margin:0">${isEdit ? 'Edit Word Book' : 'New Word Book'}</h3>
        <button class="btn btn-outline" id="modal-close" style="padding:4px 10px">✕</button>
      </div>
      <div class="form-group"><label>Name</label><input id="book-name" type="text" placeholder="e.g. TOEFL Vocabulary" value="${isEdit ? escHtml(book.name) : ''}"></div>
      <div class="form-group"><label>Description <span style="color:var(--text-dim)">(optional)</span></label><input id="book-desc" type="text" placeholder="e.g. Words for TOEFL exam prep" value="${isEdit ? escHtml(book.description || '') : ''}"></div>
      <div class="form-group"><label>Icon</label>
        <div id="icon-picker" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">
          ${ICONS.map(ic => `<button class="icon-opt${(isEdit ? book.icon === ic : ic === '📖') ? ' selected' : ''}" data-icon="${ic}" style="font-size:20px;padding:6px 8px;border-radius:8px;border:2px solid ${(isEdit ? book.icon === ic : ic === '📖') ? 'var(--accent)' : 'transparent'};background:var(--bg3);cursor:pointer">${ic}</button>`).join('')}
        </div>
      </div>
      <div class="form-group"><label>Color</label>
        <div id="color-picker" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">
          ${COLORS.map(c => `<button class="color-opt" data-color="${c}" style="width:28px;height:28px;border-radius:50%;background:${c};border:3px solid ${(isEdit ? book.color === c : c === '#4f8ef7') ? '#fff' : 'transparent'};cursor:pointer"></button>`).join('')}
        </div>
      </div>
      <div id="modal-msg" style="min-height:20px;margin-bottom:8px"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-outline" id="modal-cancel">Cancel</button>
        <button class="btn btn-primary" id="modal-save">${isEdit ? 'Save Changes' : 'Create Book'}</button>
      </div>
    </div>`;
  document.body.appendChild(modal);

  let selectedIcon = isEdit ? book.icon : '📖';
  let selectedColor = isEdit ? book.color : '#4f8ef7';

  modal.querySelectorAll('.icon-opt').forEach(btn => {
    btn.addEventListener('click', () => {
      modal.querySelectorAll('.icon-opt').forEach(b => { b.classList.remove('selected'); b.style.borderColor = 'transparent'; });
      btn.classList.add('selected'); btn.style.borderColor = 'var(--accent)';
      selectedIcon = btn.dataset.icon;
    });
  });
  modal.querySelectorAll('.color-opt').forEach(btn => {
    btn.addEventListener('click', () => {
      modal.querySelectorAll('.color-opt').forEach(b => b.style.borderColor = 'transparent');
      btn.style.borderColor = '#fff';
      selectedColor = btn.dataset.color;
    });
  });

  const close = () => modal.remove();
  modal.querySelector('#modal-close').addEventListener('click', close);
  modal.querySelector('#modal-cancel').addEventListener('click', close);
  modal.addEventListener('click', e => { if (e.target === modal) close(); });

  modal.querySelector('#modal-save').addEventListener('click', async () => {
    const name = modal.querySelector('#book-name').value.trim();
    const desc = modal.querySelector('#book-desc').value.trim();
    const msg = modal.querySelector('#modal-msg');
    if (!name) { msg.innerHTML = '<div class="alert alert-error" style="margin:0">Name is required</div>'; return; }
    const saveBtn = modal.querySelector('#modal-save');
    saveBtn.disabled = true;
    try {
      if (isEdit) {
        await fetch(`/api/wordbooks/${book.book_id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, description: desc, color: selectedColor, icon: selectedIcon }) });
      } else {
        await api.post('/api/wordbooks', { name, description: desc, color: selectedColor, icon: selectedIcon });
      }
      close();
      if (onSave) await onSave(); else await renderBooksTab(el, content);
    } catch (e) { msg.innerHTML = `<div class="alert alert-error" style="margin:0">${e.message}</div>`; saveBtn.disabled = false; }
  });
  modal.querySelector('#book-name').focus();
}

function confirmDeleteBook(el, content, book) {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal-box" style="max-width:380px;text-align:center">
      <div style="font-size:40px;margin-bottom:12px">🗑</div>
      <h3 style="margin-bottom:8px">Delete "${escHtml(book.name)}"?</h3>
      <p style="color:var(--text-dim);margin-bottom:20px">Words in your SRS deck will not be deleted.</p>
      <div style="display:flex;gap:8px;justify-content:center">
        <button class="btn btn-outline" id="del-cancel">Cancel</button>
        <button class="btn" style="background:var(--red);color:#fff" id="del-confirm">Delete</button>
      </div>
    </div>`;
  document.body.appendChild(modal);
  const close = () => modal.remove();
  modal.querySelector('#del-cancel').addEventListener('click', close);
  modal.addEventListener('click', e => { if (e.target === modal) close(); });
  modal.querySelector('#del-confirm').addEventListener('click', async () => {
    try { await fetch(`/api/wordbooks/${book.book_id}`, { method: 'DELETE' }); } catch {}
    close();
    await renderBooksTab(el, content);
  });
}

// ── Book Detail ───────────────────────────────────────────────────

async function showBookDetail(el, content, book) {
  _currentBook = book;
  content.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px">
      <button class="btn btn-outline" id="btn-back" style="font-size:12px;padding:4px 10px">← Books</button>
      <span style="font-size:24px">${book.icon}</span>
      <h2 style="margin:0">${escHtml(book.name)}</h2>
    </div>
    ${book.description ? `<p style="color:var(--text-dim);margin-bottom:12px">${escHtml(book.description)}</p>` : '<div style="margin-bottom:12px"></div>'}
    <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">
      <button class="btn btn-primary" id="btn-study-book">▶ Study Now</button>
      <button class="btn btn-outline" id="btn-add-word-book">+ Add Word</button>
      <button class="btn btn-outline" id="btn-edit-book" style="margin-left:auto">✏️ Edit</button>
    </div>
    <div id="book-stats-row" style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap"></div>
    <input id="word-filter" type="text" placeholder="Filter words…" style="width:100%;max-width:320px;margin-bottom:12px">
    <div id="book-words-container"><div style="text-align:center;padding:40px"><div class="spinner"></div></div></div>
    <div id="add-word-panel-book" style="display:none"></div>
  `;
  content.querySelector('#btn-back').addEventListener('click', () => renderBooksTab(el, content));
  content.querySelector('#btn-study-book').addEventListener('click', () => startBookSession(el, content, book));
  content.querySelector('#btn-add-word-book').addEventListener('click', () => showAddWordPanel(content, book, el));
  content.querySelector('#btn-edit-book').addEventListener('click', () => showBookModal(el, content, book));
  let filterTimer = null;
  content.querySelector('#word-filter').addEventListener('input', e => {
    clearTimeout(filterTimer);
    filterTimer = setTimeout(() => renderWordList(content, book, e.target.value.trim()), 200);
  });
  try {
    const data = await api.get(`/api/wordbooks/${book.book_id}/words`);
    _currentBook = data.book;
    const row = content.querySelector('#book-stats-row');
    row.innerHTML = `
      <div class="card" style="flex:1;min-width:90px;text-align:center;padding:14px">
        <div style="font-size:22px;font-weight:700">${data.book.word_count || 0}</div>
        <div style="font-size:11px;color:var(--text-dim)">Total words</div>
      </div>
      <div class="card" style="flex:1;min-width:90px;text-align:center;padding:14px">
        <div style="font-size:22px;font-weight:700">${data.book.due_today || 0}</div>
        <div style="font-size:11px;color:var(--text-dim)">Due today</div>
      </div>`;
    renderWordList(content, book, '', data.words);
  } catch (e) {
    content.querySelector('#book-words-container').innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

function proficiencyDot(interval) {
  // interval (days): 0=new, 1-3=learning, 4-14=young, 15+=mature
  if (!interval || interval === 0) return { color: '#888', label: 'New' };
  if (interval < 4)  return { color: '#f5c842', label: 'Learning' };
  if (interval < 15) return { color: '#4f8ef7', label: 'Young' };
  return { color: '#3ecf8e', label: 'Mature' };
}

function renderWordList(content, book, filter, words) {
  if (words !== undefined) _allWords = words;
  const container = content.querySelector('#book-words-container');
  if (!container) return;
  const list = filter
    ? _allWords.filter(w => w.word.toLowerCase().includes(filter.toLowerCase()) || (w.definition_en || '').toLowerCase().includes(filter.toLowerCase()))
    : _allWords;
  if (!list.length) {
    container.innerHTML = filter
      ? `<div style="color:var(--text-dim);padding:20px 0">No words match "${escHtml(filter)}"</div>`
      : `<div class="card" style="text-align:center;padding:32px"><div style="font-size:36px;margin-bottom:10px">📭</div><p style="color:var(--text-dim)">No words yet. Click "+ Add Word" to get started.</p></div>`;
    return;
  }

  let _selected = new Set();
  let _bulkMode = false;

  const render = () => {
    container.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <div style="font-size:12px;color:var(--text-dim)">${list.length} word${list.length !== 1 ? 's' : ''}</div>
        <button id="btn-bulk-toggle" class="btn btn-outline" style="font-size:12px;padding:4px 10px">
          ${_bulkMode ? '✕ Cancel' : '☑ Manage'}
        </button>
      </div>
      ${_bulkMode ? `
      <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap">
        <button id="btn-bulk-select-all" class="btn btn-outline" style="font-size:12px;padding:4px 10px">Select All</button>
        <button id="btn-bulk-star" class="btn btn-outline" style="font-size:12px;padding:4px 10px">⭐ Star</button>
        <button id="btn-bulk-error" class="btn btn-outline" style="font-size:12px;padding:4px 10px">❌ Error</button>
        <button id="btn-bulk-writing" class="btn btn-outline" style="font-size:12px;padding:4px 10px">✍️ Writing</button>
        <button id="btn-bulk-delete" class="btn btn-outline" style="font-size:12px;padding:4px 10px;color:var(--red)">🗑 Remove</button>
        <span style="font-size:12px;color:var(--text-dim);align-self:center" id="bulk-count">${_selected.size} selected</span>
      </div>` : ''}
      <div class="word-list">
        ${list.map(w => {
          const dot = proficiencyDot(w.interval);
          return `
          <div class="word-row" data-word-id="${w.word_id}" style="border-bottom:1px solid var(--border);${_selected.has(w.word_id) ? 'background:var(--bg3)' : ''}">
            <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;cursor:pointer" class="word-row-header">
              ${_bulkMode ? `<input type="checkbox" class="bulk-cb" data-word-id="${w.word_id}" ${_selected.has(w.word_id) ? 'checked' : ''} style="width:16px;height:16px;cursor:pointer;flex-shrink:0">` : ''}
              <div style="flex:1;min-width:0" class="word-row-body">
                <div style="display:flex;align-items:center;gap:8px">
                  <span style="font-weight:600">${escHtml(w.word)}</span>
                  ${w.part_of_speech ? `<span style="font-size:11px;color:var(--text-dim)">${escHtml(w.part_of_speech)}</span>` : ''}
                  ${w.pronunciation ? `<span style="font-size:11px;color:var(--text-dim)">${escHtml(w.pronunciation)}</span>` : ''}
                  ${!w.card_id ? '<span class="tag tag-green" style="font-size:10px">NEW</span>' : ''}
                </div>
                <div style="font-size:12px;color:var(--text-dim);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
                  ${escHtml(w.definition_en || '')}${w.definition_zh ? ` · ${escHtml(w.definition_zh)}` : ''}
                </div>
              </div>
              <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
                <button class="tts-btn" onclick="event.stopPropagation();tts('${w.word.replace(/'/g,"\\'")}')">🔊</button>
                <span title="${dot.label}" style="width:10px;height:10px;border-radius:50%;background:${dot.color};display:inline-block;flex-shrink:0"></span>
                <span class="expand-arrow" style="font-size:10px;color:var(--text-dim)">▶</span>
              </div>
            </div>
            <div class="word-row-detail" style="display:none;padding:0 14px 12px 14px;font-size:13px;border-top:1px solid var(--border)">
              ${w.example ? `<div style="margin-top:8px;color:var(--text-dim);font-style:italic">"${escHtml(w.example)}" <button class="tts-btn" onclick="tts('${w.example.replace(/'/g,"\\'").replace(/"/g,'&quot;')}')">🔊</button></div>` : ''}
              ${w.synonyms ? `<div style="margin-top:6px"><span style="color:var(--text-dim)">Synonyms: </span>${escHtml(w.synonyms)}</div>` : ''}
              ${w.antonyms ? `<div style="margin-top:4px"><span style="color:var(--text-dim)">Antonyms: </span>${escHtml(w.antonyms)}</div>` : ''}
              ${w.collocations ? `<div style="margin-top:4px"><span style="color:var(--text-dim)">Collocations: </span>${escHtml(w.collocations)}</div>` : ''}
              ${w.derivatives ? `<div style="margin-top:4px"><span style="color:var(--text-dim)">Derivatives: </span>${escHtml(w.derivatives)}</div>` : ''}
              ${w.context_sentence ? `<div style="margin-top:4px"><span style="color:var(--text-dim)">Context: </span>${escHtml(w.context_sentence)}</div>` : ''}
              <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">
                ${['star','error','writing','listening'].map(tag => `<button class="inline-tag-btn" data-tag="${tag}" data-word-id="${w.word_id}" style="padding:3px 8px;border-radius:12px;border:1px solid var(--border);background:var(--bg3);color:var(--text-dim);font-size:11px;cursor:pointer">${tag==='star'?'⭐':tag==='error'?'❌':tag==='writing'?'✍️':'🎧'} ${tag}</button>`).join('')}
              </div>
            </div>
          </div>`;
        }).join('')}
      </div>`;

    container.querySelector('#btn-bulk-toggle')?.addEventListener('click', () => {
      _bulkMode = !_bulkMode; _selected.clear(); render();
    });
    container.querySelector('#btn-bulk-select-all')?.addEventListener('click', () => {
      if (_selected.size === list.length) _selected.clear();
      else list.forEach(w => _selected.add(w.word_id));
      render();
    });
    container.querySelectorAll('.bulk-cb').forEach(cb => {
      cb.addEventListener('change', () => {
        if (cb.checked) _selected.add(cb.dataset.wordId);
        else _selected.delete(cb.dataset.wordId);
        const countEl = container.querySelector('#bulk-count');
        if (countEl) countEl.textContent = `${_selected.size} selected`;
      });
    });
    container.querySelectorAll('.word-row-body').forEach(body => {
      if (!_bulkMode) return;
      body.addEventListener('click', () => {
        const wid = body.closest('.word-row').dataset.wordId;
        const cb = body.closest('.word-row').querySelector('.bulk-cb');
        if (_selected.has(wid)) { _selected.delete(wid); if (cb) cb.checked = false; }
        else { _selected.add(wid); if (cb) cb.checked = true; }
        const countEl = container.querySelector('#bulk-count');
        if (countEl) countEl.textContent = `${_selected.size} selected`;
        body.closest('.word-row').style.background = _selected.has(wid) ? 'var(--bg3)' : '';
      });
    });

    container.querySelectorAll('.word-row-header').forEach(header => {
      header.addEventListener('click', (e) => {
        if (e.target.closest('.bulk-cb') || e.target.closest('.tts-btn')) return;
        if (_bulkMode) return;
        const row = header.closest('.word-row');
        const detail = row.querySelector('.word-row-detail');
        const arrow = header.querySelector('.expand-arrow');
        const open = detail.style.display !== 'none';
        detail.style.display = open ? 'none' : '';
        if (arrow) arrow.textContent = open ? '▶' : '▼';
      });
    });

    container.querySelectorAll('.inline-tag-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const tag = btn.dataset.tag;
        const wid = btn.dataset.wordId;
        const isActive = btn.style.background.includes('accent');
        const newActive = !isActive;
        try {
          await api.post('/api/vocab/tag', { word_id: wid, tag, active: newActive });
          btn.style.background = newActive ? 'var(--accent)' : 'var(--bg3)';
          btn.style.color = newActive ? '#fff' : 'var(--text-dim)';
        } catch {}
      });
    });

    const bulkTag = async (tag) => {
      if (!_selected.size) return;
      await Promise.all([..._selected].map(wid => api.post('/api/vocab/tag', { word_id: wid, tag, active: true }).catch(() => {})));
      _bulkMode = false; _selected.clear(); render();
    };
    container.querySelector('#btn-bulk-star')?.addEventListener('click', () => bulkTag('star'));
    container.querySelector('#btn-bulk-error')?.addEventListener('click', () => bulkTag('error'));
    container.querySelector('#btn-bulk-writing')?.addEventListener('click', () => bulkTag('writing'));
    container.querySelector('#btn-bulk-delete')?.addEventListener('click', async () => {
      if (!_selected.size) return;
      await Promise.all([..._selected].map(wid =>
        fetch(`/api/wordbooks/${book.book_id}/words/${wid}`, { method: 'DELETE' }).catch(() => {})
      ));
      _allWords = _allWords.filter(w => !_selected.has(w.word_id));
      _bulkMode = false; _selected.clear();
      renderWordList(content, book, content.querySelector('#word-filter')?.value.trim() || '');
    });
  };

  render();
}

// ── Add Word to Book panel ────────────────────────────────────────

function showAddWordPanel(content, book, el) {
  const panel = content.querySelector('#add-word-panel-book');
  panel.style.display = '';
  panel.innerHTML = `
    <div class="card" style="margin-top:16px;padding:24px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h3 style="margin:0">Add Word to "${escHtml(book.name)}"</h3>
        <button class="btn btn-outline" id="btn-close-add-book" style="font-size:12px;padding:4px 10px">✕ Close</button>
      </div>
      <div style="display:flex;gap:8px;margin-bottom:8px">
        <input id="add-word-input-book" type="text" placeholder="Search or type a word…" style="flex:1" autocomplete="off">
        <button class="btn btn-outline" id="btn-ai-fill-book" style="white-space:nowrap">✨ AI Fill</button>
      </div>
      <div id="search-results-book" style="margin-bottom:8px"></div>
      <div id="add-ai-status-book" style="font-size:12px;color:var(--text-dim);margin-bottom:8px;min-height:16px"></div>
      <div id="add-fields-book" style="display:none">
        <div class="form-group"><label>Definition (English)</label><input id="add-def-en-book" type="text" placeholder="e.g. to examine carefully"></div>
        <div class="form-group"><label>Definition (Chinese) <span style="color:var(--text-dim)">(optional)</span></label><input id="add-def-zh-book" type="text"></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="form-group"><label>Part of speech</label><input id="add-pos-book" type="text" placeholder="verb"></div>
          <div class="form-group"><label>Pronunciation</label><input id="add-pron-book" type="text" placeholder="/ɪˈzæm.ɪn/"></div>
        </div>
        <div class="form-group"><label>Example sentence</label><input id="add-example-book" type="text"></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="form-group"><label>Synonyms</label><input id="add-synonyms-book" type="text"></div>
          <div class="form-group"><label>Antonyms</label><input id="add-antonyms-book" type="text"></div>
        </div>
        <div id="add-msg-book" style="margin-bottom:8px"></div>
        <button class="btn btn-success" id="btn-add-confirm-book" style="width:100%">+ Add to Book</button>
      </div>
    </div>`;

  panel.querySelector('#btn-close-add-book').addEventListener('click', () => { panel.style.display = 'none'; });
  const wordInput = panel.querySelector('#add-word-input-book');
  const fieldsDiv = panel.querySelector('#add-fields-book');
  const statusDiv = panel.querySelector('#add-ai-status-book');
  const searchResults = panel.querySelector('#search-results-book');

  wordInput.addEventListener('input', () => {
    const q = wordInput.value.trim();
    if (q) fieldsDiv.style.display = '';
    clearTimeout(_searchTimeout);
    if (q.length < 2) { searchResults.innerHTML = ''; return; }
    _searchTimeout = setTimeout(() => searchVocab(q, searchResults, wordInput, panel), 300);
  });

  panel.querySelector('#btn-ai-fill-book').addEventListener('click', async () => {
    const word = wordInput.value.trim();
    if (!word) { wordInput.focus(); return; }
    fieldsDiv.style.display = '';
    const btn = panel.querySelector('#btn-ai-fill-book');
    btn.disabled = true; statusDiv.textContent = '✨ Fetching AI enrichment…';
    try {
      const r = await api.post('/api/vocab/enrich', { word });
      panel.querySelector('#add-def-en-book').value   = r.definition_en  || '';
      panel.querySelector('#add-def-zh-book').value   = r.definition_zh  || '';
      panel.querySelector('#add-pos-book').value      = r.part_of_speech || '';
      panel.querySelector('#add-pron-book').value     = r.pronunciation  || '';
      panel.querySelector('#add-example-book').value  = r.example        || '';
      panel.querySelector('#add-synonyms-book').value = r.synonyms       || '';
      panel.querySelector('#add-antonyms-book').value = r.antonyms       || '';
      statusDiv.textContent = '✓ AI fill complete';
      setTimeout(() => { statusDiv.textContent = ''; }, 2000);
    } catch (e) { statusDiv.textContent = `AI unavailable: ${e.message}`; }
    btn.disabled = false;
  });

  panel.querySelector('#btn-add-confirm-book').addEventListener('click', async () => {
    const word = wordInput.value.trim();
    const defEn = panel.querySelector('#add-def-en-book').value.trim();
    const msg = panel.querySelector('#add-msg-book');
    if (!word) { wordInput.focus(); return; }
    if (!defEn) { msg.innerHTML = '<div class="alert alert-error" style="margin-bottom:8px">English definition is required</div>'; return; }
    const btn = panel.querySelector('#btn-add-confirm-book');
    btn.disabled = true;
    try {
      const existingWordId = wordInput.dataset.wordId || null;
      const payload = existingWordId ? { word_id: existingWordId } : {
        word, definition_en: defEn,
        definition_zh: panel.querySelector('#add-def-zh-book').value.trim(),
        part_of_speech: panel.querySelector('#add-pos-book').value.trim(),
        pronunciation: panel.querySelector('#add-pron-book').value.trim(),
        example: panel.querySelector('#add-example-book').value.trim(),
        synonyms: panel.querySelector('#add-synonyms-book').value.trim(),
        antonyms: panel.querySelector('#add-antonyms-book').value.trim(),
      };
      await api.post(`/api/wordbooks/${book.book_id}/words`, payload);
      msg.innerHTML = `<div class="alert alert-success" style="margin-bottom:8px">✓ "${escHtml(word)}" added!</div>`;
      wordInput.value = ''; wordInput.dataset.wordId = '';
      ['#add-def-en-book','#add-def-zh-book','#add-pos-book','#add-pron-book','#add-example-book','#add-synonyms-book','#add-antonyms-book'].forEach(id => { panel.querySelector(id).value = ''; });
      fieldsDiv.style.display = 'none';
      setTimeout(() => { msg.innerHTML = ''; }, 2500);
      const data = await api.get(`/api/wordbooks/${book.book_id}/words`);
      renderWordList(content, book, '', data.words);
    } catch (e) { msg.innerHTML = `<div class="alert alert-error" style="margin-bottom:8px">${e.message}</div>`; }
    btn.disabled = false;
  });
  wordInput.focus();
}

async function searchVocab(q, resultsEl, wordInput, panel) {
  try {
    const results = await api.get(`/api/wordbooks/search/vocab?q=${encodeURIComponent(q)}&limit=6`);
    if (!results.length) { resultsEl.innerHTML = ''; return; }
    resultsEl.innerHTML = `<div style="border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:8px">
      ${results.map(r => `<div class="search-result-row" data-word-id="${r.word_id}" data-word="${escHtml(r.word)}"
        style="padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px">
        <div style="flex:1"><span style="font-weight:600">${escHtml(r.word)}</span>
          ${r.part_of_speech ? `<span style="font-size:11px;color:var(--text-dim);margin-left:6px">${escHtml(r.part_of_speech)}</span>` : ''}
          <div style="font-size:12px;color:var(--text-dim)">${escHtml(r.definition_en || '')}</div>
        </div></div>`).join('')}
    </div>`;
    resultsEl.querySelectorAll('.search-result-row').forEach(row => {
      row.addEventListener('mouseenter', () => row.style.background = 'var(--bg3)');
      row.addEventListener('mouseleave', () => row.style.background = '');
      row.addEventListener('click', () => {
        wordInput.value = row.dataset.word;
        wordInput.dataset.wordId = row.dataset.wordId;
        resultsEl.innerHTML = '';
        panel.querySelector('#add-fields-book').style.display = '';
        const match = results.find(r => r.word_id === row.dataset.wordId);
        if (match) {
          panel.querySelector('#add-def-en-book').value = match.definition_en || '';
          panel.querySelector('#add-def-zh-book').value = match.definition_zh || '';
          panel.querySelector('#add-pos-book').value = match.part_of_speech || '';
        }
      });
    });
  } catch { resultsEl.innerHTML = ''; }
}

// ── Book Study Session ────────────────────────────────────────────

async function startBookSession(el, content, book) {
  // Save as recently studied
  localStorage.setItem('lastStudiedBookId', book.book_id);
  localStorage.setItem('lastStudiedBookName', book.name);
  localStorage.setItem('lastStudiedBookIcon', book.icon || '📖');
  localStorage.setItem('lastStudiedBookColor', book.color || 'var(--accent)');
  content.innerHTML = `<div style="text-align:center;padding:60px"><div class="spinner"></div><p style="margin-top:16px;color:var(--text-dim)">Loading session…</p></div>`;
  try {
    const r = await api.post(`/api/wordbooks/${book.book_id}/start`, { max_cards: 20 });
    if (r.empty) {
      content.innerHTML = `
        <div class="card" style="text-align:center;padding:40px;max-width:480px;margin:0 auto">
          <div style="font-size:48px;margin-bottom:12px">🎉</div>
          <h2>All caught up!</h2>
          <p style="color:var(--text-dim);margin:12px 0">No cards due in <strong>${escHtml(book.name)}</strong>. Come back tomorrow!</p>
          <button class="btn btn-outline" id="btn-back-empty">← Back to Books</button>
        </div>`;
      content.querySelector('#btn-back-empty').addEventListener('click', () => renderBooksTab(el, content));
      return;
    }
    _sid = r.session_id; _total = r.total; _remaining = r.remaining;
    _wordListLabel = r.word_list_label || book.name;
    _exam = 'general';

    content.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px">
        <button class="btn btn-outline" id="btn-back-session" style="font-size:12px;padding:4px 10px">← ${escHtml(book.name)}</button>
        <span style="font-size:13px;color:var(--text-dim)">${r.total} cards</span>
      </div>
      <div id="book-session-body"></div>`;
    content.querySelector('#btn-back-session').addEventListener('click', () => showBookDetail(el, content, book));
    const sessionBody = content.querySelector('#book-session-body');
    renderBookCard(el, content, sessionBody, r.card, false, book);
    if (r.card) { ttsPreload && ttsPreload(r.card.word); }
  } catch (e) {
    content.innerHTML = `<div class="alert alert-error">${e.message} <button class="btn btn-outline" style="margin-left:8px" id="btn-retry-bs">Retry ↺</button></div>`;
    content.querySelector('#btn-retry-bs')?.addEventListener('click', () => startBookSession(el, content, book));
  }
}

function renderBookCard(el, content, sessionBody, card, revealed, book) {
  _revealed = revealed;
  const done = _total - _remaining;
  const pct = Math.round((done / _total) * 100);

  sessionBody.innerHTML = `
    <div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:${pct}%"></div></div>
    <div style="display:flex;justify-content:space-between;font-size:13px;color:var(--text-dim);margin-bottom:16px">
      <span>${done} / ${_total} cards</span>
      <span style="font-size:12px">${escHtml(_wordListLabel)}</span>
    </div>
    <div class="flashcard-wrap">
      <div class="flashcard${revealed ? ' flipped' : ''}" id="bfc">
        <div class="flashcard-front">
          <div class="flashcard-word">${escHtml(card.word)} <button class="tts-btn" onclick="event.stopPropagation();tts('${card.word.replace(/'/g,"\\'")}')">🔊</button></div>
          ${card.part_of_speech ? `<div class="flashcard-pos">${escHtml(card.part_of_speech)}</div>` : ''}
          ${card.pronunciation ? `<div class="flashcard-pron">${escHtml(card.pronunciation)}</div>` : ''}
          ${card.is_new ? '<div class="tag tag-green" style="margin-top:12px">NEW</div>' : ''}
          <div class="flashcard-hint">Click or Space to flip · Click again to flip back</div>
        </div>
        <div class="flashcard-back" id="bfc-back">
          <div class="def-en">${escHtml(card.definition_en || '')}</div>
          <div class="def-zh">${escHtml(card.definition_zh || '')}</div>
          ${card.example ? `<div class="example">"${escHtml(card.example)}" <button class="tts-btn" onclick="tts('${card.example.replace(/'/g,"\\'").replace(/"/g,'&quot;')}')">🔊</button></div>` : ''}
        </div>
      </div>
    </div>
    <div id="brating-area" class="${revealed ? '' : 'hidden'}" style="text-align:center">
      <p style="margin-bottom:8px;font-size:13px;color:var(--text-dim)">How well did you know it?</p>
      <div class="rating-bar">
        <button class="rating-btn" data-q="1">1</button>
        <button class="rating-btn" data-q="2">2</button>
        <button class="rating-btn" data-q="3">3</button>
        <button class="rating-btn" data-q="4">4</button>
        <button class="rating-btn" data-q="5">5</button>
      </div>
      <div style="display:flex;justify-content:center;gap:20px;margin-top:8px;font-size:11px;color:var(--text-dim)">
        <span>1=Forgot</span><span>3=OK</span><span>5=Easy</span><span style="margin-left:8px">Keys 1–5</span>
      </div>
      <div id="btag-bar" style="display:flex;justify-content:center;gap:8px;margin-top:12px;flex-wrap:wrap"></div>
    </div>`;

  const fc = sessionBody.querySelector('#bfc');
  fc.addEventListener('click', async () => {
    if (_revealed) {
      fc.classList.remove('flipped');
      _revealed = false;
      sessionBody.querySelector('#brating-area').classList.add('hidden');
      return;
    }
    fc.classList.add('flipped'); _revealed = true;
    try {
      const detail = await api.post(`/api/vocab/reveal/${_sid}`, {});
      const back = sessionBody.querySelector('#bfc-back');
      back.innerHTML = `
        <div class="def-en">${escHtml(detail.definition_en || '')}</div>
        <div class="def-zh">${escHtml(detail.definition_zh || '')}</div>
        ${detail.example ? `<div class="example">"${escHtml(detail.example)}" <button class="tts-btn" onclick="tts('${detail.example.replace(/'/g,"\\'").replace(/"/g,'&quot;')}')">🔊</button></div>` : ''}
        ${detail.synonyms ? `<div class="field" style="margin-top:8px"><span style="color:var(--text-dim)">Synonyms: </span>${escHtml(detail.synonyms)}</div>` : ''}
        ${detail.antonyms ? `<div class="field"><span style="color:var(--text-dim)">Antonyms: </span>${escHtml(detail.antonyms)}</div>` : ''}
        ${detail.collocations ? `<div class="field"><span style="color:var(--text-dim)">Collocations: </span>${escHtml(detail.collocations)}</div>` : ''}
        ${detail.derivatives ? `<div class="field"><span style="color:var(--text-dim)">Derivatives: </span>${escHtml(detail.derivatives)}</div>` : ''}`;
      if (_autoTts && detail.word) tts(detail.word);
      if (detail.word_id) renderTagBar(sessionBody.querySelector('#btag-bar'), detail.word_id);
    } catch {}
    sessionBody.querySelector('#brating-area').classList.remove('hidden');
  });

  sessionBody.querySelectorAll('.rating-btn').forEach(btn => {
    btn.addEventListener('click', () => rateBookCard(el, content, sessionBody, parseInt(btn.dataset.q), book));
  });

  if (_keyHandler) document.removeEventListener('keydown', _keyHandler);
  _keyHandler = (e) => {
    if (e.code === 'Space') { e.preventDefault(); sessionBody.querySelector('#bfc')?.click(); }
    else if (_revealed && e.key >= '1' && e.key <= '5') {
      const btn = sessionBody.querySelector(`.rating-btn[data-q="${e.key}"]`);
      if (btn && !btn.disabled) btn.click();
    }
  };
  document.addEventListener('keydown', _keyHandler);
}

async function rateBookCard(el, content, sessionBody, quality, book) {
  sessionBody.querySelectorAll('.rating-btn').forEach(b => b.disabled = true);
  try {
    const r = await api.post(`/api/vocab/rate/${_sid}`, { quality });
    if (r.complete) {
      if (_keyHandler) { document.removeEventListener('keydown', _keyHandler); _keyHandler = null; }
      const color = r.stats.accuracy >= 80 ? 'var(--green)' : r.stats.accuracy >= 60 ? 'var(--yellow)' : 'var(--red)';
      sessionBody.innerHTML = `
        <div class="card" style="text-align:center;padding:40px">
          <div style="font-size:48px;margin-bottom:16px">🎉</div>
          <h2>Session Complete!</h2>
          <div style="font-size:36px;font-weight:700;color:${color};margin:16px 0">${r.stats.accuracy}%</div>
          <p>${r.stats.correct} / ${r.stats.reviewed} correct</p>
          <div style="display:flex;gap:12px;justify-content:center;margin-top:24px">
            <button class="btn btn-primary" id="btn-study-again">Study Again</button>
            <button class="btn btn-outline" id="btn-back-to-book">← Back to Book</button>
          </div>
        </div>`;
      sessionBody.querySelector('#btn-study-again').addEventListener('click', () => startBookSession(el, content, book));
      sessionBody.querySelector('#btn-back-to-book').addEventListener('click', () => showBookDetail(el, content, book));
    } else {
      _remaining = r.remaining;
      renderBookCard(el, content, sessionBody, r.card, false, book);
      ttsPreload && ttsPreload(r.card.word);
    }
  } catch (e) { console.error(e); }
}

// ── ADD WORD TAB ──────────────────────────────────────────────────

async function renderAddTab(el, content) {
  let books = [];
  try { books = await api.get('/api/wordbooks'); } catch {}
  const savedId = localStorage.getItem('defaultAddBookId') || '';
  const validDefault = books.find(b => b.book_id === savedId) ? savedId : (books.length ? books[0].book_id : '');
  let selectedBookId = validDefault;

  function buildBookSelector() {
    const noSel = selectedBookId === '';
    const cards = [
      `<div class="add-book-card" data-book-id=""
        style="cursor:pointer;padding:14px;border-radius:10px;border:2px solid ${noSel ? 'var(--accent)' : 'var(--border)'};
               background:${noSel ? 'var(--bg3)' : 'var(--bg2)'};display:flex;align-items:center;gap:10px;transition:border-color .15s,background .15s">
        <span style="font-size:22px">📋</span>
        <div><div style="font-weight:600;font-size:13px">Deck only</div><div style="font-size:11px;color:var(--text-dim)">No word book</div></div>
      </div>`,
      ...books.map(b => {
        const sel = b.book_id === selectedBookId;
        return `<div class="add-book-card" data-book-id="${b.book_id}"
          style="cursor:pointer;padding:14px;border-radius:10px;border:2px solid ${sel ? b.color : 'var(--border)'};
                 background:${sel ? 'var(--bg3)' : 'var(--bg2)'};display:flex;align-items:center;gap:10px;
                 transition:border-color .15s,background .15s;position:relative;overflow:hidden">
          <span style="font-size:22px">${b.icon}</span>
          <div style="flex:1;min-width:0">
            <div style="font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escHtml(b.name)}</div>
            <div style="font-size:11px;color:var(--text-dim)">${b.word_count || 0} words${b.due_today ? ` · ${b.due_today} due` : ''}</div>
          </div>
          <div style="position:absolute;bottom:0;left:0;right:0;height:3px;background:${b.color}"></div>
        </div>`;
      }),
      `<div class="add-book-card" data-book-id="__new__"
        style="cursor:pointer;padding:14px;border-radius:10px;border:2px dashed var(--border);
               background:var(--bg2);display:flex;align-items:center;gap:10px;transition:border-color .15s">
        <span style="font-size:22px">➕</span>
        <div style="font-weight:600;font-size:13px;color:var(--text-dim)">New Book</div>
      </div>`
    ];
    return cards.join('');
  }

  content.innerHTML = `
    <div style="max-width:640px">
      <div style="margin-bottom:24px">
        <div style="font-size:12px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px">Add to Word Book</div>
        <div id="book-selector" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:10px">
          ${buildBookSelector()}
        </div>
        <div id="book-sel-hint" style="font-size:12px;color:var(--text-dim);margin-top:8px"></div>
      </div>

      <div style="padding:0">
        <div style="display:flex;gap:8px;margin-bottom:8px">
          <input id="add-word-input" type="text" placeholder="Enter a word…" style="flex:1;font-size:15px;background:var(--bg2);color:var(--text);border:1px solid var(--border);border-radius:var(--radius);padding:8px 12px">
          <button class="btn btn-outline" id="btn-ai-fill" style="white-space:nowrap">✨ AI Fill</button>
        </div>
        <div id="add-ai-status" style="font-size:12px;color:var(--text-dim);margin-bottom:8px;min-height:16px"></div>
        <div id="add-fields" style="display:none">
          <div class="form-group"><label>Definition (English)</label>
            <input id="add-def-en" type="text" placeholder="e.g. to make something better">
          </div>
          <div class="form-group"><label>Definition (Chinese) <span style="color:var(--text-dim)">(optional)</span></label>
            <input id="add-def-zh" type="text" placeholder="e.g. 改善">
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div class="form-group"><label>Part of speech</label><input id="add-pos" type="text" placeholder="verb"></div>
            <div class="form-group"><label>Pronunciation</label><input id="add-pron" type="text" placeholder="/ɪmˈpruːv/"></div>
          </div>
          <div class="form-group"><label>Example sentence</label>
            <input id="add-example" type="text" placeholder="e.g. She worked hard to improve her score.">
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div class="form-group"><label>Synonyms <span style="color:var(--text-dim)">(opt)</span></label><input id="add-synonyms" type="text" placeholder="enhance, boost"></div>
            <div class="form-group"><label>Antonyms <span style="color:var(--text-dim)">(opt)</span></label><input id="add-antonyms" type="text" placeholder="worsen"></div>
          </div>
          <div id="add-msg" style="margin-bottom:8px"></div>
          <button class="btn btn-success" id="btn-add-confirm" style="width:100%;font-size:15px;padding:10px">+ Add Word</button>
        </div>
      </div>
    </div>
  `;

  const hintEl = content.querySelector('#book-sel-hint');
  const updateHint = () => {
    if (!selectedBookId) { hintEl.textContent = 'Word will be added to your SRS deck only.'; return; }
    const b = books.find(b => b.book_id === selectedBookId);
    hintEl.textContent = b ? `Adding to: ${b.icon} ${b.name}` : '';
  };
  updateHint();

  content.querySelectorAll('.add-book-card').forEach(card => {
    card.addEventListener('click', () => {
      const bid = card.dataset.bookId;
      if (bid === '__new__') { showBookModal(el, content, null, () => renderAddTab(el, content)); return; }
      selectedBookId = bid;
      localStorage.setItem('defaultAddBookId', bid);
      content.querySelectorAll('.add-book-card').forEach(c => {
        if (c.dataset.bookId === '__new__') return;
        const cbid = c.dataset.bookId;
        const bk = books.find(b => b.book_id === cbid);
        const active = cbid === selectedBookId;
        c.style.borderColor = active ? (bk ? bk.color : 'var(--accent)') : 'var(--border)';
        c.style.background  = active ? 'var(--bg3)' : 'var(--bg2)';
      });
      updateHint();
    });
  });

  const wordInput = content.querySelector('#add-word-input');
  const fieldsDiv = content.querySelector('#add-fields');
  const statusDiv = content.querySelector('#add-ai-status');

  wordInput.addEventListener('input', () => {
    if (wordInput.value.trim()) fieldsDiv.style.display = '';
  });

  content.querySelector('#btn-ai-fill').addEventListener('click', async () => {
    const word = wordInput.value.trim();
    if (!word) { wordInput.focus(); return; }
    fieldsDiv.style.display = '';
    const btn = content.querySelector('#btn-ai-fill');
    btn.disabled = true; statusDiv.textContent = '✨ Fetching AI enrichment…';
    try {
      const r = await api.post('/api/vocab/enrich', { word });
      content.querySelector('#add-def-en').value   = r.definition_en  || '';
      content.querySelector('#add-def-zh').value   = r.definition_zh  || '';
      content.querySelector('#add-pos').value      = r.part_of_speech || '';
      content.querySelector('#add-pron').value     = r.pronunciation  || '';
      content.querySelector('#add-example').value  = r.example        || '';
      content.querySelector('#add-synonyms').value = r.synonyms       || '';
      content.querySelector('#add-antonyms').value = r.antonyms       || '';
      statusDiv.textContent = '✓ AI fill complete';
      setTimeout(() => { statusDiv.textContent = ''; }, 2000);
    } catch (e) { statusDiv.textContent = `AI unavailable: ${e.message}`; }
    btn.disabled = false;
  });

  content.querySelector('#btn-add-confirm').addEventListener('click', async () => {
    const word = wordInput.value.trim();
    const defEn = content.querySelector('#add-def-en').value.trim();
    const msg = content.querySelector('#add-msg');
    if (!word) { wordInput.focus(); return; }
    if (!defEn) { msg.innerHTML = '<div class="alert alert-error" style="margin-bottom:8px">English definition is required</div>'; return; }
    const btn = content.querySelector('#btn-add-confirm');
    btn.disabled = true;
    try {
      const r = await api.post('/api/vocab/add', {
        word, definition_en: defEn,
        definition_zh:  content.querySelector('#add-def-zh').value.trim(),
        part_of_speech: content.querySelector('#add-pos').value.trim(),
        pronunciation:  content.querySelector('#add-pron').value.trim(),
        example:        content.querySelector('#add-example').value.trim(),
        synonyms:       content.querySelector('#add-synonyms').value.trim(),
        antonyms:       content.querySelector('#add-antonyms').value.trim(),
      });
      if (selectedBookId && r.ok && r.word_id) {
        try { await api.post(`/api/wordbooks/${selectedBookId}/words`, { word_id: r.word_id }); } catch {}
      }
      if (r.already_exists) {
        msg.innerHTML = `<div class="alert alert-warn" style="margin-bottom:8px">"${escHtml(r.word)}" is already in your deck</div>`;
      } else {
        const bookName = selectedBookId ? (books.find(b => b.book_id === selectedBookId)?.name || '') : '';
        msg.innerHTML = `<div class="alert alert-success" style="margin-bottom:8px">✓ "${escHtml(r.word)}" added${bookName ? ` → ${escHtml(bookName)}` : ''}!</div>`;
        wordInput.value = '';
        ['#add-def-en','#add-def-zh','#add-pos','#add-pron','#add-example','#add-synonyms','#add-antonyms'].forEach(id => { content.querySelector(id).value = ''; });
        fieldsDiv.style.display = 'none';
        setTimeout(() => { msg.innerHTML = ''; }, 2500);
      }
    } catch (e) { msg.innerHTML = `<div class="alert alert-error" style="margin-bottom:8px">${e.message}</div>`; }
    btn.disabled = false;
  });

  wordInput.focus();
}

