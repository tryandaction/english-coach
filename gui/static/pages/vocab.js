// pages/vocab.js — Unified Vocabulary: flashcards + word books

// ── Shared state ──────────────────────────────────────────────────
let _sid = null, _total = 0, _remaining = 0, _revealed = false;
let _keyHandler = null;
let _exam = 'general', _wordListLabel = '';
let _currentTab = 'study';
let _currentBook = null;
let _allWords = [];
let _searchTimeout = null;
const AUTO_TTS_KEY = 'vocab_auto_tts';
const LEGACY_AUTO_TTS_KEY = 'autoTts';
const BUILTIN_SYNC_KEY = 'vocab_builtin_sync_v2';
let _autoTts = (() => {
  const v = localStorage.getItem(AUTO_TTS_KEY);
  if (v !== null) return v !== 'false';
  const legacy = localStorage.getItem(LEGACY_AUTO_TTS_KEY);
  return legacy !== 'false';
})();
let _cardContainer = null;
let _currentCard = null;
let _builtinSyncPromise = null;
let _builtinSyncResolved = false;
let _autoTtsStamp = { key: '', ts: 0 };

const _vocabStore = {
  get: () => { try { return JSON.parse(localStorage.getItem('vocab_session')); } catch { return null; } },
  set: (v) => { try { localStorage.setItem('vocab_session', JSON.stringify(v)); } catch {} },
  clear: () => { try { localStorage.removeItem('vocab_session'); } catch {} },
};

async function loadStudyOverview() {
  let exam = 'general';
  let deck = { total: 0, due_today: 0, mature: 0 };
  let library = { total_words: 0, by_level: [], by_subject: [] };
  let subjects = [];

  try {
    const progress = await api.get('/api/progress');
    exam = (progress.target_exam || 'general').toLowerCase();
  } catch {}

  try { deck = await api.get('/api/vocab/deck-stats'); } catch {}
  try { library = await api.get(`/api/vocab/stats?exam=${encodeURIComponent(exam)}`); } catch {}
  try {
    const subjectResp = await api.get(`/api/vocab/subjects?exam=${encodeURIComponent(exam)}`);
    subjects = (subjectResp.subjects || []).slice(0, 6);
  } catch {}

  return { exam, deck, library, subjects };
}

function ensureBuiltinSync() {
  if (_builtinSyncResolved || localStorage.getItem(BUILTIN_SYNC_KEY) === 'done') {
    _builtinSyncResolved = true;
    return null;
  }
  if (_builtinSyncPromise) return _builtinSyncPromise;

  _builtinSyncPromise = api.post('/api/vocab/ingest_builtin', {})
    .then((result) => {
      if (result?.ok) {
        localStorage.setItem(BUILTIN_SYNC_KEY, 'done');
        _builtinSyncResolved = true;
      }
      return result;
    })
    .catch(() => null)
    .finally(() => {
      _builtinSyncPromise = null;
    });

  return _builtinSyncPromise;
}

function renderStudyOverview(overview) {
  const levelHtml = (overview.library.by_level || []).map(row => `
    <div class="card" style="flex:1;min-width:84px;text-align:center;padding:12px">
      <div style="font-size:20px;font-weight:700">${row.word_count || 0}</div>
      <div style="font-size:11px;color:var(--text-dim)">Level ${row.level}</div>
    </div>
  `).join('');

  const subjectHtml = (overview.subjects || []).length
    ? overview.subjects.map(subject => `<span class="tag">${escHtml(subject.subject)} · ${subject.word_count}</span>`).join(' ')
    : '<span style="font-size:12px;color:var(--text-dim)">No subject metadata yet</span>';

  return `
    <div class="card" style="margin-bottom:16px;padding:18px">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap">
        <div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:6px">CURRENT LIBRARY</div>
          <div style="font-size:22px;font-weight:700">${overview.library.total_words || 0} <span style="font-size:14px;color:var(--text-dim)">${escHtml((overview.exam || 'general').toUpperCase())} built-in words</span></div>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
          <span class="tag">Deck ${overview.deck.total || 0}</span>
          <span class="tag">Due ${overview.deck.due_today || 0}</span>
          <span class="tag">Mature ${overview.deck.mature || 0}</span>
        </div>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:14px">${levelHtml}</div>
      <div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap">${subjectHtml}</div>
    </div>
  `;
}

function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function normalizeWordInput(value) {
  return String(value || '').trim().toLowerCase();
}

function createWordDraft(source = {}) {
  return {
    word_id: String(source.word_id || ''),
    source: String(source.source || ''),
    word: String(source.word || ''),
    definition_en: String(source.definition_en || ''),
    definition_zh: String(source.definition_zh || ''),
    part_of_speech: String(source.part_of_speech || ''),
    pronunciation: String(source.pronunciation || ''),
    example: String(source.example || ''),
    synonyms: String(source.synonyms || ''),
    antonyms: String(source.antonyms || ''),
    derivatives: String(source.derivatives || ''),
    collocations: String(source.collocations || ''),
    context_sentence: String(source.context_sentence || ''),
  };
}

function getWordEditorNodes(root, prefix) {
  const pick = suffix => root.querySelector(`#${prefix}-${suffix}`);
  return {
    wordInput: pick('word'),
    searchResults: pick('search-results'),
    status: pick('status'),
    preview: pick('preview'),
    message: pick('message'),
    aiFill: pick('ai-fill'),
    clear: pick('clear'),
    close: pick('close'),
    submit: pick('submit'),
    fields: {
      definition_en: pick('def-en'),
      definition_zh: pick('def-zh'),
      part_of_speech: pick('pos'),
      pronunciation: pick('pron'),
      example: pick('example'),
      synonyms: pick('synonyms'),
      antonyms: pick('antonyms'),
      collocations: pick('collocations'),
      derivatives: pick('derivatives'),
      context_sentence: pick('context'),
    },
  };
}

function setWordSelection(nodes, draft) {
  if (!nodes.wordInput) return;
  const normalizedWord = normalizeWordInput(draft.word);
  if (draft.word_id) {
    nodes.wordInput.dataset.wordId = draft.word_id;
    nodes.wordInput.dataset.selectedWord = normalizedWord;
    nodes.wordInput.dataset.wordSource = draft.source || '';
  } else {
    delete nodes.wordInput.dataset.wordId;
    delete nodes.wordInput.dataset.selectedWord;
    delete nodes.wordInput.dataset.wordSource;
  }
}

function collectWordEditorDraft(root, prefix) {
  const nodes = getWordEditorNodes(root, prefix);
  return createWordDraft({
    word_id: nodes.wordInput?.dataset.wordId || '',
    source: nodes.wordInput?.dataset.wordSource || '',
    word: nodes.wordInput?.value.trim() || '',
    definition_en: nodes.fields.definition_en?.value.trim() || '',
    definition_zh: nodes.fields.definition_zh?.value.trim() || '',
    part_of_speech: nodes.fields.part_of_speech?.value.trim() || '',
    pronunciation: nodes.fields.pronunciation?.value.trim() || '',
    example: nodes.fields.example?.value.trim() || '',
    synonyms: nodes.fields.synonyms?.value.trim() || '',
    antonyms: nodes.fields.antonyms?.value.trim() || '',
    derivatives: nodes.fields.derivatives?.value.trim() || '',
    collocations: nodes.fields.collocations?.value.trim() || '',
    context_sentence: nodes.fields.context_sentence?.value.trim() || '',
  });
}

function renderWordPreviewHtml(draft) {
  const word = draft.word || 'Word preview';
  const meta = [draft.part_of_speech, draft.pronunciation].filter(Boolean);
  const notes = [
    draft.definition_en ? `<div class="vocab-editor-preview-block"><div class="vocab-editor-preview-label">Definition</div><div>${escHtml(draft.definition_en)}</div></div>` : '',
    draft.definition_zh ? `<div class="vocab-editor-preview-block"><div class="vocab-editor-preview-label">中文释义</div><div>${escHtml(draft.definition_zh)}</div></div>` : '',
    draft.example ? `<div class="vocab-editor-preview-block"><div class="vocab-editor-preview-label">Example</div><div>${escHtml(draft.example)}</div></div>` : '',
    draft.context_sentence ? `<div class="vocab-editor-preview-block"><div class="vocab-editor-preview-label">Context</div><div>${escHtml(draft.context_sentence)}</div></div>` : '',
  ].filter(Boolean);
  const chips = [
    draft.synonyms ? `Synonyms · ${escHtml(draft.synonyms)}` : '',
    draft.antonyms ? `Antonyms · ${escHtml(draft.antonyms)}` : '',
    draft.collocations ? `Collocations · ${escHtml(draft.collocations)}` : '',
    draft.derivatives ? `Derivatives · ${escHtml(draft.derivatives)}` : '',
  ].filter(Boolean);
  const stateTag = draft.word_id
    ? '<span class="tag">Existing entry</span>'
    : '<span class="tag tag-green">New draft</span>';
  const sourceTag = draft.source ? `<span class="tag">${escHtml(draft.source)}</span>` : '';

  return `
    <div class="vocab-editor-preview-card">
      <div class="vocab-editor-preview-head">
        <span class="tag">Live Card</span>
        ${stateTag}
        ${sourceTag}
      </div>
      <div class="vocab-editor-preview-word">${escHtml(word)}</div>
      ${meta.length ? `<div class="vocab-editor-preview-meta">${meta.map(escHtml).join(' · ')}</div>` : '<div class="vocab-editor-preview-meta">Word / part of speech / pronunciation update here in real time.</div>'}
      <div class="vocab-editor-preview-body">
        ${notes.length ? notes.join('') : '<div class="vocab-editor-preview-empty">Fill the form or run AI Fill to build the card preview.</div>'}
      </div>
      ${chips.length ? `<div class="vocab-editor-preview-tags">${chips.map(text => `<span class="tag">${text}</span>`).join('')}</div>` : ''}
    </div>
  `;
}

function syncWordEditorPreview(root, prefix) {
  const nodes = getWordEditorNodes(root, prefix);
  if (!nodes.preview) return;
  nodes.preview.innerHTML = renderWordPreviewHtml(collectWordEditorDraft(root, prefix));
}

function applyWordEditorDraft(root, prefix, draft) {
  const nodes = getWordEditorNodes(root, prefix);
  const next = createWordDraft(draft);
  if (nodes.wordInput) nodes.wordInput.value = next.word;
  Object.entries(nodes.fields).forEach(([key, field]) => {
    if (field) field.value = next[key] || '';
  });
  setWordSelection(nodes, next);
  syncWordEditorPreview(root, prefix);
}

function resetWordEditor(root, prefix, draft = createWordDraft()) {
  const nodes = getWordEditorNodes(root, prefix);
  applyWordEditorDraft(root, prefix, draft);
  if (nodes.searchResults) nodes.searchResults.innerHTML = '';
  if (nodes.message) nodes.message.innerHTML = '';
}

function setWordEditorStatus(root, prefix, text, tone = 'muted') {
  const nodes = getWordEditorNodes(root, prefix);
  if (!nodes.status) return;
  nodes.status.textContent = text || '';
  nodes.status.dataset.tone = tone;
}

function buildWordSavePayload(draft, includeWordId = false) {
  const payload = {
    word: draft.word,
    definition_en: draft.definition_en,
    definition_zh: draft.definition_zh,
    part_of_speech: draft.part_of_speech,
    pronunciation: draft.pronunciation,
    example: draft.example,
    synonyms: draft.synonyms,
    antonyms: draft.antonyms,
    derivatives: draft.derivatives,
    collocations: draft.collocations,
    context_sentence: draft.context_sentence,
  };
  if (includeWordId && draft.word_id) payload.word_id = draft.word_id;
  return payload;
}

function wordEditorMarkup(prefix, options = {}) {
  const {
    title = '',
    subtitle = '',
    primaryLabel = 'Save',
    primaryClass = 'btn-primary',
    clearLabel = 'Clear',
    closeLabel = 'Close',
    showClose = false,
  } = options;
  return `
    <div class="vocab-editor-shell">
      ${title ? `
        <div class="vocab-editor-header">
          <div>
            <div class="vocab-editor-title">${title}</div>
            ${subtitle ? `<div class="vocab-editor-subtitle">${subtitle}</div>` : ''}
          </div>
          ${showClose ? `<button class="btn btn-outline" id="${prefix}-close" style="font-size:12px;padding:6px 12px">✕ ${closeLabel}</button>` : ''}
        </div>` : ''}
      <div class="vocab-editor-toolbar">
        <input id="${prefix}-word" type="text" placeholder="Search or type a word…" autocomplete="off">
        <button class="btn btn-outline" id="${prefix}-ai-fill" style="white-space:nowrap">✨ AI Fill</button>
        <button class="btn btn-outline" id="${prefix}-clear" style="white-space:nowrap">↺ ${clearLabel}</button>
      </div>
      <div id="${prefix}-search-results" class="vocab-editor-search-results"></div>
      <div id="${prefix}-status" class="vocab-editor-status" data-tone="muted"></div>
      <div class="vocab-editor-grid">
        <div id="${prefix}-preview"></div>
        <div class="vocab-editor-form">
          <div class="form-group vocab-editor-span-2">
            <label>Definition (English)</label>
            <textarea id="${prefix}-def-en" rows="2" placeholder="e.g. to speak for a long time in a formal way"></textarea>
          </div>
          <div class="form-group vocab-editor-span-2">
            <label>Definition (Chinese) <span style="color:var(--text-dim)">(optional)</span></label>
            <textarea id="${prefix}-def-zh" rows="2" placeholder="例如：正式发表长篇讲话"></textarea>
          </div>
          <div class="vocab-editor-inline-grid vocab-editor-inline-grid-wide">
            <div class="form-group"><label>Part of speech</label><input id="${prefix}-pos" type="text" placeholder="verb"></div>
            <div class="form-group"><label>Pronunciation</label><input id="${prefix}-pron" type="text" placeholder="/pɒnˈtɪf.ɪ.keɪt/"></div>
          </div>
          <div class="form-group vocab-editor-span-2">
            <label>Example sentence</label>
            <textarea id="${prefix}-example" rows="3" placeholder="e.g. He began to pontificate about politics at dinner."></textarea>
          </div>
          <div class="vocab-editor-inline-grid">
            <div class="form-group"><label>Synonyms</label><input id="${prefix}-synonyms" type="text" placeholder="lecture, sermonize"></div>
            <div class="form-group"><label>Antonyms</label><input id="${prefix}-antonyms" type="text" placeholder="listen, defer"></div>
          </div>
          <div class="vocab-editor-inline-grid vocab-editor-inline-grid-colloc">
            <div class="form-group"><label>Collocations</label><input id="${prefix}-collocations" type="text" placeholder="pontificate on politics"></div>
            <div class="form-group"><label>Derivatives</label><input id="${prefix}-derivatives" type="text" placeholder="pontification"></div>
          </div>
          <div class="form-group vocab-editor-span-2">
            <label>Context sentence</label>
            <textarea id="${prefix}-context" rows="2" placeholder="Add a usage note or scenario for this card."></textarea>
          </div>
        </div>
      </div>
      <div id="${prefix}-message"></div>
      <div class="vocab-editor-actions">
        <button class="btn ${primaryClass}" id="${prefix}-submit">${primaryLabel}</button>
      </div>
    </div>
  `;
}

async function searchVocab(q, resultsEl, onPick) {
  try {
    const results = await api.get(`/api/wordbooks/search/vocab?q=${encodeURIComponent(q)}&limit=6`);
    if (!results.length) {
      resultsEl.innerHTML = '';
      return;
    }
    resultsEl.innerHTML = `
      <div class="vocab-editor-search-panel">
        ${results.map((r, index) => `
          <button type="button" class="vocab-editor-search-row" data-result-index="${index}">
            <div style="flex:1;min-width:0;text-align:left">
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                <span style="font-weight:700">${escHtml(r.word)}</span>
                ${r.part_of_speech ? `<span style="font-size:11px;color:var(--text-dim)">${escHtml(r.part_of_speech)}</span>` : ''}
                ${r.pronunciation ? `<span style="font-size:11px;color:var(--accent)">${escHtml(r.pronunciation)}</span>` : ''}
              </div>
              <div style="font-size:12px;color:var(--text-dim);margin-top:4px">${escHtml(r.definition_en || '')}${r.definition_zh ? ` · ${escHtml(r.definition_zh)}` : ''}</div>
            </div>
            <span class="tag">${escHtml(r.source || 'library')}</span>
          </button>`).join('')}
      </div>
    `;
    resultsEl.querySelectorAll('.vocab-editor-search-row').forEach(row => {
      row.addEventListener('click', () => {
        const match = results[Number(row.dataset.resultIndex)];
        if (match) onPick(match);
      });
    });
  } catch {
    resultsEl.innerHTML = '';
  }
}

function bindWordEditor(root, prefix, options = {}) {
  const nodes = getWordEditorNodes(root, prefix);
  const searchEnabled = options.searchEnabled !== false;
  let searchTimer = null;

  const refreshPreview = () => syncWordEditorPreview(root, prefix);
  refreshPreview();

  nodes.wordInput?.addEventListener('input', () => {
    const normalized = normalizeWordInput(nodes.wordInput.value);
    const selectedWord = normalizeWordInput(nodes.wordInput.dataset.selectedWord || '');
    if (nodes.wordInput.dataset.wordId && normalized !== selectedWord) {
      setWordSelection(nodes, createWordDraft());
      setWordEditorStatus(root, prefix, 'Switched to a new draft. Search again to reuse an existing entry.', 'muted');
    }
    refreshPreview();
    if (!searchEnabled || !nodes.searchResults) return;
    clearTimeout(searchTimer);
    if (normalized.length < 2) {
      nodes.searchResults.innerHTML = '';
      return;
    }
    searchTimer = setTimeout(() => {
      searchVocab(nodes.wordInput.value.trim(), nodes.searchResults, (match) => {
        applyWordEditorDraft(root, prefix, createWordDraft(match));
        if (nodes.searchResults) nodes.searchResults.innerHTML = '';
        setWordEditorStatus(root, prefix, 'Loaded existing entry. Save to update this card and keep everything in sync.', 'info');
        options.onPick?.(match);
      });
    }, 250);
  });

  Object.values(nodes.fields).forEach(field => field?.addEventListener('input', refreshPreview));

  nodes.aiFill?.addEventListener('click', async () => {
    const word = nodes.wordInput?.value.trim();
    if (!word) {
      nodes.wordInput?.focus();
      return;
    }
    nodes.aiFill.disabled = true;
    setWordEditorStatus(root, prefix, '✨ Fetching AI enrichment…', 'info');
    try {
      const current = collectWordEditorDraft(root, prefix);
      const enriched = await api.post('/api/vocab/enrich', { word });
      applyWordEditorDraft(root, prefix, { ...current, ...enriched, word });
      setWordEditorStatus(root, prefix, '✓ AI fill complete. Preview has been refreshed.', 'success');
    } catch (e) {
      setWordEditorStatus(root, prefix, `AI unavailable: ${e.message}`, 'error');
    }
    nodes.aiFill.disabled = false;
  });

  nodes.clear?.addEventListener('click', () => {
    if (typeof options.onClear === 'function') {
      options.onClear();
    } else {
      resetWordEditor(root, prefix);
      setWordEditorStatus(root, prefix, 'Draft cleared.', 'muted');
    }
  });

  nodes.close?.addEventListener('click', () => options.onClose?.());
  nodes.submit?.addEventListener('click', async () => options.onSubmit?.());
}

function setAutoTts(enabled) {
  _autoTts = !!enabled;
  localStorage.setItem(AUTO_TTS_KEY, String(_autoTts));
  // Keep legacy key for backward compatibility.
  localStorage.setItem(LEGACY_AUTO_TTS_KEY, String(_autoTts));
}

function autoTtsButtonHtml() {
  return `<button class="btn ${_autoTts ? 'btn-primary' : 'btn-outline'}" id="btn-auto-tts" style="font-size:12px;padding:5px 12px">${_autoTts ? '🔊 Auto Read: ON' : '🔇 Auto Read: OFF'}</button>`;
}

function bindAutoTtsButton(root) {
  const btn = root.querySelector('#btn-auto-tts');
  if (!btn) return;
  btn.addEventListener('click', () => {
    setAutoTts(!_autoTts);
    btn.className = `btn ${_autoTts ? 'btn-primary' : 'btn-outline'}`;
    btn.textContent = _autoTts ? '🔊 Auto Read: ON' : '🔇 Auto Read: OFF';
    // Give immediate feedback when turning on.
    if (_autoTts && !_revealed && _currentCard?.word) tts(_currentCard.word);
  });
}

function maybeAutoReadCurrentWord(revealed) {
  if (_autoTts && !revealed && _currentCard?.word) {
    const word = String(_currentCard.word || '').trim();
    if (!word) return;
    const key = `${_sid || 'none'}:${word}`;
    const now = Date.now();
    if (_autoTtsStamp.key === key && now - _autoTtsStamp.ts < 3000) return;
    _autoTtsStamp = { key, ts: now };
    ttsPreload(word);
    setTimeout(() => {
      if (_currentCard?.word === word && !_revealed) tts(word);
    }, 50);
  }
}

// ── Entry point ───────────────────────────────────────────────────

export async function render(el) {
  _sid = null; _revealed = false; _currentBook = null;
  _currentTab = 'study';
  renderShell(el);
  ensureBuiltinSync();
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
  const syncPromise = ensureBuiltinSync();
  const overview = await loadStudyOverview();
  if (api.isAborted() || !el.isConnected) return;

  if (syncPromise) {
    syncPromise.then((result) => {
      if (result?.ok && _currentTab === 'study' && el.isConnected) {
        renderStudyTab(el, content);
      }
    });
  }

  const overviewHtml = renderStudyOverview(overview);

  // Restore in-progress session (navigate-back)
  const saved = _vocabStore.get();
  if (saved && saved.session_id) {
    _sid = saved.session_id;
    _total = saved.total;
    _remaining = saved.remaining;
    _exam = saved.exam || 'general';
    _wordListLabel = saved.word_list_label || '';
    content.innerHTML = `
      ${overviewHtml}
      <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;flex-wrap:wrap">
        ${autoTtsButtonHtml()}
        <span style="font-size:12px;color:var(--text-dim)">Auto pronounce current word</span>
      </div>`;
    const cardDiv = document.createElement('div');
    _cardContainer = cardDiv;
    content.appendChild(cardDiv);
    bindAutoTtsButton(content);
    renderCard(el, cardDiv, saved.card, false);
    if (saved.card) { ttsPreload && ttsPreload(saved.card.word); }
    return;
  }

  try {
    const r = await api.post('/api/vocab/start', { max_cards: 20 });
    if (r.empty) {
      let stats = {};
      try { stats = await api.get('/api/vocab/deck-stats'); } catch {}
      content.innerHTML = `
        ${overviewHtml}
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

    // Preload TTS immediately when session starts
    if (r.card?.word) {
      ttsPreload && ttsPreload(r.card.word);
    }

    content.innerHTML = `
      ${overviewHtml}
      <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;flex-wrap:wrap">
        ${autoTtsButtonHtml()}
        <span style="font-size:12px;color:var(--text-dim)">Auto pronounce current word</span>
      </div>`;

    const cardDiv = document.createElement('div');
    _cardContainer = cardDiv;
    content.appendChild(cardDiv);
    bindAutoTtsButton(content);
    renderCard(el, cardDiv, r.card, false);
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
  _currentCard = card;
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
  maybeAutoReadCurrentWord(revealed);

  const fc = content.querySelector('#fc');
  fc.addEventListener('click', async (e) => {
    // Don't flip if clicking TTS button
    if (e.target.closest('.tts-btn')) return;

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
      if (detail.example) ttsPreload && ttsPreload(detail.example);
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
const EXAM_BOOK_ORDER = ['TOEFL', 'IELTS', 'GRE', 'CET', 'GENERAL'];
const BOOK_GROUP_ORDER = ['精选词', '核心词', '全面词', '阅读高频', '听力高频', '写作词汇', '口语词汇', '学术桥接', '学术词', '学科词', '高频词', '冲刺词'];

function bookChips(book) {
  const chips = [];
  chips.push(`<span class="tag">${book.is_builtin ? '内置' : '用户'}</span>`);
  if (book.exam) chips.push(`<span class="tag">${escHtml(String(book.exam).toUpperCase())}</span>`);
  if (book.series) chips.push(`<span class="tag">${escHtml(book.series)}</span>`);
  if (book.book_group) chips.push(`<span class="tag">${escHtml(book.book_group)}</span>`);
  if (book.skill_focus) chips.push(`<span class="tag">${escHtml(book.skill_focus)}</span>`);
  if (book.stage) chips.push(`<span class="tag">${escHtml(book.stage)}</span>`);
  if (book.level) chips.push(`<span class="tag">${escHtml(book.level)}</span>`);
  return chips.join(' ');
}

function bookCard(book, opts = {}) {
  const synced = !!book.book_id;
  const due = book.due_today || 0;
  const meta = bookChips(book);
  const countLabel = synced ? (book.word_count || 0) : (book.word_count || 0);
  const actionHtml = synced
    ? `
      <button class="btn btn-outline btn-book-open" style="font-size:12px;padding:4px 10px">浏览</button>
      <button class="btn btn-primary btn-book-study" style="font-size:12px;padding:4px 10px">学习 ▶</button>`
    : `<button class="btn btn-outline btn-book-sync" style="font-size:12px;padding:4px 10px">同步内置词书</button>`;
  const manageHtml = book.is_builtin
    ? `<span style="font-size:11px;color:var(--text-dim)">只读内置词书</span>`
    : `
      <div style="display:flex;gap:6px">
        <button class="btn btn-outline btn-book-edit" style="font-size:11px;padding:3px 8px">✏️</button>
        <button class="btn btn-outline btn-book-delete" style="font-size:11px;padding:3px 8px;color:var(--red)">🗑</button>
      </div>`;

  return `
    <div class="book-card card" data-book-id="${book.book_id || ''}" data-book-key="${book.book_key || ''}" style="padding:20px;position:relative">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px;gap:12px">
        <div style="display:flex;align-items:flex-start;gap:10px;min-width:0">
          <span style="font-size:28px">${book.icon || '📖'}</span>
          <div style="min-width:0">
            <div style="font-weight:700;font-size:15px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
              <span>${escHtml(book.name || 'Untitled Book')}</span>
              ${book.is_builtin && !synced ? '<span class="tag">未同步</span>' : ''}
            </div>
            ${book.description ? `<div style="font-size:12px;color:var(--text-dim);margin-top:4px">${escHtml(book.description)}</div>` : ''}
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">${meta}</div>
          </div>
        </div>
        ${manageHtml}
      </div>
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;flex-wrap:wrap">
        <div style="display:flex;gap:12px;font-size:13px;flex-wrap:wrap">
          <span><strong>${countLabel}</strong> <span style="color:var(--text-dim)">words</span></span>
          ${synced ? `<span><strong>${due}</strong> <span style="color:var(--text-dim)">due</span></span>` : ''}
          ${book.source_label ? `<span style="color:var(--text-dim)">${escHtml(book.source_label)}</span>` : ''}
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          ${actionHtml}
        </div>
      </div>
      <div style="position:absolute;bottom:0;left:0;right:0;height:3px;border-radius:0 0 var(--radius) var(--radius);background:${book.color || 'var(--accent)'}"></div>
    </div>`;
}

async function renderBooksTab(el, content) {
  _currentBook = null;
  content.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div></div>';
  try {
    const library = await api.get('/api/vocab/library');
    let books = [];
    if (library.setup?.configured) {
      try { books = await api.get('/api/wordbooks'); } catch {}
    }

    const booksByKey = new Map(books.filter(b => b.book_key).map(b => [b.book_key, b]));
    const builtins = (library.builtin_catalog?.books || []).map(b => ({ ...b, is_builtin: true, ...(booksByKey.get(b.book_key) || {}) }));
    const users = books.filter(b => !b.is_builtin);
    const recommended = (library.recommended_path || []).map(item => ({ ...(library.builtin_catalog?.books || []).find(b => b.book_key === item.book_key), ...(booksByKey.get(item.book_key) || {}), ...item, is_builtin: true }));
    const summary = library.builtin_catalog?.stats || {};
    const db = library.database || {};
    const examOptions = ['all', ...new Set(builtins.map(book => String(book.exam || 'general').toUpperCase()))];
    const skillOptions = ['all', ...new Set(builtins.map(book => String(book.skill_focus || '').trim()).filter(Boolean))];
    const stageOptions = ['all', ...new Set(builtins.map(book => String(book.stage || '').trim()).filter(Boolean))];
    const mergedBuiltinsById = new Map(builtins.filter(book => book.book_id).map(book => [book.book_id, book]));
    const mergedBuiltinsByKey = new Map(builtins.filter(book => book.book_key).map(book => [book.book_key, book]));
    const state = { view: 'recommended', scope: 'all', exam: 'all', skill: 'all', stage: 'all' };

    const renderPage = () => {
      const matchBuiltin = (book) => {
        if (state.exam !== 'all' && String(book.exam || 'general').toUpperCase() !== state.exam) return false;
        if (state.skill !== 'all' && String(book.skill_focus || '') !== state.skill) return false;
        if (state.stage !== 'all' && String(book.stage || '') !== state.stage) return false;
        return true;
      };
      const matchUser = (book) => {
        if (state.exam !== 'all' && String(book.exam || 'general').toUpperCase() !== state.exam) return false;
        return true;
      };
      const visibleBuiltins = state.scope === 'user' ? [] : builtins.filter(matchBuiltin);
      const visibleUsers = state.scope === 'builtin' ? [] : users.filter(matchUser);
      const filteredRecommended = recommended.filter(book => {
        if (state.scope === 'user') return false;
        return matchBuiltin(book);
      });
      const examSections = {};
      visibleBuiltins.forEach(book => {
        const examKey = (book.exam || 'general').toUpperCase();
        const groupKey = book.book_group || '内置词书';
        examSections[examKey] = examSections[examKey] || {};
        examSections[examKey][groupKey] = examSections[examKey][groupKey] || [];
        examSections[examKey][groupKey].push(book);
      });
      const orderedExamKeys = Object.keys(examSections).sort((a, b) => {
        const ai = EXAM_BOOK_ORDER.indexOf(a);
        const bi = EXAM_BOOK_ORDER.indexOf(b);
        return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi) || a.localeCompare(b);
      });
      content.innerHTML = `
        <div class="card" style="margin-bottom:16px;padding:18px">
          <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start">
            <div>
              <div style="font-size:12px;font-weight:700;color:var(--text-dim);letter-spacing:.04em;margin-bottom:6px">VOCAB LIBRARY</div>
              <div style="font-size:22px;font-weight:700">推荐路径 + 全部词书</div>
              <div style="font-size:13px;color:var(--text-dim);margin-top:6px">单词书按考试与用途拆分为精选、全面和单项突破系列。内置词书增量同步，用户自建词书和词条不会被删除。</div>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button class="btn btn-outline" id="btn-sync-builtins">同步内置词书</button>
              ${library.setup?.configured ? '<button class="btn btn-primary" id="btn-create-book">+ 新建词书</button>' : '<button class="btn btn-primary" onclick="navigate(\'setup\')">去设置</button>'}
            </div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:16px">
            <div class="card" style="padding:14px;text-align:center"><div style="font-size:24px;font-weight:700">${summary.unique_words || 0}</div><div style="font-size:12px;color:var(--text-dim)">可用唯一词数</div></div>
            <div class="card" style="padding:14px;text-align:center"><div style="font-size:24px;font-weight:700">${summary.declared_entries || 0}</div><div style="font-size:12px;color:var(--text-dim)">原始词条行数</div></div>
            <div class="card" style="padding:14px;text-align:center"><div style="font-size:24px;font-weight:700">${summary.incomplete_entries || 0}</div><div style="font-size:12px;color:var(--text-dim)">缺释义未导入</div></div>
            <div class="card" style="padding:14px;text-align:center"><div style="font-size:24px;font-weight:700">${db.unique_words || 0}</div><div style="font-size:12px;color:var(--text-dim)">数据库唯一词数</div></div>
            <div class="card" style="padding:14px;text-align:center"><div style="font-size:24px;font-weight:700">${builtins.length}</div><div style="font-size:12px;color:var(--text-dim)">专业内置词书</div></div>
            <div class="card" style="padding:14px;text-align:center"><div style="font-size:24px;font-weight:700">${users.length}</div><div style="font-size:12px;color:var(--text-dim)">用户词书</div></div>
            <div class="card" style="padding:14px;text-align:center"><div style="font-size:24px;font-weight:700">${summary.quality?.definition_zh?.pct || 0}%</div><div style="font-size:12px;color:var(--text-dim)">中释义覆盖</div></div>
            <div class="card" style="padding:14px;text-align:center"><div style="font-size:24px;font-weight:700">${summary.quality?.example?.pct || 0}%</div><div style="font-size:12px;color:var(--text-dim)">例句覆盖</div></div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:14px">
            <span class="tag">${library.setup?.has_api_key ? 'AI 可用' : 'AI 未配置'}</span>
            <span class="tag">${library.setup?.offline_ready ? '离线词库可用' : '未发现内置词库'}</span>
            <span class="tag">数据目录 ${escHtml(library.setup?.data_dir || '')}</span>
          </div>
        </div>

        ${!library.setup?.configured ? `
          <div class="card" style="margin-bottom:16px;padding:22px">
            <div style="font-size:18px;font-weight:700;margin-bottom:6px">先完成用户设置，才能创建个人词书和 SRS 记录</div>
            <div style="font-size:13px;color:var(--text-dim);margin-bottom:14px">当前仍可看到内置词书规划和真实覆盖规模，但不会生成个人词书实例。</div>
            <button class="btn btn-primary" onclick="navigate('setup')">前往 Setup</button>
          </div>` : ''}

        <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px">
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn ${state.view === 'recommended' ? 'btn-primary' : 'btn-outline'}" id="btn-view-recommended">推荐学习路径</button>
            <button class="btn ${state.view === 'all' ? 'btn-primary' : 'btn-outline'}" id="btn-view-all">全部词书</button>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            <button class="btn ${state.scope === 'all' ? 'btn-primary' : 'btn-outline'}" id="btn-scope-all">全部</button>
            <button class="btn ${state.scope === 'builtin' ? 'btn-primary' : 'btn-outline'}" id="btn-scope-builtins">内置</button>
            <button class="btn ${state.scope === 'user' ? 'btn-primary' : 'btn-outline'}" id="btn-scope-users">用户</button>
            <select id="filter-exam" class="input" style="min-width:120px">
              ${examOptions.map(exam => `<option value="${escHtml(exam)}" ${state.exam === exam ? 'selected' : ''}>${exam === 'all' ? '全部考试' : exam}</option>`).join('')}
            </select>
            <select id="filter-skill" class="input" style="min-width:120px">
              ${skillOptions.map(skill => `<option value="${escHtml(skill)}" ${state.skill === skill ? 'selected' : ''}>${skill === 'all' ? '全部技能' : escHtml(skill)}</option>`).join('')}
            </select>
            <select id="filter-stage" class="input" style="min-width:120px">
              ${stageOptions.map(stage => `<option value="${escHtml(stage)}" ${state.stage === stage ? 'selected' : ''}>${stage === 'all' ? '全部阶段' : escHtml(stage)}</option>`).join('')}
            </select>
          </div>
        </div>

        ${state.view === 'recommended' ? `
          <div class="card" style="margin-bottom:16px;padding:16px">
            <div style="font-size:15px;font-weight:700;margin-bottom:6px">推荐学习路径</div>
            <div style="font-size:12px;color:var(--text-dim)">先学精选或核心，再学全面词书，最后按阅读、听力、写作单项突破。推荐顺序基于当前项目内真实可导入词量。</div>
          </div>
          <div class="book-grid">${filteredRecommended.map(book => bookCard(book)).join('') || '<div class="card" style="padding:32px;text-align:center;color:var(--text-dim)">当前筛选条件下没有可展示的推荐词书。</div>'}</div>
        ` : `
          ${orderedExamKeys.map(examKey => {
            const groups = examSections[examKey] || {};
            const orderedGroups = Object.keys(groups).sort((a, b) => {
              const ai = BOOK_GROUP_ORDER.indexOf(a);
              const bi = BOOK_GROUP_ORDER.indexOf(b);
              return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi) || a.localeCompare(b);
            });
            const examCount = orderedGroups.reduce((sum, group) => sum + (groups[group] || []).length, 0);
            return `
            <div class="card" style="margin-bottom:16px;padding:16px">
              <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px">
                <div style="font-size:16px;font-weight:700">${escHtml(examKey)}</div>
                <span class="tag">${examCount} 本词书</span>
              </div>
              ${orderedGroups.map(group => `
                <div style="margin-bottom:16px">
                  <div style="font-size:13px;font-weight:700;margin-bottom:10px;color:var(--text-dim)">${escHtml(group)}</div>
                  <div class="book-grid">${groups[group].map(book => bookCard(book)).join('')}</div>
                </div>`).join('')}
            </div>`;
          }).join('')}
          ${visibleUsers.length ? `
            <div style="margin-top:12px">
              <div style="font-size:14px;font-weight:700;margin-bottom:10px">用户自建</div>
              <div class="book-grid">${visibleUsers.map(book => bookCard(book)).join('')}</div>
            </div>` : state.scope !== 'builtin' ? `
            <div class="card" style="padding:28px;text-align:center">
              <div style="font-size:36px;margin-bottom:10px">📭</div>
              <div style="font-size:16px;font-weight:700;margin-bottom:6px">还没有用户词书</div>
              <div style="font-size:12px;color:var(--text-dim);margin-bottom:14px">你可以手动建词书，或在 Add Word 页面导入 JSON / CSV / Markdown。</div>
              ${library.setup?.configured ? '<button class="btn btn-primary" id="btn-create-first">+ 新建词书</button>' : ''}
            </div>` : ''}
        `}
      `;

      content.querySelector('#btn-sync-builtins')?.addEventListener('click', async () => {
        const btn = content.querySelector('#btn-sync-builtins');
        btn.disabled = true;
        btn.textContent = '同步中...';
        try { await api.post('/api/vocab/ingest_builtin', {}); } catch {}
        await renderBooksTab(el, content);
      });
      content.querySelector('#btn-create-book')?.addEventListener('click', () => showBookModal(el, content, null));
      content.querySelector('#btn-create-first')?.addEventListener('click', () => showBookModal(el, content, null));
      content.querySelector('#btn-view-recommended')?.addEventListener('click', () => { state.view = 'recommended'; renderPage(); });
      content.querySelector('#btn-view-all')?.addEventListener('click', () => { state.view = 'all'; renderPage(); });
      content.querySelector('#btn-scope-all')?.addEventListener('click', () => { state.scope = 'all'; renderPage(); });
      content.querySelector('#btn-scope-builtins')?.addEventListener('click', () => { state.scope = 'builtin'; renderPage(); });
      content.querySelector('#btn-scope-users')?.addEventListener('click', () => { state.scope = 'user'; renderPage(); });
      content.querySelector('#filter-exam')?.addEventListener('change', (e) => { state.exam = e.target.value; renderPage(); });
      content.querySelector('#filter-skill')?.addEventListener('change', (e) => { state.skill = e.target.value; renderPage(); });
      content.querySelector('#filter-stage')?.addEventListener('change', (e) => { state.stage = e.target.value; renderPage(); });
      content.querySelectorAll('.book-card').forEach(card => {
        const bookId = card.dataset.bookId;
        const bookKey = card.dataset.bookKey;
        const actual = mergedBuiltinsById.get(bookId) || mergedBuiltinsByKey.get(bookKey) || books.find(b => b.book_id === bookId) || booksByKey.get(bookKey);
        card.querySelector('.btn-book-open')?.addEventListener('click', () => actual && showBookDetail(el, content, actual));
        card.querySelector('.btn-book-study')?.addEventListener('click', () => actual && startBookSession(el, content, actual));
        card.querySelector('.btn-book-edit')?.addEventListener('click', e => { e.stopPropagation(); actual && showBookModal(el, content, actual); });
        card.querySelector('.btn-book-delete')?.addEventListener('click', e => { e.stopPropagation(); actual && confirmDeleteBook(el, content, actual); });
        card.querySelector('.btn-book-sync')?.addEventListener('click', async () => {
          await api.post('/api/vocab/ingest_builtin', {});
          await renderBooksTab(el, content);
        });
      });
    };

    renderPage();
  } catch (e) {
    content.innerHTML = `<div class="alert alert-error">${e.message} <button class="btn btn-outline" id="btn-retry-wb" style="margin-left:8px">Retry ↺</button></div>`;
    content.querySelector('#btn-retry-wb')?.addEventListener('click', () => renderBooksTab(el, content));
  }
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
  const readOnly = !!book.is_builtin;
  content.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px">
      <button class="btn btn-outline" id="btn-back" style="font-size:12px;padding:4px 10px">← Books</button>
      <span style="font-size:24px">${book.icon}</span>
      <h2 style="margin:0">${escHtml(book.name)}</h2>
    </div>
    ${book.description ? `<p style="color:var(--text-dim);margin-bottom:12px">${escHtml(book.description)}</p>` : '<div style="margin-bottom:12px"></div>'}
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">${bookChips(book)}${book.source_label ? `<span class="tag">${escHtml(book.source_label)}</span>` : ''}</div>
    ${readOnly ? `<div class="card" style="margin-bottom:14px;padding:14px;font-size:12px;color:var(--text-dim)">这是内置只读词书。你可以浏览和学习，但不能直接在这里增删词条。</div>` : ''}
    <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">
      <button class="btn btn-primary" id="btn-study-book">▶ Study Now</button>
      ${readOnly ? '' : '<button class="btn btn-outline" id="btn-add-word-book">+ Add Word</button>'}
      ${readOnly ? '' : '<button class="btn btn-outline" id="btn-edit-book" style="margin-left:auto">✏️ Edit</button>'}
    </div>
    <div id="book-stats-row" style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap"></div>
    <input id="word-filter" type="text" placeholder="Filter words…" style="width:100%;max-width:320px;margin-bottom:12px">
    <div id="book-words-container"><div style="text-align:center;padding:40px"><div class="spinner"></div></div></div>
    <div id="add-word-panel-book" style="display:none"></div>
  `;
  content.querySelector('#btn-back').addEventListener('click', () => renderBooksTab(el, content));
  content.querySelector('#btn-study-book').addEventListener('click', () => startBookSession(el, content, book));
  content.querySelector('#btn-add-word-book')?.addEventListener('click', () => showAddWordPanel(content, book, el));
  content.querySelector('#btn-edit-book')?.addEventListener('click', () => showBookModal(el, content, book));
  let filterTimer = null;
  content.querySelector('#word-filter').addEventListener('input', e => {
    clearTimeout(filterTimer);
    filterTimer = setTimeout(() => renderWordList(content, book, e.target.value.trim()), 200);
  });
  try {
    const data = await api.get(`/api/wordbooks/${book.book_id}/words`);
    _currentBook = data.book;
    renderBookStatsRow(content, data.book);
    renderWordList(content, data.book, '', data.words);
  } catch (e) {
    content.querySelector('#book-words-container').innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

function renderBookStatsRow(content, book) {
  const row = content.querySelector('#book-stats-row');
  if (!row) return;
  row.innerHTML = `
    <div class="card" style="flex:1;min-width:90px;text-align:center;padding:14px">
      <div style="font-size:22px;font-weight:700">${book.word_count || 0}</div>
      <div style="font-size:11px;color:var(--text-dim)">Total words</div>
    </div>
    <div class="card" style="flex:1;min-width:90px;text-align:center;padding:14px">
      <div style="font-size:22px;font-weight:700">${book.due_today || 0}</div>
      <div style="font-size:11px;color:var(--text-dim)">Due today</div>
    </div>
    <div class="card" style="flex:1;min-width:90px;text-align:center;padding:14px">
      <div style="font-size:22px;font-weight:700">${book.is_builtin ? 'Built-in' : 'Custom'}</div>
      <div style="font-size:11px;color:var(--text-dim)">Book type</div>
    </div>`;
}

function proficiencyDot(interval) {
  // interval (days): 0=new, 1-3=learning, 4-14=young, 15+=mature
  if (!interval || interval === 0) return { color: '#888', label: 'New' };
  if (interval < 4)  return { color: '#f5c842', label: 'Learning' };
  if (interval < 15) return { color: '#4f8ef7', label: 'Young' };
  return { color: '#3ecf8e', label: 'Mature' };
}

function openInlineWordEditor(host, word, book, content) {
  const prefix = `edit-${word.word_id}`;
  const originalDraft = createWordDraft(word);
  host.style.display = '';
  host.innerHTML = wordEditorMarkup(prefix, {
    title: 'Edit Card',
    subtitle: 'Saving here updates the same vocabulary card everywhere it appears in your library.',
    primaryLabel: 'Save Changes',
    primaryClass: 'btn-primary',
    clearLabel: 'Reset',
    closeLabel: 'Cancel',
    showClose: true,
  });

  bindWordEditor(host, prefix, {
    searchEnabled: false,
    onClose: () => {
      host.innerHTML = '';
      host.style.display = 'none';
    },
    onClear: () => {
      applyWordEditorDraft(host, prefix, originalDraft);
      setWordEditorStatus(host, prefix, 'Restored the last saved card.', 'muted');
    },
    onSubmit: async () => {
      const nodes = getWordEditorNodes(host, prefix);
      const draft = collectWordEditorDraft(host, prefix);
      if (!draft.word) {
        nodes.wordInput?.focus();
        return;
      }
      nodes.submit.disabled = true;
      try {
        const updated = await api.put(`/api/wordbooks/${book.book_id}/words/${word.word_id}`, buildWordSavePayload(draft, false));
        const next = createWordDraft(updated);
        const targetIndex = _allWords.findIndex(item => item.word_id === word.word_id);
        if (targetIndex >= 0) {
          _allWords[targetIndex] = { ..._allWords[targetIndex], ...next };
        }
        setWordEditorStatus(host, prefix, '✓ Card saved. List is refreshing…', 'success');
        renderWordList(content, book, content.querySelector('#word-filter')?.value.trim() || '', _allWords);
      } catch (e) {
        nodes.message.innerHTML = `<div class="alert alert-error" style="margin-bottom:8px">${e.message}</div>`;
      }
      nodes.submit.disabled = false;
    },
  });

  applyWordEditorDraft(host, prefix, originalDraft);
  setWordEditorStatus(host, prefix, 'Edit the text, then save. You can also run AI Fill to refresh the card.', 'info');
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
      : `<div class="card" style="text-align:center;padding:32px"><div style="font-size:36px;margin-bottom:10px">📭</div><p style="color:var(--text-dim)">${book.is_builtin ? '当前内置词书还没有同步到个人数据库，先返回词书页执行同步。' : 'No words yet. Click "+ Add Word" to get started.'}</p></div>`;
    return;
  }

  let _selected = new Set();
  let _bulkMode = !book.is_builtin && false;

  const render = () => {
    container.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <div style="font-size:12px;color:var(--text-dim)">${list.length} word${list.length !== 1 ? 's' : ''}</div>
        ${book.is_builtin ? '<span style="font-size:12px;color:var(--text-dim)">内置词书为只读</span>' : `<button id="btn-bulk-toggle" class="btn btn-outline" style="font-size:12px;padding:4px 10px">${_bulkMode ? '✕ Cancel' : '☑ Manage'}</button>`}
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
                ${book.is_builtin ? '' : `<button class="btn btn-outline btn-word-edit-quick" data-word-id="${w.word_id}" style="font-size:11px;padding:4px 10px">✏️ Edit</button>`}
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
              <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
                <button class="btn btn-outline btn-word-edit" data-word-id="${w.word_id}" style="font-size:12px;padding:5px 12px">✏️ Edit Card</button>
                ${book.is_builtin ? '' : `<button class="btn btn-outline btn-word-remove" data-word-id="${w.word_id}" style="font-size:12px;padding:5px 12px;color:var(--red)">🗑 Remove from Book</button>`}
              </div>
              <div class="inline-word-editor-host" data-word-id="${w.word_id}" style="display:none;margin-top:12px"></div>
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
        if (e.target.closest('.bulk-cb') || e.target.closest('.tts-btn') || e.target.closest('.btn-word-edit-quick')) return;
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

    container.querySelectorAll('.btn-word-edit').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const wid = btn.dataset.wordId;
        const word = _allWords.find(item => item.word_id === wid);
        const detail = btn.closest('.word-row-detail');
        const host = detail?.querySelector(`.inline-word-editor-host[data-word-id="${wid}"]`);
        if (!word || !host) return;
        const isOpen = host.style.display !== 'none' && host.innerHTML.trim();
        container.querySelectorAll('.inline-word-editor-host').forEach(otherHost => {
          if (otherHost !== host) {
            otherHost.innerHTML = '';
            otherHost.style.display = 'none';
          }
        });
        if (isOpen) {
          host.innerHTML = '';
          host.style.display = 'none';
          return;
        }
        openInlineWordEditor(host, word, book, content);
      });
    });

    container.querySelectorAll('.btn-word-edit-quick').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const wid = btn.dataset.wordId;
        const word = _allWords.find(item => item.word_id === wid);
        const row = btn.closest('.word-row');
        const detail = row?.querySelector('.word-row-detail');
        const arrow = row?.querySelector('.expand-arrow');
        const host = detail?.querySelector(`.inline-word-editor-host[data-word-id="${wid}"]`);
        if (!word || !detail || !host) return;
        container.querySelectorAll('.inline-word-editor-host').forEach(otherHost => {
          if (otherHost !== host) {
            otherHost.innerHTML = '';
            otherHost.style.display = 'none';
          }
        });
        detail.style.display = '';
        if (arrow) arrow.textContent = '▼';
        openInlineWordEditor(host, word, book, content);
        host.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    });

    container.querySelectorAll('.btn-word-remove').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const wid = btn.dataset.wordId;
        const word = _allWords.find(item => item.word_id === wid);
        if (!wid || !word) return;
        if (!window.confirm(`Remove "${word.word}" from "${book.name}"?`)) return;
        btn.disabled = true;
        try {
          await fetch(`/api/wordbooks/${book.book_id}/words/${wid}`, { method: 'DELETE' });
          const data = await api.get(`/api/wordbooks/${book.book_id}/words`);
          _currentBook = data.book;
          renderBookStatsRow(content, data.book);
          _allWords = data.words;
          renderWordList(content, data.book, content.querySelector('#word-filter')?.value.trim() || '', data.words);
        } finally {
          btn.disabled = false;
        }
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
      const data = await api.get(`/api/wordbooks/${book.book_id}/words`);
      _currentBook = data.book;
      renderBookStatsRow(content, data.book);
      _allWords = data.words;
      _bulkMode = false; _selected.clear();
      renderWordList(content, data.book, content.querySelector('#word-filter')?.value.trim() || '', data.words);
    });
  };

  render();
}

// ── Add Word to Book panel ────────────────────────────────────────

function showAddWordPanel(content, book, el) {
  const panel = content.querySelector('#add-word-panel-book');
  const prefix = 'book-add';
  panel.style.display = '';
  panel.innerHTML = `
    <div class="card" style="margin-top:16px;padding:24px">
      ${wordEditorMarkup(prefix, {
        title: `Add Word to "${escHtml(book.name)}"`,
        subtitle: 'Search existing vocabulary or create a fully editable card. Preview updates as you type or run AI Fill.',
        primaryLabel: '+ Add to Book',
        primaryClass: 'btn-success',
        clearLabel: 'Clear',
        closeLabel: 'Close',
        showClose: true,
      })}
    </div>`;

  bindWordEditor(panel, prefix, {
    searchEnabled: true,
    onClose: () => { panel.style.display = 'none'; },
    onClear: () => {
      resetWordEditor(panel, prefix);
      setWordEditorStatus(panel, prefix, 'Draft cleared.', 'muted');
    },
    onSubmit: async () => {
      const nodes = getWordEditorNodes(panel, prefix);
      const draft = collectWordEditorDraft(panel, prefix);
      if (!draft.word) {
        nodes.wordInput?.focus();
        return;
      }
      if (!draft.definition_en && !draft.word_id) {
        nodes.message.innerHTML = '<div class="alert alert-error" style="margin-bottom:8px">English definition is required for a brand-new word.</div>';
        return;
      }
      nodes.submit.disabled = true;
      try {
        const result = await api.post(`/api/wordbooks/${book.book_id}/words`, buildWordSavePayload(draft, true));
        const bookName = escHtml(book.name);
        if (result.already_exists) {
          if (result.updated_existing) {
            nodes.message.innerHTML = `<div class="alert alert-success" style="margin-bottom:8px">✓ Updated "${escHtml(draft.word)}" and kept it in ${bookName}.</div>`;
          } else {
            nodes.message.innerHTML = `<div class="alert alert-warn" style="margin-bottom:8px">"${escHtml(draft.word)}" is already in ${bookName}.</div>`;
          }
        } else {
          const reused = result.updated_existing ? ' and refreshed its card content' : '';
          nodes.message.innerHTML = `<div class="alert alert-success" style="margin-bottom:8px">✓ "${escHtml(draft.word)}" added to ${bookName}${reused}.</div>`;
          resetWordEditor(panel, prefix);
          setWordEditorStatus(panel, prefix, 'Ready for the next word.', 'muted');
        }
        const data = await api.get(`/api/wordbooks/${book.book_id}/words`);
        _currentBook = data.book;
        renderBookStatsRow(content, data.book);
        renderWordList(content, data.book, content.querySelector('#word-filter')?.value.trim() || '', data.words);
      } catch (e) {
        nodes.message.innerHTML = `<div class="alert alert-error" style="margin-bottom:8px">${e.message}</div>`;
      }
      nodes.submit.disabled = false;
    },
  });

  resetWordEditor(panel, prefix);
  getWordEditorNodes(panel, prefix).wordInput?.focus();
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
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:16px;flex-wrap:wrap">
        <div style="display:flex;align-items:center;gap:8px">
          <button class="btn btn-outline" id="btn-back-session" style="font-size:12px;padding:4px 10px">← ${escHtml(book.name)}</button>
          <span style="font-size:13px;color:var(--text-dim)">${r.total} cards</span>
        </div>
        ${autoTtsButtonHtml()}
      </div>
      <div id="book-session-body"></div>`;
    content.querySelector('#btn-back-session').addEventListener('click', () => showBookDetail(el, content, book));
    bindAutoTtsButton(content);
    const sessionBody = content.querySelector('#book-session-body');
    renderBookCard(el, content, sessionBody, r.card, false, book);
    if (r.card) { ttsPreload && ttsPreload(r.card.word); }
  } catch (e) {
    content.innerHTML = `<div class="alert alert-error">${e.message} <button class="btn btn-outline" style="margin-left:8px" id="btn-retry-bs">Retry ↺</button></div>`;
    content.querySelector('#btn-retry-bs')?.addEventListener('click', () => startBookSession(el, content, book));
  }
}

function renderBookCard(el, content, sessionBody, card, revealed, book) {
  _currentCard = card;
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
  maybeAutoReadCurrentWord(revealed);

  const fc = sessionBody.querySelector('#bfc');
  fc.addEventListener('click', async (e) => {
    // Don't flip if clicking TTS button
    if (e.target.closest('.tts-btn')) return;

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
  const addPrefix = 'quick-add';
  let books = [];
  try { books = await api.get('/api/wordbooks'); } catch {}
  books = books.filter(b => !b.is_builtin);
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
      <div class="card" style="margin-bottom:18px;padding:16px">
        <div style="font-size:15px;font-weight:700;margin-bottom:6px">离线也能用的词汇入口</div>
        <div style="font-size:12px;color:var(--text-dim)">没有 API key 时仍可手动录词、导入词书、浏览内置词书和做 SRS 复习。AI Fill 只是可选加速，不是必需条件。</div>
      </div>
      <div style="margin-bottom:24px">
        <div style="font-size:12px;font-weight:600;color:var(--text-dim);text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px">Add to Word Book</div>
        <div id="book-selector" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:10px">
          ${buildBookSelector()}
        </div>
        <div id="book-sel-hint" style="font-size:12px;color:var(--text-dim);margin-top:8px"></div>
      </div>

      <div class="card" style="padding:18px;margin-bottom:20px">
        <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:flex-start;margin-bottom:10px">
          <div>
            <div style="font-size:15px;font-weight:700;margin-bottom:4px">导入词书</div>
            <div style="font-size:12px;color:var(--text-dim)">支持 <code>JSON / CSV / Markdown</code>。导入前会校验、统计重复词，并保护已有用户词条。</div>
          </div>
          <div style="font-size:12px;color:var(--text-dim)">规则：同词合并，用户词优先保留</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:10px">
          <div class="form-group"><label>Format</label>
            <select id="import-format">
              <option value="auto">Auto detect</option>
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
              <option value="markdown">Markdown</option>
            </select>
          </div>
          <div class="form-group"><label>Target Book</label>
            <select id="import-target">
              <option value="__new__">Create new imported book</option>
              ${books.map(b => `<option value="${b.book_id}">${escHtml(b.name)}</option>`).join('')}
            </select>
          </div>
        </div>
        <div class="form-group" id="import-name-wrap"><label>New Book Name</label><input id="import-book-name" type="text" placeholder="e.g. My IELTS Writing Vocab"></div>
        <div class="form-group"><label>Payload</label>
          <textarea id="import-payload" rows="10" placeholder='{"book":{"name":"My Book","exam":"ielts","topic":"academic"},"words":[{"word":"abandon","definition_en":"to leave behind"}]}' style="width:100%"></textarea>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
          <button class="btn btn-outline" id="btn-import-validate">Validate</button>
          <button class="btn btn-primary" id="btn-import-run">Import</button>
        </div>
        <div id="import-result" style="margin-top:12px"></div>
      </div>

      <div class="card" style="padding:20px;margin-bottom:0">
        ${wordEditorMarkup(addPrefix, {
          title: 'Add or Update a Word Card',
          subtitle: 'Search your library, refine the content, and save it directly to the SRS deck or a selected custom book.',
          primaryLabel: '+ Add Word',
          primaryClass: 'btn-success',
          clearLabel: 'Clear',
          showClose: false,
        })}
      </div>
    </div>
  `;

  const hintEl = content.querySelector('#book-sel-hint');
  const syncAddActionLabel = () => {
    const nodes = getWordEditorNodes(content, addPrefix);
    if (nodes.submit) {
      nodes.submit.textContent = selectedBookId ? '+ Save to Book' : '+ Add to Deck';
    }
  };
  const updateHint = () => {
    if (!selectedBookId) {
      hintEl.textContent = 'Word will be added to your SRS deck only.';
      syncAddActionLabel();
      return;
    }
    const b = books.find(b => b.book_id === selectedBookId);
    hintEl.textContent = b ? `Adding to: ${b.icon} ${b.name}` : '';
    syncAddActionLabel();
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

  const importTarget = content.querySelector('#import-target');
  const importNameWrap = content.querySelector('#import-name-wrap');
  const importResult = content.querySelector('#import-result');

  const updateImportTarget = () => {
    importNameWrap.style.display = importTarget.value === '__new__' ? '' : 'none';
  };
  importTarget.addEventListener('change', updateImportTarget);
  updateImportTarget();

  content.querySelector('#btn-import-validate').addEventListener('click', async () => {
    const payload = content.querySelector('#import-payload').value.trim();
    if (!payload) { importResult.innerHTML = '<div class="alert alert-error">Import payload is required</div>'; return; }
    importResult.innerHTML = '<div style="font-size:12px;color:var(--text-dim)">Validating…</div>';
    try {
      const result = await api.post('/api/wordbooks/import/validate', {
        payload,
        format: content.querySelector('#import-format').value,
      });
      importResult.innerHTML = `
        <div class="card" style="padding:14px">
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
            <span class="tag">Format ${escHtml(result.format)}</span>
            <span class="tag">Valid ${result.stats.valid_words}</span>
            <span class="tag">Unique ${result.stats.unique_words}</span>
            <span class="tag">Existing ${result.stats.existing_words}</span>
          </div>
          ${result.errors?.length ? `<div class="alert alert-error" style="margin-bottom:8px">${result.errors.join('<br>')}</div>` : ''}
          ${result.warnings?.length ? `<div class="alert alert-warn" style="margin-bottom:8px">${result.warnings.join('<br>')}</div>` : ''}
          <div style="font-size:12px;color:var(--text-dim)">Merge rules: ${result.merge_rules.join(' / ')}</div>
        </div>`;
    } catch (e) {
      importResult.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
  });

  content.querySelector('#btn-import-run').addEventListener('click', async () => {
    const payload = content.querySelector('#import-payload').value.trim();
    if (!payload) { importResult.innerHTML = '<div class="alert alert-error">Import payload is required</div>'; return; }
    const btn = content.querySelector('#btn-import-run');
    btn.disabled = true;
    importResult.innerHTML = '<div style="font-size:12px;color:var(--text-dim)">Importing…</div>';
    try {
      const req = {
        payload,
        format: content.querySelector('#import-format').value,
        book_id: importTarget.value === '__new__' ? null : importTarget.value,
        book_name: content.querySelector('#import-book-name').value.trim(),
      };
      const result = await api.post('/api/wordbooks/import', req);
      localStorage.setItem('defaultAddBookId', result.book.book_id);
      importResult.innerHTML = `<div class="alert alert-success">✓ Imported ${result.stats.valid_words} words into ${escHtml(result.book.name)}</div>`;
      setTimeout(() => renderAddTab(el, content), 600);
    } catch (e) {
      importResult.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
    btn.disabled = false;
  });

  bindWordEditor(content, addPrefix, {
    searchEnabled: true,
    onClear: () => {
      resetWordEditor(content, addPrefix);
      setWordEditorStatus(content, addPrefix, 'Draft cleared.', 'muted');
    },
    onSubmit: async () => {
      const nodes = getWordEditorNodes(content, addPrefix);
      const draft = collectWordEditorDraft(content, addPrefix);
      if (!draft.word) {
        nodes.wordInput?.focus();
        return;
      }
      if (!draft.definition_en && !draft.word_id) {
        nodes.message.innerHTML = '<div class="alert alert-error" style="margin-bottom:8px">English definition is required for a brand-new word.</div>';
        return;
      }
      nodes.submit.disabled = true;
      try {
        if (selectedBookId) {
          const book = books.find(item => item.book_id === selectedBookId);
          const result = await api.post(`/api/wordbooks/${selectedBookId}/words`, buildWordSavePayload(draft, true));
          if (result.already_exists) {
            if (result.updated_existing) {
              nodes.message.innerHTML = `<div class="alert alert-success" style="margin-bottom:8px">✓ Updated "${escHtml(draft.word)}" inside ${escHtml(book?.name || 'the selected book')}.</div>`;
            } else {
              nodes.message.innerHTML = `<div class="alert alert-warn" style="margin-bottom:8px">"${escHtml(draft.word)}" is already in ${escHtml(book?.name || 'the selected book')}.</div>`;
            }
          } else {
            nodes.message.innerHTML = `<div class="alert alert-success" style="margin-bottom:8px">✓ "${escHtml(draft.word)}" saved to ${escHtml(book?.name || 'the selected book')}.</div>`;
            resetWordEditor(content, addPrefix);
            setWordEditorStatus(content, addPrefix, 'Saved to the selected book and your SRS deck.', 'success');
          }
        } else {
          const result = await api.post('/api/vocab/add', buildWordSavePayload(draft, false));
          if (result.already_exists) {
            if (result.updated_existing) {
              nodes.message.innerHTML = `<div class="alert alert-success" style="margin-bottom:8px">✓ Updated "${escHtml(draft.word)}" in your deck.</div>`;
            } else {
              nodes.message.innerHTML = `<div class="alert alert-warn" style="margin-bottom:8px">"${escHtml(draft.word)}" is already in your deck.</div>`;
            }
          } else {
            const reused = result.reused_existing ? ' and re-used the existing card' : '';
            nodes.message.innerHTML = `<div class="alert alert-success" style="margin-bottom:8px">✓ "${escHtml(draft.word)}" added to your deck${reused}.</div>`;
            resetWordEditor(content, addPrefix);
            setWordEditorStatus(content, addPrefix, 'Saved to your SRS deck.', 'success');
          }
        }
      } catch (e) {
        nodes.message.innerHTML = `<div class="alert alert-error" style="margin-bottom:8px">${e.message}</div>`;
      }
      nodes.submit.disabled = false;
    },
  });

  resetWordEditor(content, addPrefix);
  syncAddActionLabel();
  getWordEditorNodes(content, addPrefix).wordInput?.focus();
}
