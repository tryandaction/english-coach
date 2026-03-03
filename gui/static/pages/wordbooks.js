// pages/wordbooks.js — Anki-style custom word books

let _currentBook = null;
let _searchTimeout = null;

export async function render(el) {
  _currentBook = null;
  await showBookList(el);
}

// ── Book List ──────────────────────────────────────────────────────

async function showBookList(el) {
  el.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
      <h1 style="margin:0">📚 Word Books</h1>
      <button class="btn btn-primary" id="btn-create-book">+ New Book</button>
    </div>
    <p style="color:var(--text-dim);margin-bottom:24px">Create custom vocabulary collections and study them with spaced repetition.</p>
    <div id="books-list"><div style="text-align:center;padding:40px"><div class="spinner"></div></div></div>
  `;
  el.querySelector('#btn-create-book').addEventListener('click', () => showBookModal(el, null));
  await loadBookList(el);
}

async function loadBookList(el) {
  const container = el.querySelector('#books-list');
  try {
    const books = await api.get('/api/wordbooks');
    if (!books.length) {
      container.innerHTML = `
        <div class="card" style="text-align:center;padding:40px">
          <div style="font-size:48px;margin-bottom:12px">📭</div>
          <h3 style="margin-bottom:8px">No word books yet</h3>
          <p style="color:var(--text-dim);margin-bottom:20px">Create your first word book to start building custom vocabulary collections.</p>
          <button class="btn btn-primary" id="btn-create-first">+ Create Word Book</button>
        </div>`;
      container.querySelector('#btn-create-first').addEventListener('click', () => showBookModal(el, null));
      return;
    }
    container.innerHTML = `<div class="book-grid">${books.map(b => bookCard(b)).join('')}</div>`;
    container.querySelectorAll('.book-card').forEach(card => {
      const bookId = card.dataset.bookId;
      const book = books.find(b => b.book_id === bookId);
      card.querySelector('.btn-book-open').addEventListener('click', () => showBookDetail(el, book));
      card.querySelector('.btn-book-edit').addEventListener('click', e => { e.stopPropagation(); showBookModal(el, book); });
      card.querySelector('.btn-book-delete').addEventListener('click', e => { e.stopPropagation(); confirmDeleteBook(el, book); });
      card.querySelector('.btn-book-study').addEventListener('click', e => { e.stopPropagation(); startBookSession(el, book); });
    });
  } catch (e) {
    if (e.message.includes('profile') || e.message.includes('Profile') || e.message.includes('No profile')) {
      container.innerHTML = `
        <div class="card" style="text-align:center;padding:40px">
          <div style="font-size:40px;margin-bottom:12px">⚙️</div>
          <h3 style="margin-bottom:8px">Setup Required</h3>
          <p style="color:var(--text-dim);margin-bottom:20px">Please complete the setup wizard before using Word Books.</p>
          <button class="btn btn-primary" onclick="navigate('setup')">Go to Setup →</button>
        </div>`;
    } else {
      container.innerHTML = `<div class="alert alert-error">${e.message} <button class="btn btn-outline" style="margin-left:8px" id="btn-retry-wb">Retry ↺</button></div>`;
      container.querySelector('#btn-retry-wb')?.addEventListener('click', () => loadBookList(el));
    }
  }
}
function bookCard(b) {
  const due = b.due_today || 0;
  const dueBadge = due > 0
    ? `<span style="background:var(--accent);color:#fff;border-radius:12px;padding:2px 8px;font-size:11px;font-weight:700">${due} due</span>`
    : `<span style="color:var(--text-dim);font-size:11px">0 due</span>`;
  return `
    <div class="book-card card" data-book-id="${b.book_id}" style="cursor:pointer;padding:20px;position:relative">
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

// ── Create / Edit Modal ────────────────────────────────────────────

const ICONS = ['📖','📝','🧠','⭐','🔥','💡','🎯','🌟','📌','🏆','🌈','🔬','🎓','💬','🗂'];
const COLORS = ['#4f8ef7','#7c5cfc','#3ecf8e','#f5c842','#f26b6b','#f97316','#06b6d4','#ec4899','#a855f7','#84cc16'];

function showBookModal(el, book) {
  const isEdit = !!book;
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal-box" style="max-width:440px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
        <h3 style="margin:0">${isEdit ? 'Edit Word Book' : 'New Word Book'}</h3>
        <button class="btn btn-outline" id="modal-close" style="padding:4px 10px">✕</button>
      </div>
      <div class="form-group">
        <label>Name</label>
        <input id="book-name" type="text" placeholder="e.g. TOEFL Vocabulary" value="${isEdit ? escHtml(book.name) : ''}">
      </div>
      <div class="form-group">
        <label>Description <span style="color:var(--text-dim)">(optional)</span></label>
        <input id="book-desc" type="text" placeholder="e.g. Words for TOEFL exam prep" value="${isEdit ? escHtml(book.description || '') : ''}">
      </div>
      <div class="form-group">
        <label>Icon</label>
        <div id="icon-picker" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">
          ${ICONS.map(ic => `<button class="icon-opt${isEdit && book.icon === ic ? ' selected' : ic === '📖' && !isEdit ? ' selected' : ''}" data-icon="${ic}" style="font-size:20px;padding:6px 8px;border-radius:8px;border:2px solid transparent;background:var(--bg3);cursor:pointer">${ic}</button>`).join('')}
        </div>
      </div>
      <div class="form-group">
        <label>Color</label>
        <div id="color-picker" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">
          ${COLORS.map(c => `<button class="color-opt${isEdit && book.color === c ? ' selected' : c === '#4f8ef7' && !isEdit ? ' selected' : ''}" data-color="${c}" style="width:28px;height:28px;border-radius:50%;background:${c};border:3px solid ${(isEdit && book.color === c) || (!isEdit && c === '#4f8ef7') ? '#fff' : 'transparent'};cursor:pointer"></button>`).join('')}
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
    if (btn.classList.contains('selected')) btn.style.borderColor = 'var(--accent)';
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
        await fetch(`/api/wordbooks/${book.book_id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, description: desc, color: selectedColor, icon: selectedIcon }),
        });
      } else {
        await api.post('/api/wordbooks', { name, description: desc, color: selectedColor, icon: selectedIcon });
      }
      close();
      await loadBookList(el);
    } catch (e) {
      msg.innerHTML = `<div class="alert alert-error" style="margin:0">${e.message}</div>`;
      saveBtn.disabled = false;
    }
  });

  modal.querySelector('#book-name').focus();
}
// ── Delete Confirm ─────────────────────────────────────────────────

function confirmDeleteBook(el, book) {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal-box" style="max-width:380px;text-align:center">
      <div style="font-size:40px;margin-bottom:12px">🗑</div>
      <h3 style="margin-bottom:8px">Delete "${escHtml(book.name)}"?</h3>
      <p style="color:var(--text-dim);margin-bottom:20px">This will remove the word book. Words in your SRS deck will not be deleted.</p>
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
    try {
      await fetch(`/api/wordbooks/${book.book_id}`, { method: 'DELETE' });
      close();
      await loadBookList(el);
    } catch (e) { close(); }
  });
}

// ── Book Detail ────────────────────────────────────────────────────

async function showBookDetail(el, book) {
  _currentBook = book;
  el.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px">
      <button class="btn btn-outline" id="btn-back" style="font-size:12px;padding:4px 10px">← Back</button>
      <span style="font-size:24px">${book.icon}</span>
      <h1 style="margin:0">${escHtml(book.name)}</h1>
    </div>
    ${book.description ? `<p style="color:var(--text-dim);margin-bottom:16px">${escHtml(book.description)}</p>` : '<div style="margin-bottom:16px"></div>'}
    <div style="display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap">
      <button class="btn btn-primary" id="btn-study-book">▶ Study Now</button>
      <button class="btn btn-outline" id="btn-add-word-book">+ Add Word</button>
      <button class="btn btn-outline" id="btn-edit-book" style="margin-left:auto">✏️ Edit</button>
    </div>
    <div id="book-stats-row" style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap"></div>
    <div id="book-word-search" style="margin-bottom:16px">
      <input id="word-filter" type="text" placeholder="Filter words…" style="width:100%;max-width:320px">
    </div>
    <div id="book-words-container"><div style="text-align:center;padding:40px"><div class="spinner"></div></div></div>
    <div id="add-word-panel-book" style="display:none"></div>
  `;

  el.querySelector('#btn-back').addEventListener('click', () => showBookList(el));
  el.querySelector('#btn-study-book').addEventListener('click', () => startBookSession(el, book));
  el.querySelector('#btn-add-word-book').addEventListener('click', () => showAddWordPanel(el, book));
  el.querySelector('#btn-edit-book').addEventListener('click', () => showBookModal(el, book));

  let filterTimer = null;
  el.querySelector('#word-filter').addEventListener('input', e => {
    clearTimeout(filterTimer);
    filterTimer = setTimeout(() => renderWordList(el, book, e.target.value.trim()), 200);
  });

  await loadBookDetail(el, book);
}

async function loadBookDetail(el, book) {
  try {
    const data = await api.get(`/api/wordbooks/${book.book_id}/words`);
    _currentBook = data.book;
    renderBookStats(el, data.book);
    renderWordList(el, book, '', data.words);
  } catch (e) {
    el.querySelector('#book-words-container').innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

function renderBookStats(el, book) {
  const row = el.querySelector('#book-stats-row');
  if (!row) return;
  row.innerHTML = `
    <div class="card" style="flex:1;min-width:90px;text-align:center;padding:14px">
      <div style="font-size:22px;font-weight:700">${book.word_count || 0}</div>
      <div style="font-size:11px;color:var(--text-dim)">Total words</div>
    </div>
    <div class="card" style="flex:1;min-width:90px;text-align:center;padding:14px">
      <div style="font-size:22px;font-weight:700">${book.due_today || 0}</div>
      <div style="font-size:11px;color:var(--text-dim)">Due today</div>
    </div>`;
}
let _allWords = [];

function renderWordList(el, book, filter, words) {
  if (words !== undefined) _allWords = words;
  const container = el.querySelector('#book-words-container');
  if (!container) return;
  const list = filter
    ? _allWords.filter(w => w.word.toLowerCase().includes(filter.toLowerCase()) ||
        (w.definition_en || '').toLowerCase().includes(filter.toLowerCase()))
    : _allWords;

  if (!list.length) {
    container.innerHTML = filter
      ? `<div style="color:var(--text-dim);padding:20px 0">No words match "${escHtml(filter)}"</div>`
      : `<div class="card" style="text-align:center;padding:32px">
           <div style="font-size:36px;margin-bottom:10px">📭</div>
           <p style="color:var(--text-dim)">No words yet. Click "+ Add Word" to get started.</p>
         </div>`;
    return;
  }

  container.innerHTML = `
    <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px">${list.length} word${list.length !== 1 ? 's' : ''}</div>
    <div class="word-list">
      ${list.map(w => wordRow(w, book.book_id)).join('')}
    </div>`;

  container.querySelectorAll('.btn-remove-word').forEach(btn => {
    btn.addEventListener('click', async () => {
      const wordId = btn.dataset.wordId;
      btn.disabled = true;
      try {
        await fetch(`/api/wordbooks/${book.book_id}/words/${wordId}`, { method: 'DELETE' });
        _allWords = _allWords.filter(w => w.word_id !== wordId);
        renderWordList(el, book, el.querySelector('#word-filter')?.value.trim() || '');
      } catch { btn.disabled = false; }
    });
  });
}

function wordRow(w, bookId) {
  const interval = w.interval ? `<span style="font-size:11px;color:var(--text-dim)">${w.interval}d</span>` : '';
  const isNew = !w.card_id ? `<span class="tag tag-green" style="font-size:10px">NEW</span>` : '';
  return `
    <div class="word-row" style="display:flex;align-items:center;gap:12px;padding:10px 14px;border-bottom:1px solid var(--border)">
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-weight:600">${escHtml(w.word)}</span>
          ${w.part_of_speech ? `<span style="font-size:11px;color:var(--text-dim)">${escHtml(w.part_of_speech)}</span>` : ''}
          ${isNew}
        </div>
        <div style="font-size:12px;color:var(--text-dim);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
          ${escHtml(w.definition_en || '')}
          ${w.definition_zh ? ` · ${escHtml(w.definition_zh)}` : ''}
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
        ${interval}
        <button class="tts-btn" onclick="tts('${w.word.replace(/'/g,"\\'")}')">🔊</button>
        <button class="btn btn-outline btn-remove-word" data-word-id="${w.word_id}" style="font-size:11px;padding:3px 8px;color:var(--red)">✕</button>
      </div>
    </div>`;
}

// ── Add Word Panel ─────────────────────────────────────────────────

function showAddWordPanel(el, book) {
  const panel = el.querySelector('#add-word-panel-book');
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

  panel.querySelector('#btn-ai-fill-book').addEventListener('click', () => aiFill(panel, wordInput, statusDiv, fieldsDiv));
  panel.querySelector('#btn-add-confirm-book').addEventListener('click', () => addWordToBook(panel, book, el));
  wordInput.focus();
}
async function searchVocab(q, resultsEl, wordInput, panel) {
  try {
    const results = await api.get(`/api/wordbooks/search/vocab?q=${encodeURIComponent(q)}&limit=6`);
    if (!results.length) { resultsEl.innerHTML = ''; return; }
    resultsEl.innerHTML = `
      <div style="border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:8px">
        ${results.map(r => `
          <div class="search-result-row" data-word-id="${r.word_id}" data-word="${escHtml(r.word)}"
               style="padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px">
            <div style="flex:1">
              <span style="font-weight:600">${escHtml(r.word)}</span>
              ${r.part_of_speech ? `<span style="font-size:11px;color:var(--text-dim);margin-left:6px">${escHtml(r.part_of_speech)}</span>` : ''}
              <div style="font-size:12px;color:var(--text-dim)">${escHtml(r.definition_en || '')}</div>
            </div>
            <span style="font-size:11px;color:var(--text-dim)">${escHtml(r.source || '')}</span>
          </div>`).join('')}
      </div>`;
    resultsEl.querySelectorAll('.search-result-row').forEach(row => {
      row.addEventListener('mouseenter', () => row.style.background = 'var(--bg3)');
      row.addEventListener('mouseleave', () => row.style.background = '');
      row.addEventListener('click', () => {
        wordInput.value = row.dataset.word;
        wordInput.dataset.wordId = row.dataset.wordId;
        resultsEl.innerHTML = '';
        panel.querySelector('#add-fields-book').style.display = '';
        // Fill fields from search result
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

async function aiFill(panel, wordInput, statusDiv, fieldsDiv) {
  const word = wordInput.value.trim();
  if (!word) { wordInput.focus(); return; }
  fieldsDiv.style.display = '';
  const btn = panel.querySelector('#btn-ai-fill-book');
  btn.disabled = true;
  statusDiv.textContent = '✨ Fetching AI enrichment…';
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
  } catch (e) {
    statusDiv.textContent = `AI unavailable: ${e.message}`;
  }
  btn.disabled = false;
}

async function addWordToBook(panel, book, el) {
  const wordInput = panel.querySelector('#add-word-input-book');
  const word = wordInput.value.trim();
  const defEn = panel.querySelector('#add-def-en-book').value.trim();
  const msg = panel.querySelector('#add-msg-book');
  if (!word) { wordInput.focus(); return; }

  const existingWordId = wordInput.dataset.wordId || null;

  // If adding from search (existing word), no definition required
  // If creating new word, definition is required
  if (!existingWordId && !defEn) {
    msg.innerHTML = '<div class="alert alert-error" style="margin-bottom:8px">English definition is required</div>';
    return;
  }

  const btn = panel.querySelector('#btn-add-confirm-book');
  btn.disabled = true;
  try {
    const payload = existingWordId
      ? { word_id: existingWordId }
      : {
          word,
          definition_en:   defEn,
          definition_zh:   panel.querySelector('#add-def-zh-book').value.trim(),
          part_of_speech:  panel.querySelector('#add-pos-book').value.trim(),
          pronunciation:   panel.querySelector('#add-pron-book').value.trim(),
          example:         panel.querySelector('#add-example-book').value.trim(),
          synonyms:        panel.querySelector('#add-synonyms-book').value.trim(),
          antonyms:        panel.querySelector('#add-antonyms-book').value.trim(),
        };
    console.log('[WordBook] Adding word:', { book_id: book.book_id, book_name: book.name, word, payload });
    const result = await api.post(`/api/wordbooks/${book.book_id}/words`, payload);
    console.log('[WordBook] Add result:', result);

    if (result.already_exists) {
      // Word already exists in book - navigate to it
      msg.innerHTML = `<div class="alert alert-warning" style="margin-bottom:8px">⚠ "${escHtml(word)}" already exists in this book</div>`;
      setTimeout(() => { msg.innerHTML = ''; }, 2500);
      await loadBookDetail(el, book);
      // Scroll to the word in the list
      setTimeout(() => {
        const wordRow = el.querySelector(`.btn-remove-word[data-word-id="${result.word_id}"]`)?.closest('.word-row');
        if (wordRow) {
          wordRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
          wordRow.style.background = 'var(--accent-dim)';
          setTimeout(() => { wordRow.style.background = ''; }, 2000);
        }
      }, 300);
    } else {
      // Successfully added new word
      msg.innerHTML = `<div class="alert alert-success" style="margin-bottom:8px">✓ "${escHtml(word)}" added!</div>`;
      // Reset form
      wordInput.value = ''; wordInput.dataset.wordId = '';
      ['#add-def-en-book','#add-def-zh-book','#add-pos-book','#add-pron-book',
       '#add-example-book','#add-synonyms-book','#add-antonyms-book'].forEach(id => {
        panel.querySelector(id).value = '';
      });
      panel.querySelector('#add-fields-book').style.display = 'none';
      setTimeout(() => { msg.innerHTML = ''; }, 2500);
      await loadBookDetail(el, book);
    }
  } catch (e) {
    msg.innerHTML = `<div class="alert alert-error" style="margin-bottom:8px">${e.message}</div>`;
  }
  btn.disabled = false;
}

// ── Study Session ──────────────────────────────────────────────────

async function startBookSession(el, book) {
  el.innerHTML = `<div style="text-align:center;padding:60px"><div class="spinner"></div><p style="margin-top:16px;color:var(--text-dim)">Loading session…</p></div>`;
  try {
    const r = await api.post(`/api/wordbooks/${book.book_id}/start`, { max_cards: 20 });
    if (r.empty) {
      el.innerHTML = `
        <div class="card" style="text-align:center;padding:40px;max-width:480px;margin:0 auto">
          <div style="font-size:48px;margin-bottom:12px">🎉</div>
          <h2>All caught up!</h2>
          <p style="color:var(--text-dim);margin:12px 0">No cards due in <strong>${escHtml(book.name)}</strong>. Come back tomorrow!</p>
          <button class="btn btn-outline" id="btn-back-empty">← Back to Books</button>
        </div>`;
      el.querySelector('#btn-back-empty').addEventListener('click', () => showBookList(el));
      return;
    }
    el.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px">
        <button class="btn btn-outline" id="btn-back-session" style="font-size:12px;padding:4px 10px">← ${escHtml(book.name)}</button>
        <span style="font-size:13px;color:var(--text-dim)">${r.total} cards</span>
      </div>
      <div id="vocab-session-host"></div>`;
    el.querySelector('#btn-back-session').addEventListener('click', () => showBookDetail(el, book));
    const host = el.querySelector('#vocab-session-host');
    // Bootstrap the vocab session with the already-started session
    runVocabSession(host, r);
  } catch (e) {
    el.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}
// ── Inline Vocab Session (reuses vocab card UI logic) ──────────────

let _vsid = null, _vtotal = 0, _vremaining = 0, _vrevealed = false, _vkeyHandler = null;

function runVocabSession(el, startData) {
  _vsid = startData.session_id;
  _vtotal = startData.total;
  _vremaining = startData.remaining;
  _vrevealed = false;
  renderVCard(el, startData.card, false, startData.word_list_label || '');
}

function renderVCard(el, card, revealed, label) {
  _vrevealed = revealed;
  const done = _vtotal - _vremaining;
  const pct = Math.round((done / _vtotal) * 100);

  el.innerHTML = `
    <div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:${pct}%"></div></div>
    <div style="display:flex;justify-content:space-between;font-size:13px;color:var(--text-dim);margin-bottom:16px">
      <span>${done} / ${_vtotal} cards</span>
      ${label ? `<span style="font-size:12px">${escHtml(label)}</span>` : ''}
    </div>
    <div class="flashcard-wrap">
      <div class="flashcard${revealed ? ' flipped' : ''}" id="vfc">
        <div class="flashcard-front">
          <div class="flashcard-word">${escHtml(card.word)} <button class="tts-btn" onclick="event.stopPropagation();tts('${card.word.replace(/'/g,"\\'")}')">🔊</button></div>
          ${card.part_of_speech ? `<div class="flashcard-pos">${escHtml(card.part_of_speech)}</div>` : ''}
          ${card.pronunciation ? `<div class="flashcard-pron">${escHtml(card.pronunciation)}</div>` : ''}
          ${card.is_new ? '<div class="tag tag-green" style="margin-top:12px">NEW</div>' : ''}
          <div class="flashcard-hint">Click or press Space to flip</div>
        </div>
        <div class="flashcard-back" id="vfc-back">
          <div class="def-en">${escHtml(card.definition_en || '')}</div>
          <div class="def-zh">${escHtml(card.definition_zh || '')}</div>
          ${card.example ? `<div class="example">"${escHtml(card.example)}" <button class="tts-btn" onclick="tts('${card.example.replace(/'/g,"\\'").replace(/"/g,'&quot;')}')">🔊</button></div>` : ''}
        </div>
      </div>
    </div>
    <div id="vrating-area" class="${revealed ? '' : 'hidden'}" style="text-align:center">
      <p style="margin-bottom:8px;font-size:13px;color:var(--text-dim)">How well did you know it?</p>
      <div class="rating-bar">
        <button class="rating-btn" data-q="1" title="Forgot">1</button>
        <button class="rating-btn" data-q="2" title="Hard">2</button>
        <button class="rating-btn" data-q="3" title="OK">3</button>
        <button class="rating-btn" data-q="4" title="Good">4</button>
        <button class="rating-btn" data-q="5" title="Easy">5</button>
      </div>
      <div style="display:flex;justify-content:center;gap:20px;margin-top:8px;font-size:11px;color:var(--text-dim)">
        <span>1=Forgot</span><span>3=OK</span><span>5=Easy</span><span style="margin-left:8px">Keys 1–5</span>
      </div>
    </div>`;

  const fc = el.querySelector('#vfc');
  fc.addEventListener('click', async () => {
    if (_vrevealed) return;
    fc.classList.add('flipped');
    _vrevealed = true;
    try {
      const detail = await api.post(`/api/vocab/reveal/${_vsid}`, {});
      const back = el.querySelector('#vfc-back');
      back.innerHTML = `
        <div class="def-en">${escHtml(detail.definition_en || '')}</div>
        <div class="def-zh">${escHtml(detail.definition_zh || '')}</div>
        ${detail.example ? `<div class="example">"${escHtml(detail.example)}" <button class="tts-btn" onclick="tts('${detail.example.replace(/'/g,"\\'").replace(/"/g,'&quot;')}')">🔊</button></div>` : ''}
        ${detail.synonyms ? `<div class="field" style="margin-top:8px"><span style="color:var(--text-dim)">Synonyms: </span>${escHtml(detail.synonyms)}</div>` : ''}
        ${detail.antonyms ? `<div class="field"><span style="color:var(--text-dim)">Antonyms: </span>${escHtml(detail.antonyms)}</div>` : ''}
        ${detail.collocations ? `<div class="field"><span style="color:var(--text-dim)">Collocations: </span>${escHtml(detail.collocations)}</div>` : ''}`;
    } catch {}
    el.querySelector('#vrating-area').classList.remove('hidden');
  });

  el.querySelectorAll('.rating-btn').forEach(btn => {
    btn.addEventListener('click', () => rateVCard(el, parseInt(btn.dataset.q), label));
  });

  if (_vkeyHandler) document.removeEventListener('keydown', _vkeyHandler);
  _vkeyHandler = (e) => {
    if (e.code === 'Space' && !_vrevealed) { e.preventDefault(); el.querySelector('#vfc')?.click(); }
    else if (_vrevealed && e.key >= '1' && e.key <= '5') {
      const btn = el.querySelector(`.rating-btn[data-q="${e.key}"]`);
      if (btn && !btn.disabled) btn.click();
    }
  };
  document.addEventListener('keydown', _vkeyHandler);
}

async function rateVCard(el, quality, label) {
  el.querySelectorAll('.rating-btn').forEach(b => b.disabled = true);
  try {
    const r = await api.post(`/api/vocab/rate/${_vsid}`, { quality });
    if (r.complete) {
      if (_vkeyHandler) { document.removeEventListener('keydown', _vkeyHandler); _vkeyHandler = null; }
      const color = r.stats.accuracy >= 80 ? 'var(--green)' : r.stats.accuracy >= 60 ? 'var(--yellow)' : 'var(--red)';
      el.innerHTML = `
        <div class="card" style="text-align:center;padding:40px">
          <div style="font-size:48px;margin-bottom:16px">🎉</div>
          <h2>Session Complete!</h2>
          <div style="font-size:36px;font-weight:700;color:${color};margin:16px 0">${r.stats.accuracy}%</div>
          <p>${r.stats.correct} / ${r.stats.reviewed} correct</p>
        </div>`;
    } else {
      _vremaining = r.remaining;
      renderVCard(el, r.card, false, label);
      ttsPreload && ttsPreload(r.card.word);
    }
  } catch (e) { console.error(e); }
}

// ── Utilities ──────────────────────────────────────────────────────

function escHtml(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}





