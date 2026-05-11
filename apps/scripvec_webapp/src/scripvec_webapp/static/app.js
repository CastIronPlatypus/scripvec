// scripvec webapp client — wires the four scenes to the FastAPI backend.

/* -------------------- API helpers -------------------- */

async function apiGet(path) {
  const resp = await fetch(path);
  if (!resp.ok) throw await toApiError(resp);
  return resp.json();
}

async function apiPost(path, body) {
  const resp = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw await toApiError(resp);
  return resp.json();
}

async function toApiError(resp) {
  let detail = `${resp.status} ${resp.statusText}`;
  try {
    const data = await resp.json();
    if (data && data.detail) {
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    }
  } catch (_) { /* non-JSON body */ }
  const err = new Error(detail);
  err.status = resp.status;
  return err;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function fmtScore(s) {
  if (s == null || Number.isNaN(s)) return '';
  return Number(s).toFixed(2);
}

function volumeOf(book) {
  if (book === 'D&C') return 'D&C';
  return 'Book of Mormon';
}

function parseRef(ref) {
  // Match: "<book> <chapter>:<verse>"
  const m = /^(.+?)\s+(\d+):(\d+)$/.exec(ref);
  if (!m) return null;
  return { book: m[1], chapter: parseInt(m[2], 10), verse: parseInt(m[3], 10) };
}

/* -------------------- Tab switching -------------------- */

const tabs = document.querySelectorAll('.tab');
const scenes = document.querySelectorAll('.scene');

function showScene(id) {
  tabs.forEach(t => t.classList.toggle('active', t.dataset.scene === id));
  scenes.forEach(s => s.classList.toggle('active', s.id === id));
  try { localStorage.setItem('scripvec_scene', id); } catch (_) {}
}

tabs.forEach(t => t.addEventListener('click', () => showScene(t.dataset.scene)));

try {
  const saved = localStorage.getItem('scripvec_scene');
  if (saved && document.getElementById(saved)) showScene(saved);
} catch (_) {}

/* -------------------- Version line + indexes -------------------- */

const versionLine = document.getElementById('versionLine');

(async function loadVersion() {
  try {
    const v = await apiGet('/api/version');
    const hash = v.latest_index_hash;
    const shortHash = hash ? hash.slice(0, 8) : 'none';
    const indexBadge = hash
      ? `<span class="ok">index ${shortHash}</span>`
      : `<span class="warn">no index built</span>`;
    versionLine.innerHTML = `v${escapeHtml(v.cli_version || '?')} · ${escapeHtml(v.embedding_model || '?')} · ${indexBadge}`;
  } catch (err) {
    versionLine.innerHTML = `<span class="warn">CLI unreachable</span>`;
    console.error('version load failed:', err);
  }
})();

/* -------------------- Shared search state -------------------- */

const state = {
  s1Mode: 'hybrid',
  s1K: 10,
  s2Mode: 'hybrid',
  s2K: 15,
  s2Floor: 0.0,
  s2Volumes: new Set(['Book of Mormon', 'D&C']),
  s2Books: new Set(),         // empty = all
  s4Query: '',
  s4Results: [],
};

/* -------------------- Verse card rendering -------------------- */

function renderVerse(hit) {
  const ref = escapeHtml(hit.ref || '');
  const text = escapeHtml(hit.text || '');
  const score = (hit.score != null) ? Number(hit.score) : null;
  const scorePct = score != null ? Math.max(0, Math.min(100, Math.round(score * 100))) : 0;
  const scoreBlock = score != null
    ? `<div class="score"><b>${fmtScore(score)}</b>${escapeHtml(hit.mode_label || 'score')}<div class="bar"><i style="width:${scorePct}%"></i></div></div>`
    : `<div class="score"></div>`;
  const volLabel = escapeHtml(volumeOf((parseRef(hit.ref) || {}).book || ''));
  const forcedTag = hit.forced ? `<span class="forced-tag">forced</span>` : '';
  const forcedClass = hit.forced ? ' forced' : '';
  return `
    <div class="verse${forcedClass}" data-ref="${ref}" data-verse-id="${escapeHtml(hit.verse_id || '')}">
      <div class="ref">${ref}<small>${volLabel}</small>${forcedTag}</div>
      <div class="verse-body">${text}</div>
      ${scoreBlock}
    </div>
  `;
}

function filterHits(hits, opts) {
  let out = hits;
  if (opts && opts.volumes && opts.volumes.size && opts.volumes.size < 2) {
    out = out.filter(h => {
      const parsed = parseRef(h.ref);
      if (!parsed) return true;
      return opts.volumes.has(volumeOf(parsed.book));
    });
  }
  if (opts && opts.books && opts.books.size > 0) {
    out = out.filter(h => {
      const parsed = parseRef(h.ref);
      if (!parsed) return true;
      return opts.books.has(parsed.book) || h.forced;
    });
  }
  if (opts && typeof opts.floor === 'number' && opts.floor > 0) {
    out = out.filter(h => h.forced || (h.score != null && h.score >= opts.floor));
  }
  return out;
}

/* -------------------- Scene 1: Search-first -------------------- */

const s1Form = document.getElementById('s1Form');
const s1Input = document.getElementById('s1Input');
const s1Results = document.getElementById('s1Results');
const s1Heading = document.getElementById('s1Heading');
const s1KLabel = document.getElementById('s1KLabel');

document.querySelectorAll('#s1 .mode-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('#s1 .mode-chip').forEach(c => c.classList.remove('on'));
    chip.classList.add('on');
    state.s1Mode = chip.dataset.mode;
  });
});

document.querySelectorAll('#s1 .suggest').forEach(s => {
  s.addEventListener('click', () => {
    s1Input.value = s.textContent.trim();
    s1Form.dispatchEvent(new Event('submit', { cancelable: true }));
  });
});

s1Form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = s1Input.value.trim();
  if (!text) return;
  s1Heading.innerHTML = `searching… <span class="spinner"></span>`;
  s1Results.innerHTML = '';
  try {
    const res = await apiPost('/api/query', {
      text, k: state.s1K, mode: state.s1Mode, show_scores: true,
    });
    renderS1Results(res);
  } catch (err) {
    s1Heading.textContent = 'search failed';
    s1Results.innerHTML = `<div class="err">${escapeHtml(err.message)}</div>`;
  }
});

function renderS1Results(res) {
  const hits = res.results || [];
  s1Heading.textContent = `${hits.length} verses · semantically nearest`;
  if (!hits.length) {
    s1Results.innerHTML = `<div class="empty">No results.</div>`;
    return;
  }
  s1Results.innerHTML = hits.map(renderVerse).join('');
  wireVerseClicks(s1Results, res.query);
}

/* -------------------- Scene 2: Split pane -------------------- */

const s2Form = document.getElementById('s2Form');
const s2Input = document.getElementById('s2Input');
const s2Results = document.getElementById('s2Results');
const s2Meta = document.getElementById('s2Meta');
const s2K = document.getElementById('s2K');
const s2KLabel = document.getElementById('s2KLabel');
const s2Floor = document.getElementById('s2Floor');
const s2FloorLabel = document.getElementById('s2FloorLabel');
const s2BookList = document.getElementById('s2BookList');
const s2ActiveFilters = document.getElementById('s2ActiveFilters');
const s2FilterCount = document.getElementById('s2FilterCount');
const s2Reset = document.getElementById('s2Reset');

let s2LastRes = null; // raw response, re-filtered on client when sliders change

s2K.addEventListener('input', () => {
  state.s2K = parseInt(s2K.value, 10);
  s2KLabel.textContent = state.s2K;
  renderS2ActiveFilters();
});

s2Floor.addEventListener('input', () => {
  state.s2Floor = parseInt(s2Floor.value, 10) / 100;
  s2FloorLabel.textContent = state.s2Floor.toFixed(2);
  renderS2ActiveFilters();
  if (s2LastRes) renderS2Results(s2LastRes); // re-apply floor client-side
});

document.querySelectorAll('#s2 .row[data-vol]').forEach(row => {
  row.addEventListener('click', () => {
    const vol = row.dataset.vol;
    if (state.s2Volumes.has(vol)) {
      state.s2Volumes.delete(vol);
      row.classList.remove('checked');
    } else {
      state.s2Volumes.add(vol);
      row.classList.add('checked');
    }
    renderS2ActiveFilters();
    if (s2LastRes) renderS2Results(s2LastRes);
  });
});

document.querySelectorAll('#s2 .mode-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('#s2 .mode-chip').forEach(c => c.classList.remove('on'));
    chip.classList.add('on');
    state.s2Mode = chip.dataset.mode;
    renderS2ActiveFilters();
  });
});

s2Reset.addEventListener('click', () => {
  state.s2Mode = 'hybrid';
  state.s2K = 15;
  state.s2Floor = 0;
  state.s2Volumes = new Set(['Book of Mormon', 'D&C']);
  state.s2Books = new Set();
  s2K.value = '15';
  s2KLabel.textContent = '15';
  s2Floor.value = '0';
  s2FloorLabel.textContent = '0.00';
  document.querySelectorAll('#s2 .row[data-vol]').forEach(r => r.classList.add('checked'));
  document.querySelectorAll('#s2 .mode-chip').forEach(c => c.classList.toggle('on', c.dataset.mode === 'hybrid'));
  document.querySelectorAll('#s2 .book-row.checked').forEach(r => r.classList.remove('checked'));
  renderS2ActiveFilters();
  if (s2LastRes) renderS2Results(s2LastRes);
});

s2Form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = s2Input.value.trim();
  if (!text) return;
  s2Meta.innerHTML = `<span>searching… <span class="spinner"></span></span><span></span>`;
  s2Results.innerHTML = '';
  try {
    const res = await apiPost('/api/query', {
      text, k: state.s2K, mode: state.s2Mode, show_scores: true,
    });
    s2LastRes = res;
    renderS2Results(res);
  } catch (err) {
    s2Meta.innerHTML = `<span>search failed</span><span></span>`;
    s2Results.innerHTML = `<div class="err">${escapeHtml(err.message)}</div>`;
  }
});

function renderS2Results(res) {
  const filtered = filterHits(res.results || [], {
    volumes: state.s2Volumes,
    books: state.s2Books,
    floor: state.s2Floor,
  });
  const totalLatency = (res.latency_ms && res.latency_ms.total)
    ? Math.round(res.latency_ms.total)
    : null;
  const latStr = totalLatency != null ? `${totalLatency}ms` : '';
  const idxStr = res.index ? `· index ${res.index.slice(0, 8)}` : '';
  s2Meta.innerHTML = `
    <span>${filtered.length}/${(res.results || []).length} after filters · ${latStr} ${idxStr}</span>
    <span>${escapeHtml(res.mode || '')}</span>
  `;
  if (!filtered.length) {
    s2Results.innerHTML = `<div class="empty">No results match these filters.</div>`;
    return;
  }
  s2Results.innerHTML = filtered.map(renderVerse).join('');
  wireVerseClicks(s2Results, res.query);
}

function renderS2ActiveFilters() {
  const chips = [];
  state.s2Volumes.forEach(v => chips.push(`<span class="chip on"><span class="dot"></span>${escapeHtml(v)}</span>`));
  if (state.s2Books.size) {
    chips.push(`<span class="chip">books: ${state.s2Books.size}</span>`);
  }
  chips.push(`<span class="chip">${escapeHtml(state.s2Mode)}</span>`);
  chips.push(`<span class="chip">k=${state.s2K}</span>`);
  if (state.s2Floor > 0) chips.push(`<span class="chip">≥ ${state.s2Floor.toFixed(2)}</span>`);
  s2ActiveFilters.innerHTML = chips.join('');
  s2FilterCount.textContent = `— ${chips.length} active`;
}

(async function loadBooks() {
  try {
    const books = await apiGet('/api/books');
    const rows = [];
    for (const [book, chapters] of Object.entries(books)) {
      const safeBook = escapeHtml(book);
      rows.push(`
        <div class="row book-row" data-book="${safeBook}">
          <span class="box"></span>${safeBook}
          <span style="margin-left:auto; font-family:'JetBrains Mono',monospace; font-size:10px; color: var(--ink-3);">${chapters.length}</span>
        </div>`);
    }
    s2BookList.innerHTML = rows.join('') || `<div class="empty">No books found.</div>`;
    document.querySelectorAll('#s2 .book-row').forEach(row => {
      row.addEventListener('click', () => {
        const b = row.dataset.book;
        if (state.s2Books.has(b)) {
          state.s2Books.delete(b);
          row.classList.remove('checked');
        } else {
          state.s2Books.add(b);
          row.classList.add('checked');
        }
        renderS2ActiveFilters();
        if (s2LastRes) renderS2Results(s2LastRes);
      });
    });
  } catch (err) {
    s2BookList.innerHTML = `<div class="err">${escapeHtml(err.message)}</div>`;
  }
})();

renderS2ActiveFilters();

/* -------------------- Scene 3: Research (thread + notes) -------------------- */

const s3Thread = document.getElementById('s3Thread');
const s3Form = document.getElementById('s3Form');
const s3Input = document.getElementById('s3Input');

s3Form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = s3Input.value.trim();
  if (!text) return;
  s3Input.value = '';

  if (s3Thread.querySelector('.empty')) s3Thread.innerHTML = '';

  const youMsg = document.createElement('div');
  youMsg.className = 'msg you';
  youMsg.textContent = text;
  s3Thread.appendChild(youMsg);

  const botMsg = document.createElement('div');
  botMsg.className = 'msg bot';
  botMsg.innerHTML = `<div class="label">searching… <span class="spinner"></span></div>`;
  s3Thread.appendChild(botMsg);
  s3Thread.scrollTop = s3Thread.scrollHeight;

  try {
    const res = await apiPost('/api/query', { text, k: 5, mode: 'hybrid', show_scores: true });
    renderS3Bot(botMsg, res);
  } catch (err) {
    botMsg.innerHTML = `<div class="err">${escapeHtml(err.message)}</div>`;
  }
  s3Thread.scrollTop = s3Thread.scrollHeight;
});

function renderS3Bot(botEl, res) {
  const hits = res.results || [];
  if (!hits.length) {
    botEl.innerHTML = `<div class="label">no results</div>`;
    return;
  }
  const verses = hits.map(h => {
    const ref = escapeHtml(h.ref);
    const text = escapeHtml(h.text);
    const score = h.score != null ? fmtScore(h.score) : '';
    const pinned = notes.containsVerse(h.ref) ? ' pinned' : '';
    const iconName = pinned ? 'check' : 'add';
    return `
      <div class="v${pinned}" data-ref="${ref}" data-body="${text}">
        <button class="pin-btn" title="pin to list"><span class="material-icons">${iconName}</span></button>
        <div class="ref-line">${ref} <span class="sc">${score}</span></div>
        <div class="body">${text}</div>
      </div>`;
  }).join('');
  botEl.innerHTML = `
    <div class="label">↳ ${hits.length} nearest verses</div>
    <div class="verses">${verses}</div>
  `;
  botEl.querySelectorAll('.v').forEach(v => {
    const ref = v.dataset.ref;
    const body = v.dataset.body;
    v.addEventListener('click', (ev) => {
      if (ev.target.closest('.pin-btn')) return; // pin button handled separately
      openDetails({ ref, query: res.query });
    });
    const btn = v.querySelector('.pin-btn');
    btn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      if (notes.containsVerse(ref)) return;
      notes.pinVerse(ref, body);
      v.classList.add('pinned');
      btn.innerHTML = '<span class="material-icons">check</span>';
    });
  });
}

/* -------------------- Scene 3: Notes & Verses list (with localStorage) -------------------- */

const nvList = document.getElementById('nvList');
const nvCount = document.getElementById('nvCount');
const nvTitle = document.getElementById('nvTitle');
const savedListEl = document.getElementById('savedList');
const savedCountEl = document.getElementById('savedCount');

const STORAGE_KEY = 'scripvec_saved_lists';

const notes = {
  items: [],
  name: 'Untitled list',
  dirty: false,

  containsVerse(ref) {
    return this.items.some(i => i.kind === 'verse' && i.ref === ref);
  },

  pinVerse(ref, body) {
    if (this.containsVerse(ref)) return false;
    this.items.push({ kind: 'verse', ref, body });
    this.dirty = true;
    this.render();
    return true;
  },

  addNote(text) {
    this.items.push({ kind: 'note', text: text || '' });
    this.dirty = true;
    this.render();
  },

  removeAt(idx) {
    this.items.splice(idx, 1);
    this.dirty = true;
    this.render();
  },

  updateNoteAt(idx, text) {
    if (this.items[idx] && this.items[idx].kind === 'note') {
      this.items[idx].text = text;
      this.dirty = true;
      this.renderTitle();
    }
  },

  loadFrom(name, items) {
    this.name = name;
    this.items = items.slice();
    this.dirty = false;
    this.render();
  },

  clear() {
    this.items = [];
    this.name = 'Untitled list';
    this.dirty = false;
    this.render();
  },

  renderTitle() {
    nvTitle.classList.toggle('dirty', this.dirty);
    nvTitle.querySelector('.nv-name').textContent = this.name;
  },

  render() {
    nvCount.textContent = `${this.items.length} item${this.items.length === 1 ? '' : 's'}`;
    this.renderTitle();

    if (!this.items.length) {
      nvList.innerHTML = `<div class="nv-empty">Pin verses from your searches.<br>Add notes between them.</div>`;
      // Sync pin buttons in thread to unpinned state
      document.querySelectorAll('#s3 .msg.bot .v.pinned').forEach(v => {
        v.classList.remove('pinned');
        const b = v.querySelector('.pin-btn');
        if (b) b.innerHTML = '<span class="material-icons">add</span>';
      });
      return;
    }

    nvList.innerHTML = this.items.map((item, idx) => {
      if (item.kind === 'verse') {
        return `
          <div class="nv-item verse" data-idx="${idx}" data-ref="${escapeHtml(item.ref)}">
            <span class="marker">v.</span>
            <div class="ref-line" data-open>${escapeHtml(item.ref)}</div>
            <div class="body">${escapeHtml(item.body)}</div>
            <span class="rm">remove</span>
          </div>`;
      } else {
        return `
          <div class="nv-item note" contenteditable="true" spellcheck="false" data-idx="${idx}">${escapeHtml(item.text)}
            <span class="rm">remove</span>
          </div>`;
      }
    }).join('');

    // wire remove
    nvList.querySelectorAll('.rm').forEach(rm => {
      rm.addEventListener('click', (ev) => {
        ev.stopPropagation();
        const item = rm.closest('.nv-item');
        const idx = parseInt(item.dataset.idx, 10);
        this.removeAt(idx);
      });
    });
    // wire note edits
    nvList.querySelectorAll('.nv-item.note').forEach(el => {
      el.addEventListener('input', () => {
        const idx = parseInt(el.dataset.idx, 10);
        // strip the trailing rm button text by reading first text node
        const text = Array.from(el.childNodes)
          .filter(n => n.nodeType === 3)
          .map(n => n.textContent).join('').trim();
        this.updateNoteAt(idx, text);
      });
    });
    // wire verse open → details view
    nvList.querySelectorAll('.nv-item.verse [data-open]').forEach(el => {
      el.addEventListener('click', () => {
        const ref = el.parentElement.dataset.ref;
        openDetails({ ref, query: notes.name });
      });
    });

    // sync pin state in the s3 thread
    const pinned = new Set(this.items.filter(i => i.kind === 'verse').map(i => i.ref));
    document.querySelectorAll('#s3 .msg.bot .v').forEach(v => {
      const isPinned = pinned.has(v.dataset.ref);
      v.classList.toggle('pinned', isPinned);
      const b = v.querySelector('.pin-btn');
      if (b) b.innerHTML = `<span class="material-icons">${isPinned ? 'check' : 'add'}</span>`;
    });
  },
};

document.getElementById('addNote').addEventListener('click', () => {
  notes.addNote('');
  // focus the new note
  requestAnimationFrame(() => {
    const last = nvList.querySelector('.nv-item.note:last-of-type');
    if (last) last.focus();
  });
});

document.getElementById('saveList').addEventListener('click', () => {
  const promptedName = window.prompt(
    'Name this list:',
    notes.name === 'Untitled list' ? '' : notes.name,
  );
  if (!promptedName) return;
  savedLists.save(promptedName, notes.items);
  notes.name = promptedName;
  notes.dirty = false;
  notes.renderTitle();
});

document.getElementById('exportList').addEventListener('click', () => {
  const md = renderListAsMarkdown(notes.name, notes.items);
  const blob = new Blob([md], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const filename = notes.name.replace(/[^a-z0-9]+/gi, '-').toLowerCase() || 'scripvec-list';
  a.href = url; a.download = `${filename}.md`;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
});

function renderListAsMarkdown(name, items) {
  let out = `# ${name}\n\n`;
  for (const item of items) {
    if (item.kind === 'verse') {
      out += `> **${item.ref}** — ${item.body}\n\n`;
    } else {
      out += `${item.text}\n\n`;
    }
  }
  return out;
}

/* Saved lists rail (localStorage) */

const savedLists = {
  items: [], // [{name, items, savedAt}]

  load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      this.items = raw ? JSON.parse(raw) : [];
    } catch (_) {
      this.items = [];
    }
    this.render();
  },

  persist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(this.items)); } catch (_) {}
  },

  save(name, items) {
    const existingIdx = this.items.findIndex(l => l.name === name);
    const entry = { name, items: items.slice(), savedAt: new Date().toISOString() };
    if (existingIdx >= 0) this.items[existingIdx] = entry;
    else this.items.unshift(entry);
    this.persist();
    this.render();
  },

  remove(name) {
    this.items = this.items.filter(l => l.name !== name);
    this.persist();
    this.render();
  },

  load_into_notes(name) {
    const entry = this.items.find(l => l.name === name);
    if (!entry) return;
    // auto-save rule: if dirty and has items, save current first
    if (notes.dirty && notes.items.length > 0) {
      const autoName = notes.name === 'Untitled list'
        ? `Auto-saved ${new Date().toLocaleTimeString()}`
        : notes.name;
      this.save(autoName, notes.items);
    }
    notes.loadFrom(entry.name, entry.items);
    this.render();
  },

  render() {
    savedCountEl.textContent = String(this.items.length);
    if (!this.items.length) {
      savedListEl.innerHTML = `<div class="empty">No saved lists yet.</div>`;
      return;
    }
    savedListEl.innerHTML = this.items.map(entry => {
      const dt = new Date(entry.savedAt);
      const meta = `${entry.items.length} items · ${dt.toLocaleDateString()}`;
      const cls = entry.name === notes.name && !notes.dirty ? 'saved-item active' : 'saved-item';
      return `
        <div class="${cls}" data-name="${escapeHtml(entry.name)}">
          <span class="saved-del" title="delete">×</span>
          <div class="name">${escapeHtml(entry.name)}</div>
          <div class="meta">${escapeHtml(meta)}</div>
        </div>`;
    }).join('');
    savedListEl.querySelectorAll('.saved-item').forEach(el => {
      el.addEventListener('click', (ev) => {
        if (ev.target.classList.contains('saved-del')) return;
        savedLists.load_into_notes(el.dataset.name);
      });
      const del = el.querySelector('.saved-del');
      if (del) del.addEventListener('click', (ev) => {
        ev.stopPropagation();
        if (window.confirm(`Delete "${el.dataset.name}"?`)) savedLists.remove(el.dataset.name);
      });
    });
  },
};

notes.render();
savedLists.load();

/* -------------------- Scene 4: Details view -------------------- */

const s4Form = document.getElementById('s4Form');
const s4Input = document.getElementById('s4Input');
const s4ResultList = document.getElementById('s4ResultList');
const s4ResultCount = document.getElementById('s4ResultCount');
const s4QueryText = document.getElementById('s4QueryText');
const s4Heading = document.getElementById('s4Heading');
const s4Breadcrumb = document.getElementById('s4Breadcrumb');
const s4Chapter = document.getElementById('s4Chapter');
const s4Similar = document.getElementById('s4Similar');
const s4SimilarCount = document.getElementById('s4SimilarCount');

s4Form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = s4Input.value.trim();
  if (!text) return;
  await runS4Search(text);
});

async function runS4Search(text) {
  s4QueryText.textContent = text;
  s4ResultList.innerHTML = `<div class="empty">searching…</div>`;
  s4ResultCount.textContent = '';
  try {
    const res = await apiPost('/api/query', { text, k: 12, mode: 'hybrid', show_scores: true });
    state.s4Query = text;
    state.s4Results = res.results || [];
    renderS4Results();
    if (state.s4Results.length) {
      openVerse(state.s4Results[0]);
    } else {
      s4Heading.textContent = 'No results';
      s4Chapter.innerHTML = `<p class="empty">Try a different query.</p>`;
      s4Similar.innerHTML = '';
    }
  } catch (err) {
    s4ResultList.innerHTML = `<div class="err">${escapeHtml(err.message)}</div>`;
  }
}

function renderS4Results(activeRef) {
  s4ResultCount.textContent = `${state.s4Results.length} verse${state.s4Results.length === 1 ? '' : 's'}`;
  if (!state.s4Results.length) {
    s4ResultList.innerHTML = `<div class="empty">No results yet.</div>`;
    return;
  }
  s4ResultList.innerHTML = state.s4Results.map(hit => {
    const isActive = activeRef && hit.ref === activeRef ? ' active' : '';
    return `
      <div class="s4-res${isActive}" data-ref="${escapeHtml(hit.ref)}">
        <div class="top">
          <span class="r">${escapeHtml(hit.ref)}</span>
          <span class="s">${hit.score != null ? fmtScore(hit.score) : ''}</span>
        </div>
        <div class="snip">${escapeHtml(hit.text)}</div>
      </div>`;
  }).join('');
  s4ResultList.querySelectorAll('.s4-res').forEach(el => {
    el.addEventListener('click', () => {
      const ref = el.dataset.ref;
      const hit = state.s4Results.find(h => h.ref === ref);
      if (hit) openVerse(hit);
    });
  });
}

async function openVerse(hit) {
  const parsed = parseRef(hit.ref);
  if (!parsed) {
    s4Heading.textContent = hit.ref;
    s4Chapter.innerHTML = `<p>${escapeHtml(hit.text || '')}</p>`;
    return;
  }
  renderS4Results(hit.ref);
  s4Breadcrumb.textContent = `${parsed.book} › Chapter ${parsed.chapter} › verse ${parsed.verse}`;
  s4Heading.textContent = `${parsed.book} ${parsed.chapter}`;
  s4Chapter.innerHTML = `<p class="empty">loading…</p>`;
  s4Similar.innerHTML = `<div class="empty">loading similar…</div>`;
  s4SimilarCount.textContent = '';

  try {
    const ch = await apiGet(
      `/api/chapter?book=${encodeURIComponent(parsed.book)}&chapter=${parsed.chapter}&focus_verse=${parsed.verse}`,
    );
    renderChapter(ch, parsed.verse);
  } catch (err) {
    s4Chapter.innerHTML = `<div class="err">${escapeHtml(err.message)}</div>`;
  }

  // Auto-run a similarity search using the verse text as the query
  try {
    const verseText = hit.text || '';
    if (verseText) {
      const sim = await apiPost('/api/query', { text: verseText, k: 8, mode: 'dense', show_scores: true });
      renderSimilar(sim, hit.ref);
    } else {
      s4Similar.innerHTML = '';
    }
  } catch (err) {
    s4Similar.innerHTML = `<div class="err">${escapeHtml(err.message)}</div>`;
  }
}

function renderChapter(ch, focusVerse) {
  s4Breadcrumb.textContent = ch.breadcrumb;
  s4Heading.textContent = `${ch.book === 'D&C' ? 'D&C ' + ch.chapter : ch.book + ' ' + ch.chapter}`;
  if (!ch.verses.length) {
    s4Chapter.innerHTML = `<p class="empty">No verses found.</p>`;
    return;
  }
  s4Chapter.innerHTML = ch.verses.map(v => {
    const focused = v.verse === focusVerse ? ' class="focus"' : '';
    return `<p${focused} data-verse="${v.verse}"><span class="vn">${v.verse}</span>${escapeHtml(v.text)}</p>`;
  }).join('');
  // scroll the focused verse into view
  if (focusVerse) {
    const target = s4Chapter.querySelector(`p[data-verse="${focusVerse}"]`);
    if (target) target.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }
}

function renderSimilar(res, currentRef) {
  const hits = (res.results || []).filter(h => h.ref !== currentRef);
  s4SimilarCount.textContent = `${hits.length} found`;
  if (!hits.length) {
    s4Similar.innerHTML = `<div class="empty">No neighbors.</div>`;
    return;
  }
  s4Similar.innerHTML = hits.map(h => `
    <div class="similar-row" data-ref="${escapeHtml(h.ref)}">
      <div class="r"><span>${escapeHtml(h.ref)}</span><span>${h.score != null ? fmtScore(h.score) : ''}</span></div>
      <div class="b">${escapeHtml(h.text)}</div>
    </div>
  `).join('');
  s4Similar.querySelectorAll('.similar-row').forEach(row => {
    row.addEventListener('click', () => {
      const ref = row.dataset.ref;
      const hit = hits.find(h => h.ref === ref);
      if (hit) {
        // Promote this to the active selection (don't lose the original result list)
        const exists = state.s4Results.some(h => h.ref === ref);
        if (!exists) state.s4Results = [hit, ...state.s4Results];
        openVerse(hit);
      }
    });
  });
}

/* -------------------- Cross-scene navigation -------------------- */

function wireVerseClicks(container, queryText) {
  container.querySelectorAll('.verse').forEach(el => {
    el.addEventListener('click', () => {
      const ref = el.dataset.ref;
      const body = el.querySelector('.verse-body').textContent;
      openDetails({ ref, text: body, query: queryText });
    });
  });
}

function openDetails({ ref, text, query }) {
  state.s4Query = query || ref;
  if (s4Input) s4Input.value = query || '';
  s4QueryText.textContent = state.s4Query;
  // synthesize a result entry so the left rail isn't empty
  if (!state.s4Results.length || !state.s4Results.some(h => h.ref === ref)) {
    state.s4Results = [{ ref, text: text || '', score: null }];
  }
  showScene('s4');
  const hit = state.s4Results.find(h => h.ref === ref) || { ref, text: text || '', score: null };
  openVerse(hit);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* -------------------- Tweaks panel -------------------- */

const tweaksToggle = document.getElementById('tweaksToggle');
const tweaksPanel = document.getElementById('tweaksPanel');
const closeTweaks = document.getElementById('closeTweaks');

tweaksToggle.addEventListener('click', () => {
  tweaksPanel.classList.add('open');
  tweaksToggle.style.display = 'none';
});
closeTweaks.addEventListener('click', () => {
  tweaksPanel.classList.remove('open');
  tweaksToggle.style.display = 'block';
});

document.querySelectorAll('.tweaks .opts').forEach(group => {
  group.querySelectorAll('.opt').forEach(opt => {
    opt.addEventListener('click', () => {
      group.querySelectorAll('.opt').forEach(o => o.classList.remove('on'));
      opt.classList.add('on');
      const key = group.dataset.tw;
      const val = opt.dataset.val;
      document.body.dataset[key] = val;
      try { localStorage.setItem('scripvec_tw_' + key, val); } catch (_) {}
    });
  });
});

['scores', 'density'].forEach(key => {
  try {
    const v = localStorage.getItem('scripvec_tw_' + key);
    if (v) {
      document.body.dataset[key] = v;
      const group = document.querySelector(`.tweaks .opts[data-tw="${key}"]`);
      if (group) {
        group.querySelectorAll('.opt').forEach(o => o.classList.toggle('on', o.dataset.val === v));
      }
    }
  } catch (_) {}
});
