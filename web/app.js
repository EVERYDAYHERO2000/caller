/* Caller SPA — vanilla JS, no build step (runs fine from a Raspberry Pi). */
'use strict';

// ------------------------------------------------------------------ icons (lucide paths)
const ICONS = {
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
  phoneIn: '<polyline points="16 2 16 8 22 8"/><line x1="22" y1="2" x2="16" y2="8"/><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
  phoneOut: '<polyline points="22 8 22 2 16 2"/><line x1="16" y1="8" x2="22" y2="2"/><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
  phoneOff: '<path d="M10.7 13.3a16 16 0 0 0 3.4 2.6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.4 19.4 0 0 1-3.3-2.7m-2.7-3.4A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9"/><line x1="22" y1="2" x2="2" y2="22"/>',
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
  script: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="13" y2="17"/>',
  tag: '<path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
  layers: '<path d="M12 2l10 5-10 5L2 7z"/><path d="M2 12l10 5 10-5"/><path d="M2 17l10 5 10-5"/>',
  bot: '<rect x="3" y="8" width="18" height="12" rx="3"/><path d="M12 8V4"/><circle cx="12" cy="3" r="1"/><circle cx="9" cy="14" r="1.2"/><circle cx="15" cy="14" r="1.2"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  signal: '<path d="M2 20h.01"/><path d="M7 20v-4"/><path d="M12 20v-8"/><path d="M17 20V8"/><path d="M22 4v16"/>',
  tower: '<path d="M4.9 16.1a10 10 0 0 1 0-14.2"/><path d="M7.8 13.2a6 6 0 0 1 0-8.4"/><circle cx="12" cy="9" r="2"/><path d="M16.2 4.8a6 6 0 0 1 0 8.4"/><path d="M19.1 1.9a10 10 0 0 1 0 14.2"/><path d="M9.5 18h5"/><path d="m8 22 4-11 4 11"/>',
  chip: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
  thermo: '<path d="M14 4v10.5a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0z"/>',
  plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  trash: '<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>',
  x: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  send: '<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',
  refresh: '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  menu: '<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>',
  eye: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M17.9 17.9A10.1 10.1 0 0 1 12 20C5 20 1 12 1 12a18.5 18.5 0 0 1 5.1-5.9M9.9 4.2A9.1 9.1 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.2 3.2M14.1 14.1a3 3 0 1 1-4.2-4.2"/><line x1="1" y1="1" x2="23" y2="23"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
  terminal: '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
  power: '<path d="M18.4 6.6a9 9 0 1 1-12.8 0"/><line x1="12" y1="2" x2="12" y2="12"/>',
  sim: '<path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/><rect x="8" y="11" width="8" height="7" rx="1"/>',
  info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
  check: '<polyline points="20 6 9 17 4 12"/>',
  lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  play: '<polygon points="6 4 20 12 6 20 6 4"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
  download: '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>',
  sparkle: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  tasks: '<path d="M9 6h11"/><path d="M9 12h11"/><path d="M9 18h11"/><polyline points="3 6 4.5 7.5 7 5"/><polyline points="3 12 4.5 13.5 7 11"/><polyline points="3 18 4.5 19.5 7 17"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
  pin: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="3"/>',
  search: '<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  more: '<circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/>',
  chevronLeft: '<polyline points="15 18 9 12 15 6"/>',
  chevronRight: '<polyline points="9 18 15 12 9 6"/>',
  arrowRight: '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="13 6 19 12 13 18"/>',
  pause: '<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/>',
  wave: '<path d="M2 12h2"/><path d="M6 8v8"/><path d="M10 4v16"/><path d="M14 7v10"/><path d="M18 10v4"/><path d="M22 12h0"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
  memory: '<rect x="2" y="7" width="20" height="10" rx="2"/><path d="M6 7V5M10 7V5M14 7V5M18 7V5M6 17v2M18 17v2"/><path d="M6 11h2v2H6zM11 11h2v2h-2zM16 11h2v2h-2z"/>',
  disk: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
  server: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
  wifi: '<path d="M2 8.8a15 15 0 0 1 20 0"/><path d="M5 12.5a10 10 0 0 1 14 0"/><path d="M8.5 16a5 5 0 0 1 7 0"/><path d="M12 19.5h.01"/>',
  mic: '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v1a7 7 0 0 0 14 0v-1"/><line x1="12" y1="18" x2="12" y2="22"/>',
  micOff: '<line x1="2" y1="2" x2="22" y2="22"/><path d="M18.9 13.3A7 7 0 0 0 19 11v-1M5 10v1a7 7 0 0 0 12 4.9"/><path d="M15 9.3V5a3 3 0 0 0-5.7-1.3M9 9v2a3 3 0 0 0 5.1 2.1"/><line x1="12" y1="18" x2="12" y2="22"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
  key: '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
};
const icon = (name, cls = '') => `<svg class="i ${cls}" viewBox="0 0 24 24">${ICONS[name] || ''}</svg>`;

// ------------------------------------------------------------------ helpers
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtDate = (s) => { if (!s) return '—'; const d = new Date(s); return d.toLocaleDateString(I18N.locale, { day: '2-digit', month: '2-digit' }) + ' ' + d.toLocaleTimeString(I18N.locale, { hour: '2-digit', minute: '2-digit' }); };
const fmtDur = (sec) => { sec = Math.max(0, Math.round(sec || 0)); const m = Math.floor(sec / 60), s = sec % 60; return `${m}:${String(s).padStart(2, '0')}`; };
const fmtNum = (v, unit = '') => (v === null || v === undefined || v === '') ? '—' : `${v}${unit}`;
const initials = (s) => (s || '').trim().split(/\s+/).filter((w) => /^[\p{L}\p{N}]/u.test(w)).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '?';
// Contact avatars: every character has its own hue (a dictionary; neighbouring letters are spread by the golden
// angle so similar initials differ). Two initials mix by averaging the hues on the colour wheel — lightness and
// chroma stay fixed (see .avatar in style.css), so a mix is a clean pastel, never a muddy grey like RGB mixing.
const AVATAR_HUES = Object.fromEntries([...'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#']
  .map((ch, i) => [ch, Math.round((i * 137.508) % 360)]));
// the wheel is squeezed into OKLCH hues 140°→40° (through blue, violet, pink, red): the ochre / olive / khaki band
// in between turns muddy on a dark background whatever the lightness
const avatarWheel = (h) => Math.round((140 + h * 260 / 360) % 360);
function avatarHue(name) {
  const hues = [...initials(name)].map((ch) => AVATAR_HUES[ch]).filter((h) => h != null);
  if (!hues.length) return null;
  let x = 0, y = 0;
  for (const h of hues) { x += Math.cos(h * Math.PI / 180); y += Math.sin(h * Math.PI / 180); }
  const mix = Math.hypot(x, y) < 0.2 ? hues[0]  // opposite hues cancel out — keep the first letter's
    : (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  return avatarWheel(mix);
}
const avatarStyle = (name) => { const h = avatarHue(name); return h == null ? '' : ` style="--av-h:${h}"`; };

const state = {
  user: null,
  modem: null, active: null, stats: null,
  agents: [], scripts: [], contacts: [],
  view: null, callStart: null,
};

// A button that sends something shows a spinner until its request is done: the button pressed just before
// a non-GET request is busy while it runs (handlers stay as they are). Modal and dialog buttons spin themselves.
let pressed = null;
document.addEventListener('click', (e) => {
  const b = e.target.closest?.('button, .btn');
  pressed = b && !b.matches('[role=tab], .menu-item') ? { b, t: performance.now() } : null;
}, true);
document.addEventListener('submit', (e) => {
  const b = e.submitter || e.target.querySelector('button[type=submit], button:not([type])');
  if (b) pressed = { b, t: performance.now() };
}, true);
function busyButton(b, promise) {
  b._busy = (b._busy || 0) + 1;
  const timer = setTimeout(() => {  // fast requests don't flicker
    if (!b._busy || b.classList.contains('busy')) return;
    const sp = document.createElement('span');
    sp.className = 'spin btn-spin';
    sp.style.color = getComputedStyle(b).color;
    b.classList.add('busy'); b.disabled = true; b.appendChild(sp);
  }, 150);
  const done = () => {
    if (--b._busy) return;
    clearTimeout(timer);
    if (!b.classList.contains('busy')) return;
    b.classList.remove('busy'); b.disabled = false; $('.btn-spin', b)?.remove();
  };
  promise.then(done, done);
}
// the page's first data: the view shows a spinner until the requests started while it renders are done
const pageLoad = { on: false, n: 0, idle: null };

async function api(path, opts = {}) {
  const p = apiCall(path, opts);
  const b = pressed && performance.now() - pressed.t < 400 && pressed.b.isConnected && !pressed.b.disabled ? pressed.b : null;
  if (b && (opts.method || 'GET') !== 'GET') busyButton(b, p);
  if (pageLoad.on) {
    pageLoad.n++;
    const done = () => { if (--pageLoad.n === 0) pageLoad.idle?.(); };
    p.then(done, done);
  }
  return p;
}

async function apiCall(path, { method = 'GET', body } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const r = await fetch('/api' + path, { method, headers, credentials: 'same-origin', body: body !== undefined ? JSON.stringify(body) : undefined });
  if (r.status === 401 && !path.startsWith('/auth/')) { showLogin(); throw new Error('Требуется вход'); }
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json() : await r.text();
  if (!r.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === 'string' ? d : d ? d.map((x) => x.msg || JSON.stringify(x)).join('; ') : r.statusText);
  }
  return data;
}

const recentToasts = new Map();  // the same message from two sources (API error + live event) shows once
function toast(msg, type = 'info', ms = 3500) {
  const now = Date.now();
  if (now - (recentToasts.get(msg) || 0) < 3000) return;
  recentToasts.set(msg, now);
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `${icon(type === 'err' ? 'alert' : type === 'ok' ? 'check' : 'info')}<div>${esc(msg)}</div>`;
  $('#toasts').appendChild(el);
  setTimeout(() => el.remove(), ms);
}
// a toast with a countdown and «Отменить»: onCommit runs when the time is up, onUndo if the user cancels.
// Returns undo() — e.g. for the same checkbox clicked again.
function undoToast(msg, seconds, onCommit, onUndo) {
  const el = document.createElement('div');
  el.className = 'toast ok undo-toast';
  el.innerHTML = `${icon('check')}<div class="undo-msg">${esc(msg)}</div><span class="undo-left mono">${seconds}</span>
    <button type="button" class="btn btn-ghost btn-sm">Отменить</button><span class="undo-bar" style="animation-duration:${seconds}s"></span>`;
  $('#toasts').appendChild(el);
  let left = seconds, done = false;
  const finish = (commit) => {
    if (done) return;
    done = true; clearInterval(tick); el.remove();
    (commit ? onCommit : onUndo)?.();
  };
  const tick = setInterval(() => { left -= 1; $('.undo-left', el).textContent = left; if (left <= 0) finish(true); }, 1000);
  $('button', el).onclick = () => finish(false);
  return () => finish(false);
}
const guard = (fn) => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message, 'err', 5000); } };

// kv rows are one line high: give truncated values a tooltip with the full text
function kvTitles(root) {
  // empty values ("—" or nothing) get the same "no data" pill as table cells
  $$('.kv > dd', root).forEach((dd) => {
    if (!dd.querySelector('svg, .badge, audio') && /^[\s—-]*$/.test(dd.textContent)) dd.innerHTML = dash;
  });
  $$('.kv > dd, .kv > dt', root).forEach((el) => {
    if (el.scrollWidth > el.clientWidth) el.title = el.textContent.trim(); else el.removeAttribute('title');
  });
}

function modal({ title, body, size = '', buttons = [], onMount }) {
  const root = $('#modal-root');
  const wrap = document.createElement('div');
  wrap.className = 'modal-backdrop';
  wrap.innerHTML = `<div class="modal ${size}"><div class="modal-head"><h2>${title}</h2><span class="spacer"></span>
    <button class="btn btn-ghost btn-icon btn-sm" data-close>${icon('x')}</button></div>
    <div class="modal-body">${body}</div>
    ${buttons.length ? `<div class="modal-foot">${buttons.map((b, i) => `<button class="btn btn-lg ${b.cls || ''}" data-btn="${i}">${b.label}</button>`).join('')}</div>` : ''}</div>`;
  const onKey = (e) => {
    if (!wrap.isConnected) { document.removeEventListener('keydown', onKey); return; }
    if (e.key === 'Escape' && root.lastElementChild === wrap) close();  // only the topmost panel
  };
  const close = () => {
    document.removeEventListener('keydown', onKey);
    if (!wrap.isConnected || wrap.classList.contains('closing')) return;
    wrap.classList.add('closing');
    setTimeout(() => wrap.remove(), 180);
  };
  document.addEventListener('keydown', onKey);
  wrap.addEventListener('mousedown', (e) => { if (e.target === wrap) close(); });
  $('[data-close]', wrap).onclick = close;
  // while a button's action runs (e.g. «Позвонить» waits for the agent to get ready) it spins and the buttons are locked
  const btns = buttons.map((_, i) => $(`[data-btn="${i}"]`, wrap));
  buttons.forEach((b, i) => {
    btns[i].onclick = guard(async () => {
      if (!b.onClick) return close();
      const label = btns[i].innerHTML;
      btns.forEach((x) => { x.disabled = true; });
      btns[i].innerHTML = '<span class="spin"></span>';
      try {
        if ((await b.onClick(wrap)) !== false) close();
      } finally {
        btns.forEach((x) => { x.disabled = false; });
        btns[i].innerHTML = label;
      }
    });
  });
  root.appendChild(wrap);
  onMount?.(wrap);
  requestAnimationFrame(() => kvTitles(wrap));
  return { el: wrap, close };
}
// ------------------------------------------------------------------ confirm dialog (centred)
// dialog({ title, text, confirm, danger, onConfirm }) → Promise<boolean>. onConfirm runs while the button
// spins; if it throws, the dialog stays open and the error is shown. Esc / Enter / backdrop click work,
// and Esc closes only the dialog, not a drawer under it.
function dialog({ title = 'Подтверждение', text = '', confirm = 'OK', cancel = 'Отмена', danger = false, onConfirm } = {}) {
  return new Promise((resolve) => {
    const wrap = document.createElement('div');
    wrap.className = 'dialog-backdrop';
    wrap.innerHTML = `<div class="dialog" role="alertdialog" aria-modal="true" aria-labelledby="dlg-title" aria-describedby="dlg-text">
      <h2 id="dlg-title">${esc(title)}</h2>
      ${text ? `<p id="dlg-text">${esc(text)}</p>` : ''}
      <div class="dialog-actions"><button type="button" class="btn btn-ghost" data-no>${esc(cancel)}</button>
        <button type="button" class="btn ${danger ? 'btn-danger solid' : 'btn-primary'}" data-yes>${esc(confirm)}</button></div></div>`;
    const prevFocus = document.activeElement;
    const yes = $('[data-yes]', wrap), no = $('[data-no]', wrap);
    let busy = false;
    const close = (result) => {
      document.removeEventListener('keydown', onKey, true);
      wrap.classList.add('closing');
      setTimeout(() => wrap.remove(), 150);
      prevFocus?.focus?.();
      resolve(result);
    };
    const ok = async () => {
      if (busy) return;
      if (onConfirm) {
        busy = true; yes.disabled = no.disabled = true;
        const label = yes.innerHTML;
        yes.innerHTML = '<span class="spin"></span>';
        try { await onConfirm(); } catch (e) {
          toast(e.message || String(e), 'err', 6000);
          busy = false; yes.disabled = no.disabled = false; yes.innerHTML = label;
          return;
        }
      }
      close(true);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); if (!busy) close(false); }
      else if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); ok(); }
    };
    yes.onclick = ok;
    no.onclick = () => !busy && close(false);
    wrap.addEventListener('mousedown', (e) => { if (e.target === wrap && !busy) close(false); });
    document.addEventListener('keydown', onKey, true);
    document.body.appendChild(wrap);
    yes.focus();
  });
}
const confirmBox = (text, onYes, label = 'Удалить') => /^Удал/.test(label)
  ? dialog({ title: text, text: 'Это действие нельзя отменить.', confirm: label, danger: true, onConfirm: onYes })
  : dialog({ title: 'Подтверждение', text, confirm: label, onConfirm: onYes });

// «v1.0.0 · 01.10.26 14:05» under «Caller»: the release + when its code was built
const versionLabel = () => (state.version ? `v${state.version.version}${state.version.build ? ` · ${state.version.build}` : ''}` : '');

// ------------------------------------------------------------------ login
function showLogin() {
  if ($('#login')) return;
  state.user = null;
  document.body.classList.add('logged-out');
  const el = document.createElement('div');
  el.id = 'login';
  el.className = 'login-screen';
  el.innerHTML = `<form class="card login-card" id="login-form">
      <div class="brand" style="padding:0 0 18px"><div class="brand-logo">${icon('phone')}</div>
        <div><div class="brand-name">Caller</div><div class="brand-sub" data-version>${esc(versionLabel())}</div></div></div>
      <h2 style="font-size:18px;margin-bottom:4px">Вход</h2>
      <p class="muted small" style="margin:0 0 18px">Войдите, чтобы управлять звонками и агентами</p>
      <div class="form">
        <div class="field"><label>Логин</label><input name="username" autocomplete="username" autofocus required></div>
        <div class="field"><label>Пароль</label><input name="password" type="password" autocomplete="current-password" required></div>
        <div class="login-error" id="login-error"></div>
        <button class="btn btn-lg btn-primary" type="submit" style="width:100%">Войти</button>
      </div></form>`;
  document.body.appendChild(el);
  $('#login-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = $('button', e.target); btn.disabled = true;
    $('#login-error').textContent = '';
    try {
      const r = await api('/auth/login', { method: 'POST', body: formData(e.target) });
      state.user = r.user;
      el.remove();
      document.body.classList.remove('logged-out');
      start();
    } catch (err) {
      $('#login-error').textContent = err.message;
      btn.disabled = false;
    }
  };
}

async function logout() {
  try { await api('/auth/logout', { method: 'POST' }); } catch { /* ignore */ }
  location.hash = '';
  location.reload();
}

function renderUser() {
  const u = state.user;
  $('#user-box').innerHTML = u ? `<div class="avatar" style="width:30px;height:30px;font-size:12px">${esc(initials(u.username))}</div>
    <span class="ellipsis small" style="flex:1">${esc(u.username)}</span>
    <button class="btn btn-ghost btn-sm btn-icon" id="logout" title="Выйти">${icon('logout')}</button>` : '';
  if (u) $('#logout').onclick = logout;
  // closed with «×» — until the next session (it's a security reminder, so it comes back after a new login)
  const notice = u?.default_password && !sessionStorage.getItem('caller.notice.password');
  document.body.classList.toggle('has-notice', !!notice);
  $('#notice').innerHTML = notice
    ? `<div class="notice">${icon('alert')}<span>Используется пароль по умолчанию. Смените его в разделе <a href="#/settings?tab=security">Настройки → Безопасность</a>.</span>
        <button type="button" class="notice-close" title="Закрыть" aria-label="Закрыть">${icon('x')}</button></div>` : '';
  const close = $('#notice .notice-close');
  if (close) close.onclick = () => {
    sessionStorage.setItem('caller.notice.password', '1');
    $('#notice').innerHTML = '';
    document.body.classList.remove('has-notice');
  };
}

function formData(root) {
  const out = {};
  $$('[name]', root).forEach((el) => {
    const k = el.name;
    if (el.type === 'checkbox') out[k] = el.checked;
    else if (el.type === 'number' || el.type === 'range') out[k] = el.value === '' ? null : Number(el.value);
    else if (el.dataset.type === 'int') out[k] = el.value === '' ? null : Number(el.value);
    else out[k] = el.value;
  });
  return out;
}

const STATUS = {
  completed: ['ok', 'Завершён'], active: ['info', 'Разговор'], dialing: ['warn', 'Набор'], ringing: ['warn', 'Звонит'],
  answering: ['warn', 'Ответ'], missed: ['err', 'Пропущен'], rejected: ['err', 'Отклонён'], busy: ['err', 'Занято'],
  no_answer: ['err', 'Нет ответа'], failed: ['err', 'Ошибка'], cancelled: ['', 'Отменён'], queued: ['primary', 'В очереди'],
};
// section-level buttons go to the page header, next to the title (secondary first, primary last)
function setActions(html) {
  const el = $('#topbar-right');
  el.innerHTML = html;
  return el;
}

// ---------- form explanations -> "?" next to the field label
// A static `.hint` under a field (no id) becomes a "?" whose tooltip shows the text.
// Hints with an id are live status lines (counters, warnings) and stay under the field.
function helpify(root) {
  // Every note under a field goes to a "?" next to its label.
  //  - static note (no id): text is copied into the "?" and the note is removed;
  //  - live note (has id, updated by code): the note stays hidden and the "?" mirrors its text,
  //    appearing only while there is something to say.
  $$('.field .hint', root).forEach((hint) => {
    if (hint.dataset.helped) return;
    const live = !!hint.id;
    // the tooltip is built from the hint's pieces, each translated on its own: a hint with a link or a value inside
    // («… Все скиллы →») is several text nodes, and the language engine translates text node by text node
    const text = () => [...hint.childNodes].map((n) => {
      const v = n.textContent.replace(/\s+/g, ' ').trim();
      return v && window.I18N ? I18N.t(v) : v;
    }).filter(Boolean).join(' ').replace(/\s+([.,;:!?])/g, '$1').trim();
    const field = hint.closest('.field');
    const label = field && [...field.children].find((el) => el.tagName === 'LABEL')
      || field?.querySelector('label');
    if (!label || (!live && !text())) return;
    const help = document.createElement('span');
    help.className = 'help sm';
    help.tabIndex = 0;
    help.setAttribute('role', 'note');
    help.addEventListener('click', (e) => e.preventDefault());  // don't toggle/focus the labelled input
    const sync = () => {
      const t = text();
      help.dataset.tip = t;
      help.setAttribute('aria-label', t);
      help.hidden = !t;
    };
    help.textContent = '?';
    sync();
    // a label that wraps its control (switches) gets the "?" right after it, otherwise inside it
    if (label.querySelector('input,select,textarea')) label.after(help); else label.append(' ', help);
    if (live) {
      hint.dataset.helped = '1';
      hint.hidden = true;
      new MutationObserver(sync).observe(hint, { childList: true, characterData: true, subtree: true });
    } else {
      hint.remove();
    }
  });
}
// sliders: keep the filled part of the track (--fill) in sync with the value
function syncRange(el) {
  const min = +el.min || 0, max = el.max === '' ? 100 : +el.max;
  el.style.setProperty('--fill', `${((+el.value - min) / (max - min || 1)) * 100}%`);
}
const initRanges = (root) => {
  if (root.matches?.('input[type=range]')) syncRange(root);
  $$('input[type=range]', root).forEach(syncRange);
};
document.addEventListener('input', (e) => { if (e.target.matches?.('input[type=range]')) syncRange(e.target); });

new MutationObserver((records) => {
  for (const r of records) r.addedNodes.forEach((n) => { if (n.nodeType === 1) { helpify(n); initRanges(n); } });
}).observe(document.body, { childList: true, subtree: true });
// one floating tooltip for every "?": fixed-positioned, so drawers' scroll areas can't clip it
const tip = document.createElement('div');
tip.className = 'tooltip';
tip.setAttribute('role', 'tooltip');
document.body.appendChild(tip);
function showTip(h) {
  tip.textContent = h.dataset.tip;
  tip.style.display = 'block';
  const r = h.getBoundingClientRect(), w = tip.offsetWidth, ht = tip.offsetHeight;
  const left = Math.max(8, Math.min(r.left - 8, innerWidth - w - 8));
  const top = r.bottom + 8 + ht > innerHeight - 8 ? r.top - 8 - ht : r.bottom + 8;
  tip.style.left = `${left}px`;
  tip.style.top = `${Math.max(8, top)}px`;
}
const hideTip = () => { tip.style.display = 'none'; };
// .help — the "?" marks; .has-tip — any element with data-tip (e.g. the modem status dot in the menu)
const TIP_SEL = '.help, .has-tip';
document.addEventListener('mouseover', (e) => { const h = e.target.closest?.(TIP_SEL); if (h?.dataset.tip) showTip(h); });
document.addEventListener('mouseout', (e) => { if (e.target.closest?.(TIP_SEL) && !e.relatedTarget?.closest?.(TIP_SEL)) hideTip(); });
document.addEventListener('focusin', (e) => { const h = e.target.closest?.(TIP_SEL); if (h?.dataset.tip) showTip(h); else hideTip(); });
window.addEventListener('scroll', hideTip, true);

// ---------- row actions: click = open, "⋮" = dropdown with all actions
const KEBAB = `<button class="btn btn-ghost btn-sm btn-icon kebab" title="Действия" aria-label="Действия" aria-haspopup="menu">${icon('more', 'filled')}</button>`;
let menuState = null;

function closeMenu() {
  if (!menuState) return;
  menuState.el.remove();
  if (menuState.mark) menuState.anchor.classList.remove('active');
  document.removeEventListener('mousedown', menuState.onOutside, true);
  document.removeEventListener('keydown', menuState.onKey, true);
  window.removeEventListener('scroll', closeMenu, true);
  window.removeEventListener('resize', closeMenu);
  menuState = null;
}

// a right click opens the "⋮" menu of its row at the mouse: set by the contextmenu handler below
let menuAt = null;

function openMenu(anchor, items) {
  const at = menuAt;
  menuAt = null;
  const reopen = !at && menuState?.anchor === anchor;
  closeMenu();
  if (reopen) return;  // second click on the same "⋮" just closes it
  const el = document.createElement('div');
  el.className = 'menu';
  el.setAttribute('role', 'menu');
  el.innerHTML = items.filter(Boolean).map((it, i) => (it === '-' ? '<div class="menu-sep"></div>'
    : `<button class="menu-item ${it.danger ? 'danger' : ''}" role="menuitem" data-i="${i}">${icon(it.icon)}<span>${esc(it.label)}</span></button>`)).join('');
  document.body.appendChild(el);
  // fixed positioning: never clipped by the table's scroll container
  const r = at ? { top: at.y, bottom: at.y, right: at.x + el.offsetWidth } : anchor.getBoundingClientRect();
  const top = r.bottom + 4 + el.offsetHeight > innerHeight - 8 ? r.top - 4 - el.offsetHeight : r.bottom + 4;
  el.style.top = `${Math.max(8, top)}px`;
  el.style.left = `${Math.max(8, Math.min(r.right - el.offsetWidth, innerWidth - el.offsetWidth - 8))}px`;
  const list = items.filter(Boolean);
  $$('.menu-item', el).forEach((b) => b.onclick = (e) => { e.stopPropagation(); closeMenu(); guard(list[+b.dataset.i].run)(); });
  // a "⋮" stays highlighted while its menu is open; a list item opened by a right click keeps its own classes
  const mark = !at || anchor.classList.contains('kebab');
  if (mark) anchor.classList.add('active');
  menuState = {
    el, anchor, mark,
    onOutside: (e) => { if (!el.contains(e.target) && !anchor.contains(e.target)) closeMenu(); },
    onKey: (e) => { if (e.key === 'Escape') { e.stopPropagation(); closeMenu(); anchor.focus(); } },
  };
  document.addEventListener('mousedown', menuState.onOutside, true);
  document.addEventListener('keydown', menuState.onKey, true);
  window.addEventListener('scroll', closeMenu, true);
  window.addEventListener('resize', closeMenu);
  el.querySelector('.menu-item')?.focus();
}

// a click on a call widget's header (who · when · status) opens the call's drawer — in the feed, a task, a chat
document.addEventListener('click', (e) => {
  const head = e.target.closest('.call-card > .row:first-child');
  if (!head || e.target.closest('.kebab, button, a, .menu')) return;
  const card = head.closest('.call-card');
  if (card.classList.contains('live') || !+card.dataset.id) return;
  showCall(+card.dataset.id);
});

// Right click on a table row or a widget (calls, the chat's contacts and tasks) = its "⋮" menu, opened at the
// mouse. Text fields, links and selected text keep the browser's own behaviour.
// a right click on a person in a list (Звонки, SMS): the same menu as "⋮" in the person's head, at the mouse
function personContext(el, open) {
  el.oncontextmenu = (e) => {
    if (String(getSelection()).trim()) return;
    e.preventDefault(); e.stopPropagation();
    menuAt = { x: e.clientX, y: e.clientY };
    open(el);
    menuAt = null;
  };
}

document.addEventListener('contextmenu', (e) => {
  // (the player of a call widget is part of the widget: a right click there opens the widget's menu too)
  if (e.target.closest('input, textarea, select, a[href], .menu') || String(getSelection()).trim()) return;
  const row = e.target.closest('tr, .call-card, .asst-obj');
  const k = row && $('.kebab', row);
  if (!k || k.disabled) return;
  e.preventDefault();
  menuAt = { x: e.clientX, y: e.clientY };
  k.click();
  menuAt = null;  // a kebab without a menu must not leave it for the next one
});

// rows: `tr[data-id]` with a KEBAB cell. open(id) is the default action; actions(id) -> menu items
function bindRows(container, { open, actions }) {
  $$('tr[data-id]', container).forEach((tr) => {
    const id = +tr.dataset.id;
    tr.onclick = (e) => { if (!e.target.closest('a,button,.menu')) open(id); };
    const k = $('.kebab', tr);
    if (k) k.onclick = (e) => {
      e.stopPropagation();
      openMenu(k, [{ label: 'Открыть', icon: 'eye', run: () => open(id) }, ...actions(id)]);
    };
  });
}

// first column of every table: the entity name, optional grey second line
const entityCell = (title, sub = '', subTitle = '') => `<div class="cell-title ellipsis">${esc(title)}</div>`
  + (sub ? `<div class="cell-sub ellipsis" title="${esc(subTitle || sub)}">${esc(sub)}</div>` : '');
// "no data" in table cells: a translucent pill instead of a dash
const dash = '<svg class="nodata" width="28" height="8" viewBox="0 0 28 8" role="img" aria-label="нет данных"><rect width="28" height="8" rx="4"/></svg>';
const statusBadge = (s) => { const [c, l] = STATUS[s] || ['', s]; return `<span class="badge ${c}">${esc(l)}</span>`; };

async function loadRefs() {
  const [agents, scripts, contacts, voices] = await Promise.all([api('/agents'), api('/scripts'), api('/contacts'), api('/voices')]);
  Object.assign(state, { agents, scripts, contacts, voices });
}
const agentOptions = (sel, empty = '— по умолчанию —') => `<option value="">${empty}</option>` + state.agents.map((a) => `<option value="${a.id}" ${String(sel) === String(a.id) ? 'selected' : ''}>${esc(a.name)}</option>`).join('');
const scriptOptions = (sel, dir) => '<option value="">— без сценария —</option>' + state.scripts.filter((s) => !dir || s.direction === 'any' || s.direction === dir).map((s) => `<option value="${s.id}" ${String(sel) === String(s.id) ? 'selected' : ''}>${esc(s.name)}</option>`).join('');
const fullName = (c) => [c?.name, c?.last_name].map((x) => (x || '').trim()).filter(Boolean).join(' ');
const findContact = (num) => { const t = (num || '').replace(/\D/g, '').slice(-10); return t.length === 10 ? state.contacts.find((x) => x.phone.replace(/\D/g, '').slice(-10) === t) : null; };
const contactName = (num) => { const t = (num || '').replace(/\D/g, '').slice(-10); const c = t && state.contacts.find((x) => x.phone.replace(/\D/g, '').slice(-10) === t); return c ? fullName(c) : ''; };

// ------------------------------------------------------------------ chart (single series, hover crosshair)
function lineChart(el, points, { unit = '', label = '' } = {}) {
  const pts = points.filter((p) => p.v !== null && p.v !== undefined);
  if (pts.length < 2) { el.innerHTML = `<div class="empty small">Недостаточно данных</div>`; return; }
  const W = el.clientWidth || 400, H = 140, pl = 36, pr = 8, pt = 8, pb = 20;
  let min = Math.min(...pts.map((p) => p.v)), max = Math.max(...pts.map((p) => p.v));
  if (max - min < 4) { min -= 2; max += 2; }
  const t0 = pts[0].t, t1 = pts[pts.length - 1].t || t0 + 1;
  const x = (t) => pl + (W - pl - pr) * (t - t0) / Math.max(1, t1 - t0);
  const y = (v) => pt + (H - pt - pb) * (1 - (v - min) / (max - min));
  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join('');
  const area = `${path}L${x(t1).toFixed(1)},${H - pb}L${x(t0).toFixed(1)},${H - pb}Z`;
  const ticks = [min, (min + max) / 2, max];
  const tm = (t) => new Date(t * 1000).toLocaleTimeString(I18N.locale, { hour: '2-digit', minute: '2-digit' });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(label)}">
    ${ticks.map((v) => `<line class="grid-line" x1="${pl}" x2="${W - pr}" y1="${y(v)}" y2="${y(v)}"/><text class="axis-label" x="${pl - 6}" y="${y(v) + 3}" text-anchor="end">${Math.round(v)}</text>`).join('')}
    <text class="axis-label" x="${pl}" y="${H - 4}">${tm(t0)}</text><text class="axis-label" x="${W - pr}" y="${H - 4}" text-anchor="end">${tm(t1)}</text>
    <path class="area" d="${area}"/><path class="line" d="${path}"/>
    <line class="cross" y1="${pt}" y2="${H - pb}" style="display:none"/><circle class="marker" r="4" style="display:none"/>
    <rect x="${pl}" y="0" width="${W - pl - pr}" height="${H}" fill="transparent" class="hit"/></svg><div class="tip" style="display:none"></div>`;
  const svg = $('svg', el), cross = $('.cross', el), mk = $('.marker', el), tip = $('.tip', el);
  $('.hit', el).addEventListener('mousemove', (e) => {
    const r = svg.getBoundingClientRect();
    const mx = (e.clientX - r.left) * W / r.width;
    let best = pts[0];
    for (const p of pts) if (Math.abs(x(p.t) - mx) < Math.abs(x(best.t) - mx)) best = p;
    const px = x(best.t), py = y(best.v);
    cross.setAttribute('x1', px); cross.setAttribute('x2', px); cross.style.display = '';
    mk.setAttribute('cx', px); mk.setAttribute('cy', py); mk.style.display = '';
    tip.style.display = ''; tip.style.left = (px * r.width / W) + 'px'; tip.style.top = (py * r.height / H) + 'px';
    tip.innerHTML = `<b>${best.v}${unit}</b> <span class="muted">· ${tm(best.t)}</span>`;
  });
  $('.hit', el).addEventListener('mouseleave', () => { cross.style.display = mk.style.display = tip.style.display = 'none'; });
}

// signal quality → status (with label, never color alone)
function quality(kind, v) {
  if (v === null || v === undefined) return ['', '—'];
  const th = { rsrp: [-80, -90, -100], sinr: [20, 13, 0], rsrq: [-10, -15, -20], rssi: [-65, -75, -85] }[kind];
  if (!th) return ['', ''];
  if (v >= th[0]) return ['ok', 'отлично'];
  if (v >= th[1]) return ['ok', 'хорошо'];
  if (v >= th[2]) return ['warn', 'средне'];
  return ['err', 'слабо'];
}

// ------------------------------------------------------------------ views
const VIEWS = {};

VIEWS.dashboard = {
  title: 'Модем', icon: 'signal',
  async render(root) {
    const [m, stats] = await Promise.all([api('/modem'), api('/stats')]);
    state.modem = m; state.stats = stats;
    root.innerHTML = `
      <div class="grid grid-4" id="tiles"></div>
      <div class="grid grid-3 mt">
        <div class="card span-2"><div class="card-head"><h2>Параметры соты</h2><span class="actions">
          <button class="btn btn-ghost btn-sm" id="refresh">${icon('refresh')} Обновить</button></span></div>
          <div class="grid grid-2" id="cell"></div></div>
        <div class="card"><div class="card-head"><h2>Модем и SIM</h2></div><dl class="kv" id="info"></dl></div>
      </div>
      <div class="grid grid-2 mt">
        <div class="card"><div class="card-head"><h2>RSRP, дБм</h2><span class="muted small">мощность сигнала LTE</span></div><div class="chart" id="ch-rsrp"></div></div>
        <div class="card"><div class="card-head"><h2>SINR, дБ</h2><span class="muted small">сигнал / шум</span></div><div class="chart" id="ch-sinr"></div></div>
      </div>
      <div class="grid grid-4 mt" id="stats"></div>`;
    $('#refresh', root).onclick = guard(async () => { state.modem = await api('/modem/refresh', { method: 'POST' }); this.paint(root); toast('Обновлено', 'ok'); });
    this.paint(root);
  },
  paint(root) {
    const m = state.modem || {}, s = m.status || {}, info = m.info || {};
    const pct = s.signal_percent || 0;
    const bars = [20, 40, 60, 80, 100].map((b, i) => `<i class="${pct >= b - 10 && m.connected ? 'on' : ''}" style="height:${6 + i * 4}px"></i>`).join('');
    const reg = s.reg_code === 1 || s.reg_code === 5;
    $('#tiles', root).innerHTML = `
      <div class="card stat"><div class="row"><div class="label">${icon('signal')} Уровень сигнала</div><span class="spacer"></span><span class="bars">${bars}</span></div>
        <div class="value">${m.connected ? pct + '%' : '—'}</div><div class="sub">RSSI ${fmtNum(s.rssi_dbm, ' дБм')} · CSQ ${fmtNum(s.csq)}</div></div>
      <div class="card stat"><div class="label">${icon('tower')} Оператор</div>
        <div class="value ellipsis">${esc(s.operator || '—')}</div><div class="sub">${esc(s.network_type || s.access_tech || '—')} ${s.band ? '· ' + esc(s.band) : ''}</div></div>
      <div class="card stat"><div class="label">${icon('sim')} Регистрация</div>
        <div class="value" style="font-size:20px"><span class="badge ${!m.connected ? 'err' : reg ? 'ok' : 'warn'}">${!m.connected ? icon('alert') + ' Нет связи с модемом' : (reg ? icon('check') + ' ' : '') + esc(s.registration || '—')}</span></div>
        <div class="sub">${esc(m.error || (s.mcc_mnc ? 'MCC-MNC ' + s.mcc_mnc : ''))}</div></div>
      <div class="card stat"><div class="label">${icon('thermo')} Модуль</div>
        <div class="value">${fmtNum(s.temperature, '°C')}</div><div class="sub">Питание ${fmtNum(s.voltage, ' В')} ${m.mock ? '· <span class="badge warn">эмуляция</span>' : ''}</div></div>`;
    const q = (k, v, unit) => { const [c, l] = quality(k, v); return `<div class="stat"><div class="label">${k.toUpperCase()}</div><div class="row wrap" style="margin-top:4px"><span class="value" style="margin:0;font-size:20px">${fmtNum(v, unit)}</span>${l ? `<span class="badge ${c}">${l}</span>` : ''}</div></div>`; };
    $('#cell', root).innerHTML = `
      <div class="grid grid-2">${q('rsrp', s.rsrp, ' дБм')}${q('rsrq', s.rsrq, ' дБ')}${q('sinr', s.sinr, ' дБ')}${q('rssi', s.rssi, ' дБм')}</div>
      <dl class="kv">
        <dt>Режим</dt><dd>${esc(s.system_mode || '—')} ${esc(s.operation_mode || '')}</dd>
        <dt>Диапазон</dt><dd>${esc(s.band || '—')}</dd>
        <dt>EARFCN / BW</dt><dd>${esc(s.earfcn || s.uarfcn || '—')}${s.dl_bw ? ` · ${esc(s.dl_bw)}/${esc(s.ul_bw)}` : ''}</dd>
        <dt>Cell ID / PCI</dt><dd>${esc(s.cell_id || '—')}${s.pci ? ' / ' + esc(s.pci) : ''}</dd>
        <dt>TAC / LAC</dt><dd>${esc(s.tac || s.lac || '—')}</dd>
        <dt>MCC-MNC</dt><dd>${esc(s.mcc_mnc || '—')}</dd>
        <dt>Обновлено</dt><dd>${s.updated_at ? fmtDate(s.updated_at) : '—'}</dd>
      </dl>`;
    $('#info', root).innerHTML = [
      ['Модель', info.model], ['Производитель', info.manufacturer], ['Прошивка', info.firmware], ['IMEI', info.imei],
      ['IMSI', info.imsi], ['ICCID', info.iccid], ['Номер', info.own_number], ['SIM', info.sim], ['Режим сети', info.network_mode_name],
    ].map(([k, v]) => `<dt>${k}</dt><dd class="mono">${esc(v || '—')}</dd>`).join('');
    kvTitles(root);
    const hist = m.history || [];
    lineChart($('#ch-rsrp', root), hist.map((h) => ({ t: h.t, v: h.rsrp ?? h.rssi })), { unit: ' дБм', label: 'RSRP' });
    lineChart($('#ch-sinr', root), hist.map((h) => ({ t: h.t, v: h.sinr })), { unit: ' дБ', label: 'SINR' });
    const st = state.stats || {};
    const tile = (ic, label, value, sub = '') => `<div class="card stat"><div class="row"><div class="stat-icon">${icon(ic)}</div><div><div class="label">${label}</div><div class="value" style="font-size:22px;margin-top:0">${value}</div></div></div>${sub ? `<div class="sub">${sub}</div>` : ''}</div>`;
    $('#stats', root).innerHTML =
      tile('phone', 'Звонков сегодня', st.calls_today ?? 0, `всего ${st.calls_total ?? 0} · пропущено ${st.calls_missed ?? 0}`) +
      tile('clock', 'Время разговоров', fmtDur(st.talk_seconds), `в очереди ${st.calls_queued ?? 0}`) +
      tile('message', 'SMS', st.sms_total ?? 0, `непрочитанных ${st.sms_unread ?? 0}`) +
      tile('bot', 'Агенты / сценарии', `${st.agents ?? 0} / ${st.scripts ?? 0}`, `контактов ${st.contacts ?? 0}`);
  },
  onEvent(ev, root) {
    if (ev.event === 'modem.status') {
      const m = state.modem || (state.modem = {});
      Object.assign(m, { connected: ev.data.connected, error: ev.data.error, status: ev.data.status });
      if (ev.data.point) {
        m.history = m.history || [];
        const last = m.history[m.history.length - 1];
        if (!last || last.t !== ev.data.point.t) m.history.push(ev.data.point);
        if (m.history.length > 180) m.history.shift();
      }
      this.paint(root);
    }
  },
};

// ------------------------------------------------------------------ system (Raspberry Pi)
const plural = (n, one, few, many) => { const a = Math.abs(n) % 100, b = a % 10; return a > 10 && a < 20 ? many : b === 1 ? one : b >= 2 && b <= 4 ? few : many; };
const fmtBytes = (b, unit = 'auto') => {
  if (b == null) return '—';
  const gb = b / 1024 ** 3;
  return unit === 'MB' || (unit === 'auto' && gb < 2) ? `${Math.round(b / 1024 ** 2)} МБ` : `${gb.toFixed(1)} ГБ`;
};
const fmtUptime = (sec) => {
  if (sec == null) return '—';
  const d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60);
  return d ? `${d} дн ${h} ч` : h ? `${h} ч ${m} мин` : `${m} мин`;
};
const GOVERNOR_LABEL = {
  ondemand: 'по нагрузке (ondemand)', schedutil: 'по планировщику (schedutil)', conservative: 'плавно по нагрузке (conservative)',
  performance: 'максимальная частота (performance)', powersave: 'минимальная частота (powersave)', userspace: 'вручную (userspace)',
};
VIEWS.system = {
  title: 'Система', icon: 'server',
  hint: 'Состояние Raspberry Pi, на котором работает Caller: процессор, температура, память, диск, сеть. Обновляется каждые 10 секунд.',
  async render(root) {
    root.innerHTML = `
      <div class="grid grid-4" id="sys-tiles"></div>
      <div class="grid grid-3 mt">
        <div class="card span-2"><div class="card-head"><h2>Raspberry Pi</h2><span class="actions">
          <button class="btn btn-ghost btn-sm" id="sys-refresh">${icon('refresh')} Обновить</button></span></div>
          <div class="grid grid-2"><dl class="kv" id="sys-host"></dl><dl class="kv" id="sys-power"></dl></div></div>
        <div class="card"><div class="card-head"><h2>Сеть и сервис</h2></div><dl class="kv" id="sys-net"></dl></div>
      </div>
      <div class="grid grid-3 mt">
        <div class="card"><div class="card-head"><h2>Процессор, %</h2><span class="muted small">за последний час</span></div><div class="chart" id="ch-cpu"></div></div>
        <div class="card"><div class="card-head"><h2>Температура, °C</h2><span class="muted small">за последний час</span></div><div class="chart" id="ch-temp"></div></div>
        <div class="card"><div class="card-head"><h2>Память, %</h2><span class="muted small">за последний час</span></div><div class="chart" id="ch-mem"></div></div>
      </div>`;
    $('#sys-refresh', root).onclick = guard(async () => { await this.load(root); toast('Обновлено', 'ok'); });
    await this.load(root);
    clearInterval(this.timer);
    this.timer = setInterval(() => {
      if (state.view !== this || !root.isConnected) { clearInterval(this.timer); return; }
      this.load(root).catch(() => {});
    }, 10000);
  },
  async load(root) {
    const s = await api('/system');
    const pctOf = (a, b) => (a != null && b ? Math.round(100 * a / b) : null);
    const cpu = s.cpu || {}, mem = s.memory || {}, disk = s.disk || {}, th = s.throttled, w = s.network?.wifi || {};
    const t = s.temperature;
    const tempBadge = t == null ? '' : t >= 80 ? '<span class="badge err">горячо</span>' : t >= 70 ? '<span class="badge warn">тепло</span>' : '<span class="badge ok">норма</span>';
    const memPct = pctOf(mem.used, mem.total), diskPct = pctOf(disk.used, disk.total);
    const bar = (p) => p == null ? '' : `<div class="meter"><div style="width:${Math.min(100, p)}%" class="${p >= 90 ? 'err' : p >= 75 ? 'warn' : ''}"></div></div>`;
    $('#sys-tiles', root).innerHTML = `
      <div class="card stat"><div class="label">${icon('cpu')} Процессор</div>
        <div class="value">${cpu.percent != null ? cpu.percent + '%' : '—'}</div>${bar(cpu.percent)}
        <div class="sub">${cpu.cores ?? '—'} ${plural(cpu.cores, 'ядро', 'ядра', 'ядер')} · ${cpu.freq_mhz ? cpu.freq_mhz + ' МГц' : '—'}${cpu.load ? ' · нагрузка ' + cpu.load.join(' ') : ''}</div></div>
      <div class="card stat"><div class="row"><div class="label">${icon('thermo')} Температура</div><span class="spacer"></span>${tempBadge}</div>
        <div class="value">${t != null ? t + '°C' : '—'}</div>
        <div class="sub">${th?.throttled ? '<span class="badge err">частота снижена</span>' : 'троттлинга нет'} · ${esc(cpu.governor?.current || '—')}</div></div>
      <div class="card stat"><div class="label">${icon('memory')} Память</div>
        <div class="value">${memPct != null ? memPct + '%' : '—'}</div>${bar(memPct)}
        <div class="sub">${fmtBytes(mem.used, 'MB')} из ${fmtBytes(mem.total, 'MB')}${mem.swap_total ? ` · подкачка ${fmtBytes(mem.swap_used, 'MB')}` : ''}</div></div>
      <div class="card stat"><div class="label">${icon('disk')} Диск</div>
        <div class="value">${diskPct != null ? diskPct + '%' : '—'}</div>${bar(diskPct)}
        <div class="sub">${fmtBytes(disk.used)} из ${fmtBytes(disk.total)} · свободно ${fmtBytes(disk.free)}</div></div>`;
    const kv = (rows) => rows.map(([k, v]) => `<dt>${k}</dt><dd>${v ?? '—'}</dd>`).join('');
    const powerState = !th ? '—' : th.under_voltage ? '<span class="badge err">низкое напряжение сейчас</span>'
      : th.under_voltage_occurred ? '<span class="badge warn">было низкое напряжение</span>' : '<span class="badge ok">в норме</span>';
    const throttleState = !th ? '—' : th.throttled ? '<span class="badge err">снижена сейчас</span>'
      : th.throttled_occurred || th.freq_capped_occurred ? '<span class="badge warn">снижалась</span>' : '<span class="badge ok">не снижалась</span>';
    $('#sys-host', root).innerHTML = kv([
      ['Модель', esc(s.model)], ['ОС', esc(s.os)], ['Ядро', `<span class="mono">${esc(s.kernel)}</span>`],
      ['Имя хоста', `<span class="mono">${esc(s.hostname)}</span>`], ['Работает', fmtUptime(s.uptime)],
    ]);
    $('#sys-power', root).innerHTML = kv([
      ['Питание', powerState], ['Частота процессора', throttleState], ['Режим процессора', esc(GOVERNOR_LABEL[cpu.governor?.current] || cpu.governor?.current || '—')],
      ['Нагрузка (1/5/15 мин)', cpu.load ? `<span class="mono">${cpu.load.join(' · ')}</span>` : '—'], ['Данные', `<span class="mono">${esc(disk.path)}</span>`],
    ]);
    const ps = w.power_save;
    $('#sys-net', root).innerHTML = kv([
      ['IP-адрес', `<span class="mono">${esc(s.network?.ip || '—')}</span>`], ['Wi-Fi', esc(w.ssid || '—')],
      ['Сигнал', w.signal_dbm != null ? `${w.signal_dbm} дБм` : '—'], ['Скорость', esc(w.bitrate || '—')],
      ['Энергосбережение Wi-Fi', ps == null ? '—' : `<a href="#/settings?tab=power">${ps ? '<span class="badge warn">включено</span>' : '<span class="badge ok">выключено</span>'}</a>`],
      ['Процесс Caller', `PID ${s.process?.pid ?? '—'} · ${fmtBytes(s.process?.rss, 'MB')}`], ['Caller работает', fmtUptime(s.process?.uptime)],
      ['Python', esc(s.process?.python || '—')],
    ]);
    kvTitles(root);
    const h = s.history || [];
    lineChart($('#ch-cpu', root), h.map((p) => ({ t: p.t, v: p.cpu })), { unit: '%', label: 'CPU' });
    lineChart($('#ch-temp', root), h.map((p) => ({ t: p.t, v: p.temp })), { unit: '°C', label: 'Температура' });
    lineChart($('#ch-mem', root), h.map((p) => ({ t: p.t, v: p.mem })), { unit: '%', label: 'Память' });
  },
};

// ------------------------------------------------------------------ providers: the connection to Yandex and Kitta
const COUNTRY = { RU: 'Россия', ES: 'Испания', FI: 'Финляндия', SE: 'Швеция', NL: 'Нидерланды', DE: 'Германия', FR: 'Франция',
  GB: 'Великобритания', US: 'США', KZ: 'Казахстан', TR: 'Турция', AE: 'ОАЭ', LV: 'Латвия', EE: 'Эстония', LT: 'Литва', PL: 'Польша' };
VIEWS.providers = {
  title: 'Провайдеры', icon: 'tower',
  hint: 'Связь Raspberry Pi с Yandex AI Studio и Kitta (Fish Audio): пинг, время соединения, через какой выход в интернет идёт трафик. Проверка идёт раз в минуту и ничего не стоит; тест потока Kitta — только по кнопке.',
  async render(root) {
    setActions(`<button class="btn" id="net-check">${icon('refresh')} Проверить сейчас</button>`);
    root.innerHTML = `<h2 class="section-title" style="margin-top:0">Ресурсы</h2>
      <div id="res-yandex"></div><div id="res-kitta" class="mt"></div>
      <h2 class="section-title">Связь</h2>
      <div class="grid grid-3" id="net-cards"></div>
      <div class="grid grid-2 mt">
        <div class="card"><div class="card-head"><h2>Yandex Realtime — начало сессии</h2></div>
          <p class="muted small" style="margin-top:0">Сколько занимает подключение к Realtime API до готовой сессии — так начинается каждый звонок. Токены не тратятся.</p>
          <div id="ya-hs" class="muted small">Нажмите «Проверить сейчас».</div></div>
        <div class="card"><div class="card-head"><h2>Kitta — тест потока</h2><span class="actions">
          <button class="btn btn-sm" id="kitta-test">${icon('play')} Запустить</button></span></div>
          <p class="muted small" style="margin-top:0">Две короткие фразы через realtime-соединение: когда приходит первый звук и во сколько раз быстрее реального времени идёт поток. Меньше ×1 — голос в звонке заикается. Тратит пару кредитов и на несколько секунд занимает единственное соединение Kitta, поэтому во время звонка не запускается.</p>
          <div id="kitta-res"></div></div></div>`;
    $('#net-check').onclick = guard(async () => {
      const b = $('#net-check'); b.disabled = true;
      try {
        const r = await api('/providers/network/check', { method: 'POST' });
        this.draw(root, r);
        const h = r.yandex_handshake;
        $('#ya-hs', root).innerHTML = h.ok
          ? `<dl class="kv"><dt>WebSocket открыт</dt><dd>${h.connect_ms} мс</dd><dt>Сессия готова</dt><dd>${h.session_ms} мс</dd></dl>`
          : `<span class="badge err">ошибка</span> <span class="small">${esc(h.error)}</span>`;
        toast('Проверено', 'ok');
      } finally { b.disabled = false; }
    });
    $('#kitta-test', root).onclick = guard(async () => {
      const b = $('#kitta-test', root), label = b.innerHTML;
      b.disabled = true; b.innerHTML = '<span class="spin"></span>';
      $('#kitta-res', root).innerHTML = '<span class="muted small">Синтезируем…</span>';
      try {
        const r = await api('/providers/kitta/stream-test', { method: 'POST' });
        const sp = (x) => `<span class="${x >= 2 ? 'st-ok' : x >= 1 ? 'st-warn' : 'st-err'}">×${x}</span>`;
        $('#kitta-res', root).innerHTML = (r.error ? `<p><span class="badge err">ошибка</span> ${esc(r.error)}</p>` : '')
          + (r.ready_ms != null ? `<dl class="kv"><dt>Голос</dt><dd>${esc(r.voice)}</dd><dt>Соединение готово</dt><dd>${r.ready_ms} мс</dd></dl>` : '')
          + (r.phrases || []).map((p) => `<div class="call-card" style="margin-top:8px"><div class="small muted">${esc(p.text)}</div>
              ${p.error ? `<div class="st-err small">${esc(p.error)}</div>` : `<div class="row small"><span>первый звук ${p.first_ms} мс</span><span class="faint">·</span>
              <span>${p.audio_s} с речи пришли за ${p.stream_s} с</span><span class="spacer"></span><b>${sp(p.speed)}</b></div>`}</div>`).join('');
      } catch (e) {
        $('#kitta-res', root).innerHTML = '';
        throw e;
      } finally { b.disabled = false; b.innerHTML = label; }
    });
    providerUsage($('#res-yandex', root), 'yandex', 'Yandex AI Studio — токены');
    providerUsage($('#res-kitta', root), 'fish', 'Kitta · Fish Audio — кредиты');
    await this.load(root);
    clearInterval(this.timer);
    this.timer = setInterval(() => {
      if (state.view !== this || !root.isConnected) { clearInterval(this.timer); return; }
      this.load(root).catch(() => {});
    }, 30000);
  },
  async load(root) { this.draw(root, await api('/providers/network')); },
  draw(root, data) {
    const ms = (v) => (v == null ? '—' : `${Math.round(v)} мс`);
    const lvl = (v, good, bad) => (v == null ? '' : v <= good ? 'st-ok' : v <= bad ? 'st-warn' : 'st-err');
    $('#net-cards', root).innerHTML = data.targets.map((t) => {
      const r = t.last;
      const state_ = !r ? '<span class="badge">ещё не проверено</span>'
        : r.ok ? '<span class="badge ok">связь есть</span>' : '<span class="badge err">нет связи</span>';
      const exit = r?.exit ? `${esc(r.exit.ip)} · ${esc(COUNTRY[r.exit.loc] || r.exit.loc || '—')}${r.exit.colo ? ` · узел Cloudflare ${esc(r.exit.colo)}` : ''}` : null;
      const tile = (label, v, cls, sub = '') => `<div class="net-tile"><div class="label">${label}</div><div class="v ${cls}">${v}</div>${sub ? `<div class="sub">${sub}</div>` : ''}</div>`;
      return `<div class="card net-card">
        <div class="card-head"><div style="min-width:0"><h2 class="ellipsis">${esc(t.provider)}</h2><div class="small muted ellipsis">${esc(t.name)}</div></div><span class="spacer"></span>${state_}</div>
        ${r && !r.ok ? `<p class="small st-err" style="margin:0 0 10px">${esc(r.error)}</p>` : ''}
        <div class="net-tiles">
          ${tile('Пинг', ms(r?.ping_ms), lvl(r?.ping_ms, 60, 150), r?.loss_pct != null ? `потери ${r.loss_pct}%` + (r.ping_max_ms ? ` · макс ${Math.round(r.ping_max_ms)}` : '') : '')}
          ${tile('TCP', ms(r?.tcp_ms), lvl(r?.tcp_ms, 80, 200))}
          ${tile('TLS', ms(r?.tls_ms), lvl(r?.tls_ms, 150, 400))}
          ${tile('Ответ', ms(r?.http_ms), lvl(r?.http_ms, 300, 800), r?.http_status ? `HTTP ${r.http_status}` : '')}
        </div>
        <dl class="kv">
          <dt>Адрес</dt><dd class="mono small">${esc(t.host)}</dd>
          <dt>DNS</dt><dd class="small">${r?.ips ? `<span class="mono">${esc(r.ips.join(', '))}</span> · ${ms(r.dns_ms)}` : '—'}</dd>
          ${t.trace ? `<dt>Выход в интернет</dt><dd class="small">${exit || '—'}</dd>` : ''}
          <dt>За сутки</dt><dd class="small">${t.day.probes ? `${t.day.probes} ${plural(t.day.probes, 'проверка', 'проверки', 'проверок')}${t.day.failed ? ` · <span class="st-err">без связи ${t.day.failed}</span>` : ' · без сбоев'}` : '—'}</dd>
        </dl>
        <div class="small muted mt">Пинг за последний час, мс</div><div class="chart" data-chart="${t.id}"></div></div>`;
    }).join('');
    kvTitles(root);
    for (const t of data.targets) {
      lineChart($(`[data-chart="${t.id}"]`, root), t.history.map((p) => ({ t: p.t, v: p.ping_ms ?? p.tcp_ms })), { unit: ' мс', label: 'Пинг' });
    }
  },
};

// ------------------------------------------------------------------ calls
// ------------------------------------------------------------------ tag folders (Звонки, SMS, Контакты)
// A narrow rail of phone book tags that works like Telegram folders: «Все» first, then every tag. The folder
// is shared by the three sections and remembered. A number belongs to a tag through its phone book contact.
const contactTags = (c) => (c?.tags || '').split(',').map((t) => t.trim()).filter(Boolean);
const allTags = () => [...new Set(state.contacts.flatMap(contactTags))].sort((a, b) => a.localeCompare(b, I18N.locale));
// system folders exist only where they make sense (calls: '@missed', '@spam'); elsewhere they read as «Все»
const currentTag = (system = []) => { const t = localStorage.getItem('caller.tag') || ''; return allTags().includes(t) || system.some((x) => x.t === t) ? t : ''; };
const numberInTag = (num, tag) => !tag || contactTags(findContact(num)).includes(tag);
// counts: {'' | tag: n} — unseen calls / unread messages of the numbers in each folder;
// system: [{t, label, icon}] — folders of the section itself, after «Все» and before the tags
function tagRail(el, onChange, counts = {}, system = []) {
  const cur = currentTag(system);
  const item = (t, label, ic) => `<button type="button" class="tag-folder ${t === cur ? 'active' : ''}" data-t="${esc(t)}" title="${esc(label)}">
    <span class="ic">${icon(ic)}${counts[t] ? `<span class="count">${counts[t] > 99 ? '99+' : counts[t]}</span>` : ''}</span><span class="ellipsis">${esc(label)}</span></button>`;
  const tags = allTags();
  el.innerHTML = item('', 'Все', 'layers') + system.map((x) => item(x.t, x.label, x.icon)).join('')
    + (tags.length && system.length ? '<div class="tag-sep"></div>' : '') + tags.map((t) => item(t, t, 'tag')).join('');
  $$('.tag-folder', el).forEach((b) => b.onclick = () => {
    localStorage.setItem('caller.tag', b.dataset.t);
    $$('.tag-folder', el).forEach((x) => x.classList.toggle('active', x === b));
    onChange(b.dataset.t);
  });
}
const threadKey = (num) => (num ? num.replace(/\D/g, '').slice(-10) : 'hidden');
// the search field above the people list: by name or by digits of the number
const peopleSearch = (placeholder) => `<div class="people-search"><input type="search" id="people-q" placeholder="${esc(placeholder)}" autocomplete="off"></div>`;
function matchesPerson(q, name, number) {
  q = (q || '').trim().toLowerCase();
  if (!q) return true;
  const d = q.replace(/\D/g, ''), nd = (number || '').replace(/\D/g, '');
  return (name || '').toLowerCase().includes(q) || (d.length >= 2 && (nd.includes(d) || (d[0] === '8' && nd.includes('7' + d.slice(1)))));
}
const CALL_FOLDERS = [{ t: '@missed', label: 'Пропущенные', icon: 'phoneOff' }, { t: '@spam', label: 'Спам', icon: 'alert' }];
// per-folder sums of something per number (unseen calls, unread SMS)
function tagCounts(items, n) {
  const out = { '': 0 };
  for (const it of items) {
    const k = n(it);
    if (!k) continue;
    out[''] += k;
    for (const t of contactTags(findContact(it.number))) out[t] = (out[t] || 0) + k;
  }
  return out;
}

// Under a call widget: only the gist (without the «Суть:» label) and the agreements if there are any.
// The summary is «Суть: … / Договорённости: … / Следующий шаг: … / Настроение: …»; one-line summaries go as is.
function callGistParts(c) {
  const text = (c.ai_summary || '').trim();
  let gist = '', agreed = '';
  if (text) {
    const fields = {};
    for (const line of text.split('\n')) {
      const m = line.match(/^\s*([А-ЯЁа-яё ]+):\s*(.*)$/);
      if (m) fields[m[1].trim().toLowerCase()] = m[2].trim();
    }
    gist = fields['суть'] ?? (Object.keys(fields).length ? '' : text);
    const a = fields['договорённости'] ?? fields['договоренности'] ?? '';
    agreed = /^(нет|нету|—|-)?\.?$/i.test(a) ? '' : a;
  } else if (c.summary) {
    gist = c.summary;  // what the agent saved (save_result) when there's no AI summary
  }
  gist = gist && gist.charAt(0).toUpperCase() + gist.slice(1);
  agreed = agreed && agreed.charAt(0).toLowerCase() + agreed.slice(1);  // it follows «Договорились:»
  return { gist, agreed };
}
function callGist(c) {
  const { gist, agreed } = callGistParts(c);
  if (!gist && !agreed) return '';
  return `<div class="call-summary">${gist ? `<div>${esc(gist)}</div>` : ''}${agreed ? `<div class="agreed"><span>Договорились:</span> ${esc(agreed)}</div>` : ''}</div>`;
}

// ------------------------------------------------------------------ calls: people on the left, a feed of calls on the right
VIEWS.calls = {
  title: 'Звонки', icon: 'phone',
  hint: 'Звонки сгруппированы по абонентам. Исходящий звонок можно отдать голосовому агенту или провести самому через браузер. Входящие принимает агент по сценарию.',
  current: null,  // threadKey of the selected person
  async render(root, params) {
    await loadRefs();
    setActions(`<button class="btn" id="new-call-browser" title="Вы говорите сами через микрофон и динамики">${icon('phoneOut')} Позвонить</button>
      <button class="btn btn-primary" id="new-call-agent">${icon('bot')} Звонок агентом</button>`);
    root.innerHTML = `<div class="hub-layout">
      <div class="card hub-side"><nav class="tag-rail" id="tags" aria-label="Теги"></nav>
        <div class="hub-people">${peopleSearch('Поиск')}<div class="hub-list" id="threads"></div></div></div>
      <div class="card hub-main" id="feed"></div></div>`;
    let timer;
    $('#people-q', root).oninput = () => { clearTimeout(timer); timer = setTimeout(() => this.renderPeople(root), 150); };
    const openDial = (p = {}) => openDialModal(p, () => this.loadThreads(root));
    this.openDial = openDial;
    $('#new-call-agent').onclick = () => openDial({ mode: 'agent' });
    $('#new-call-browser').onclick = () => openDial({ mode: 'browser' });
    if (params.get('number') || params.get('script')) {
      // opened from the phone book / SMS / scripts: show the form once, then drop the params
      history.replaceState(null, '', '#/calls');
      openDial({ mode: params.get('mode') === 'browser' ? 'browser' : 'agent', number: params.get('number'),
                 script: params.get('script'), agent: params.get('agent') });
    }
    if (params.get('person')) {  // a link to a person's calls (the assistant)
      localStorage.setItem('caller.tag', '');
      this.current = threadKey(params.get('person'));
    } else if (state.active) this.current = threadKey(state.active.number);
    this.liveId = state.active?.id || null;
    await this.loadThreads(root);
  },
  async loadThreads(root) {
    this.threads = await api('/calls/threads');
    this.renderPeople(root);
    await this.loadFeed(root);
    // the opened person's new calls are now seen
    const t = this.thread();
    if (t?.unseen) { await markCallsSeen(t.number || 'hidden'); this.loadThreads(root); }
  },
  // folders: «Все» and tags hide spam; «Пропущенные» — the last call is a missed incoming one; «Спам» — marked numbers
  inFolder(t, tag) {
    if (tag === '@spam') return t.spam;
    if (t.spam) return false;
    if (tag === '@missed') return t.last.direction === 'in' && t.last.status === 'missed';
    return numberInTag(t.number, tag);
  },
  renderPeople(root) {
    const all = this.threads || [];
    const counts = tagCounts(all.filter((t) => !t.spam), (t) => t.unseen);
    counts['@missed'] = all.filter((t) => this.inFolder(t, '@missed')).reduce((n, t) => n + t.unseen, 0);
    tagRail($('#tags', root), () => this.renderPeople(root), counts, CALL_FOLDERS);
    const tag = currentTag(CALL_FOLDERS);
    const q = $('#people-q', root)?.value || '';
    const list = all.filter((t) => this.inFolder(t, tag) && matchesPerson(q, t.contact_name, t.number));
    $('#threads', root).innerHTML = list.map((t) => {
      const c = t.last;
      const name = t.contact_name || t.number || 'Скрытый номер';
      return `<div class="hub-item ${threadKey(t.number) === this.current ? 'active' : ''}" data-k="${esc(threadKey(t.number))}">
        <div class="avatar"${t.number ? avatarStyle(t.contact_name || '#') : ''}>${t.number ? esc(initials(t.contact_name || '#')) : icon('phone')}</div>
        <div class="body"><div class="row"><span class="person-name ellipsis">${esc(name)}</span><span class="spacer"></span><span class="small faint nowrap">${fmtDate(c.started_at || c.created_at)}</span></div>
          <div class="row small muted"><span class="call-dir" title="${c.direction === 'in' ? 'Входящий' : 'Исходящий'}">${icon(c.direction === 'in' ? 'phoneIn' : 'phoneOut')}</span>
            ${((g) => g ? `<span class="ellipsis" title="${esc(g)}">${esc(g)}</span>` : `<span class="nowrap faint">${c.direction === 'in' ? 'Входящий' : 'Исходящий'}</span>`)(callGistParts(c).gist)}
            <span class="spacer"></span>${t.unseen && !t.spam ? `<span class="badge primary" title="Новые звонки">${t.unseen}</span>` : ''}</div></div></div>`;
    }).join('') || `<div class="empty small">${icon('phone')}<div>${q ? 'Никого не нашлось' : tag ? 'В этой папке звонков нет' : 'Звонков пока нет'}</div></div>`;
    $$('.hub-item', root).forEach((el) => el.onclick = () => {
      this.current = el.dataset.k;
      $$('.hub-item', root).forEach((x) => x.classList.toggle('active', x === el));
      if (this.thread()?.unseen) this.loadThreads(root); else this.loadFeed(root);  // loadThreads marks them seen
    });
    $$('.hub-item', root).forEach((el) => {
      const t = list.find((x) => threadKey(x.number) === el.dataset.k);
      if (t?.number) personContext(el, (a) => personMenu(a, t.number, { spam: t.spam, changed: () => this.loadThreads(root) }));
    });
  },
  thread() { return (this.threads || []).find((t) => threadKey(t.number) === this.current); },
  async loadFeed(root, older = false) {
    const feed = $('#feed', root);
    const t = this.thread();
    if (!t) { feed.innerHTML = `<div class="empty" style="margin:auto">${icon('phone')}<div>Выберите абонента</div></div>`; return; }
    if (!older) { this.items = []; this.total = 0; }
    const data = await api(`/calls?thread=${encodeURIComponent(t.number || 'hidden')}&limit=20&offset=${this.items.length}`);
    if (this.thread() !== t) return;  // another person was picked meanwhile
    this.items = [...data.items.slice().reverse(), ...this.items];  // oldest at the top, the newest at the bottom
    this.total = data.total;
    const name = t.contact_name || t.number || 'Скрытый номер';
    const c = findContact(t.number);
    const list = $('.call-feed', feed);
    const keep = older && list ? list.scrollHeight - list.scrollTop : null;
    feed.innerHTML = `<div class="head"><div class="avatar"${t.number ? avatarStyle(t.contact_name || '#') : ''}>${t.number ? esc(initials(t.contact_name || '#')) : icon('phone')}</div>
        <div style="min-width:0"><div class="person-name ellipsis">${esc(name)}</div><div class="small muted mono">${esc([t.number, c?.company].filter(Boolean).join(' · ') || 'номер не определён')}</div></div>
        <span class="spacer"></span>
        ${t.number ? `<span class="head-kebab">${KEBAB}</span>` : ''}</div>
      <div class="call-feed">${this.items.length < this.total ? `<div class="row" style="justify-content:center"><button class="btn btn-sm" data-older>Показать ранние (${this.total - this.items.length})</button></div>` : ''}
        ${this.items.map((x) => this.card(x)).join('')}</div>`;
    const feedEl = $('.call-feed', feed);
    feedEl.scrollTop = keep != null ? feedEl.scrollHeight - keep : feedEl.scrollHeight;
    // the person's actions: behind "⋮" in the head
    const hk = $('.head-kebab .kebab', feed);
    if (hk) hk.onclick = (e) => { e.stopPropagation(); personMenu(hk, t.number, { spam: t.spam, changed: () => this.loadThreads(root) }); };
    const more = $('[data-older]', feed); if (more) more.onclick = () => this.loadFeed(root, true);
    $$('.call-card', feed).forEach((el) => {
      const id = +el.dataset.id;
      const k = $('.kebab', el);
      const c = this.items.find((x) => x.id === id);
      if (k) k.onclick = (e) => { e.stopPropagation(); openMenu(k, callMenuItems(c || { id }, () => this.loadThreads(root))); };
    });
    if (state.active && this.items.some((x) => x.id === state.active.id)) await this.renderLive(root);
  },
  // a call in the feed: when, how it went, the recording and the summary
  // a call: the widget (who / when / status / player) and right under it, as one block, the gist of the summary
  card(c) {
    const live = state.active && state.active.id === c.id;
    return `<div class="call-item">
      <div class="call-card ${live ? 'live' : ''}" data-id="${c.id}">
      <div class="row"><span class="call-dir" title="${c.direction === 'in' ? 'Входящий' : 'Исходящий'}">${icon(c.direction === 'in' ? 'phoneIn' : 'phoneOut')}</span>
        ${((who) => `<span class="ellipsis" title="${esc(who)}">${esc(who)}</span>`)([c.agent_name ? `Агент ${c.agent_name}` : c.mode === 'browser' ? 'Через браузер' : 'Без агента', c.script_name].filter(Boolean).join(' · '))}
        <span class="small faint nowrap">${fmtDate(c.started_at || c.created_at)}</span>
        ${statusBadge(c.status)}${c.forgotten ? `<span class="badge forgot" title="Не в истории агента: агенты не учитывают этот звонок" aria-label="Не в истории агента">${icon('eyeOff')}</span>` : ''}<span class="spacer"></span>
        ${live ? '<span class="mono" data-timer></span>' : c.duration && !c.recording ? `<span class="small muted mono">${fmtDur(c.duration)}</span>` : ''}${KEBAB}</div>
      ${live ? '<div class="live-slot"></div>' : c.recording ? wavePlayer(`/api/calls/${c.id}/recording`, `/api/calls/${c.id}/waveform`, { labels: ['собеседник', c.mode === 'browser' ? 'вы' : 'агент'] }) : ''}</div>
      ${live ? '' : callGist(c)}</div>`;
  },
  // the call in progress: its card in the feed shows the live transcript and DTMF
  async renderLive(root) {
    const a = state.active;
    const slot = a && $(`.call-card[data-id="${a.id}"] .live-slot`, root);
    if (!slot) return;
    const detail = await api('/calls/' + a.id);
    this.who = callSpeakers(detail);
    const agentBadge = a.browser ? 'через браузер' : !a.agent_id ? 'без агента' : a.agent_active ? 'агент на линии' : 'агент не подключён';
    slot.innerHTML = `<div class="row small">${statusBadge(a.state)} <span class="badge ${a.agent_active ? 'ok' : ''}">${icon('bot')} ${agentBadge}</span></div>
      <div class="transcript" id="live-transcript">${detail.messages.map((m) => msgHtml(m, this.who)).join('') || '<div class="muted small">Транскрипт появится здесь…</div>'}</div>
      <div class="row"><input id="dtmf" placeholder="DTMF: 1, *, #" style="max-width:160px"><button class="btn" id="dtmf-send">Отправить DTMF</button></div>`;
    $('#dtmf-send', root).onclick = guard(async () => { await api('/calls/active/dtmf', { method: 'POST', body: { digits: $('#dtmf', root).value } }); $('#dtmf', root).value = ''; });
    const tr = $('#live-transcript', root); tr.scrollTop = tr.scrollHeight;
    const feedEl = $('.call-feed', root); if (feedEl) feedEl.scrollTop = feedEl.scrollHeight;
  },
  onEvent(ev, root) {
    if (ev.event === 'call.state') {
      const a = state.active;
      if (a && a.id !== this.liveId) this.current = threadKey(a.number);  // a new call: show its person
      this.liveId = a?.id || null;
      this.loadThreads(root);
    }
    if (ev.event === 'call.ended' || ev.event === 'call.updated' || ev.event === 'call.summary') this.loadThreads(root);
    if (ev.event === 'call.message' && state.active && ev.data.call_id === state.active.id) {
      const t = $('#live-transcript', root);
      const html = msgHtml(ev.data, this.who || {});
      if (t && html) { if (!$('.msg', t)) t.innerHTML = ''; t.insertAdjacentHTML('beforeend', html); t.scrollTop = t.scrollHeight; }
    }
  },
};

// transcript of a call: the other person by name (or number), the agent by its name; function calls are not shown
const callSpeakers = (c) => ({
  user: c.contact_name || contactName(c.number) || c.number || 'Номер скрыт',
  assistant: c.agent_name ? `Агент ${c.agent_name}` : 'Агент',
  operator: 'Вы',  // a browser call: you talked yourself (recognized from the recording after the call)
  system: 'Система',
});
const msgHtml = (m, who = {}) => (m.role === 'tool' ? ''
  : `<div class="msg ${m.role}">${esc(m.text)}<div class="meta">${esc(who[m.role] || m.role)} · ${m.ts ? new Date(m.ts).toLocaleTimeString(I18N.locale) : ''}</div></div>`);

// ------------------------------------------------------------------ contact suggest for phone inputs
function attachContactSuggest(input, { onPick } = {}) {
  input.autocomplete = 'off';
  const holder = document.createElement('div');  // anchors the dropdown right under the input
  holder.style.position = 'relative';
  input.replaceWith(holder);
  const box = document.createElement('div');
  box.className = 'suggest';
  box.hidden = true;
  holder.append(input, box);
  const picked = document.createElement('div');  // teaser of the matched contact, right under the field
  picked.className = 'contact-teaser';
  picked.hidden = true;
  holder.after(picked);
  let items = [], idx = -1;

  const digits = (s) => (s || '').replace(/\D/g, '');
  const mark = (text, q) => {
    const i = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
    return i < 0 ? esc(text) : `${esc(text.slice(0, i))}<mark>${esc(text.slice(i, i + q.length))}</mark>${esc(text.slice(i + q.length))}`;
  };
  const showPicked = () => {
    if (onPick) return;
    const c = findContact(input.value);
    picked.hidden = !c;
    picked.innerHTML = c ? `<div class="avatar"${avatarStyle(fullName(c))}>${esc(initials(fullName(c)))}</div>
      <div class="body"><div class="ellipsis"><b>${esc(fullName(c))}</b></div>
        <div class="small muted ellipsis">${[c.company, c.phone].filter(Boolean).map(esc).join(' · ')}</div></div>` : '';
  };
  const hide = () => { box.hidden = true; idx = -1; };
  const choose = (c) => {
    if (onPick) { onPick(c); input.value = ''; hide(); picked.innerHTML = ''; return; }
    input.value = c.phone;
    hide(); showPicked();
    input.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const render = () => {
    const q = input.value.trim();
    const qd = digits(q);
    const qd7 = qd.startsWith('8') ? '7' + qd.slice(1) : qd;  // 8 926… == +7 926…
    items = state.contacts.filter((c) => !q
      || fullName(c).toLowerCase().includes(q.toLowerCase())
      || (c.company || '').toLowerCase().includes(q.toLowerCase())
      || (qd.length >= 2 && (digits(c.phone).includes(qd) || digits(c.phone).includes(qd7)))).slice(0, 8);
    // nothing to suggest, or the field already holds exactly that contact's number
    if (!items.length || (items.length === 1 && qd && [qd, qd7].includes(digits(items[0].phone)))) { hide(); return; }
    idx = Math.min(idx, items.length - 1);
    box.innerHTML = items.map((c, i) => `<div class="suggest-item ${i === idx ? 'active' : ''}" data-i="${i}">
        <div style="min-width:0;flex:1"><div class="ellipsis">${mark(fullName(c), /\d/.test(q) ? '' : q)}</div>
          <div class="small muted mono">${qd.length >= 2 ? esc(c.phone).replace(digits(c.phone).includes(qd) ? qd : qd7, (m) => `<mark>${m}</mark>`) : esc(c.phone)}${c.company ? ` · <span class="faint">${esc(c.company)}</span>` : ''}</div></div></div>`).join('');
    box.hidden = false;
    $$('.suggest-item', box).forEach((el) => {
      el.onmousedown = (e) => { e.preventDefault(); choose(items[+el.dataset.i]); };  // before blur
    });
  };
  input.addEventListener('input', () => { idx = -1; render(); showPicked(); });
  input.addEventListener('focus', render);
  input.addEventListener('blur', () => setTimeout(hide, 100));
  input.addEventListener('keydown', (e) => {
    if (box.hidden) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      idx = (idx + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      render();
    } else if (e.key === 'Enter' && idx >= 0) {
      e.preventDefault();
      choose(items[idx]);
    } else if (e.key === 'Escape') {
      e.stopPropagation();  // close the suggestions, not the drawer
      hide();
    }
  });
  showPicked();
}

const SCHEDULING = false;  // queued / scheduled calls — hidden in the UI for now

// A script variable that the phone book card can fill: by its name or label («имя», {{company}}, «Фамилия клиента»…)
const VAR_FROM_CONTACT = [
  [/фио|fullname|полноеимя/, (c) => fullName(c)],
  [/компан|организац|company/, (c) => c.company],
  [/фамил|lastname|surname/, (c) => c.last_name],
  [/имя|name/, (c) => c.name],
  [/почт|email|mail/, (c) => c.email],
  [/телефон|phone|номер/, (c) => c.phone],
];
function contactValue(v, c) {
  for (const key of [v.name, v.label]) {
    const k = (key || '').toLowerCase().replace(/[^a-zа-яё]/g, '');
    const hit = k && VAR_FROM_CONTACT.find(([re]) => re.test(k));
    if (hit) return hit[1](c) || '';
  }
  return null;
}

// ---------------------------------------------------------------- audio player with a waveform
// wavePlayer() renders a placeholder; any .wplayer that appears in the page is brought to life (one observer for
// all views). The waveform comes from the server as peaks (`wave` URL) — the audio itself loads only on play.
// Stereo recordings: the left channel (the other person) is drawn up, the right one (agent / you) down.
function wavePlayer(src, wave, { labels = [] } = {}) {
  return `<div class="wplayer" data-src="${esc(src)}" data-wave="${esc(wave || '')}" data-labels="${esc(labels.join('|'))}" tabindex="0" role="group" aria-label="Плеер">
    <button type="button" class="wp-btn" title="Слушать" aria-label="Слушать">${icon('play')}</button>
    <div class="wp-wave"><canvas></canvas><span class="wp-tip mono" hidden></span></div>
    <span class="wp-time mono">0:00</span></div>`;
}
const wpFmt = (t) => { t = Math.max(0, Math.floor(t || 0)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`; };
let wpCurrent = null;  // only one player sounds at a time

function initWavePlayer(el) {
  el.dataset.ready = '1';
  const btn = $('.wp-btn', el), box = $('.wp-wave', el), cv = $('canvas', box), tip = $('.wp-tip', el), time = $('.wp-time', el);
  const labels = (el.dataset.labels || '').split('|').filter(Boolean);
  let peaks = null, duration = 0, audio = null, hover = null, raf = 0, pendingSeek = null;

  const cur = () => (audio ? audio.currentTime : pendingSeek || 0);
  const showTime = () => { time.textContent = duration ? `${wpFmt(cur())} / ${wpFmt(duration)}` : wpFmt(cur()); };
  const draw = () => {
    const dpr = window.devicePixelRatio || 1, w = box.clientWidth, h = box.clientHeight;
    if (!w || !h) return;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    const g = cv.getContext('2d'), css = getComputedStyle(el);
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    const colors = [css.getPropertyValue('--wp-a').trim(), css.getPropertyValue('--wp-b').trim()];
    const step = 3, bars = Math.floor(w / step), progress = duration ? cur() / duration : 0;
    const chans = peaks?.length ? peaks : [[]];
    const mid = h / 2;
    for (let i = 0; i < bars; i++) {
      const x = i * step, played = (i + 0.5) / bars <= progress;
      chans.forEach((ch, c) => {
        let v = 0;
        if (ch.length) {
          const a = Math.floor(i * ch.length / bars), b = Math.max(a + 1, Math.floor((i + 1) * ch.length / bars));
          for (let k = a; k < b; k++) v = Math.max(v, ch[k]);
        }
        g.globalAlpha = played ? 1 : 0.38;
        g.fillStyle = colors[c] || colors[0];
        if (chans.length > 1) {  // sqrt: quiet speech is still visible
          const amp = Math.max(1, Math.sqrt(v) * (mid - 2));
          g.fillRect(x, c === 0 ? mid - amp - 0.5 : mid + 0.5, 2, amp);
        } else {
          const full = Math.max(2, Math.sqrt(v) * (h - 4));
          g.fillRect(x, (h - full) / 2, 2, full);
        }
      });
    }
    if (hover != null) { g.globalAlpha = 0.9; g.fillStyle = css.getPropertyValue('--text'); g.fillRect(Math.round(hover * w), 0, 1, h); }
    g.globalAlpha = 1;
  };
  const loop = () => { draw(); showTime(); if (audio && !audio.paused) raf = requestAnimationFrame(loop); };
  const setBtn = (playing) => { btn.innerHTML = icon(playing ? 'pause' : 'play'); btn.title = playing ? 'Пауза' : 'Слушать'; el.classList.toggle('playing', playing); };

  const ensureAudio = () => {
    if (audio) return audio;
    audio = new Audio(el.dataset.src);
    audio.preload = 'auto';
    audio.addEventListener('loadedmetadata', () => {
      if (isFinite(audio.duration)) duration = audio.duration;
      if (pendingSeek != null) { audio.currentTime = pendingSeek; pendingSeek = null; }
      draw(); showTime();
    });
    audio.addEventListener('play', () => {
      if (wpCurrent && wpCurrent !== audio) wpCurrent.pause();
      wpCurrent = audio; setBtn(true); cancelAnimationFrame(raf); loop();
    });
    audio.addEventListener('pause', () => { setBtn(false); draw(); showTime(); });
    audio.addEventListener('ended', () => { audio.currentTime = 0; setBtn(false); draw(); showTime(); });
    audio.addEventListener('timeupdate', () => { if (!el.isConnected) audio.pause(); });  // the view was closed
    audio.addEventListener('error', () => { setBtn(false); toast('Не удалось загрузить запись', 'err'); });
    return audio;
  };
  const toggle = () => { const a = ensureAudio(); a.paused ? a.play().catch(() => {}) : a.pause(); };
  const seek = (frac) => {
    frac = Math.min(1, Math.max(0, frac));
    if (!duration) return;
    const t = frac * duration;
    if (audio && audio.readyState >= 1) audio.currentTime = t; else { pendingSeek = t; ensureAudio(); }
    draw(); showTime();
  };
  const frac = (e) => { const r = box.getBoundingClientRect(); return (e.clientX - r.left) / r.width; };

  btn.onclick = (e) => { e.stopPropagation(); toggle(); };
  box.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    box.setPointerCapture(e.pointerId); seek(frac(e));
    const move = (ev) => seek(frac(ev));
    box.addEventListener('pointermove', move);
    box.addEventListener('pointerup', () => box.removeEventListener('pointermove', move), { once: true });
  });
  box.addEventListener('pointermove', (e) => {
    hover = Math.min(1, Math.max(0, frac(e)));
    if (duration) {
      const r = box.getBoundingClientRect();
      tip.hidden = false; tip.textContent = wpFmt(hover * duration);
      tip.style.left = `${Math.min(r.width - tip.offsetWidth, Math.max(0, hover * r.width - tip.offsetWidth / 2))}px`;
    }
    draw();
  });
  box.addEventListener('pointerleave', () => { hover = null; tip.hidden = true; draw(); });
  el.addEventListener('contextmenu', (e) => e.preventDefault());  // no browser menu on the player
  el.addEventListener('click', (e) => e.stopPropagation());       // clicks don't open the card under it
  el.addEventListener('keydown', (e) => {
    if (e.target !== el && e.target !== btn) return;
    if (e.key === ' ' || (e.key === 'Enter' && e.target === el)) { e.preventDefault(); toggle(); }
    else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault();
      if (duration) seek((cur() + (e.key === 'ArrowRight' ? 5 : -5)) / duration);
    }
  });
  if (labels.length) box.title = `Вверх — ${labels[0]}, вниз — ${labels[1] || ''}`;
  new ResizeObserver(() => draw()).observe(box);
  draw(); showTime();
  if (el.dataset.wave) {
    fetch(el.dataset.wave, { credentials: 'same-origin' }).then((r) => (r.ok ? r.json() : null)).then((d) => {
      if (!d) return;
      peaks = d.channels; duration = duration || d.duration; draw(); showTime();
    }).catch(() => {});
  }
}
new MutationObserver(() => $$('.wplayer:not([data-ready])').forEach(initWavePlayer))
  .observe(document.documentElement, { childList: true, subtree: true });

// "⋮" in the head of a person (Звонки, SMS): calls, SMS, the contact and its AI assistant, spam.
// spam: whether the number is marked; changed(): reload the view; extra: items of the view itself (at the end)
function personMenu(anchor, number, { spam = false, sms = true, changed, extra = [] } = {}) {
  const c = findContact(number);
  const reloadContacts = async () => { state.contacts = await api('/contacts'); changed?.(); };
  openMenu(anchor, [
    { label: 'Звонок агентом', icon: 'bot', run: () => openDialModal({ mode: 'agent', number }, changed) },
    { label: 'Позвонить', icon: 'phoneOut', run: () => openDialModal({ mode: 'browser', number }, changed) },
    sms ? { label: 'Отправить сообщение', icon: 'message', run: () => { location.hash = `#/sms?number=${encodeURIComponent(number)}`; } } : null,
    c ? { label: 'ИИ-ассистент', icon: 'sparkle', run: () => editContact(c, reloadContacts, 0) } : null,
    c ? { label: 'Редактировать контакт', icon: 'edit', run: () => editContact(c, reloadContacts, 1) }
      : { label: 'Сохранить контакт', icon: 'book', run: () => editContact({ phone: number }, reloadContacts) },
    '-',
    { label: spam ? 'Убрать из спама' : 'Пометить как спам', icon: 'alert', danger: !spam, run: guard(async () => {
      if (spam) await api('/spam?number=' + encodeURIComponent(number), { method: 'DELETE' });
      else await api('/spam', { method: 'POST', body: { number } });
      toast(spam ? 'Номер убран из спама' : 'Номер помечен как спам — его звонки теперь в папке «Спам»', 'ok');
      refreshBadges();
      changed?.();
    }) },
    '-',
    ...historyMenuItems(number, changed, { forget: false }),  // clearing the agent's memory — only in Контакты
    ...extra,
  ]);
}

// The agents' memory of a person. «Очистить историю агента»: the agents forget the calls and SMS (they stay in
// the journal) and the contact's AI chat is erased. «Удалить все звонки»: the calls go, the AI chat too.
// Both can't be undone — a confirmation first.
function historyMenuItems(number, changed, { forget = true } = {}) {
  const q = encodeURIComponent(number);
  return [
    forget && { label: 'Очистить историю агента', icon: 'eyeOff', danger: true, run: () => dialog({
      title: 'Очистить историю агента?', danger: true, confirm: 'Очистить',
      text: 'Агенты забудут все звонки и SMS с этим абонентом, переписка с ИИ-ассистентом по нему удалится. Сами звонки и SMS останутся в журнале. Это действие нельзя отменить.',
      onConfirm: async () => {
        const r = await api('/history/forget', { method: 'POST', body: { number } });
        toast(`История агента очищена: звонков — ${r.calls}, SMS — ${r.sms}`, 'ok');
      } }).then((ok) => ok && changed?.()) },
    { label: 'Удалить все звонки', icon: 'trash', danger: true, run: () => dialog({
      title: 'Удалить все звонки?', danger: true, confirm: 'Удалить',
      text: 'Все звонки с этим абонентом удалятся вместе с записями, расшифровками и резюме, переписка с ИИ-ассистентом по нему — тоже. SMS останутся. Это действие нельзя отменить.',
      onConfirm: async () => {
        const r = await api('/history/calls?number=' + q, { method: 'DELETE' });
        toast(`Удалено звонков: ${r.calls}`, 'ok');
        refreshBadges();
      } }).then((ok) => ok && changed?.()) },
  ];
}

// "⋮" of a call widget (the calls feed, the contact's AI chat): changed() reloads what shows it
function callMenuItems(c, changed) {
  return [
    { label: 'Подробнее', icon: 'eye', run: () => showCall(c.id) },
    c.recording ? { label: 'Скачать аудиофайл', icon: 'download', run: () => downloadRecording(c) } : null,
    { label: 'Найти договорённости', icon: 'tasks', run: async () => {
      toast('ИИ ищет договорённости в разговоре…', 'info');
      const r = await api(`/calls/${c.id}/tasks`, { method: 'POST' });
      toast(r.added ? `В «Дела» добавлено: ${r.added}` : 'Договорённостей в разговоре не нашлось', r.added ? 'ok' : 'info');
    } },
    '-',
    c.forgotten
      ? { label: 'Вернуть в историю агента', icon: 'eye', run: async () => {
        await api(`/calls/${c.id}/forgotten`, { method: 'PUT', body: { forgotten: false } });
        toast('Агенты снова учитывают этот звонок', 'ok'); changed?.();
      } }
      : { label: 'Убрать из истории агента', icon: 'eyeOff', run: async () => {
        await api(`/calls/${c.id}/forgotten`, { method: 'PUT', body: { forgotten: true } });
        toast('Агенты больше не учитывают этот звонок — в журнале он остаётся', 'ok'); changed?.();
      } },
    { label: 'Удалить звонок', icon: 'trash', danger: true, run: () => dialog({
      title: 'Удалить звонок?', danger: true, confirm: 'Удалить',
      text: 'Звонок удалится вместе с записью, расшифровкой и резюме, агенты перестанут его знать. Это действие нельзя отменить.',
      onConfirm: async () => { await api('/calls/' + c.id, { method: 'DELETE' }); toast('Звонок удалён', 'ok'); refreshBadges(); },
    }).then((ok) => ok && changed?.()) },
  ];
}

// the call's recording as a file named after the person and the time: «Пётр Васильев 2025-09-27 20-00.wav»
function downloadRecording(c) {
  const who = c.contact_name || c.number || 'звонок';
  const when = (c.started_at || c.created_at || '').slice(0, 16).replace('T', ' ').replace(':', '-');
  const a = document.createElement('a');
  a.href = `/api/calls/${c.id}/recording`;
  a.download = `${who} ${when}.wav`.replace(/[\\/:*?"<>|]/g, '').trim();
  document.body.append(a); a.click(); a.remove();
}

// background sounds under the agent's voice (city noise): fetched once
let ambienceCache = null;
const ambienceList = async () => (ambienceCache ??= (await api('/ambience')).items);
const ambienceOpts = (items, sel) => [['', 'Без фона'], ['random', 'Случайный'], ...items.map((a) => [a.id, a.name])]
  .map(([v, l]) => `<option value="${v}" ${v === (sel || '') ? 'selected' : ''}>${esc(l)}</option>`).join('');
// a select of background sounds + a button to listen to the chosen one
function bindAmbience(sel, btn) {
  let player = null;
  const idle = () => { player?.pause(); player = null; btn.innerHTML = icon('play'); btn.title = 'Прослушать'; };
  const sync = () => { btn.disabled = !sel.value || sel.value === 'random'; if (btn.disabled) idle(); };
  btn.onclick = () => {
    if (player) return idle();
    player = new Audio(`/api/ambience/${sel.value}.wav`);
    player.onended = idle;
    player.ontimeupdate = () => { if (!btn.isConnected) idle(); };  // the form was closed
    player.play();
    btn.innerHTML = icon('stop'); btn.title = 'Остановить';
  };
  sel.addEventListener('change', () => { idle(); sync(); });
  sync();
  return idle;
}

// Two separate forms: «Звонок агентом» (a voice agent talks, script + variables) and «Позвонить» (you talk
// yourself through the browser: microphone and speakers).
function openDialModal({ mode = 'agent', number = '', script = '', agent = '' } = {}, done) {
  const browser = mode === 'browser';
  const outScripts = state.scripts.filter((x) => x.direction === 'any' || x.direction === 'outbound');
  modal({
    title: browser ? 'Позвонить через браузер' : 'Звонок агентом',
    body: `<form class="form" id="dial">
      <div class="field"><label>Номер или имя контакта</label><input name="number" placeholder="+7 900 000-00-00 или имя" required value="${esc(number || '')}">
        ${browser ? `<span class="hint">${window.isSecureContext
          ? 'Вы будете говорить сами через микрофон и динамики. Лучше использовать наушники, чтобы не было эха.'
          : `Микрофон доступен только по HTTPS — откройте ${httpsUrl()}`}</span>` : ''}</div>
      ${browser ? '' : `
      <div class="field"><label>Агент</label><select name="agent_id" id="dial-agent">
        ${state.agents.map((a) => `<option value="${a.id}" ${String(agent) === String(a.id) ? 'selected' : ''}>${esc(a.name)}</option>`).join('')}</select></div>
      <div class="field"><label>Сценарий</label><select name="script_id" id="dial-script">
        ${outScripts.map((x) => `<option value="${x.id}" ${String(script) === String(x.id) ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}
        <option value="">— без сценария —</option></select></div>
      <div id="dial-vars" class="form"></div>
      <label class="switch"><input type="checkbox" name="history" checked> Агент знает предыдущие разговоры
        <span class="help sm" tabindex="0" role="note" data-tip="Агент получит суть и договорённости последних звонков и SMS с этим номером — и продолжит разговор с того места, не спрашивая заново то, что уже известно.">?</span></label>
      <details id="dial-queue" ${SCHEDULING ? '' : 'hidden'}><summary class="muted small" style="cursor:pointer">Очередь и отложенный звонок</summary>
        <div class="form" style="margin-top:10px">
          <label class="switch"><input type="checkbox" name="queue"> В очередь, если линия занята</label>
          <div class="field"><label>Позвонить в</label><input type="datetime-local" name="scheduled_at"></div>
        </div></details>`}</form>`,
    onMount: (m) => {
      const numIn = $('[name=number]', m);
      attachContactSuggest(numIn);
      numIn.focus();
      $('#dial', m).onsubmit = (e) => { e.preventDefault(); $('[data-btn="1"]', m).click(); };
      if (browser) return;
      const agentSel = $('#dial-agent', m), scriptSel = $('#dial-script', m);
      // variables the contact card can fill are filled — until the user types there themselves
      const fillFromContact = () => {
        const c = findContact(numIn.value);
        $$('[data-var]', m).forEach((i) => {
          if (i.dataset.touched) return;
          const v = { name: i.dataset.var, label: i.dataset.label };
          const val = c ? contactValue(v, c) : null;
          i.value = val ?? i.dataset.default;
          i.classList.toggle('from-contact', !!(c && val));
          i.title = c && val ? `Из карточки контакта: ${fullName(c)}` : '';
        });
      };
      const renderVars = () => {
        const sc = state.scripts.find((x) => String(x.id) === scriptSel.value);
        $('#dial-vars', m).innerHTML = (sc?.variables || []).map((v) => `<div class="field"><label>${esc(v.label || v.name)} <span class="faint mono">{{${esc(v.name)}}}</span></label>
          <input data-var="${esc(v.name)}" data-label="${esc(v.label || '')}" data-default="${esc(v.default || '')}" value="${esc(v.default || '')}"></div>`).join('');
        $$('[data-var]', m).forEach((i) => { i.oninput = () => { i.dataset.touched = '1'; i.classList.remove('from-contact'); i.title = ''; }; });
        fillFromContact();
      };
      // the script's own agent, unless one was chosen by hand (or passed in)
      let agentPicked = !!agent;
      agentSel.addEventListener('change', () => { agentPicked = true; });
      scriptSel.onchange = () => {
        const sc = state.scripts.find((x) => String(x.id) === scriptSel.value);
        $('[name=history]', m).checked = !(sc && (sc.history === 0 || sc.history === false));  // as the script says
        if (sc?.default_agent_id && !agentPicked && state.agents.some((a) => a.id === sc.default_agent_id)) {
          agentSel.value = sc.default_agent_id;
        }
        renderVars();
      };
      numIn.addEventListener('input', fillFromContact);
      numIn.addEventListener('change', fillFromContact);  // a contact picked from the suggestions
      scriptSel.onchange();
    },
    buttons: [{ label: 'Отмена', cls: 'btn-ghost' }, { label: `${icon('phoneOut')} Позвонить`, cls: 'btn-primary', onClick: async (m) => {
      const form = $('#dial', m);
      if (!form.reportValidity()) return false;
      const f = formData(form);
      const variables = {}; $$('[data-var]', m).forEach((i) => { variables[i.dataset.var] = i.value; });
      const body = browser ? { number: f.number, browser: true } : {
        number: f.number,
        agent_id: f.agent_id ? +f.agent_id : null,
        script_id: f.script_id ? +f.script_id : null,
        variables,
        history: !!f.history,
        queue: SCHEDULING && !!f.queue,
        scheduled_at: SCHEDULING && f.scheduled_at ? new Date(f.scheduled_at).toISOString() : null,
      };
      if (browser) await softphone.start();  // ask for the microphone before dialing
      let r;
      try { r = await api('/calls', { method: 'POST', body }); } catch (e) { if (browser) softphone.stop(); throw e; }
      toast(r.status === 'queued' ? 'Звонок поставлен в очередь' : 'Набираем номер…', 'ok');
      done?.();
    } }],
  });
}

function summaryHtml(c) {
  const s = c.summary_record;
  if (s) {
    return `<div class="summary-box">${esc(s.text)}</div>
      <div class="small faint mt" style="margin-top:6px">${icon('lock')} ${esc(s.model)} · ${fmtDate(s.created_at)} · изменить нельзя</div>`;
  }
  if (c.status === 'active' || c.status === 'dialing' || c.status === 'ringing') return '<span class="muted">Появится после окончания звонка</span>';
  if (c.can_summarize) {
    return `<div class="row"><span class="muted">Суммаризации нет (не удалась или ещё готовится).</span>
      <button class="btn btn-sm" data-summarize="${c.id}">${icon('refresh')} Сделать суммаризацию</button></div>`;
  }
  return '<span class="muted">Нет расшифровки разговора — суммаризация недоступна.</span>';
}

function bindSummarize(el) {
  const b = $('[data-summarize]', el);
  if (!b) return;
  b.onclick = guard(async () => {
    const label = b.innerHTML;
    b.disabled = true; b.textContent = 'Готовим…';
    try {
      const s = await api(`/calls/${b.dataset.summarize}/summary`, { method: 'POST' });
      el.innerHTML = summaryHtml({ summary_record: s });
    } finally { b.disabled = false; b.innerHTML = label; }
  });
}

async function showCall(id) {
  const c = await api('/calls/' + id);
  const talk = c.messages.filter((x) => ['user', 'assistant', 'operator'].includes(x.role)).length;
  const agentSaid = c.summary || c.result?.summary || '';  // the agent's own summary — text only, not the raw JSON
  modal({
    title: `Звонок #${c.id}`, size: 'lg',
    body: `<div class="tabs drawer-tabs" role="tablist" data-tabs>
        <button type="button" role="tab" data-tab="0" class="active">Звонок</button>
        <button type="button" role="tab" data-tab="1">Транскрипт${talk ? ` (${talk})` : ''}</button></div>
      <section class="tab-pane" data-pane="0" role="tabpanel">
      <div class="grid grid-2">
      <dl class="kv">
        <dt>Направление</dt><dd>${c.direction === 'in' ? 'Входящий' : 'Исходящий'}</dd>
        <dt>Номер</dt><dd class="mono">${esc(c.number || '—')}</dd>
        <dt>Контакт</dt><dd>${esc(c.contact_name || '—')}</dd>
        <dt>Статус</dt><dd>${statusBadge(c.status)}</dd>
        <dt>Агент</dt><dd>${esc(c.agent_name || '—')}</dd>
        <dt>Сценарий</dt><dd>${esc(c.script_name || '—')}</dd>
      </dl>
      <dl class="kv">
        <dt>Начало</dt><dd>${fmtDate(c.started_at)}</dd>
        <dt>Ответ</dt><dd>${fmtDate(c.answered_at)}</dd>
        <dt>Конец</dt><dd>${fmtDate(c.ended_at)}</dd>
        <dt>Длительность</dt><dd>${c.duration ? fmtDur(c.duration) : ''}</dd>
        <dt>Переменные</dt><dd class="small mono">${esc(Object.entries(c.variables || {}).map(([k, v]) => `${k}=${v}`).join(', ') || '—')}</dd>
        ${c.error ? `<dt>Ошибка</dt><dd class="small" style="color:var(--err)">${esc(c.error)}</dd>` : ''}
      </dl></div>
      ${c.recording ? `<h3 class="mt">Запись <span class="muted small">вверх — собеседник, вниз — ${c.mode === 'browser' ? 'вы' : 'агент'}</span></h3>${wavePlayer(`/api/calls/${c.id}/recording`, `/api/calls/${c.id}/waveform`, { labels: ['собеседник', c.mode === 'browser' ? 'вы' : 'агент'] })}` : ''}
      <h3 class="mt">Суммаризация</h3><div id="call-summary">${summaryHtml(c)}</div>
      ${agentSaid ? `<h3 class="mt">Итог, сохранённый агентом</h3><p>${esc(agentSaid)}</p>` : ''}
      </section>
      <section class="tab-pane" data-pane="1" role="tabpanel" hidden>
        <div class="transcript transcript-full">${c.messages.map((m) => msgHtml(m, callSpeakers(c))).join('') || (c.can_transcribe
          ? `<div class="empty">Расшифровки пока нет. Её можно сделать по записи звонка — SpeechKit распознает, кто что сказал.<div class="mt"><button class="btn" data-transcribe="${c.id}">${icon('wave')} Сделать расшифровку</button></div></div>`
          : '<div class="empty">Расшифровки нет: у звонка нет записи или разговора не было.</div>')}</div>
      </section>`,
    onMount: (m) => {
      bindSummarize($('#call-summary', m));
      setupDrawerTabs(m);
      const tb = $('[data-transcribe]', m);
      if (tb) tb.onclick = guard(async () => {
        tb.disabled = true; tb.innerHTML = '<span class="spin"></span> Распознаём запись…';
        try {
          const r = await api(`/calls/${id}/transcribe`, { method: 'POST' });
          toast(r.phrases ? `Расшифровка готова: ${r.phrases} ${plural(r.phrases, 'фраза', 'фразы', 'фраз')}` : 'В записи не нашлось речи', r.phrases ? 'ok' : 'warn');
          $('[data-close]', m)?.click(); showCall(id);  // reopen with the transcript and the summary
        } catch (e) { tb.disabled = false; tb.innerHTML = `${icon('wave')} Сделать расшифровку`; throw e; }
      });
    },
  });
}

// ------------------------------------------------------------------ sms
VIEWS.sms = {
  title: 'SMS', icon: 'message', current: null,
  async render(root, params) {
    await loadRefs();
    if (params.get('number')) this.current = params.get('number');
    setActions(`<button class="btn btn-primary" id="new-sms">${icon('plus')} Новое сообщение</button>`);
    root.innerHTML = `<div class="hub-layout">
      <div class="card hub-side"><nav class="tag-rail" id="tags" aria-label="Теги"></nav>
        <div class="hub-people">${peopleSearch('Поиск')}<div class="hub-list" id="threads"></div></div></div>
      <div class="card sms-chat hub-main" id="chat"></div></div>`;
    let timer;
    $('#people-q', root).oninput = () => { clearTimeout(timer); timer = setTimeout(() => this.loadThreads(root), 150); };
    $('#new-sms').onclick = () => modal({
      title: 'Новое сообщение',
      body: `<div class="form"><div class="field"><label>Номер</label><input id="n-num" placeholder="+7 900 000-00-00 или имя"></div>
        <div class="field"><label>Текст</label><textarea id="n-text"></textarea><span class="hint" id="n-count"></span></div></div>`,
      onMount: (m) => {
        attachContactSuggest($('#n-num', m));
        $('#n-num', m).focus();
        $('#n-text', m).oninput = () => { $('#n-count', m).textContent = smsCounter($('#n-text', m).value); };
      },
      buttons: [{ label: 'Отмена', cls: 'btn-ghost' }, { label: `${icon('send')} Отправить`, cls: 'btn-primary', onClick: async (m) => {
        const number = $('#n-num', m).value.trim();
        const text = $('#n-text', m).value.trim();
        if (!number) throw new Error('Укажите номер');
        if (!text) throw new Error('Введите текст сообщения');
        // the modem may need up to a couple of minutes — close the window right away
        this.current = number;
        sendSmsInBackground(number, text);
      } }],
    });
    await this.loadThreads(root);
  },
  async loadThreads(root) {
    const all = await api('/sms/threads');
    this.spam = new Set(all.filter((t) => t.spam).map((t) => (t.number || '').replace(/\D/g, '').slice(-10)));
    tagRail($('#tags', root), () => { this.current = null; this.loadThreads(root); }, tagCounts(all, (t) => t.unread));
    const tag = currentTag();
    const q = $('#people-q', root)?.value || '';
    const threads = all.filter((t) => numberInTag(t.number, tag) && matchesPerson(q, t.contact_name, t.number));
    // no dialog opens by itself (it would be marked read) — until one is picked
    const norm = (n) => (n || '').replace(/\D/g, '').slice(-10);
    $('#threads', root).innerHTML = threads.map((t) => `<div class="sms-item ${norm(t.number) === norm(this.current) ? 'active' : ''}" data-n="${esc(t.number)}">
        <div class="avatar"${avatarStyle(t.contact_name || '#')}>${esc(initials(t.contact_name || '#'))}</div>
        <div class="body"><div class="row"><span class="person-name ellipsis">${esc(t.contact_name || t.number)}</span><span class="spacer"></span><span class="small faint">${fmtDate(t.ts)}</span></div>
        <div class="row"><span class="small muted ellipsis">${t.direction === 'out' ? 'Вы: ' : ''}${esc(t.text)}</span><span class="spacer"></span>${t.unread ? `<span class="badge primary">${t.unread}</span>` : ''}</div></div></div>`).join('')
      || `<div class="empty small">${icon('message')}<div>${q ? 'Никого не нашлось' : tag ? 'В этой папке сообщений нет' : 'Сообщений нет'}</div></div>`;
    $$('.sms-item', root).forEach((el) => {
      el.onclick = () => { this.current = el.dataset.n; this.loadThreads(root); };
      personContext(el, (a) => this.personMenu(a, el.dataset.n, root));
    });
    await this.loadChat(root);
  },
  async loadChat(root) {
    const chat = $('#chat', root);
    if (!this.current) { chat.innerHTML = `<div class="empty" style="margin:auto">${icon('message')}<div>Выберите диалог</div></div>`; return; }
    const msgs = (await api('/sms?number=' + encodeURIComponent(this.current))).reverse();
    if (msgs.some((m) => !m.is_read)) {
      await api('/sms/read?number=' + encodeURIComponent(this.current), { method: 'POST' });
      refreshBadges();
      this.loadThreads(root);  // the person's and the folders' badges (nothing unread now — no loop)
      return;
    }
    const name = contactName(this.current);
    chat.innerHTML = `<div class="head"><div class="avatar"${avatarStyle(name || '#')}>${esc(initials(name || '#'))}</div><div><div class="person-name">${esc(name || this.current)}</div><div class="small muted mono">${esc(this.current)}</div></div><span class="spacer"></span>
        <span class="head-kebab">${KEBAB}</span></div>
      <div class="thread" id="thread">${msgs.map((m) => `<div class="msg ${m.direction}">${esc(m.text)}<div class="meta">${fmtDate(m.ts)}${m.direction === 'out' ? ' · ' + ({ sent: 'отправлено', sending: 'отправка…', failed: 'ошибка: ' + esc(m.error) }[m.status] || m.status) : ''}</div></div>`).join('')}</div>
      <form class="compose" id="compose"><div class="field" style="flex:1"><textarea id="c-text" rows="1" placeholder="Текст SMS…"></textarea><span class="hint" id="c-count"></span></div>
        <button class="btn btn-primary btn-icon" type="submit" title="Отправить" aria-label="Отправить">${icon('send')}</button></form>`;
    const th = $('#thread', root); th.scrollTop = th.scrollHeight;
    $('#c-text', root).oninput = (e) => {
      const t = e.target; t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 160) + 'px';  // grows with the text
      $('#c-count', root).textContent = t.value ? smsCounter(t.value) : '';
    };
    $('#c-text', root).onkeydown = (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) $('#compose', root).requestSubmit(); };
    $('#compose', root).onsubmit = guard(async (e) => {
      e.preventDefault();
      const text = $('#c-text', root).value.trim(); if (!text) return;
      $('#c-text', root).value = '';
      $('#c-count', root).textContent = '';
      sendSmsInBackground(this.current, text);
    });
    const hk = $('.head-kebab .kebab', chat), number = this.current;
    hk.onclick = (e) => { e.stopPropagation(); this.personMenu(hk, number, root); };
  },
  // the person's menu: "⋮" in the dialog's head, or a right click on the person in the list
  personMenu(anchor, number, root) {
    personMenu(anchor, number, { spam: this.spam?.has((number || '').replace(/\D/g, '').slice(-10)), sms: false, changed: () => this.loadThreads(root), extra: [
      { label: 'Удалить диалог', icon: 'trash', danger: true, run: () => confirmBox('Удалить весь диалог?', async () => {
        await api('/sms?number=' + encodeURIComponent(number), { method: 'DELETE' });
        if ((this.current || '').replace(/\D/g, '').slice(-10) === (number || '').replace(/\D/g, '').slice(-10)) this.current = null;
        this.loadThreads(root);
      }) },
    ] });
  },
  onEvent(ev, root) { if (ev.event === 'sms.new' || ev.event === 'sms.updated') this.loadThreads(root); },
};

function sendSmsInBackground(number, text) {
  toast('Отправляем SMS…', 'info', 2500);
  // the message shows up in the thread immediately (sms.new) and its status updates via sms.updated
  api('/sms', { method: 'POST', body: { number, text } })
    .then((r) => {
      if (r.status === 'sent') toast(`SMS на ${contactName(r.number) || r.number} отправлено`, 'ok');
      else toast(`SMS не отправлено: ${r.error || r.status}`, 'err', 8000);
    })
    .catch((e) => toast(`SMS не отправлено: ${e.message}`, 'err', 8000));
}

function smsCounter(text) {
  const gsm = /^[@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&'()*+,\-./0-9:;<=>?¡A-ZÄÖÑÜ§¿a-zäöñüà^{}\\[~\]|€]*$/.test(text);
  const len = text.length;
  const [one, multi] = gsm ? [160, 153] : [70, 67];
  const parts = len <= one ? 1 : Math.ceil(len / multi);
  return `${len} симв. · ${parts} SMS · ${gsm ? 'GSM-7' : 'UCS-2'}`;
}

// ------------------------------------------------------------------ contacts
// ------------------------------------------------------------------ «Дела»
// Agreements from the calls (the AI lists them after a call) and tasks added by hand. Three tabs: the table,
// the calendar (events the user confirmed + dashed suggestions from the tasks' dates) and the Yandex map
// (points the user confirmed). Events and points are made only through a prefilled form the user checks.
const pad2 = (n) => String(n).padStart(2, '0');
const isoLocal = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
const isoDay = (d) => isoLocal(d).slice(0, 10);
const WD = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];
const MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
const parseLocal = (s) => (s ? new Date(s.length === 10 ? s + 'T00:00' : s) : null);
// an open task whose deadline has passed (a date without a time — once the day is over)
function isOverdue(t) {
  const d = parseLocal(t.due_at);
  if (!d || t.status === 'done') return false;
  return t.due_at.length > 10 ? d < new Date() : isoDay(d) < isoDay(new Date());
}
const TASK_FOLDERS = [{ t: '@overdue', label: 'Просрочено', icon: 'clock' }, { t: '@done', label: 'Выполненные', icon: 'check' }];
function fmtDue(t) {
  const d = parseLocal(t.due_at);
  if (!d) return t.due_text ? `<span class="muted">${esc(t.due_text)}</span>` : dash;
  const time = t.due_at.length > 10 ? ' ' + t.due_at.slice(11, 16) : '';
  const overdue = isOverdue(t);
  return `<span class="${overdue ? 'overdue' : ''}" title="${esc(t.due_text ? `В разговоре: «${t.due_text}»` : '')}">${WD[d.getDay()]}, ${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}${time}</span>`;
}
const taskWho = (t) => t.contact_name || t.number || '';
const taskTags = (t) => contactTags(findContact(t.number));

// ---- Yandex Maps JS API 2.1 (the key: Настройки → Yandex AI Studio, or right in the «Карта» tab)
let ymapsLoading = null;
async function mapsKey() {
  if (state.mapsKey === undefined) state.mapsKey = (await api('/settings'))['maps.api_key'] || '';
  return state.mapsKey;
}
function loadYmaps(key) {
  if (window.ymaps?.Map) return Promise.resolve(window.ymaps);
  ymapsLoading ??= new Promise((ok, fail) => {
    const s = document.createElement('script');
    s.src = `https://api-maps.yandex.ru/2.1/?apikey=${encodeURIComponent(key)}&lang=ru_RU`;
    s.onload = () => window.ymaps.ready(() => ok(window.ymaps));
    s.onerror = () => { ymapsLoading = null; s.remove(); fail(new Error('Не удалось загрузить Яндекс Карты')); };
    document.head.append(s);
  });
  return ymapsLoading;
}
// no key yet: where to get one and a field to save it
function mapsKeyForm(el, onSaved) {
  el.innerHTML = `<div class="maps-key"><div class="empty">${icon('pin')}<div>Для карты нужен ключ API Яндекс Карт</div></div>
    <ol class="small muted">
      <li>Откройте <a href="https://developer.tech.yandex.ru/services" target="_blank" rel="noopener">Кабинет разработчика Яндекса</a> и нажмите «Подключить API».</li>
      <li>Выберите «JavaScript API и HTTP Геокодер» — бесплатно для личного некоммерческого использования.</li>
      <li>Скопируйте ключ сюда или в «Настройки → Яндекс Карты».</li></ol>
    <form class="row" id="mk-form" style="gap:8px;flex-wrap:nowrap"><input id="mk" class="mono" placeholder="Ключ API" autocomplete="off" style="flex:1">
      <button class="btn btn-primary" type="submit">Сохранить</button></form></div>`;
  $('#mk-form', el).onsubmit = guard(async (e) => {
    e.preventDefault();
    const key = $('#mk', el).value.trim();
    if (!key) return;
    await api('/settings', { method: 'PUT', body: { 'maps.api_key': key } });
    state.mapsKey = key;
    onSaved();
  });
}

VIEWS.tasks = {
  title: 'Дела', icon: 'tasks', hint: 'Договорённости из телефонных разговоров: после звонка ИИ выписывает, кто что пообещал, когда и где. Событие в календаре и точку на карте вы подтверждаете сами.',
  tab: localStorage.getItem('caller.tasks.tab') || 'list',
  month: null,
  async render(root, params = new URLSearchParams()) {
    setActions(`<button class="btn btn-primary" id="add-task">${icon('plus')} Дело</button>`);
    await loadRefs();
    // a link (e.g. from the assistant) opens a folder, a search, a tab, a month
    if (params.has('folder')) localStorage.setItem('caller.tag', params.get('folder'));
    if (['list', 'calendar', 'map'].includes(params.get('tab'))) { this.tab = params.get('tab'); localStorage.setItem('caller.tasks.tab', this.tab); }
    const month = /^(\d{4})-(\d{2})$/.exec(params.get('month') || '');
    if (month) this.month = new Date(+month[1], +month[2] - 1, 1);
    root.innerHTML = `<div class="card hub-side wide tasks-hub">
      <nav class="tag-rail" id="tags" aria-label="Теги"></nav>
      <div class="hub-table tasks-main"><div class="card-head tasks-head">
        <div class="tabs" id="ttabs" role="tablist">${[['list', 'Список'], ['calendar', 'Календарь'], ['map', 'Карта']]
          .map(([k, l]) => `<button type="button" role="tab" data-t="${k}" class="${this.tab === k ? 'active' : ''}">${l}</button>`).join('')}</div>
        <input id="q" type="search" placeholder="Поиск" style="max-width:280px"></div>
        <div class="tasks-body" id="tbody"></div></div></div>`;
    $('#add-task').onclick = () => newTask(() => this.load(root));
    $$('#ttabs button', root).forEach((b) => b.onclick = () => {
      this.tab = b.dataset.t; localStorage.setItem('caller.tasks.tab', this.tab);
      $$('#ttabs button', root).forEach((x) => x.classList.toggle('active', x === b));
      this.draw(root);
    });
    let timer;
    $('#q', root).value = params.get('q') || '';
    $('#q', root).oninput = () => { clearTimeout(timer); timer = setTimeout(() => this.draw(root), 200); };
    await this.load(root);
  },
  async load(root) {
    this.items = await api('/tasks');
    // «Все» and the tags count open tasks; «Просрочено» — the overdue ones; «Выполненные» — no badge
    const counts = tagCounts(this.items.filter((t) => t.status !== 'done').map((t) => ({ number: t.number, n: 1 })), (x) => x.n);
    counts['@overdue'] = this.items.filter(isOverdue).length;
    tagRail($('#tags', root), () => this.draw(root), counts, TASK_FOLDERS);
    this.draw(root);
  },
  visible(root) {
    const tag = currentTag(TASK_FOLDERS), q = ($('#q', root)?.value || '').trim().toLowerCase();
    const inFolder = (t) => (tag === '@done' ? t.status === 'done' || this.pending.has(t.id)
      : tag === '@overdue' ? isOverdue(t) : t.status !== 'done' && (!tag || taskTags(t).includes(tag)));
    return this.items.filter((t) => inFolder(t)
      && (!q || [t.title, t.details, t.place, t.due_text, taskWho(t), t.number].join(' ').toLowerCase().includes(q)));
  },
  draw(root) {
    const body = $('#tbody', root);
    if (!body) return;
    const items = this.visible(root);
    $('#q', root).hidden = this.tab !== 'list';
    if (this.tab === 'calendar') return this.drawCalendar(root, body, items);
    if (this.tab === 'map') return this.drawMap(root, body, items);
    this.drawList(root, body, items);
  },
  drawList(root, body, items) {
    items = items.slice().sort((a, b) => b.id - a.id);  // the newest on top
    body.innerHTML = `<div class="table-wrap"><table class="tasks-table"><thead><tr><th class="check-cell"></th><th>Дело</th><th>С кем</th><th>Срок</th><th>Место</th><th></th><th></th></tr></thead><tbody>
      ${items.map((t) => { const done = t.status === 'done' || this.pending.has(t.id); return `<tr class="clickable ${done ? 'done' : ''}" data-id="${t.id}">
        <td class="check-cell"><label class="task-check" title="${done ? 'Вернуть в работу' : 'Выполнено'}"><input type="checkbox" data-done ${done ? 'checked' : ''}><span>${icon('check')}</span></label></td>
        <td style="max-width:340px">${entityCell(t.title, t.details || '')}</td>
        <td>${taskWho(t) ? `<div class="row" style="gap:8px;flex-wrap:nowrap"><div class="avatar sm"${avatarStyle(t.contact_name || '#')}>${esc(initials(t.contact_name || '#'))}</div><div style="min-width:0">${entityCell(taskWho(t), t.assignee ? `делает: ${t.assignee}` : '')}</div></div>` : dash}</td>
        <td class="nowrap">${fmtDue(t)}</td>
        <td class="ellipsis" style="max-width:220px" title="${esc(t.geo?.address || t.place)}">${esc(t.geo?.address || t.place) || dash}</td>
        <td class="nowrap task-marks">
          ${t.event ? `<button class="btn btn-ghost btn-sm btn-icon on" data-cal title="${esc(`В календаре: ${t.event.title}, ${t.event.start.slice(8, 10)}.${t.event.start.slice(5, 7)}${t.event.all_day ? '' : ' ' + t.event.start.slice(11, 16)}`)}">${icon('calendar')}</button>` : ''}
          ${t.geo ? `<button class="btn btn-ghost btn-sm btn-icon on" data-geo title="${esc(`На карте: ${t.geo.address || 'точка'}`)}">${icon('pin')}</button>` : ''}</td>
        <td class="kebab-cell">${KEBAB}</td></tr>`; }).join('')
        || `<tr><td colspan="7" class="empty">${icon('tasks')}<div>${{ '@overdue': 'Просроченных дел нет', '@done': 'Выполненных дел пока нет' }[currentTag(TASK_FOLDERS)] || 'Дел нет. Они появятся после звонков, в которых о чём-то договорились, или добавьте дело кнопкой «+ Дело».'}</div></td></tr>`}
      </tbody></table></div>`;
    const reload = () => this.load(root);
    const byId = (id) => this.items.find((x) => x.id === id);
    bindRows(body, {
      open: (id) => openTask(byId(id), 'task', reload),
      actions: (id) => taskActions(byId(id), reload),
    });
    $$('tr[data-id]', body).forEach((tr) => {
      const t = byId(+tr.dataset.id);
      $('.task-check', tr).onclick = (e) => e.stopPropagation();  // the checkbox never opens the task
      $('[data-done]', tr).onchange = (e) => this.toggleDone(root, t, e.target.checked, tr);
      $('[data-cal]', tr)?.addEventListener('click', (e) => { e.stopPropagation(); openTask(t, 'calendar', reload); });
      $('[data-geo]', tr)?.addEventListener('click', (e) => { e.stopPropagation(); openTask(t, 'map', reload); });
    });
  },
  // «выполнено»: the row is struck through at once and goes to «Выполненные» after 10 s unless undone
  pending: new Map(),
  // marks the task done after 10 s unless «Отменить» (the row is struck through meanwhile)
  complete(t, after) {
    const root = $('#view');
    const undo = undoToast(`«${t.title}» — выполнено`, 10,
      guard(async () => { this.pending.delete(t.id); await api('/tasks/' + t.id, { method: 'PUT', body: { status: 'done' } }); after?.(); if (state.view === this) this.load(root); }),
      () => { this.pending.delete(t.id); if (state.view === this) this.draw(root); });
    this.pending.set(t.id, undo);
    if (state.view === this) this.draw(root);
  },
  toggleDone(root, t, checked, tr) {
    const reload = () => this.load(root);
    if (!checked && this.pending.has(t.id)) { this.pending.get(t.id)(); return; }  // unticked again: undo
    tr.classList.toggle('done', checked);
    if (!checked) { guard(async () => { await api('/tasks/' + t.id, { method: 'PUT', body: { status: 'open' } }); reload(); })(); return; }
    this.complete(t);
  },
  drawCalendar(root, body, items) {
    const today = new Date();
    this.month ??= new Date(today.getFullYear(), today.getMonth(), 1);
    const m = this.month;
    const first = new Date(m.getFullYear(), m.getMonth(), 1);
    const start = new Date(first); start.setDate(1 - ((first.getDay() + 6) % 7));  // weeks start on Monday
    // a day's entries: confirmed events, and dashed suggestions — tasks with a date but no event yet
    const days = {};
    const put = (day, e) => (days[day] ??= []).push(e);
    for (const t of items) {
      if (t.event) put(t.event.start.slice(0, 10), { t, time: t.event.all_day ? '' : t.event.start.slice(11, 16), title: t.event.title, ev: true });
      else if (t.due_at) put(t.due_at.slice(0, 10), { t, time: t.due_at.length > 10 ? t.due_at.slice(11, 16) : '', title: t.title, ev: false });
    }
    Object.values(days).forEach((l) => l.sort((a, b) => (a.time || '00').localeCompare(b.time || '00')));
    const cells = [];
    for (let i = 0; i < 42; i++) {
      const d = new Date(start); d.setDate(start.getDate() + i);
      const k = isoDay(d), list = days[k] || [];
      cells.push(`<div class="cal-day ${d.getMonth() !== m.getMonth() ? 'other' : ''} ${k === isoDay(today) ? 'today' : ''}" data-day="${k}">
        <div class="cal-num">${d.getDate()}</div>
        ${list.slice(0, 4).map((e) => `<button type="button" class="cal-ev ${e.ev ? '' : 'suggested'} ${e.t.status === 'done' ? 'done' : ''}" data-id="${e.t.id}" title="${esc((e.ev ? '' : 'Не в календаре — нажмите, чтобы создать событие: ') + e.title)}">${e.time ? `<b>${e.time}</b> ` : ''}${esc(e.title)}</button>`).join('')}
        ${list.length > 4 ? `<div class="cal-more small muted">ещё ${list.length - 4}</div>` : ''}</div>`);
    }
    body.innerHTML = `<div class="cal">
      <div class="row cal-head"><div class="tabs month-switch" role="group" aria-label="Месяц">
          <button type="button" data-mv="-1" title="Предыдущий месяц" aria-label="Предыдущий месяц">${icon('chevronLeft')}</button>
          <span class="month-label">${MONTHS[m.getMonth()]} ${m.getFullYear()}</span>
          <button type="button" data-mv="1" title="Следующий месяц" aria-label="Следующий месяц">${icon('chevronRight')}</button></div>
        <button class="btn" data-mv="0">Сегодня</button><span class="spacer"></span>
        <span class="small muted"><span class="cal-key"></span> событие <span class="cal-key suggested"></span> дата из разговора, ещё не в календаре</span></div>
      <div class="cal-grid">${['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((w) => `<div class="cal-wd">${w}</div>`).join('')}${cells.join('')}</div></div>`;
    $$('[data-mv]', body).forEach((b) => b.onclick = () => {
      const mv = +b.dataset.mv;
      this.month = mv ? new Date(m.getFullYear(), m.getMonth() + mv, 1) : new Date(today.getFullYear(), today.getMonth(), 1);
      this.draw(root);
    });
    $$('.cal-ev', body).forEach((b) => b.onclick = () => {
      const t = this.items.find((x) => x.id === +b.dataset.id);
      openTask(t, 'calendar', () => this.load(root), { add: !t.event });  // a dashed date: the event form is ready to confirm
    });
  },
  async drawMap(root, body, items) {
    body.innerHTML = LOADER;
    const key = await mapsKey();
    if (!key) return mapsKeyForm(body, () => this.draw(root));
    let ym;
    try { ym = await loadYmaps(key); } catch (e) { body.innerHTML = `<div class="empty">${icon('alert')}<div>${esc(e.message)}</div></div>`; return; }
    if (this.tab !== 'map') return;
    const placed = items.filter((t) => t.geo);
    body.innerHTML = '<div class="tasks-map"><div class="map-box" id="tmap"></div></div>';
    const map = new ym.Map($('#tmap', body), { center: [55.751, 37.618], zoom: 10, controls: ['zoomControl', 'fullscreenControl'] });
    for (const t of placed) {  // a marker opens its event card
      const pm = new ym.Placemark([t.geo.lat, t.geo.lon], { hintContent: esc(t.event?.title || t.title) },
        { preset: t.status === 'done' ? 'islands#grayCircleDotIcon' : 'islands#violetCircleDotIcon', hasBalloon: false });
      pm.events.add('click', () => openTask(t, 'map', () => this.load(root)));
      map.geoObjects.add(pm);
    }
    if (placed.length > 1) map.setBounds(map.geoObjects.getBounds(), { checkZoomRange: true, zoomMargin: 40 });
    else if (placed.length === 1) map.setCenter([placed[0].geo.lat, placed[0].geo.lon], 14);
  },
  onEvent(ev, root) { if (ev.event === 'tasks.updated') this.load(root); },
};

function taskActions(t, done) {
  return [
    { label: 'Календарь', icon: 'calendar', run: () => openTask(t, 'calendar', done) },
    { label: 'Карта', icon: 'pin', run: () => openTask(t, 'map', done) },
    t.call_id ? { label: 'Открыть звонок', icon: 'phone', run: () => showCall(t.call_id) } : null,
    { label: t.status === 'done' ? 'Вернуть в работу' : 'Выполнено', icon: 'check', run: async () => { await api('/tasks/' + t.id, { method: 'PUT', body: { status: t.status === 'done' ? 'open' : 'done' } }); done(); } },
    '-',
    { label: 'Удалить', icon: 'trash', danger: true, run: () => confirmBox(`Удалить дело «${t.title}»?`, async () => { await api('/tasks/' + t.id, { method: 'DELETE' }); done(); }) },
  ];
}

// The task drawer: three tabs — «Дело», «Календарь», «Карта». The task is the main thing; its calendar event and
// its place on the map hang off it and can be added («+») or removed without touching the task. Each tab ends
// with its own panel that manages just that thing. tab: 'task' | 'calendar' | 'map'; add: open the form of
// a missing event / place right away (e.g. from a dashed date in the calendar).
function openTask(t, tab = 'task', done, { add = false } = {}) {
  if (!t?.id) return newTask(done);
  const TABS = ['task', 'calendar', 'map'];
  const tabLabel = (k) => ({ task: 'Дело', calendar: 'Календарь', map: 'Карта' }[k])
    + ((k === 'calendar' && !t.event) || (k === 'map' && !t.geo) ? ' <span class="tab-plus" title="Ещё нет — можно добавить">+</span>' : '');
  const bar = (ic, label, left, right) => `<div class="entity-bar"><span class="entity-label">${icon(ic)} ${label}</span>${left}<span class="spacer"></span>${right}</div>`;
  const m = modal({
    title: esc(t.title), size: 'lg',
    body: `<div class="tabs drawer-tabs" role="tablist" data-tabs>${TABS.map((k, i) => `<button type="button" role="tab" data-tab="${i}">${tabLabel(k)}</button>`).join('')}</div>
      <section class="tab-pane" data-pane="0" role="tabpanel"></section>
      <section class="tab-pane" data-pane="1" role="tabpanel" hidden></section>
      <section class="tab-pane" data-pane="2" role="tabpanel" hidden></section>`,
  }).el;
  const pane = (k) => $(`[data-pane="${TABS.indexOf(k)}"]`, m);
  const changed = (fresh) => {  // after saving: the drawer stays, its tabs and the list follow
    if (fresh) Object.assign(t, fresh);
    $('.modal-head h2', m).textContent = t.title;
    TABS.forEach((k, i) => { $(`[data-tab="${i}"]`, m).innerHTML = tabLabel(k); });
    done?.();
  };
  const close = () => $('[data-close]', m)?.click();
  // the call the task came from: its widget (who, when, the player) at the top of «Дело»; «⋮» opens the call
  const callWidget = async (el) => {
    const slot = $('[data-callw]', el);
    if (!slot) return;
    let c;
    try { c = await api('/calls/' + t.call_id); } catch { slot.remove(); return; }
    slot.innerHTML = VIEWS.calls.card(c);
    $$('.call-summary', slot).forEach((x) => x.remove());  // only the call and its player: the task is the summary here
    const k = $('.kebab', slot);
    if (k) k.onclick = (e) => { e.stopPropagation(); openMenu(k, [
      { label: 'Открыть звонок', icon: 'eye', run: () => showCall(c.id) },
      c.recording ? { label: 'Скачать аудиофайл', icon: 'download', run: () => downloadRecording(c) } : null,
    ]); };
  };
  const busy = (btn, fn) => guard(async () => { const l = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spin"></span>'; try { await fn(); } finally { btn.disabled = false; btn.innerHTML = l; } });

  // ---- «Дело»
  const drawTask = () => {
    const el = pane('task'), due = t.due_at || '', isDone = t.status === 'done';
    el.innerHTML = `${t.call_id ? '<div class="task-call" data-callw></div>' : ''}<form class="form" id="tf">
      <div class="field"><label>Что сделать</label><input name="title" value="${esc(t.title)}" required></div>
      <div class="field"><label>Подробности</label><textarea name="details" rows="3">${esc(t.details)}</textarea></div>
      <div class="form-2"><div class="field"><label>С кем</label><input name="number" value="${esc(t.number)}" placeholder="Номер или имя контакта"></div>
        <div class="field"><label>Кто делает</label><input name="assignee" value="${esc(t.assignee)}" placeholder="я, собеседник…"></div></div>
      <div class="form-2"><div class="field"><label>Срок</label><input type="date" name="due_date" value="${esc(due.slice(0, 10))}"></div>
        <div class="field"><label>Время</label><input type="time" name="due_time" value="${esc(due.slice(11, 16))}"></div></div>
      ${t.due_text ? `<span class="hint">В разговоре: «${esc(t.due_text)}»</span>` : ''}
      <div class="field"><label>Место</label><input name="place" value="${esc(t.place)}" placeholder="Как назвали в разговоре"></div></form>
      ${bar('tasks', 'Дело', `<button type="button" class="btn btn-ghost ${isDone ? '' : 'ok-text'}" data-done>${icon(isDone ? 'refresh' : 'check')} ${isDone ? 'Вернуть в работу' : 'Выполнено'}</button>
         <button type="button" class="btn btn-ghost danger-text" data-del>${icon('trash')} Удалить</button>`,
        `<button type="button" class="btn btn-primary" data-save>Сохранить</button>`)}`;
    attachContactSuggest($('[name=number]', el));
    callWidget(el);
    $('[data-save]', el).onclick = busy($('[data-save]', el), async () => {
      const f = formData($('#tf', el));
      if (!f.title.trim()) throw new Error('Укажите, что нужно сделать');
      const c = findContact(f.number) || state.contacts.find((x) => fullName(x) === f.number.trim());
      changed(await api('/tasks/' + t.id, { method: 'PUT', body: { title: f.title.trim(), details: f.details, assignee: f.assignee, place: f.place,
        number: c ? c.phone : f.number.trim(), due_at: f.due_date ? f.due_date + (f.due_time ? 'T' + f.due_time : '') : '' } }));
      toast('Дело сохранено', 'ok');
    });
    $('[data-done]', el).onclick = busy($('[data-done]', el), async () => {
      if (isDone) { changed(await api('/tasks/' + t.id, { method: 'PUT', body: { status: 'open' } })); drawTask(); toast('Дело снова в работе', 'ok'); return; }
      close();
      VIEWS.tasks.complete(t, () => done?.());  // the same 10-second «Отменить» as the checkbox in the list
    });
    $('[data-del]', el).onclick = () => confirmBox(`Удалить дело «${t.title}» вместе с событием и местом?`, async () => {
      await api('/tasks/' + t.id, { method: 'DELETE' }); close(); done?.();
    });
  };

  // ---- «Календарь»: the event of the task
  const drawCalendar = (adding = false) => {
    const el = pane('calendar');
    if (!t.event && !adding) {
      el.innerHTML = `<div class="entity-empty">${icon('calendar')}<div>У дела нет события в календаре</div>
        <button type="button" class="btn btn-primary" data-add>${icon('plus')} Добавить событие</button>
        <span class="small muted">Форма заполнится по сроку дела${t.due_text ? ` («${esc(t.due_text)}»)` : ''} — останется проверить.</span></div>`;
      $('[data-add]', el).onclick = () => drawCalendar(true);
      return;
    }
    let ev = t.event;
    if (!ev) {
      const d = parseLocal(t.due_at) || (() => { const x = new Date(); x.setDate(x.getDate() + 1); x.setHours(10, 0, 0, 0); return x; })();
      const allDay = (t.due_at || '').length === 10;
      const end = new Date(d); allDay ? end.setDate(end.getDate() + 1) : end.setHours(end.getHours() + 1);
      const who = t.contact_name || '';
      ev = { title: t.title + (who && !t.title.includes(who.split(' ')[0]) ? ` — ${who}` : ''), start: isoLocal(d), end: isoLocal(end), all_day: allDay, notes: t.details || '' };
    }
    el.innerHTML = `<form class="form" id="ef">
      ${t.event ? '' : '<p class="small muted" style="margin:0">Заполнено по разговору — проверьте и сохраните.</p>'}
      <div class="field"><label>Название события</label><input name="title" value="${esc(ev.title)}" required></div>
      <div class="form-3"><div class="field"><label>Дата</label><input type="date" name="date" value="${ev.start.slice(0, 10)}" required></div>
        <div class="field"><label>Начало</label><input type="time" name="start" value="${ev.start.slice(11, 16)}"></div>
        <div class="field"><label>Конец</label><input type="time" name="end" value="${ev.end.slice(11, 16)}"></div></div>
      <label class="switch"><input type="checkbox" name="all_day" ${ev.all_day ? 'checked' : ''}> Весь день</label>
      ${t.due_text ? `<span class="hint">В разговоре: «${esc(t.due_text)}»</span>` : ''}
      <div class="field"><label>Заметка</label><textarea name="notes" rows="3">${esc(ev.notes)}</textarea></div></form>
      ${bar('calendar', 'Событие',
        t.event ? `<button type="button" class="btn btn-ghost danger-text" data-del>${icon('trash')} Удалить событие</button>` : `<button type="button" class="btn btn-ghost" data-cancel>Отмена</button>`,
        `<button type="button" class="btn btn-primary" data-save>${t.event ? 'Сохранить событие' : 'Добавить в календарь'}</button>`)}`;
    const sync = () => { const all = $('[name=all_day]', el).checked; $$('[name=start],[name=end]', el).forEach((i) => { i.disabled = all; }); };
    $('[name=all_day]', el).onchange = sync; sync();
    $('[data-cancel]', el)?.addEventListener('click', () => drawCalendar(false));
    $('[data-save]', el).onclick = busy($('[data-save]', el), async () => {
      const f = formData($('#ef', el));
      if (!f.title.trim() || !f.date) throw new Error('Укажите название и дату');
      const start = f.date + 'T' + (f.all_day ? '00:00' : f.start || '10:00');
      let end = f.date + 'T' + (f.all_day ? '23:59' : f.end || f.start || '11:00');
      if (end < start) end = start;
      const was = !!t.event;
      changed(await api('/tasks/' + t.id, { method: 'PUT', body: { event: { title: f.title.trim(), start, end, all_day: !!f.all_day, notes: f.notes } } }));
      drawCalendar();
      toast(was ? 'Событие сохранено' : 'Событие добавлено в календарь', 'ok');
    });
    $('[data-del]', el)?.addEventListener('click', () => confirmBox('Удалить событие из календаря? Дело останется.', async () => {
      changed(await api(`/tasks/${t.id}/event`, { method: 'DELETE' })); drawCalendar();
    }));
  };

  // ---- «Карта»: the place of the task
  const drawMap = async (adding = false) => {
    const el = pane('map');
    if (!t.geo && !adding) {
      el.innerHTML = `<div class="entity-empty">${icon('pin')}<div>У дела нет места на карте</div>
        <button type="button" class="btn btn-primary" data-add>${icon('plus')} Добавить место</button>
        ${t.place ? `<span class="small muted">В разговоре назвали: «${esc(t.place)}» — найдём его на карте.</span>` : ''}</div>`;
      $('[data-add]', el).onclick = () => drawMap(true);
      return;
    }
    const key = await mapsKey();
    if (!key) {
      el.innerHTML = `<div class="entity-empty">${icon('pin')}<div>Для карты нужен ключ API Яндекс Карт</div>
        <a class="btn" href="#/settings?tab=maps">Настройки → Яндекс Карты</a></div>`;
      return;
    }
    const address = t.geo?.address || t.place || '';
    el.innerHTML = `<form class="form" id="gf">
      <div class="field"><label>Адрес</label><div class="row" style="gap:8px;flex-wrap:nowrap">
          <input name="address" value="${esc(address)}" placeholder="Адрес или название места" style="flex:1" autocomplete="off">
          <button type="button" class="btn" data-find>${icon('search')} Найти</button></div>
        <span class="hint" data-info>Точку можно перетащить или кликнуть по карте в нужном месте.</span></div>
      <div class="map-box map-form" data-map></div></form>
      ${bar('pin', 'Место',
        t.geo ? `<button type="button" class="btn btn-ghost danger-text" data-del>${icon('trash')} Удалить место</button>` : `<button type="button" class="btn btn-ghost" data-cancel>Отмена</button>`,
        `<button type="button" class="btn btn-primary" data-save>${t.geo ? 'Сохранить место' : 'Добавить на карту'}</button>`)}`;
    $('[data-cancel]', el)?.addEventListener('click', () => drawMap(false));
    $('[data-del]', el)?.addEventListener('click', () => confirmBox('Убрать место с карты? Дело останется.', async () => {
      changed(await api(`/tasks/${t.id}/geo`, { method: 'DELETE' })); drawMap();
    }));
    const box = $('[data-map]', el), info = $('[data-info]', el), addr = $('[name=address]', el);
    let point = t.geo ? [t.geo.lat, t.geo.lon] : null;
    $('[data-save]', el).onclick = busy($('[data-save]', el), async () => {
      if (!point) throw new Error('Найдите адрес или поставьте точку на карте');
      const was = !!t.geo;
      changed(await api('/tasks/' + t.id, { method: 'PUT', body: { geo: { address: addr.value.trim(), lat: point[0], lon: point[1] } } }));
      drawMap();
      toast(was ? 'Место сохранено' : 'Место добавлено на карту', 'ok');
    });
    let ym;
    try { ym = await loadYmaps(key); } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
    const map = new ym.Map(box, { center: point || [55.751, 37.618], zoom: point ? 15 : 10, controls: ['zoomControl'] });
    const mark = new ym.Placemark(point || [55.751, 37.618], {}, { draggable: true, preset: 'islands#violetDotIcon', visible: !!point });
    map.geoObjects.add(mark);
    const setPoint = (p, why) => { point = p; mark.geometry.setCoordinates(p); mark.options.set('visible', true); info.textContent = `${why} · ${p[0].toFixed(5)}, ${p[1].toFixed(5)}`; };
    mark.events.add('dragend', () => setPoint(mark.geometry.getCoordinates(), 'Точка перенесена'));
    map.events.add('click', (e) => setPoint(e.get('coords'), 'Точка поставлена вручную'));
    const find = async () => {
      const q = addr.value.trim();
      if (!q) return;
      info.textContent = 'Ищем адрес…';
      try {
        const res = await ym.geocode(q, { results: 1 });
        const obj = res.geoObjects.get(0);
        if (!obj) { info.textContent = 'Адрес не найден — уточните его или поставьте точку кликом по карте.'; return; }
        const p = obj.geometry.getCoordinates();
        setPoint(p, `Найдено: ${obj.getAddressLine()}`);
        map.setCenter(p, 16);
      } catch (e) { info.textContent = 'Геокодер не ответил: ' + (e?.message || e); }
    };
    $('[data-find]', el).onclick = find;
    addr.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); find(); } };
    if (!point && addr.value.trim()) find();
  };

  const drawn = {};
  setupDrawerTabs(m, (i) => {
    const k = TABS[i];
    if (drawn[k]) return;
    drawn[k] = true;  // drawn when first shown: the map needs a visible box
    if (k === 'task') drawTask(); else if (k === 'calendar') drawCalendar(add); else drawMap(add);
  });
  m.showTab(Math.max(0, TABS.indexOf(tab)));
}

// a new task added by hand: just the task; the event and the place are added in its drawer afterwards
function newTask(done) {
  modal({
    title: 'Новое дело',
    body: `<form class="form" id="tf">
      <div class="field"><label>Что сделать *</label><input name="title" required></div>
      <div class="field"><label>Подробности</label><textarea name="details" rows="3"></textarea></div>
      <div class="form-2"><div class="field"><label>С кем</label><input name="number" placeholder="Номер или имя контакта"></div>
        <div class="field"><label>Кто делает</label><input name="assignee" placeholder="я, собеседник…"></div></div>
      <div class="form-2"><div class="field"><label>Срок</label><input type="date" name="due_date"></div>
        <div class="field"><label>Время</label><input type="time" name="due_time"></div></div>
      <div class="field"><label>Место</label><input name="place" placeholder="Адрес или название места"></div></form>`,
    onMount: (m) => { attachContactSuggest($('[name=number]', m)); $('[name=title]', m).focus(); },
    buttons: [{ label: 'Отмена', cls: 'btn-ghost' }, { label: 'Создать', cls: 'btn-primary', onClick: async (m) => {
      const f = formData($('#tf', m));
      if (!f.title.trim()) throw new Error('Укажите, что нужно сделать');
      const c = findContact(f.number) || state.contacts.find((x) => fullName(x) === f.number.trim());
      await api('/tasks', { method: 'POST', body: { title: f.title.trim(), details: f.details, assignee: f.assignee, place: f.place,
        number: c ? c.phone : f.number.trim(), due_at: f.due_date ? f.due_date + (f.due_time ? 'T' + f.due_time : '') : '' } });
      toast('Дело добавлено', 'ok'); done?.();
    } }],
  });
}

VIEWS.contacts = {
  title: 'Контакты', icon: 'book',
  async render(root, params = new URLSearchParams()) {
    setActions(`<button class="btn" id="import">${icon('upload')} Импорт CSV</button>
      <button class="btn btn-primary" id="add">${icon('plus')} Контакт</button>`);
    root.innerHTML = `<div class="card hub-side wide">
      <nav class="tag-rail" id="tags" aria-label="Теги"></nav>
      <div class="hub-table"><div class="card-head"><input id="q" type="search" placeholder="Поиск" style="max-width:360px"></div>
      <div class="table-wrap"><table><thead><tr><th class="avatar-cell"></th><th>Имя</th><th>Телефон</th><th>Компания</th><th>Теги</th><th>Комментарий</th><th></th></tr></thead><tbody id="rows"></tbody></table></div></div></div>`;
    let timer;
    if (params.get('q')) { $('#q', root).value = params.get('q'); localStorage.setItem('caller.tag', ''); }  // a link: the search, all tags
    $('#q', root).oninput = () => { clearTimeout(timer); timer = setTimeout(() => this.load(root), 250); };
    $('#add').onclick = () => editContact({}, () => this.load(root));
    $('#import').onclick = () => importContacts(() => this.load(root));
    await this.load(root);
  },
  async load(root) {
    const q = $('#q', root).value;
    const [contacts, calls, sms] = await Promise.all([api('/contacts'), api('/calls/threads'), api('/sms/threads')]);
    state.contacts = contacts;  // tags may have changed — the rail follows
    const news = {};  // unseen calls + unread SMS per contact, for the folder badges
    for (const t of calls) if (t.unseen && t.contact_id) news[t.contact_id] = (news[t.contact_id] || 0) + t.unseen;
    for (const t of sms) if (t.unread && t.contact_id) news[t.contact_id] = (news[t.contact_id] || 0) + t.unread;
    tagRail($('#tags', root), () => this.load(root), tagCounts(contacts.map((c) => ({ number: c.phone, n: news[c.id] || 0 })), (x) => x.n));
    const tag = currentTag();
    const list = (q ? await api('/contacts?q=' + encodeURIComponent(q)) : state.contacts).filter((c) => !tag || contactTags(c).includes(tag));
    $('#rows', root).innerHTML = list.map((c) => `<tr class="clickable" data-id="${c.id}">
      <td class="avatar-cell"><div class="avatar"${avatarStyle(fullName(c) || '#')}>${esc(initials(fullName(c) || '#'))}</div></td>
      <td style="max-width:260px">${entityCell(fullName(c), c.is_self ? 'Этот номер · это вы' : c.relation || '')}</td>
      <td>${esc(c.phone)}</td><td>${esc(c.company) || dash}</td>
      <td>${(c.tags || '').split(',').filter(Boolean).map((t) => `<span class="chip">${esc(t.trim())}</span>`).join(' ') || dash}</td>
      <td class="ellipsis" style="max-width:240px" title="${esc(c.notes)}">${esc(c.notes) || dash}</td>
      <td class="kebab-cell">${KEBAB}</td></tr>`).join('')
      || `<tr><td colspan="7" class="empty">${icon('book')}<div>${tag ? 'С этим тегом контактов нет' : 'Контактов нет'}</div></td></tr>`;
    const byId = (id) => list.find((c) => c.id === id);
    bindRows(root, {
      open: (id) => editContact(byId(id), () => this.load(root)),
      actions: (id) => [
        { label: 'Редактировать', icon: 'edit', run: () => editContact(byId(id), () => this.load(root), 1) },
        '-',
        { label: 'Звонок агентом', icon: 'bot', run: () => { location.hash = `#/calls?number=${encodeURIComponent(byId(id).phone)}`; } },
        { label: 'Позвонить', icon: 'phoneOut', run: () => { location.hash = `#/calls?mode=browser&number=${encodeURIComponent(byId(id).phone)}`; } },
        { label: 'Написать SMS', icon: 'message', run: () => { location.hash = `#/sms?number=${encodeURIComponent(byId(id).phone)}`; } },
        '-',
        ...historyMenuItems(byId(id).phone, () => this.load(root)),
        ...(byId(id).is_self ? [] : ['-',  // «Этот номер» stays
          { label: 'Удалить', icon: 'trash', danger: true, run: () => confirmBox('Удалить контакт?', async () => { await api('/contacts/' + id, { method: 'DELETE' }); this.load(root); }) }]),
      ],
    });
  },
};

// the contact card: «Контакт» (the fields) and, for a saved contact, «ИИ-ассистент» — calls, summaries, SMS and an AI chat
// one extra field of a contact in its form: «ключ — значение» and a remove button
const kvFieldRow = (f = {}) => `<div class="kv-row"><input data-k="key" value="${esc(f.key || '')}" placeholder="Название: день рождения" autocomplete="off">
  <input data-k="value" value="${esc(f.value || '')}" placeholder="Значение" autocomplete="off">
  <button type="button" class="btn btn-ghost btn-icon" data-rm title="Удалить поле" aria-label="Удалить поле">${icon('x')}</button></div>`;

function editContact(c, done, tab = 0) {
  const form = `<form class="form" id="cf"><div class="form-2">
      <div class="field"><label>Имя *</label><input name="name" value="${esc(c.name)}"></div>
      <div class="field"><label>Фамилия</label><input name="last_name" value="${esc(c.last_name)}"></div>
      <div class="field"><label>Телефон *</label><input name="phone" value="${esc(c.phone)}" placeholder="+7…">
        ${c.is_self ? '<span class="hint">Номер SIM-карты Caller — тот же, что в «Настройки → Оператор». Меняется в обоих местах.</span>' : ''}</div>
      <div class="field"><label>Компания</label><input name="company" value="${esc(c.company)}"></div>
      <div class="field"><label>E-mail</label><input name="email" value="${esc(c.email)}"></div></div>
      <div class="field"><label>Адрес</label><input name="address" value="${esc(c.address)}" placeholder="Город, улица, дом — или СНТ, участок">
        ${c.is_self ? '<span class="hint">Агент назовёт адрес и поля этой карточки только в скиллах с отметкой «Знает адрес из „Этот номер“» — например, курьеру. В остальных разговорах он его не знает.</span>' : ''}</div>
      ${c.is_self ? `<p class="small muted" style="margin:0">Это вы. Имя отсюда агент называет как имя хозяина. Добавьте свои поля, которые пригодятся скиллам: «Как доехать», «Код ворот», «Где оставлять посылки».</p>` : `
      <div class="field"><label>Связь со звонящим</label><input name="relation" value="${esc(c.relation)}" placeholder="Мама, жена, директор…">
        <span class="hint">Кем человек приходится вам — владельцу системы. Агент будет говорить с ним с учётом этого.</span></div>`}
      <div class="field"><label>Теги</label><input type="hidden" name="tags" value="${esc(c.tags)}" data-tag-input></div>
      <div class="field"><label>Свои поля</label>
        <div class="kv-fields" id="kv-fields">${(c.fields || []).map(kvFieldRow).join('')}</div>
        <div><button type="button" class="btn btn-ghost btn-sm" id="kv-add">${icon('plus')} Добавить поле</button></div></div>
      <div class="field"><label>Комментарий</label><textarea name="notes" placeholder="Что важно знать агенту о человеке: как обращаться, история общения, договорённости…">${esc(c.notes)}</textarea>
        <span class="hint">Все поля карточки, включая свои, передаются голосовому агенту во время звонка с этим контактом. Агент учитывает их, но не зачитывает дословно.</span></div></form>`;
  modal({
    title: c.id ? fullName(c) || 'Контакт' : 'Новый контакт', size: c.id ? 'lg' : '',
    body: !c.id ? form : `<div class="tabs drawer-tabs" role="tablist" data-tabs>
        <button type="button" role="tab" data-tab="0" class="active">ИИ-ассистент</button>
        <button type="button" role="tab" data-tab="1">Контакт</button></div>
      <section class="tab-pane" data-pane="1" role="tabpanel" hidden>${form}</section>
      <section class="tab-pane history-pane" data-pane="0" role="tabpanel">
        <div class="history">
          <div class="hist-feed" id="hist-feed">${LOADER}</div>
          <form class="hist-compose" id="hist-ask"><textarea id="hist-q" rows="1" placeholder="Спросите ИИ об истории общения: «когда мы договорились встретиться?»"></textarea>
            <button class="btn btn-primary btn-icon" type="submit" title="Спросить">${icon('send')}</button></form></div>
      </section>`,
    onMount: (m) => {
      const tagsIn = $('[data-tag-input]', m);
      if (tagsIn) tagInput(tagsIn);
      // the contact's own fields: key — value rows, × removes one
      const kv = $('#kv-fields', m);
      $('#kv-add', m).onclick = () => { kv.insertAdjacentHTML('beforeend', kvFieldRow()); $$('[data-k=key]', kv).pop().focus(); };
      kv.onclick = (e) => { const x = e.target.closest('[data-rm]'); if (x) x.closest('.kv-row').remove(); };
      if (!c.id) return;
      let loaded = false;
      const foot = $('.modal-foot', m);
      setupDrawerTabs(m, (i) => {
        if (foot) foot.hidden = i === 0;  // the chat has its own input; «Сохранить» belongs to the fields
        if (i === 0 && !loaded) { loaded = true; contactHistory(m, c); }
      });
      m.showTab(tab);  // «ИИ-ассистент» first; the fields are the second tab
    },
    buttons: [{ label: 'Отмена', cls: 'btn-ghost' }, { label: 'Сохранить', cls: 'btn-primary', onClick: async (m) => {
      const body = formData($('form#cf', m) || $('form', m));
      delete body.undefined;
      body.fields = $$('#kv-fields .kv-row', m).map((row) => ({ key: $('[data-k=key]', row).value.trim(), value: $('[data-k=value]', row).value.trim() }))
        .filter((f) => f.key);
      await api(c.id ? '/contacts/' + c.id : '/contacts', { method: c.id ? 'PUT' : 'POST', body });
      toast('Сохранено', 'ok'); done();
    } }],
  });
}

// Tag input: a multiselect with typing. The tags show as chips with «×»; typing suggests the existing tags
// (from all contacts) and offers to create a new one; Enter / comma / Tab adds, Backspace in an empty field removes
// the last chip. The value goes to the hidden input as «тег1, тег2» — the format the contacts store.
// suggest(): the known values to offer (the contacts' tags by default); onChange(tags) after every change
function tagInput(hidden, { suggest = allTags, placeholder = 'Добавить тег…', create = (t) => `Создать тег «${t}»`, onChange } = {}) {
  let tags = (hidden.value || '').split(',').map((t) => t.trim()).filter(Boolean);
  const box = document.createElement('div');
  box.className = 'tag-input';
  box.innerHTML = `<span class="chips"></span><input type="text" autocomplete="off" placeholder="${esc(placeholder)}"><div class="suggest" hidden></div>`;
  hidden.after(box);
  const chips = $('.chips', box), input = $('input', box), menu = $('.suggest', box);
  let items = [], idx = 0;
  const sync = () => {
    hidden.value = tags.join(', ');
    chips.innerHTML = tags.map((t, i) => `<span class="chip-tag">${esc(t)}<button type="button" data-rm="${i}" title="Убрать">${icon('x')}</button></span>`).join('');
    input.placeholder = tags.length ? '' : placeholder;
    onChange?.(tags);
  };
  const hide = () => { menu.hidden = true; items = []; };
  const add = (t) => {
    t = t.trim().replace(/,/g, ' ').replace(/\s+/g, ' ');
    if (t && !tags.some((x) => x.toLowerCase() === t.toLowerCase())) tags.push(t);
    input.value = ''; sync(); hide(); input.focus();
  };
  const render = () => {
    const q = input.value.trim().toLowerCase();
    const known = suggest().filter((t) => !tags.some((x) => x.toLowerCase() === t.toLowerCase()) && (!q || t.toLowerCase().includes(q)));
    items = known.slice(0, 8).map((t) => ({ tag: t, label: t }));
    if (q && !suggest().some((t) => t.toLowerCase() === q) && !tags.some((x) => x.toLowerCase() === q)) {
      items.push({ tag: input.value.trim(), label: create(input.value.trim()), create: true });
    }
    if (!items.length) { hide(); return; }
    idx = Math.min(idx, items.length - 1);
    menu.innerHTML = items.map((it, i) => `<div class="suggest-item ${i === idx ? 'active' : ''}" data-i="${i}">${it.create ? icon('plus') : icon('tag')}<span>${esc(it.label)}</span></div>`).join('');
    menu.hidden = false;
    // fixed to the screen: a drawer's scroll area or footer must not clip it; upwards if there's no room below
    const r = box.getBoundingClientRect(), h = menu.offsetHeight;
    const below = innerHeight - r.bottom - 8;
    menu.style.cssText = `position:fixed;left:${r.left}px;width:${r.width}px;right:auto;z-index:60;margin:0;`
      + (below >= Math.min(h, 220) || below >= r.top ? `top:${r.bottom + 4}px;bottom:auto;` : `top:auto;bottom:${innerHeight - r.top + 4}px;`);
  };
  box.onclick = (e) => {
    const rm = e.target.closest('[data-rm]');
    if (rm) { tags.splice(+rm.dataset.rm, 1); sync(); render(); return; }
    input.focus();
  };
  menu.onmousedown = (e) => {  // mousedown: before the input loses focus
    const it = e.target.closest('[data-i]');
    if (it) { e.preventDefault(); add(items[+it.dataset.i].tag); }
  };
  input.onfocus = () => { idx = 0; render(); };
  box.closest('.modal-body')?.addEventListener('scroll', () => { if (!menu.hidden) render(); });
  input.oninput = () => { idx = 0; render(); };
  input.onblur = () => setTimeout(() => { if (input.value.trim()) add(input.value); hide(); }, 120);
  input.onkeydown = (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!items.length) return;
      e.preventDefault();
      idx = (idx + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      render();
    } else if (e.key === 'Enter' || e.key === ',' || (e.key === 'Tab' && input.value.trim())) {
      e.preventDefault();
      if (!menu.hidden && items[idx] && (e.key !== ',' || !input.value.trim())) add(items[idx].tag);
      else if (input.value.trim()) add(input.value);
    } else if (e.key === 'Backspace' && !input.value && tags.length) {
      tags.pop(); sync(); render();
    } else if (e.key === 'Escape' && !menu.hidden) {
      e.stopPropagation(); hide();
    }
  };
  sync();
}

// «ИИ-ассистент» of a contact: a chat feed — calls (player + summary), SMS and the AI's answers on the left,
// the user's questions and sent SMS on the right; the AI answers from the whole history of dealings
async function contactHistory(m, c) {
  const feed = $('#hist-feed', m), q = $('#hist-q', m);
  const time = (ts) => (ts ? fmtDate(ts) : '');
  const bubble = (side, text, meta, cls = '') => `<div class="hist-row ${side}"><div class="bubble ${cls}">${esc(text)}<div class="meta">${meta}</div></div></div>`;
  const render = (items) => {
    feed.innerHTML = items.map((it) => {
      if (it.kind === 'call') return `<div class="hist-row left"><div class="hist-call">${VIEWS.calls.card(it.call)}</div></div>`;
      if (it.kind === 'sms') {
        const x = it.sms, out = x.direction === 'out';
        return bubble(out ? 'right' : 'left', x.text, `SMS · ${time(x.ts)}${out && x.status !== 'sent' ? ' · ' + esc(x.status) : ''}${x.forgotten ? ' · не в истории агента' : ''}`, out ? 'me sms' : 'sms');
      }
      const x = it.chat;
      if (x.role === 'user') return bubble('right', x.text, `Вы · ${time(x.created_at)}`, 'me');
      return bubble('left', x.text, `ИИ · ${time(x.created_at)}${x.tokens_in ? ` · ${fmtInt(x.tokens_in + x.tokens_out)} ${plural(x.tokens_in + x.tokens_out, 'токен', 'токена', 'токенов')}` : ''}`, x.error ? 'ai err' : 'ai');
    }).join('') || `<div class="empty small">${icon('message')}<div>С этим контактом ещё не общались. Когда будут звонки и SMS, здесь появится история — и ИИ сможет отвечать на вопросы по ней.</div></div>`;
    $$('.hist-call .call-card', feed).forEach((el) => {
      const k = $('.kebab', el), id = +el.dataset.id;
      const call = items.find((it) => it.kind === 'call' && it.call.id === id)?.call;
      if (k) k.onclick = (e) => { e.stopPropagation(); openMenu(k, callMenuItems(call || { id }, load)); };  // the same menu as elsewhere
    });
    feed.scrollTop = feed.scrollHeight;
  };
  const load = async () => render((await api(`/contacts/${c.id}/history`)).items);
  await load();
  q.onkeydown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#hist-ask', m).requestSubmit(); } };
  q.oninput = () => { q.style.height = 'auto'; q.style.height = Math.min(q.scrollHeight, 140) + 'px'; };
  $('#hist-ask', m).onsubmit = guard(async (e) => {
    e.preventDefault();
    const question = q.value.trim();
    if (!question) return;
    q.value = ''; q.oninput();
    const btn = $('#hist-ask button', m); btn.disabled = true;
    feed.insertAdjacentHTML('beforeend', bubble('right', question, 'Вы · сейчас', 'me')
      + '<div class="hist-row left" id="hist-wait"><div class="asst-typing" title="ИИ смотрит историю…"><span></span><span></span><span></span></div></div>');
    feed.scrollTop = feed.scrollHeight;
    try { await api(`/contacts/${c.id}/history/ask`, { method: 'POST', body: { question } }); } finally {
      btn.disabled = false;
      await load();
      q.focus();
    }
  });
  // clearing the chat (calls and SMS stay)
}

function importContacts(done) {
  modal({
    title: 'Импорт контактов',
    body: `<div class="form"><p class="muted small">CSV с колонками: <code>name,last_name,phone,company,tags,notes</code> (первая строка — заголовок). Разделитель — запятая или точка с запятой.</p>
      <input type="file" id="csv" accept=".csv,text/csv"></div>`,
    buttons: [{ label: 'Отмена', cls: 'btn-ghost' }, { label: 'Импортировать', cls: 'btn-primary', onClick: async (m) => {
      const file = $('#csv', m).files[0]; if (!file) throw new Error('Выберите файл');
      const lines = (await file.text()).split(/\r?\n/).filter((l) => l.trim());
      const sep = lines[0].includes(';') ? ';' : ',';
      const head = lines.shift().split(sep).map((h) => h.trim().toLowerCase());
      let n = 0;
      for (const line of lines) {
        const cols = line.split(sep).map((x) => x.trim().replace(/^"|"$/g, ''));
        const row = {}; head.forEach((h, i) => { row[h] = cols[i] || ''; });
        if (row.name && row.phone) { await api('/contacts', { method: 'POST', body: row }); n++; }
      }
      toast(`Импортировано: ${n}`, 'ok'); done();
    } }],
  });
}

// ------------------------------------------------------------------ scripts
const DIRS = { inbound: 'Входящие', outbound: 'Исходящие', any: 'Любые' };
VIEWS.scripts = {
  title: 'Сценарии', icon: 'script',
  hint: 'Сценарий — задача поверх агента: что он делает в звонке. Переменные {{имя}} подставляются при звонке, входящие распределяются по номерам звонящих.',
  async render(root) {
    await loadRefs();
    skillsCache = await api('/skills').catch(() => skillsCache || []);  // names for the «Скиллы» column
    root.innerHTML = `<div class="card"><div class="card-head">
        <input id="q" type="search" placeholder="Поиск" style="max-width:360px"></div>
      <div class="table-wrap"><table><thead><tr><th class="dir-cell"></th><th>Название</th><th>Агент</th><th>Скиллы</th><th>Переменные</th><th>Кто звонит</th><th></th></tr></thead>
        <tbody id="rows"></tbody></table></div></div>`;
    setActions(`<button class="btn btn-primary" id="add">${icon('plus')} Сценарий</button>`);
    $('#add').onclick = () => editScript({ direction: 'outbound', variables: [] }, () => this.render(root));
    $('#q', root).oninput = () => this.rows(root);
    this.rows(root);
  },
  rows(root) {
    const q = $('#q', root).value.trim().toLowerCase();
    const list = state.scripts.filter((s) => !q || [s.name, s.description, s.prompt].some((v) => (v || '').toLowerCase().includes(q)));
    const inboundContacts = (s) => {
      const names = (s.inbound_contacts || []).map((id) => state.contacts.find((c) => c.id === id)).filter(Boolean).map(fullName);
      return names.length ? `<span title="${esc(names.join(', '))}">${esc(names.slice(0, 2).join(', '))}${names.length > 2 ? ` +${names.length - 2}` : ''}</span>` : 'абоненты не выбраны';
    };
    const agentName = (id) => state.agents.find((a) => a.id === id)?.name;
    $('#rows', root).innerHTML = list.map((s) => `<tr class="clickable" data-id="${s.id}">
      <td class="dir-cell"><span class="dir-ic ${s.direction}" title="${esc(DIRS[s.direction] || s.direction)}">${icon(s.direction === 'inbound' ? 'phoneIn' : s.direction === 'outbound' ? 'phoneOut' : 'phone')}</span></td>
      <td style="max-width:300px">${entityCell(s.name, s.description || s.prompt || '')}</td>
      <td>${esc(agentName(s.default_agent_id) || 'по умолчанию')}</td>
      <td>${(s.skills || []).map((id) => (skillsCache || []).find((x) => x.id === id)).filter(Boolean).map((k) => `<span class="chip">${esc(k.name)}</span>`).join(' ') || dash}</td>
      <td class="ellipsis" style="max-width:200px" title="${esc((s.variables || []).map((v) => v.name).join(', '))}">${esc((s.variables || []).map((v) => v.name).join(', ')) || dash}</td>
      <td>${s.direction === 'outbound' ? dash
        : s.inbound_scope === 'all' ? 'все входящие'
        : s.inbound_scope === 'contacts' ? inboundContacts(s)
        : (s.inbound_numbers || []).length
          ? `<span title="${esc(s.inbound_numbers.join(', '))}">${s.inbound_numbers.slice(0, 2).map((n) => esc(n.endsWith('*') ? n : contactName(n) || n)).join(', ')}${s.inbound_numbers.length > 2 ? ` +${s.inbound_numbers.length - 2}` : ''}</span>`
          : '<span title="Сценарий работает для входящих, только если выбран по умолчанию в Настройки → Звонки">не заданы</span>'}</td>
      <td class="kebab-cell">${KEBAB}</td></tr>`).join('')
      || `<tr><td colspan="7" class="empty">${icon('script')}<div>${q ? 'Ничего не найдено' : 'Сценариев пока нет'}</div></td></tr>`;
    const byId = (id) => state.scripts.find((s) => s.id === id);
    bindRows(root, {
      open: (id) => editScript(byId(id), () => this.render(root)),
      actions: (id) => [
        byId(id).direction !== 'inbound' && { label: 'Позвонить по сценарию', icon: 'phoneOut', run: () => { location.hash = `#/calls?script=${id}`; } },
        '-',
        { label: 'Удалить', icon: 'trash', danger: true, run: () => confirmBox('Удалить сценарий?', async () => { await api('/scripts/' + id, { method: 'DELETE' }); this.render(root); }) },
      ],
    });
  },
};

// ------------------------------------------------------------------ skills
// What an agent can do in a call: knowledge and actions for a situation («Курьер», «Запись на приём»). A script
// lists its skills; in the call the agent sees «name — when to use» and loads the skill when it's needed.
VIEWS.skills = {
  title: 'Скиллы', icon: 'sparkle',
  hint: 'Скилл — что агент умеет: знание и действия под ситуацию. Сценарий выбирает свои скиллы, агент подключает нужный по ходу разговора — например, «Курьер», когда понимает, что звонит курьер.',
  async render(root) {
    setActions(`<button class="btn btn-primary" id="add">${icon('plus')} Скилл</button>`);
    root.innerHTML = `<div class="card"><div class="card-head"><input id="q" type="search" placeholder="Поиск" style="max-width:360px"></div>
      <div class="table-wrap"><table><thead><tr><th>Название</th><th>Когда применять</th><th>Сохраняет в итог</th><th>Сценарии</th><th></th></tr></thead>
        <tbody id="rows"></tbody></table></div></div>`;
    $('#add').onclick = () => editSkill({ collect: [] }, () => this.render(root));
    $('#q', root).oninput = () => this.rows(root);
    this.items = await api('/skills');
    this.rows(root);
  },
  rows(root) {
    const q = $('#q', root).value.trim().toLowerCase();
    const list = this.items.filter((x) => !q || [x.name, x.trigger, x.instructions].some((v) => (v || '').toLowerCase().includes(q)));
    $('#rows', root).innerHTML = list.map((x) => `<tr class="clickable" data-id="${x.id}">
      <td style="max-width:240px">${entityCell(x.name, [x.always ? 'подключается сразу' : '', x.knows_owner ? 'знает ваш адрес' : ''].filter(Boolean).join(' · '))}</td>
      <td class="ellipsis" style="max-width:300px" title="${esc(x.trigger)}">${esc(x.trigger) || dash}</td>
      <td>${(x.collect || []).map((c) => `<span class="chip">${esc(c)}</span>`).join(' ') || dash}${x.sms_to ? ` <span class="chip" title="Отправляет SMS-сводку на ${esc(x.sms_to)}">SMS</span>` : ''}</td>
      <td class="ellipsis" style="max-width:220px" title="${esc((x.scripts || []).join(', '))}">${esc((x.scripts || []).join(', ')) || '<span class="muted small">ни в одном</span>'}</td>
      <td class="kebab-cell">${KEBAB}</td></tr>`).join('')
      || `<tr><td colspan="5" class="empty">${icon('sparkle')}<div>${q ? 'Ничего не найдено' : 'Скиллов пока нет. Создайте первый — например, «Курьер»: как объяснить дорогу и что спросить для пропуска.'}</div></td></tr>`;
    const byId = (id) => this.items.find((x) => x.id === id);
    bindRows(root, {
      open: (id) => editSkill(byId(id), () => this.render(root)),
      actions: (id) => ['-', { label: 'Удалить', icon: 'trash', danger: true, run: () => confirmBox(`Удалить скилл «${byId(id).name}»? Он пропадёт и из сценариев.`, async () => { await api('/skills/' + id, { method: 'DELETE' }); this.render(root); }) }],
    });
  },
};

function editSkill(x, done) {
  modal({
    title: x.id ? 'Скилл' : 'Новый скилл', size: 'lg',
    body: `<form class="form" id="skf">
      <div class="field"><label>Название *</label><input name="name" value="${esc(x.name)}" placeholder="Курьер" required></div>
      <div class="field"><label>Когда применять</label><input name="trigger" value="${esc(x.trigger)}" placeholder="звонит курьер или служба доставки">
        <span class="hint">По этой строке агент понимает, что пора подключить скилл. Пишите ситуацию, а не действие.</span></div>
      <div class="field"><label>Инструкция</label><textarea name="instructions" class="code" rows="9" placeholder="Адрес: …, подъезд …, код домофона …&#10;Как подъехать: …&#10;Посылку можно оставить …&#10;Если нужен пропуск — спроси номер машины.">${esc(x.instructions)}</textarea>
        <span class="hint">Что агент должен знать и делать в этой ситуации. Подгружается в разговор, только когда нужна.</span></div>
      <div class="field"><label>Узнать и сохранить в итог звонка</label><input type="hidden" name="collect" value="${esc((x.collect || []).join(', '))}">
        <span class="hint">Агент спросит это у собеседника и запишет в итог — например, «номер машины», «время приезда».</span></div>
      <div class="field"><label>SMS-сводка на номер</label><input name="sms_to" value="${esc(x.sms_to)}" placeholder="+7 900 000-00-00 — необязательно">
        <span class="hint">Когда агент всё узнает, он отправит на этот номер короткую сводку — например, охране номер машины для пропуска.</span></div>
      <label class="switch"><input type="checkbox" name="knows_owner" ${x.knows_owner ? 'checked' : ''}> Знает адрес из контакта «Этот номер»</label>
      <span class="hint" style="margin-top:-8px">Пока скилл подключён, агент знает ваш адрес и поля карточки «Этот номер» (как доехать, код ворот…) и может назвать их собеседнику. Без отметки адреса агент не знает.</span>
      <label class="switch"><input type="checkbox" name="always" ${x.always ? 'checked' : ''}> Подключать сразу, в начале звонка</label></form>`,
    onMount: (m) => {
      tagInput($('[name=collect]', m), { placeholder: 'Добавить поле…', create: (t) => `Добавить «${t}»`,
        suggest: () => ['номер машины', 'время приезда', 'имя', 'компания', 'телефон для связи', 'адрес', 'причина звонка', 'удобное время'] });
      $('[name=name]', m).focus();
    },
    buttons: [{ label: 'Отмена', cls: 'btn-ghost' }, { label: 'Сохранить', cls: 'btn-primary', onClick: async (m) => {
      const f = formData($('#skf', m));
      if (!f.name.trim()) throw new Error('Укажите название');
      const body = { name: f.name.trim(), trigger: f.trigger.trim(), instructions: f.instructions, sms_to: f.sms_to.trim(), always: !!f.always, knows_owner: !!f.knows_owner,
        collect: f.collect.split(',').map((t) => t.trim()).filter(Boolean) };
      await api(x.id ? '/skills/' + x.id : '/skills', { method: x.id ? 'PUT' : 'POST', body });
      toast('Скилл сохранён', 'ok'); done?.();
    } }],
  });
}

const SCRIPT_TOOLS = { hangup_call: 'Сам завершает звонок', save_result: 'Сохраняет итог разговора', send_dtmf: 'Голосовое меню (DTMF)' };
// tabs inside a drawer: <div class="tabs drawer-tabs" data-tabs> buttons[data-tab] + sections.tab-pane[data-pane]
function setupDrawerTabs(m, onShow) {
  const show = (i) => {
    $$('[data-tabs] [data-tab]', m).forEach((b) => {
      const on = b.dataset.tab === String(i);
      b.classList.toggle('active', on);
      b.setAttribute('aria-selected', on);
    });
    $$('.tab-pane', m).forEach((p) => { p.hidden = p.dataset.pane !== String(i); });
    $('.modal-body', m).scrollTop = 0;
    onShow?.(+i);
  };
  $$('[data-tabs] [data-tab]', m).forEach((b) => b.onclick = () => show(b.dataset.tab));
  m.showTab = show;
  return show;
}

let skillsCache = null;  // for the script form's skills field
async function editScript(s, done) {
  skillsCache = await api('/skills').catch(() => []);
  const collect = (m) => {
    const body = formData($('#sf', m));
    const scope = body.direction === 'outbound' ? 'numbers' : body.inbound_scope;
    body.inbound_numbers = scope === 'numbers' && body.direction !== 'outbound' ? $$('#nums .chip-tag', m).map((c) => c.dataset.v) : [];
    body.inbound_contacts = scope === 'contacts' ? $$('#cts .chip-tag', m).map((c) => +c.dataset.id) : [];
    body.history = $('[name=history]', m).checked;
    body.call_tools = $$('[data-calltool]', m).filter((i) => i.checked).map((i) => i.dataset.calltool);
    const names = (body.skills_names || '').split(',').map((t) => t.trim().toLowerCase()).filter(Boolean);
    body.skills = names.map((n) => (skillsCache || []).find((x) => x.name.trim().toLowerCase() === n)?.id).filter(Boolean);
    delete body.skills_names;
    body.variables = $$('tr.var-row', m).map((r) => ({ name: $('[data-k=name]', r).value.trim(), label: $('[data-k=label]', r).value, default: $('[data-k=default]', r).value })).filter((v) => v.name);
    return body;
  };
  const varRow = (v = {}) => `<tr class="var-row">
    <td><input data-k="name" value="${esc(v.name)}" placeholder="name"></td>
    <td><input data-k="label" value="${esc(v.label)}" placeholder="Имя клиента"></td>
    <td><input data-k="default" value="${esc(v.default)}" placeholder="—"></td>
    <td class="kebab-cell"><button type="button" class="btn btn-ghost btn-icon" data-rm title="Удалить переменную">${icon('x')}</button></td></tr>`;
  const BUILTIN = ['phone', 'contact_name', 'contact_last_name', 'contact_full_name', 'contact_company', 'contact_email', 'contact_notes', 'contact_relation', 'today', 'now'];
  // only one script may take all incoming calls
  const catchAll = state.scripts.find((x) => x.id !== s.id && x.inbound_scope === 'all' && x.direction !== 'outbound');
  const scope0 = s.inbound_scope || (s.id || catchAll ? 'numbers' : 'all');
  modal({
    title: s.id ? 'Сценарий' : 'Новый сценарий', size: 'lg',
    body: `<form class="form" id="sf">
      <div class="tabs drawer-tabs" role="tablist" data-tabs>
        <button type="button" role="tab" data-tab="0" class="active">Сценарий</button>
        <button type="button" role="tab" data-tab="1">Переменные <span id="vars-count"></span></button>
        <button type="button" role="tab" data-tab="2">Предпросмотр</button></div>

      <section class="tab-pane" data-pane="0" role="tabpanel">
        <div class="form-3"><div class="field"><label>Название *</label><input name="name" value="${esc(s.name)}"></div>
          <div class="field"><label>Тип звонков</label><select name="direction">${Object.entries(DIRS).map(([k, l]) => `<option value="${k}" ${s.direction === k ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
          <div class="field"><label>Агент по умолчанию</label><select name="default_agent_id" data-type="int">${agentOptions(s.default_agent_id, '— не выбран —')}</select></div></div>
        <div class="field"><label>Описание</label><input name="description" value="${esc(s.description)}"></div>
        <div id="nums-field" class="form">
          <div class="field"><label>Кто звонит</label><select name="inbound_scope" id="scope">
            ${[['all', catchAll ? `Все входящие номера — уже в «${catchAll.name}»` : 'Все входящие номера'], ['contacts', 'Абоненты из контактов'], ['numbers', 'Номера и префиксы']]
              .map(([k, l]) => `<option value="${k}" ${scope0 === k ? 'selected' : ''} ${k === 'all' && catchAll ? 'disabled' : ''}>${esc(l)}</option>`).join('')}</select>
            <span class="hint">Если входящему подходят несколько сценариев, срабатывает самый точный: номер → абонент из контактов → префикс → все входящие.</span></div>
          <div class="field" id="scope-all"><div class="muted small">Сценарий примет любой входящий звонок, в том числе со скрытого номера.</div></div>
          <div class="field" id="scope-contacts"><label>Абоненты</label>
            <div class="chips" id="cts"></div>
            <input id="ct-in" placeholder="Имя или номер из контактов">
            <span class="hint">Сценарий привязан к контактам, а не к номерам: если номер в карточке изменится, сценарий продолжит работать.</span></div>
          <div class="field" id="scope-numbers"><label>Номера звонящих</label>
            <div class="chips" id="nums"></div>
            <input id="num-in" placeholder="Номер или префикс +7926*">
            <span class="hint">Входящие с этих номеров обработает этот сценарий. Enter — добавить. Пусто — сценарий
              работает только если выбран по умолчанию в «Настройки → Звонки».</span></div></div>
        <div class="field"><label>Промпт сценария — что агент делает в этом звонке</label><textarea name="prompt" class="code" rows="9" placeholder="Цель звонка, шаги разговора, как обрабатывать возражения, что сохранить в результат…">${esc(s.prompt)}</textarea>
          <span class="hint">Опишите задачу звонка, а не характер (он задан в агенте). Переменные вида {{имя}} настраиваются на вкладке «Переменные».</span></div>
        <div class="field"><label>Первая фраза агента</label><input name="first_message" value="${esc(s.first_message)}"></div>
        <div class="field"><label>Фоновый звук
          <span class="help sm" tabindex="0" role="note" data-tip="Тихий шум города под голосом агента — заполняет паузы, пока готовится ответ. Слышит только собеседник: распознавание речи его не получает. Есть в записи звонка. Работает во входящих и исходящих звонках сценария. Громкость — в «Настройки → Звонки».">?</span></label>
          <div class="row" style="gap:8px"><select name="ambience" id="sc-amb" style="flex:1">${ambienceOpts(ambienceCache || [], s.ambience)}</select>
          <button type="button" class="btn btn-icon" id="sc-amb-play" title="Прослушать" aria-label="Прослушать">${icon('play')}</button></div></div>
        <label class="switch"><input type="checkbox" name="history" ${s.history === 0 || s.history === false ? '' : 'checked'}> Агент знает предыдущие разговоры
          <span class="help sm" tabindex="0" role="note" data-tip="Агент получит суть и договорённости прошлых звонков и SMS с этим номером — и продолжит разговор с того места, не спрашивая заново то, что уже известно. Для исходящих это значение по умолчанию в форме звонка.">?</span></label>
        <div class="field"><label>Что агент может делать в этом звонке</label><div class="switch-list">
          ${Object.entries(SCRIPT_TOOLS).map(([k, l]) => `<label class="switch"><input type="checkbox" data-calltool="${k}" ${(s.call_tools || ['hangup_call', 'save_result']).includes(k) ? 'checked' : ''}> ${l}</label>`).join('')}</div>
          <span class="hint">Базовые действия звонка. Особые действия (SMS, сбор данных) дают скиллы.</span></div>
        <div class="field"><label>Скиллы</label><input type="hidden" name="skills_names" value="${esc((s.skills || []).map((id) => (skillsCache || []).find((x) => x.id === id)?.name).filter(Boolean).join(', '))}" data-skills>
          <span class="hint">Что агент умеет в этом сценарии. Он подключит нужный скилл, когда поймёт ситуацию. <a href="#/skills">Все скиллы →</a></span></div>
      </section>

      <section class="tab-pane" data-pane="1" role="tabpanel" hidden>
        <div class="row">
          <span class="muted small">Значения подставляются вместо {{имя}} в промпте и первой фразе</span>
          <span class="help sm" tabindex="0" role="note" data-tip="Встроенные переменные заполняются автоматически: ${BUILTIN.map((b) => `{{${b}}}`).join(', ')}. Свои переменные заполняются в форме звонка; если там пусто — берётся значение по умолчанию.">?</span>
          <span class="spacer"></span>
          <button type="button" class="btn" id="detect">Найти в тексте</button>
          <button type="button" class="btn" id="addvar">${icon('plus')} Добавить переменную</button></div>
        <div class="edit-table-wrap"><table class="edit-table">
          <thead><tr><th>Имя</th><th>Подпись в форме звонка</th><th>Значение по умолчанию</th><th></th></tr></thead>
          <tbody id="vars">${(s.variables || []).map(varRow).join('')}</tbody></table>
          <div class="empty small" id="vars-empty">Переменных нет. Нажмите «Найти в тексте», чтобы собрать их из промпта.</div></div>
      </section>

      <section class="tab-pane" data-pane="2" role="tabpanel" hidden>
        <div class="row"><span class="small muted" id="preview-meta"></span><span class="spacer"></span>
          <button type="button" class="btn" id="preview-refresh">${icon('refresh')} Обновить</button></div>
        <pre class="preview preview-full" id="preview">…</pre>
      </section></form>`,
    onMount: (m) => {
      // ---- skills: chosen from «Скиллы» by name
      tagInput($('[data-skills]', m), { placeholder: 'Добавить скилл…', create: (t) => `Нет скилла «${t}» — создайте в «Скиллы»`,
        suggest: () => (skillsCache || []).map((x) => x.name) });
      // ---- background sound
      const ambSel = $('#sc-amb', m);
      bindAmbience(ambSel, $('#sc-amb-play', m));
      if (!ambienceCache) ambienceList().then((items) => { ambSel.innerHTML = ambienceOpts(items, s.ambience); ambSel.dispatchEvent(new Event('change')); }).catch(() => {});
      // ---- caller numbers (inbound routing)
      const nums = $('#nums', m), numIn = $('#num-in', m);
      const chip = (v) => {
        const name = v.endsWith('*') ? '' : contactName(v);
        const label = v.endsWith('*') ? `${esc(v.slice(0, -1))}… <span class="faint">(префикс)</span>` : name ? `${esc(name)} <span class="faint mono">${esc(v)}</span>` : `<span class="mono">${esc(v)}</span>`;
        return `<span class="chip-tag" data-v="${esc(v)}">${label}<button type="button" data-x title="Убрать">${icon('x')}</button></span>`;
      };
      const addNum = (raw) => {
        const v = (raw || '').trim();
        if (!v) return;
        if (!/^[+\d][\d\s()-]*\*?$/.test(v)) { toast('Укажите номер телефона или префикс вида +7926*', 'warn'); return; }
        if ($$('.chip-tag', nums).some((c) => c.dataset.v.replace(/\D/g, '') === v.replace(/\D/g, '') && c.dataset.v.endsWith('*') === v.endsWith('*'))) return;
        nums.insertAdjacentHTML('beforeend', chip(v));
      };
      nums.onclick = (e) => { const x = e.target.closest('[data-x]'); if (x) x.parentElement.remove(); };
      (s.inbound_numbers || []).forEach(addNum);
      attachContactSuggest(numIn, { onPick: (c) => addNum(c.phone) });
      numIn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.defaultPrevented) { e.preventDefault(); addNum(numIn.value); numIn.value = ''; }
      });
      m.addPendingNumber = () => { if (numIn.value.trim()) { addNum(numIn.value); numIn.value = ''; } };
      // ---- contacts from the phone book (inbound routing)
      const cts = $('#cts', m);
      const addContact = (id) => {
        const c = state.contacts.find((x) => x.id === id);
        if (!c || $$('.chip-tag', cts).some((x) => +x.dataset.id === id)) return;
        cts.insertAdjacentHTML('beforeend', `<span class="chip-tag" data-id="${c.id}">${esc(fullName(c))} <span class="faint mono">${esc(c.phone)}</span><button type="button" data-x title="Убрать">${icon('x')}</button></span>`);
      };
      cts.onclick = (e) => { const x = e.target.closest('[data-x]'); if (x) x.parentElement.remove(); };
      (s.inbound_contacts || []).forEach(addContact);
      attachContactSuggest($('#ct-in', m), { onPick: (c) => addContact(c.id) });

      const dirSel = $('[name=direction]', m), scopeSel = $('#scope', m);
      const syncDir = () => {
        $('#nums-field', m).hidden = dirSel.value === 'outbound';
        ['all', 'contacts', 'numbers'].forEach((k) => { $('#scope-' + k, m).hidden = scopeSel.value !== k; });
      };
      dirSel.addEventListener('change', syncDir); scopeSel.addEventListener('change', syncDir); syncDir();

      // ---- variables table
      const vars = $('#vars', m);
      const syncVars = () => {
        const n = $$('tr.var-row', vars).length;
        $('#vars-count', m).textContent = n ? `(${n})` : '';
        $('#vars-empty', m).hidden = n > 0;
        $('.edit-table thead', m).hidden = n === 0;
      };
      vars.onclick = (e) => { const b = e.target.closest('[data-rm]'); if (b) { b.closest('tr').remove(); syncVars(); } };
      $('#addvar', m).onclick = () => {
        vars.insertAdjacentHTML('beforeend', varRow());
        syncVars();
        $('tr.var-row:last-child [data-k=name]', vars).focus();
      };
      $('#detect', m).onclick = () => {
        const have = new Set($$('[data-k="name"]', vars).map((i) => i.value.trim()));
        const txt = $('[name=prompt]', m).value + ' ' + $('[name=first_message]', m).value;
        const found = [...txt.matchAll(/\{\{\s*(\w+)\s*\}\}/g)].map((x) => x[1]).filter((n) => !have.has(n) && !BUILTIN.includes(n));
        [...new Set(found)].forEach((n) => vars.insertAdjacentHTML('beforeend', varRow({ name: n })));
        syncVars();
        toast(found.length ? `Добавлено переменных: ${new Set(found).size}` : 'Новых переменных в тексте нет', found.length ? 'ok' : 'info');
      };
      syncVars();

      // ---- preview: rebuilt from the current form every time the tab is opened
      let lastPreview = null;
      m.refreshPreview = async () => {
        const out = $('#preview', m);
        out.style.opacity = '.5';
        try {
          const r = await api('/scripts/preview', { method: 'POST', body: { script: collect(m) } });
          const changed = lastPreview !== null && r.instructions !== lastPreview;
          const same = lastPreview !== null && !changed;
          lastPreview = r.instructions;
          out.textContent = r.instructions;
          out.classList.remove('flash'); void out.offsetWidth; out.classList.add('flash');
          $('#preview-meta', m).innerHTML = `Агент: ${esc(r.agent || 'не выбран')} · ${new Date().toLocaleTimeString(I18N.locale)}`
            + (changed ? ' · <span style="color:var(--ok)">изменено</span>' : same ? ' · без изменений' : '');
        } catch (e) {
          out.textContent = 'Не удалось построить предпросмотр: ' + e.message;
        } finally { out.style.opacity = ''; }
      };
      $('#preview-refresh', m).onclick = () => m.refreshPreview();
      setupDrawerTabs(m, (i) => { if (i === 2) m.refreshPreview(); });
    },
    buttons: [{ label: 'Закрыть', cls: 'btn-ghost' }, { label: 'Сохранить', cls: 'btn-primary', onClick: async (m) => {
      if (!$('[name=name]', m).value.trim()) {  // the name lives on the first tab
        m.showTab(0);
        $('[name=name]', m).focus();
        throw new Error('Укажите название сценария');
      }
      m.addPendingNumber();  // a number typed but not confirmed with Enter
      const body = collect(m);
      const saved = await api(s.id ? '/scripts/' + s.id : '/scripts', { method: s.id ? 'PUT' : 'POST', body });
      s = saved;  // a new script now has an id: the next save updates it
      $('.modal-head h2', m).textContent = 'Сценарий';
      toast('Сценарий сохранён', 'ok');
      done();                                  // refresh the list behind the drawer
      if (!$('[data-pane="2"]', m).hidden) m.refreshPreview();
      return false;                            // keep the drawer open
    } }],
  });
}

// ------------------------------------------------------------------ agents
const TOOLS = { hangup_call: 'Завершать звонок', save_result: 'Сохранять итог', send_dtmf: 'Тоновый набор (DTMF)' };
// ------------------------------------------------------------------ voices (Голоса): shared helpers
const ENGINE_LABEL = { yandex: 'Yandex', fish: 'Fish Audio' };
const FISH_LANGS = [['ru', 'русский'], ['en', 'английский'], ['uk', 'украинский'], ['kk', 'казахский'], ['de', 'немецкий'],
  ['fr', 'французский'], ['es', 'испанский'], ['it', 'итальянский'], ['pt', 'португальский'], ['tr', 'турецкий'],
  ['ar', 'арабский'], ['zh', 'китайский'], ['ja', 'японский'], ['ko', 'корейский']];
const langLabel = (code) => FISH_LANGS.find(([c]) => c === code)?.[1] || code || '';
const voiceById = (id) => (state.voices || []).find((v) => v.id === +id);
const roleLabel = (catalog, voice, role) => catalog?.find((c) => c.name === voice)?.roles.find((r) => r.id === role)?.label || role;
function voiceDetails(v, catalog) {
  if (!v) return '';
  const parts = [ENGINE_LABEL[v.engine] || v.engine];
  if (v.engine === 'yandex') { parts.push(v.voice); if (v.role) parts.push(roleLabel(catalog, v.voice, v.role)); }
  if (v.engine === 'fish' && v.language && v.language !== 'ru') parts.push(langLabel(v.language));
  if (v.speed && Math.abs(v.speed - 1) > 0.001) parts.push(`${(+v.speed).toFixed(2)}×`);
  return parts.join(' · ');
}
const voiceOptions = (sel) => ['yandex', 'fish'].map((eng) => {
  const list = (state.voices || []).filter((v) => v.engine === eng);
  return list.length ? `<optgroup label="${ENGINE_LABEL[eng]}">${list.map((v) => `<option value="${v.id}" ${+sel === v.id ? 'selected' : ''}>${esc(v.name)}</option>`).join('')}</optgroup>` : '';
}).join('');

// «Прослушать»: getParams() → {engine, voice, role, speed, model}
function mountVoiceTest(m, getParams) {
  let player = null;
  const btn = $('#vt-play', m), hint = $('#vt-hint', m);
  const idle = () => { btn.disabled = false; btn.innerHTML = icon('play'); btn.title = 'Прослушать'; };
  btn.onclick = async () => {
    if (player && !player.paused) { player.pause(); idle(); return; }
    const p = getParams();
    if (!p || !p.voice) return toast('Сначала выберите голос', 'err');
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span>'; btn.title = 'Синтез…'; hint.textContent = 'синтез…';
    const t0 = performance.now();
    try {
      const r = await fetch('/api/agents/voice-test', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
        body: JSON.stringify({ engine: p.engine, voice: p.voice, role: p.engine === 'yandex' ? p.role || '' : '', speed: +p.speed || 1, model: p.model || '', language: p.language || 'ru', text: $('#vt-text', m).value, phone: $('#vt-phone', m).checked }),
      });
      if (r.status === 401) { showLogin(); throw new Error('Требуется вход'); }
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || r.statusText); }
      const url = URL.createObjectURL(await r.blob());
      player?.pause();
      player = new Audio(url);
      player.onended = () => { idle(); URL.revokeObjectURL(url); };
      await player.play();
      btn.disabled = false; btn.innerHTML = icon('stop'); btn.title = 'Остановить';
      hint.textContent = `${ENGINE_LABEL[p.engine]} · ответ за ${((performance.now() - t0) / 1000).toFixed(1)} с`;
    } catch (e) { idle(); toast('Проверка голоса: ' + e.message, 'err', 6000); }
  };
  $('#vt-text', m).onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); btn.click(); } };
  new MutationObserver((_, obs) => { if (!m.isConnected) { player?.pause(); obs.disconnect(); } })
    .observe(document.getElementById('modal-root'), { childList: true });
  return { play: (url) => { player?.pause(); player = new Audio(url); player.play(); } };
}
// the voice test panel (agent and voice editors): a phrase, play / stop, "as the caller hears it"
const voiceTestHtml = (text) => `<div class="voice-test">
  <div class="voice-test-head"><span class="voice-test-title">Проверка голоса</span><span class="spacer"></span><span class="muted small" id="vt-hint"></span></div>
  <div class="voice-test-row"><input id="vt-text" value="${esc(text || 'Здравствуйте! Так звучит мой голос.')}" maxlength="300" placeholder="Фраза для проверки">
    <button type="button" class="btn btn-primary btn-icon" id="vt-play" title="Прослушать" aria-label="Прослушать">${icon('play')}</button></div>
  <label class="switch"><input type="checkbox" id="vt-phone"> Как услышит собеседник по телефону (8 кГц, громкость звонка)</label></div>`;

// заготовки хезитаций голоса Fish: прослушать; перегенерировать — только в «Голосах»
const FILLER_KIND = { short: 'короткая', long: 'длинная' };
// the hesitations tab of the voice editor: a table with add / delete / regenerate
function mountFillerTable(m, voiceId, play) {
  let poll;
  const fmtDur = (ms) => ms ? `${(ms / 1000).toFixed(1)} с` : dash;
  const load = async () => {
    clearTimeout(poll);
    if (!m.isConnected) return;
    const { status = 'missing', items = [] } = await api(`/voices/${voiceId}/fillers`).catch(() => ({}));
    $('#ft-rows', m).innerHTML = items.map((f) => `<tr data-id="${f.id}">
        <td class="ellipsis" style="max-width:320px" title="${esc(f.text)}">${esc(f.text)}</td>
        <td>${FILLER_KIND[f.kind] || f.kind}</td><td>${fmtDur(f.duration_ms)}</td>
        <td class="kebab-cell"><div class="actions">
          <button type="button" class="btn btn-ghost btn-sm btn-icon" data-play="${esc(f.url)}" title="Прослушать">${icon('play')}</button>
          <button type="button" class="btn btn-ghost btn-sm btn-icon" data-del="${f.id}" title="Удалить">${icon('trash')}</button></div></td></tr>`).join('')
      || `<tr><td colspan="4" class="empty">${icon('wave')}<div>${status === 'generating' ? 'Генерируются…' : 'Фраз пока нет'}</div></td></tr>`;
    $$('[data-play]', m).forEach((b) => { b.onclick = () => play(b.dataset.play); });
    $$('[data-del]', m).forEach((b) => { b.onclick = async () => {
      b.disabled = true;
      await api(`/voices/${voiceId}/fillers/${b.dataset.del}`, { method: 'DELETE' }).catch((e) => toast(e.message, 'err'));
      load();
    }; });
    $('#ft-status', m).textContent = status === 'generating' ? 'генерируются в фоне (~20 с)…'
      : status.startsWith('error') ? 'ошибка: ' + status.slice(7)
      : `${items.length} ${items.length === 1 ? 'фраза' : items.length < 5 && items.length ? 'фразы' : 'фраз'}`;
    $('#ft-regen', m).disabled = status === 'generating';
    $('#ft-add', m).disabled = status === 'generating';
    if (status === 'generating') poll = setTimeout(load, 3000);
  };
  const add = async () => {
    const input = $('#ft-text', m), btn = $('#ft-add', m), text = input.value.trim();
    if (!text) return input.focus();
    btn.disabled = true; btn.innerHTML = 'Синтез…';
    try {
      const f = await api(`/voices/${voiceId}/fillers`, { method: 'POST', body: { text, kind: $('#ft-kind', m).value } });
      input.value = '';
      await load();
      play(f.url);
    } catch (e) { toast('Хезитация: ' + e.message, 'err', 6000); }
    btn.disabled = false; btn.innerHTML = `${icon('plus')} Добавить`;
  };
  $('#ft-add', m).onclick = add;
  $('#ft-text', m).onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } };
  $('#ft-regen', m).onclick = () => confirmBox('Синтезировать все фразы заново этим голосом?', async () => {
    await api(`/voices/${voiceId}/fillers/regenerate`, { method: 'POST' });
    load();
  }, 'Перегенерировать');
  load();
  return load;
}

// ------------------------------------------------------------------ voices view
VIEWS.voices = {
  title: 'Голоса', icon: 'wave',
  hint: 'Голоса для агентов: Yandex SpeechKit (с эмоцией и скоростью) и Fish Audio. У голосов Fish здесь же заготовки хезитаций.',
  async render(root) {
    [this.catalog, state.voices] = await Promise.all([api('/agents/voices'), api('/voices')]);
    const lib = await api('/voices/library').catch(() => ({}));
    const libNote = !lib.has_key ? `Добавьте API-ключ Fish Audio (<a href="#/settings?tab=fish">Настройки → Fish Audio</a>) — в список добавятся 50 русских голосов из библиотеки. Остальные находятся поиском при создании голоса.`
      : lib.running ? 'Добавляю 50 русских голосов из библиотеки Fish Audio…'
      : lib.error ? `Не удалось загрузить голоса Fish Audio: ${esc(lib.error)}` : '';
    if (lib.running) setTimeout(() => { if (state.view === this && root.isConnected) this.render(root); }, 3000);
    root.innerHTML = `${libNote ? `<div class="card small muted" style="margin-bottom:12px">${libNote}</div>` : ''}<div class="card"><div class="card-head">
        <div class="row"><input id="q" type="search" placeholder="Поиск" style="max-width:280px">
          <select id="eng" style="max-width:170px"><option value="">все движки</option><option value="yandex">Yandex</option><option value="fish">Fish Audio</option></select></div></div>
      <div class="table-wrap"><table><thead><tr><th>Голос</th><th>Движок</th><th>Эмоция</th><th>Скорость</th><th>Заготовки</th><th>Агенты</th><th></th></tr></thead>
        <tbody id="rows"></tbody></table></div></div>`;
    setActions(`<button class="btn btn-primary" id="add">${icon('plus')} Голос</button>`);
    $('#add').onclick = () => editVoice({ engine: 'fish', speed: 1 }, this.catalog, () => this.render(root));
    $('#q', root).oninput = () => this.rows(root);
    $('#eng', root).onchange = () => this.rows(root);
    this.rows(root);
  },
  rows(root) {
    const q = $('#q', root).value.trim().toLowerCase(), eng = $('#eng', root).value;
    const list = state.voices.filter((v) => (!eng || v.engine === eng) && (!q || [v.name, v.voice, v.description].some((x) => (x || '').toLowerCase().includes(q))));
    const fillers = (v) => v.fillers_status === 'generating' ? '<span class="badge warn">генерируются…</span>'
      : v.fillers_status?.startsWith('error') ? `<span class="badge err" title="${esc(v.fillers_status)}">ошибка</span>`
      : v.fillers_count ? `${v.fillers_count} шт.` : '<span class="muted small">нет</span>';
    $('#rows', root).innerHTML = list.map((v) => `<tr class="clickable" data-id="${v.id}">
      <td style="max-width:300px">${entityCell(v.name, v.description || '')}</td>
      <td>${ENGINE_LABEL[v.engine]}<div class="cell-sub">${v.engine === 'yandex' ? esc(v.voice) : esc(langLabel(v.language || 'ru'))}</div></td>
      <td>${v.engine === 'yandex' && v.role ? esc(roleLabel(this.catalog, v.voice, v.role)) : dash}</td>
      <td>${v.speed && Math.abs(v.speed - 1) > 0.001 ? `${(+v.speed).toFixed(2)}×` : dash}</td>
      <td>${fillers(v)}</td>
      <td>${v.agents || dash}</td>
      <td class="kebab-cell">${KEBAB}</td></tr>`).join('')
      || `<tr><td colspan="7" class="empty">${icon('wave')}<div>${q || eng ? 'Ничего не найдено' : 'Голосов пока нет'}</div></td></tr>`;
    bindRows(root, {
      open: (id) => editVoice(state.voices.find((v) => v.id === id), this.catalog, () => this.render(root)),
      actions: (id) => [
        { label: 'Удалить', icon: 'trash', danger: true, run: () => confirmBox('Удалить голос?', async () => {
          try { await api('/voices/' + id, { method: 'DELETE' }); this.render(root); } catch (e) { toast(e.message, 'err', 6000); }
        }) },
      ],
    });
    clearTimeout(this.poll);
    if (state.voices.some((v) => v.fillers_status === 'generating')) {
      this.poll = setTimeout(async () => { if (state.view !== this || !root.isConnected) return; state.voices = await api('/voices'); this.rows(root); }, 3000);
    }
  },
};

function editVoice(v, catalog, done) {
  const roleOptions = (voice, selected) => {
    const roles = catalog.find((c) => c.name === voice)?.roles || [];
    return '<option value="">по умолчанию</option>' + roles.map((r) => `<option value="${r.id}" ${r.id === selected ? 'selected' : ''}>${esc(r.label)}</option>`).join('');
  };
  const yv = v.engine === 'yandex' ? v.voice : 'dasha';
  modal({
    title: v.id ? 'Голос' : 'Новый голос', size: 'lg',
    body: `<form class="form" id="vf">
      <div class="tabs drawer-tabs" role="tablist" data-tabs>
        <button type="button" role="tab" data-tab="0" class="active">Голос</button>
        <button type="button" role="tab" data-tab="1">Хезитации</button></div>
      <section class="tab-pane form" data-pane="0" role="tabpanel">
      <div class="form-2"><div class="field"><label>Название *</label><input name="name" value="${esc(v.name)}" placeholder="например: Даша дружелюбная"></div>
        <div class="field"><label>Описание</label><input name="description" value="${esc(v.description)}"></div></div>
      ${v.id ? `<div class="field"><label>Движок</label><div>${ENGINE_LABEL[v.engine]}</div></div>` : `<div class="field"><label>Движок</label>
        <select id="v-engine">
          <option value="fish" ${v.engine === 'fish' ? 'selected' : ''}>Fish Audio — реалистичный голос</option>
          <option value="yandex" ${v.engine === 'yandex' ? 'selected' : ''}>Yandex SpeechKit — голос Realtime API</option></select>
        <span class="hint">Fish звучит естественнее, но отвечает примерно на секунду позже (паузу закрывают заготовки); Yandex отвечает сразу.</span></div>`}
      <div class="form-2" id="yandex-block">
        <div class="field"><label>Голос SpeechKit</label><select id="y-voice">${catalog.map((c) => `<option value="${esc(c.name)}" ${c.name === yv ? 'selected' : ''}>${esc(c.name)}${c.gender ? ` · ${c.gender}` : ''}${c.lang !== 'ru' ? ` · ${c.lang}` : ''}</option>`).join('')}</select></div>
        <div class="field"><label>Эмоция</label><select id="y-role">${roleOptions(yv, v.role)}</select><span class="hint" id="role-hint"></span></div></div>
      <div id="fish-block" class="form">
        <div class="form-2" style="grid-template-columns:minmax(0,1fr) minmax(0,2fr)">
        <div class="field"><label>Язык речи</label>
          <select id="fish-lang">${FISH_LANGS.map(([c, l]) => `<option value="${c}" ${(v.language || 'ru') === c ? 'selected' : ''}>${l}</option>`).join('')}</select>
          <span class="hint">на каком языке голос говорит; по нему же ищутся голоса в библиотеке</span></div>
        <div class="field"><label>Голос из библиотеки Fish Audio</label>
          <select id="fish-voice"><option value="${v.engine === 'fish' ? esc(v.voice || '') : ''}">${v.engine === 'fish' && v.voice ? esc(v.name || v.voice) : '— выберите голос —'}</option></select>
          <span class="hint">в списке первые 30 голосов выбранного языка, остальные — поиском; только совместимые с потоковой моделью S2.1 Pro Flash</span></div></div></div>
      <div class="field"><label>Скорость речи: <span id="speedv">${(+(v.speed ?? 1)).toFixed(2)}×</span></label>
        <input type="range" name="speed" min="0.7" max="1.5" step="0.05" value="${v.speed ?? 1}"></div>
      ${voiceTestHtml()}
      </section>
      <section class="tab-pane form" data-pane="1" role="tabpanel" hidden>
        ${v.id ? `<p class="muted small" style="margin:0">Хезитации звучат в звонке, пока готовится ответ агента, — этим же голосом.
          Каждая фраза хранится у голоса отдельным аудиофайлом. Если изменить звучание голоса (голос, эмоцию, скорость, язык),
          после сохранения все фразы синтезируются заново.</p>
        <div class="row"><span class="muted small" id="ft-status"></span><span class="spacer"></span>
          <button type="button" class="btn btn-sm" id="ft-regen">${icon('refresh')} Перегенерировать все</button></div>
        <div class="edit-table-wrap"><table class="rows-s"><thead><tr><th>Фраза</th><th>Вид</th><th>Длительность</th><th></th></tr></thead>
          <tbody id="ft-rows"></tbody></table></div>
        <div class="form-2" style="grid-template-columns:minmax(0,1fr) 170px auto;align-items:end">
          <div class="field"><label>Новая фраза</label><input id="ft-text" maxlength="120" placeholder="например: Так, сейчас гляну…"></div>
          <div class="field"><label>Вид</label><select id="ft-kind"><option value="short">короткая</option><option value="long">длинная</option></select></div>
          <button type="button" class="btn" id="ft-add">${icon('plus')} Добавить</button></div>`
        : `<div class="empty">${icon('wave')}<div>Сохраните голос — стандартный набор хезитаций сгенерируется автоматически,<br>затем здесь можно будет его прослушать, дополнить и удалить лишнее.</div></div>`}
      </section>
    </form>`,
    onMount: (m) => {
      setupDrawerTabs(m);
      const engine = () => v.id ? v.engine : ($('#v-engine', m)?.value || 'yandex');
      const ySel = $('#y-voice', m), rSel = $('#y-role', m), fSel = $('#fish-voice', m), lSel = $('#fish-lang', m);
      $('[name=speed]', m).oninput = (e) => { $('#speedv', m).textContent = `${(+e.target.value).toFixed(2)}×`; };
      const syncRoles = () => {
        const prev = rSel.value;
        rSel.innerHTML = roleOptions(ySel.value, prev);
        const roles = catalog.find((c) => c.name === ySel.value)?.roles || [];
        rSel.disabled = !roles.length;
        $('#role-hint', m).textContent = roles.length ? '' : 'у этого голоса нет вариантов';
      };
      ySel.onchange = syncRoles; syncRoles();
      const tester = mountVoiceTest(m, () => engine() === 'fish'
        ? { engine: 'fish', voice: fSel.value, speed: $('[name=speed]', m).value, model: v.model, language: lSel.value }
        : { engine: 'yandex', voice: ySel.value, role: rSel.value, speed: $('[name=speed]', m).value });
      if (v.id) mountFillerTable(m, v.id, tester.play);
      // the library is thousands of voices: 30 on open, the rest via the search inside the dropdown
      fSel._remote = async (q) => {
        const list = await api(`/agents/fish-voices?search=${encodeURIComponent(q)}&language=${encodeURIComponent(lSel.value)}`);
        return list.slice(0, q ? 100 : 30).map((x) => ({ value: x.id, label: (x.personal ? '★ ' : '') + x.name, title: x.description }));
      };
      fSel.onchange = () => {
        const nameEl = $('[name=name]', m);
        if (!nameEl.value.trim()) nameEl.value = fSel.selectedOptions[0]?.textContent.replace(/^★ /, '') || '';
      };
      lSel.onchange = () => { fSel._remoteFirst = null; };  // the next open lists voices of the new language
      const syncEngine = () => {
        const f = engine() === 'fish';
        $('#fish-block', m).hidden = !f; $('#yandex-block', m).hidden = f;
      };
      if (!v.id) $('#v-engine', m).onchange = syncEngine;  // the engine is chosen only for a new voice
      syncEngine();
    },
    buttons: [{ label: 'Отмена', cls: 'btn-ghost' }, { label: 'Сохранить', cls: 'btn-primary', onClick: async (m) => {
      const eng = v.id ? v.engine : ($('#v-engine', m)?.value || 'yandex');
      const body = {
        name: $('[name=name]', m).value.trim(), description: $('[name=description]', m).value.trim(), engine: eng,
        language: eng === 'fish' ? $('#fish-lang', m).value : undefined,
        speed: +$('[name=speed]', m).value,
        voice: eng === 'fish' ? $('#fish-voice', m).value : $('#y-voice', m).value,
        role: eng === 'fish' ? '' : $('#y-role', m).value,
      };
      if (!body.voice) throw new Error('Выберите голос');
      if (!body.name) throw new Error('Укажите название');
      const saved = await api(v.id ? '/voices/' + v.id : '/voices', { method: v.id ? 'PUT' : 'POST', body });
      toast(saved.fillers_status === 'generating' ? 'Голос сохранён · хезитации генерируются в фоне' : 'Голос сохранён', 'ok');
      done();
    } }],
  });
}

VIEWS.agents = {
  title: 'Агенты', icon: 'bot',
  hint: 'Агент — характер и голос: кто говорит и как. Что делать в конкретном звонке, задаёт сценарий.',
  async render(root) {
    await loadRefs();
    this.catalog = await api('/agents/voices');
    root.innerHTML = `<div class="card"><div class="card-head">
        <input id="q" type="search" placeholder="Поиск" style="max-width:360px"></div>
      <div class="table-wrap"><table><thead><tr><th>Агент</th><th>Голос</th><th>Характер</th><th>Сценарии</th><th></th></tr></thead>
        <tbody id="rows"></tbody></table></div></div>`;
    setActions(`<button class="btn btn-primary" id="add">${icon('plus')} Агент</button>`);
    const def = state.voices.find((v) => v.engine === 'yandex' && v.voice === 'dasha' && !v.role) || state.voices[0];
    $('#add').onclick = () => editAgent({ voice_id: def?.id, speaks_first: true, tools: Object.keys(TOOLS), vad_threshold: 0.5, silence_ms: 800, max_duration_sec: 600, extra: {} }, this.catalog, () => this.render(root));
    $('#q', root).oninput = () => this.rows(root);
    this.rows(root);
  },
  rows(root) {
    const q = $('#q', root).value.trim().toLowerCase();
    const list = state.agents.filter((a) => !q || [a.name, a.role, a.description, a.instructions].some((v) => (v || '').toLowerCase().includes(q)));
    const used = (a) => state.scripts.filter((s) => s.default_agent_id === a.id);
    $('#rows', root).innerHTML = list.map((a) => { const v = voiceById(a.voice_id); return `<tr class="clickable" data-id="${a.id}">
      <td style="max-width:260px">${entityCell(a.name, a.role || a.description || '')}</td>
      <td><div>${v ? esc(v.name) : esc(a.voice || '—')}</div><div class="cell-sub">${v ? esc(voiceDetails(v, this.catalog)) + ' · ' : ''}${a.speaks_first ? 'говорит первым' : 'ждёт собеседника'}</div></td>
      <td class="ellipsis" style="max-width:420px" title="${esc(a.instructions)}">${esc(a.instructions) || dash}</td>
      <td title="${esc(used(a).map((s) => s.name).join(', '))}">${used(a).length || dash}</td>
      <td class="kebab-cell">${KEBAB}</td></tr>`; }).join('')
      || `<tr><td colspan="5" class="empty">${icon('bot')}<div>${q ? 'Ничего не найдено' : 'Агентов пока нет'}</div></td></tr>`;
    bindRows(root, {
      open: (id) => editAgent(state.agents.find((a) => a.id === id), this.catalog, () => this.render(root)),
      actions: (id) => [
        { label: 'Удалить', icon: 'trash', danger: true, run: () => confirmBox('Удалить агента?', async () => { await api('/agents/' + id, { method: 'DELETE' }); this.render(root); }) },
      ],
    });
  },
};

// intonation tags of a Fish voice (app/agent/emotions.py PRESETS): suggestions, any other text works too
const EMOTIONS = ['спокойно', 'тепло', 'радостно', 'сочувственно', 'удивлённо', 'твёрдо и холодно', 'angry', 'шёпотом',
  'виновато', 'воодушевлённо', 'игриво', 'устало', 'раздражённо', 'грустно', 'испуганно'];

function editAgent(a, catalog, done) {
  modal({
    title: a.id ? 'Агент' : 'Новый агент', size: 'lg',
    body: `<form class="form" id="af">
      <div class="tabs drawer-tabs" id="agent-tabs" role="tablist" data-tabs>
        <button type="button" role="tab" data-tab="0" class="active">Промпт и характер</button>
        <button type="button" role="tab" data-tab="1">Голос</button>
        <button type="button" role="tab" data-tab="2">Поведение при звонке</button></div>
      <section class="tab-pane" data-pane="0" role="tabpanel">
        <div class="form-2"><div class="field"><label>Имя *</label><input name="name" value="${esc(a.name)}"></div>
          <div class="field"><label>Роль</label><input name="role" value="${esc(a.role)}" placeholder="Менеджер клиники, оператор поддержки…"></div></div>
        <div class="field"><label>Описание</label><input name="description" value="${esc(a.description)}"></div>
        <div class="field"><label>Характер и манера речи</label><textarea name="instructions" class="code" rows="8" placeholder="Кто этот агент, как он общается: тон, темп, обращение на «вы», чего избегать…">${esc(a.instructions)}</textarea>
          <span class="hint">Только личность и стиль. Задачу звонка (что выяснить, что предложить) описывайте в сценарии.</span></div>
      </section>

      <section class="tab-pane" data-pane="1" role="tabpanel" hidden>
        <div class="field"><label>Голос</label>
          <div class="row"><select name="voice_id" id="voice-sel">${voiceOptions(a.voice_id)}</select>
            <a class="btn btn-ghost" href="#/voices" title="Создать и настроить голоса">Все голоса →</a></div>
          <span class="hint" id="voice-info"></span></div>
        ${voiceTestHtml(a.greeting)}
        <h3 class="mt">Спектр эмоций</h3>
        <p class="hint" id="emo-note" style="margin:0">Агент ставит перед фразой тег интонации — «[твёрдо и холодно] Давайте вернёмся к делу.» — и голос Fish произносит её так. Сам тег не звучит и не попадает в расшифровку. Пусто в «Допустимых» — агент говорит ровным тоном.</p>
        <div class="form-2" id="emo-fields">
          <div class="field"><label>Допустимые эмоции</label><input type="hidden" name="emotions_allowed" value="${esc(a.emotions_allowed || '')}">
            <span class="hint">Только эти теги дойдут до голоса, остальные отбрасываются.</span></div>
          <div class="field"><label>Недопустимые эмоции</label><input type="hidden" name="emotions_forbidden" value="${esc(a.emotions_forbidden || '')}">
            <span class="hint">Агенту запрещено так говорить, даже если собеседник провоцирует.</span></div></div>
      </section>

      <section class="tab-pane" data-pane="2" role="tabpanel" hidden>
        <div class="field"><label class="switch"><input type="checkbox" name="speaks_first" ${a.speaks_first !== false ? 'checked' : ''}> Агент начинает разговор первым</label></div>
        <div class="form-2">
          <div class="field"><label>Приветствие</label><input name="greeting" value="${esc(a.greeting)}">
            <span class="hint">Первая фраза агента, если в сценарии не задана своя. Синтезируется заранее, пока идёт дозвон, и звучит сразу после ответа. Неизвестная переменная убирается: «Здравствуйте, {{contact_name}}!» без имени — «Здравствуйте!».</span></div>
          <div class="field"><label>Пауза перед приветствием, мс</label><input type="number" name="greeting_delay_ms" value="${a.greeting_delay_ms ?? 1000}" min="0" max="5000" step="100">
            <span class="hint">Исходящий звонок: сколько ждать после ответа, пока человек подносит телефон к уху. Если он сам говорит «Алло?», агент дождётся конца фразы.</span></div></div>
        <div class="form-3">
          <div class="field"><label>Чувствительность VAD: <span id="vadv">${a.vad_threshold ?? 0.5}</span></label><input type="range" name="vad_threshold" min="0.1" max="0.9" step="0.05" value="${a.vad_threshold ?? 0.5}"><span class="hint">выше — меньше реагирует на шум</span></div>
          <div class="field"><label>Пауза конца реплики, мс</label><input type="number" name="silence_ms" value="${a.silence_ms ?? 800}" min="100" max="5000" step="50">
            <span class="hint">Сколько молчания считать концом фразы собеседника. Больше — агент реже перебивает, но отвечает позже.</span></div>
          <div class="field"><label>Макс. длительность, сек</label><input type="number" name="max_duration_sec" value="${a.max_duration_sec ?? 600}" min="0">
            <span class="hint">Звонок завершится автоматически. 0 — без ограничения.</span></div></div>
        <details><summary class="muted small" style="cursor:pointer">Дополнительно: модель и параметры session.update</summary>
          <div class="field mt"><label>Модель</label><input name="model" value="${esc(a.model)}" placeholder="из настроек"><span class="hint">например speech-realtime-250923</span></div>
          <div class="field mt"><label>Параметры session.update (JSON)</label><textarea id="extra" class="code" rows="5">${esc(JSON.stringify(a.extra || {}, null, 2))}</textarea>
          <span class="hint">Объект вливается в сессию Realtime API — например, для tools типа file_search или своих параметров.</span></div></details>
      </section></form>`,
    onMount: (m) => {
      setupDrawerTabs(m);
      $('[name=vad_threshold]', m).oninput = (e) => { $('#vadv', m).textContent = e.target.value; };
      const vSel = $('#voice-sel', m);
      const cur = () => voiceById(vSel.value);
      const tester = mountVoiceTest(m, () => { const v = cur(); return v && { engine: v.engine, voice: v.voice, role: v.role, speed: v.speed, model: v.model, language: v.language }; });
      const syncVoice = () => {
        const v = cur();
        $('#voice-info', m).textContent = v ? voiceDetails(v, catalog) + (v.description ? ` — ${v.description}` : '') : '';
      };
      // the emotions: a tag is either allowed or forbidden, so each list doesn't offer what the other has
      const lists = {};
      const other = (k) => (lists[k === 'a' ? 'f' : 'a'] || []).map((t) => t.toLowerCase());
      tagInput($('[name=emotions_allowed]', m), { placeholder: 'Добавить эмоцию…', create: (t) => `Добавить «${t}»`, suggest: () => EMOTIONS.filter((t) => !other('a').includes(t)), onChange: (t) => { lists.a = t; } });
      tagInput($('[name=emotions_forbidden]', m), { placeholder: 'Добавить эмоцию…', create: (t) => `Добавить «${t}»`, suggest: () => EMOTIONS.filter((t) => !other('f').includes(t)), onChange: (t) => { lists.f = t; } });
      const syncEmo = () => {
        const fish = cur()?.engine === 'fish';
        $('#emo-fields', m).hidden = !fish;
        $('#emo-note', m).textContent = fish ? $('#emo-note', m).dataset.text : 'Эмоции тегами работают только с голосами Fish Audio.';
      };
      $('#emo-note', m).dataset.text = $('#emo-note', m).textContent;
      vSel.addEventListener('change', syncEmo);
      vSel.onchange = syncVoice;
      syncVoice(); syncEmo();
    },
    buttons: [{ label: 'Отмена', cls: 'btn-ghost' }, { label: 'Сохранить', cls: 'btn-primary', onClick: async (m) => {
      if (!$('[name=name]', m).value.trim()) {  // the name lives on the first tab
        m.showTab(0);
        $('[name=name]', m).focus();
        throw new Error('Укажите имя агента');
      }
      const body = formData($('#af', m));
      delete body.undefined;
      body.voice_id = +body.voice_id || null;
      if (!body.voice_id) { m.showTab(1); throw new Error('Выберите голос'); }
      try { body.extra = JSON.parse($('#extra', m).value || '{}'); } catch { throw new Error('Некорректный JSON в доп. параметрах'); }
      const saved = await api(a.id ? '/agents/' + a.id : '/agents', { method: a.id ? 'PUT' : 'POST', body });
      toast(saved.fillers_status === 'generating' ? 'Агент сохранён · заготовки голоса генерируются в фоне (их видно в разделе «Голоса»)' : 'Агент сохранён', 'ok');
      done();
    } }],
  });
}

// ------------------------------------------------------------------ provider usage / balance (settings)
const fmtInt = (n) => (n == null ? '—' : Number(n).toLocaleString(I18N.locale));
// title: the card heading (Settings → a provider tab: «Использование»; «Провайдеры»: the provider name)
async function providerUsage(el, provider, title = '') {
  el.innerHTML = `<div class="card">${LOADER}</div>`;
  let d;
  try { d = await api('/providers/usage'); } catch (e) { el.innerHTML = `<div class="card muted small">${esc(e.message)}</div>`; return; }
  const tile = (label, value, sub = '') => `<div class="card stat"><div class="label">${label}</div><div class="value" style="font-size:22px">${value}</div>${sub ? `<div class="sub">${sub}</div>` : ''}</div>`;
  const head = (title, note) => `<div class="card-head"><h2>${title}</h2><span class="actions"><span class="muted small">${note}</span>
    <button class="btn btn-ghost btn-sm" data-refresh>${icon('refresh')} Обновить</button></span></div>`;
  const parts = (x, keys) => keys.filter(([k]) => x[k]).map(([k, l]) => `${l} ${fmtInt(x[k])}`).join(' · ') || 'расхода нет';
  if (provider === 'yandex') {
    const u = d.yandex.usage;
    const keys = [['call', 'звонки'], ['summary', 'суммаризация'], ['history_chat', 'ИИ-ассистент'], ['filler', 'хезитации'], ['greeting', 'приветствия'], ['voice_test', 'проверка голоса']];
    el.innerHTML = `<div class="card">${head(title || 'Использование', 'считает Caller')}
      <div class="grid grid-4">
        ${tile('Токены за сегодня', fmtInt(u.today.total), parts(u.today, keys))}
        ${tile('Токены за 30 дней', fmtInt(u.month.total), parts(u.month, keys))}
        ${tile('Токены всего', fmtInt(u.total.total), `входные ${fmtInt(u.total.tokens_in)} · выходные ${fmtInt(u.total.tokens_out)}`)}
        ${tile('Баланс Yandex Cloud', '—', 'по API-ключу AI Studio недоступен · <a href="https://billing.yandex.cloud" target="_blank" rel="noopener">консоль биллинга</a>')}
      </div></div>`;
  } else {
    const f = d.fish, u = f.usage;
    const keys = [['call', 'звонки'], ['filler', 'хезитации'], ['greeting', 'приветствия'], ['voice_test', 'проверка голоса']];
    const bal = !f.configured ? tile('API-квота', '—', title ? 'укажите ключ в <a href="#/settings?tab=fish">настройках</a>' : 'укажите ключ выше')
      : f.error ? tile('API-квота', '—', `<span class="badge err">ошибка</span> ${esc(f.error)}`)
      : tile('API-квота', fmtInt(f.api_quota_remaining), `осталось кредитов · тариф ${esc(f.tier || '—')}`);
    el.innerHTML = `<div class="card">${head(title || 'Баланс и расход', 'расход считает Caller')}
      <div class="grid grid-4">
        ${bal}
        ${tile('Кредиты за сегодня', fmtInt(u.today.total), parts(u.today, keys))}
        ${tile('Кредиты за 30 дней', fmtInt(u.month.total), parts(u.month, keys))}
        ${tile('Кредиты всего', fmtInt(u.total.total), parts(u.total, keys))}
      </div></div>`;
  }
  $('[data-refresh]', el).onclick = () => providerUsage(el, provider, title);
}

// ------------------------------------------------------------------ settings
VIEWS.settings = {
  title: 'Настройки', icon: 'settings', tab: 'modem',
  async render(root, params) {
    if (params?.get('tab')) this.tab = params.get('tab');
    await loadRefs();
    const [s, m] = await Promise.all([api('/settings'), api('/modem')]);
    this.s = s; this.m = m;
    const tabs = { modem: 'Модем', operator: 'Оператор', calls: 'Звонки', yandex: 'Yandex AI Studio', fish: 'Fish Audio', maps: 'Яндекс Карты', telegram: 'Telegram', power: 'Энергосбережение', ui: 'Интерфейс', security: 'Безопасность', console: 'AT-консоль' };
    root.innerHTML = `<div class="tabs" id="tabs" style="margin-bottom:16px">${Object.entries(tabs).map(([k, l]) => `<button data-t="${k}" class="${this.tab === k ? 'active' : ''}">${l}</button>`).join('')}</div><div id="pane"></div>`;
    $$('#tabs button', root).forEach((b) => b.onclick = () => { this.tab = b.dataset.t; $$('#tabs button', root).forEach((x) => x.classList.toggle('active', x === b)); this.pane(root); });
    this.pane(root);
  },
  field(key, label, { type = 'text', hint = '', opts = null, min, max, step } = {}) {
    const v = this.s[key];
    if (type === 'switch') return `<div class="field"><label class="switch"><input type="checkbox" name="${key}" ${v ? 'checked' : ''}> ${label}</label>${hint ? `<span class="hint">${hint}</span>` : ''}</div>`;
    if (opts) return `<div class="field"><label>${label}</label><select name="${key}" ${type === 'int' ? 'data-type="int"' : ''}>${opts}</select>${hint ? `<span class="hint">${hint}</span>` : ''}</div>`;
    return `<div class="field"><label>${label}</label><input name="${key}" type="${type}" value="${esc(v ?? '')}" ${min !== undefined ? `min="${min}"` : ''} ${max !== undefined ? `max="${max}"` : ''} ${step ? `step="${step}"` : ''} autocomplete="off">${hint ? `<span class="hint">${hint}</span>` : ''}</div>`;
  },
  form(inner, id = 'sform') { return `<form id="${id}" class="form">${inner}<div><button class="btn btn-lg btn-primary" type="submit">Сохранить</button></div></form>`; },
  bindSave(root, id = 'sform') {
    const f = $('#' + id, root); if (!f) return;
    f.onsubmit = guard(async (e) => {
      e.preventDefault();
      const r = await api('/settings', { method: 'PUT', body: formData(f) });
      this.s = r.settings;
      state.mapsKey = undefined;  // «Дела» → «Карта» reads the key again
      r.errors?.length ? toast('Сохранено, но модем вернул ошибки: ' + r.errors.join('; '), 'warn', 7000) : toast('Настройки сохранены', 'ok');
    });
  },
  async pane(root) {
    const p = $('#pane', root), s = this.s;
    if (this.tab === 'operator') {
      // the mobile operator: network settings of the SIM and USSD requests
      const modes = this.m.network_modes || {};
      const st = this.m.status || {}, inf = this.m.info || {};
      const kv = (rows) => rows.map(([k, v]) => `<dt>${k}</dt><dd>${v || '—'}</dd>`).join('');
      p.innerHTML = `<div class="grid grid-3">
        <div class="card span-2"><div class="card-head"><h2>Сеть оператора</h2></div>${this.form(`
          <div class="form-3">${this.field('modem.network_mode', 'Режим сети', { type: 'int', opts: Object.entries(modes).map(([k, l]) => `<option value="${k}" ${+k === +s['modem.network_mode'] ? 'selected' : ''}>${esc(l)}</option>`).join('') })}
            ${this.field('modem.apn', 'APN', { hint: 'Точка доступа мобильного интернета оператора (например internet.mts.ru). Пусто — не менять.' })}
            ${this.field('modem.sms_service', 'Отправка SMS (CGSMS)', { type: 'int', opts: Object.entries(this.m.sms_services || {}).map(([k, l]) => `<option value="${k}" ${+k === +s['modem.sms_service'] ? 'selected' : ''}>${esc(l)}</option>`).join(''), hint: 'если SMS не уходят в LTE — попробуйте другой вариант' })}</div>
          ${inf.network_mode != null && +inf.network_mode !== +s['modem.network_mode'] ? `<p class="small" style="margin:0"><span class="badge warn">не применён</span>
            Модем сейчас работает в режиме «${esc(inf.network_mode_name || inf.network_mode)}», а не в выбранном. Нажмите «Сохранить», чтобы применить режим — модем заново зарегистрируется в сети (несколько секунд без связи).</p>` : ''}`, 'opform')}</div>
        <div class="card"><div class="card-head"><h2>SIM-карта</h2></div><dl class="kv">${kv([
          ['Оператор', esc(st.operator)], ['Сеть', esc([st.network_type, st.registration].filter(Boolean).join(' · '))],
          ['Сигнал', st.rssi_dbm != null ? `${st.rssi_dbm} дБм` : ''],
          ['IMSI', `<span class="mono">${esc(inf.imsi)}</span>`], ['ICCID', `<span class="mono">${esc(inf.iccid)}</span>`],
        ])}</dl>
        <form class="form mt" id="simform"><div class="field"><label>Номер SIM-карты</label>
          <div class="row" style="gap:8px;flex-wrap:nowrap"><input name="modem.own_number" class="mono" value="${esc(s['modem.own_number'] || '')}" placeholder="${esc(inf.own_number || '+7 900 000-00-00')}" autocomplete="off" style="flex:1">
          <button class="btn btn-primary" type="submit">Сохранить</button></div>
          <span class="hint">${inf.own_number ? `<span>Модем сообщает номер</span> <span class="mono">${esc(inf.own_number)}</span><span>; поле нужно, только если он неверный.</span>` : '<span>Модем номер не знает (оператор не записал его в SIM) — укажите вручную.</span>'} <span>Агенты знают этот номер и называют его, если спросят.</span> <span>Тот же номер — в контакте «Этот номер».</span></span></div></form></div>
      </div>
      <div class="card mt ussd-card"><div class="card-head"><h2>USSD-запросы</h2><span class="muted small">баланс, остатки пакетов, подключение услуг</span></div>
        <form class="row ussd-form" id="ussd-form">
          <input id="ussd-code" class="mono" placeholder="*100#" autocomplete="off" style="max-width:220px">
          <button class="btn btn-primary" type="submit">${icon('send')} Отправить</button>
          <span class="chips">${['*100#', '*102#', '*105#', '*111#'].map((c) => `<button type="button" class="chip" data-ussd="${c}">${c}</button>`).join('')}</span>
        </form>
        <div class="ussd-log" id="ussd-log"><div class="muted small">Ответы оператора появятся здесь. Коды баланса у операторов разные: МТС и МегаФон — *100#, Билайн — *102#, Т2 — *105#.</div></div>
      </div>`;
      this.bindSave(root, 'opform'); this.bindSave(root, 'simform');
      const log = $('#ussd-log', p), codeIn = $('#ussd-code', p);
      const add = (html) => { if (!$('.ussd-item', log)) log.innerHTML = ''; log.insertAdjacentHTML('beforeend', html); log.scrollTop = log.scrollHeight; };
      const send = async (code) => {
        code = (code || '').trim(); if (!code) return;
        const btn = $('#ussd-form button[type=submit]', p); btn.disabled = true;
        add(`<div class="ussd-item me"><span class="mono">${esc(code)}</span></div><div class="ussd-item wait"><span class="spin"></span> ждём ответ оператора…</div>`);
        try {
          const r = await api('/modem/ussd', { method: 'POST', body: { code } });
          $('.ussd-item.wait', log)?.remove();
          add(`<div class="ussd-item op">${esc(r.text || '(пустой ответ)')}${r.note ? `<div class="small faint">${esc(r.note)}</div>` : ''}</div>`);
          codeIn.value = '';
          codeIn.placeholder = r.more ? 'Ответ в меню, например 1' : '*100#';
          $('#ussd-end', p)?.remove();
          if (r.more) $('#ussd-form', p).insertAdjacentHTML('beforeend', `<button type="button" class="btn btn-ghost" id="ussd-end">Завершить сеанс</button>`);
          const end = $('#ussd-end', p);
          if (end) end.onclick = guard(async () => { await api('/modem/ussd/cancel', { method: 'POST' }); end.remove(); codeIn.placeholder = '*100#'; toast('Сеанс завершён', 'ok'); });
        } catch (e) {
          $('.ussd-item.wait', log)?.remove();
          add(`<div class="ussd-item op err">${esc(e.message)}</div>`);
        } finally { btn.disabled = false; codeIn.focus(); }
      };
      $('#ussd-form', p).onsubmit = guard(async (e) => { e.preventDefault(); await send(codeIn.value); });
      $$('[data-ussd]', p).forEach((b) => b.onclick = () => send(b.dataset.ussd));
    } else if (this.tab === 'modem') {
      p.innerHTML = `<div class="grid grid-3"><div class="card span-2"><div class="card-head"><h2>Модем SIM7600G-H</h2></div>${this.form(`
        <div class="form-3">${this.field('modem.at_port', 'AT-порт', { hint: '/dev/sim7600-at (обычно ttyUSB2)' })}${this.field('modem.audio_port', 'Аудио-порт', { hint: '/dev/sim7600-audio (обычно ttyUSB4)' })}${this.field('modem.baudrate', 'Скорость', { type: 'number' })}</div>
        <div class="form-3">${this.field('modem.poll_interval', 'Опрос статуса, сек', { type: 'number', min: 3 })}</div>
        <div class="form-3">${this.field('modem.speaker_volume', 'Громкость (CLVL 0–5)', { type: 'number', min: 0, max: 5 })}${this.field('modem.mic_gain', 'Усиление микрофона (0–8)', { type: 'number', min: 0, max: 8 })}${this.field('modem.out_gain', 'Усиление выхода (0–8)', { type: 'number', min: 0, max: 8 })}</div>
        ${this.field('modem.sms_delete_after_read', 'Удалять SMS с SIM-карты после импорта', { type: 'switch' })}`)}</div>
        <div class="card"><div class="card-head"><h2>Управление</h2></div>
          <div class="row" style="margin-bottom:14px"><span class="dot ${this.m.connected ? 'ok' : 'err'}"></span>${this.m.connected ? 'Подключён' : 'Нет связи'}${this.m.mock ? ' <span class="badge warn">эмуляция</span>' : ''}</div>
          ${this.m.error ? `<p class="small" style="color:var(--err)">${esc(this.m.error)}</p>` : ''}
          <div class="form">
            <button class="btn" data-act="reconnect">${icon('refresh')} Переподключить порт</button>
            <button class="btn" data-act="airplane-on">${icon('power')} Режим полёта: вкл</button>
            <button class="btn" data-act="airplane-off">${icon('tower')} Режим полёта: выкл</button>
            <button class="btn btn-danger" data-act="restart">${icon('power')} Перезагрузить модем</button>
          </div>
          ${this.m.mock ? `<h3 class="mt">Эмуляция</h3><div class="form"><button class="btn" data-act="mock-call">${icon('phoneIn')} Входящий звонок</button><button class="btn" data-act="mock-sms">${icon('message')} Входящее SMS</button></div>` : ''}
        </div></div>`;
      this.bindSave(root);
      const acts = {
        reconnect: () => api('/modem/reconnect', { method: 'POST' }),
        'airplane-on': () => api('/modem/airplane?enabled=true', { method: 'POST' }),
        'airplane-off': () => api('/modem/airplane?enabled=false', { method: 'POST' }),
        restart: () => api('/modem/restart', { method: 'POST' }),
        'mock-call': () => api('/modem/mock/incoming-call', { method: 'POST', body: {} }),
        'mock-sms': () => api('/modem/mock/incoming-sms', { method: 'POST', body: {} }),
      };
      $$('[data-act]', p).forEach((b) => b.onclick = guard(async () => { await acts[b.dataset.act](); toast('Выполнено', 'ok'); }));
    } else if (this.tab === 'calls') {
      const ag = state.agents.map((a) => `<option value="${a.id}" ${+s['calls.inbound_agent_id'] === a.id ? 'selected' : ''}>${esc(a.name)}</option>`).join('');
      const sc = state.scripts.filter((x) => x.direction !== 'outbound').map((x) => `<option value="${x.id}" ${+s['calls.inbound_script_id'] === x.id ? 'selected' : ''}>${esc(x.name)}</option>`).join('');
      p.innerHTML = `<div class="grid grid-2"><div class="card"><div class="card-head"><h2>Входящие звонки</h2></div>${this.form(`
        ${this.field('calls.auto_answer', 'Автоматически отвечать агентом', { type: 'switch' })}
        ${this.field('calls.answer_after_rings', 'Ответ после N гудков', { type: 'number', min: 1, max: 10 })}
        ${this.field('calls.inbound_script_id', 'Сценарий по умолчанию', { type: 'int', opts: '<option value="">— нет —</option>' + sc, hint: 'для номеров, которых нет ни в одном сценарии' })}
        ${this.field('calls.inbound_agent_id', 'Агент по умолчанию', { type: 'int', opts: '<option value="">— нет —</option>' + ag, hint: 'если у выбранного сценария нет своего агента' })}
        <h3 class="mt">Исходящие</h3>
        ${this.field('calls.dial_timeout', 'Ожидание ответа, сек', { type: 'number', min: 10 })}
        ${this.field('calls.queue_enabled', 'Обрабатывать очередь звонков', { type: 'switch' })}
        ${this.field('calls.record', 'Записывать разговоры (WAV)', { type: 'switch' })}
        <h3 class="mt">Фоновый звук</h3>
        <p class="hint" style="margin:0">Тихий шум города под голосом агента — заполняет паузы, пока готовится ответ. Сам звук выбирается в сценарии.</p>
        <div class="field"><label>Громкость фона: <b id="amb-vol">${Math.round((s['ambience.volume'] ?? 0.3) * 100)}%</b></label>
          <input type="range" name="ambience.volume" min="0.05" max="1" step="0.05" value="${s['ambience.volume'] ?? 0.3}">
          <span class="hint">От уровня самого звука (он выровнен заранее). 30% — заметно тише голоса агента и собеседника.</span></div>
        <h3 class="mt">Суммаризация</h3>
        ${this.field('summary.enabled', 'Делать суммаризацию после звонка (YandexGPT)', { type: 'switch' })}
        ${this.field('summary.model', 'Модель', { hint: 'yandexgpt-lite/latest — быстрее и дешевле, yandexgpt/latest — точнее' })}
        <h3 class="mt">ИИ-ассистент контакта</h3>
        ${this.field('history_chat.model', 'Модель', { hint: 'Отвечает на вопросы во вкладке «ИИ-ассистент» карточки контакта. yandexgpt/latest (Pro) — рекомендуется: нужно сопоставлять разговоры и пересчитывать даты' })}
        <h3 class="mt">Дела</h3>
        ${this.field('tasks.auto', 'После звонка выписывать договорённости в «Дела»', { type: 'switch' })}
        ${this.field('tasks.model', 'Модель', { hint: 'yandexgpt/latest (Pro) — точнее переводит «в пятницу вечером» в дату' })}
        <div class="field"><label>Прошлые звонки</label><div><button type="button" class="btn" id="tasks-backfill">${icon('tasks')} Найти договорённости в прошлых звонках</button></div>
          <span class="hint" id="tasks-backfill-info">ИИ разберёт звонки, которые ещё не разбирал (с расшифровкой). Несколько сотен токенов на звонок.</span></div>`, 'f1')}</div>
        <div class="card"><div class="card-head"><h2>Аудио</h2></div>${this.form(`
        ${this.field('audio.agent_rate', 'Частота PCM для агента, Гц', { type: 'int', opts: [8000, 16000, 24000, 44100, 48000].map((r) => `<option ${+s['audio.agent_rate'] === r ? 'selected' : ''}>${r}</option>`).join(''), hint: 'модем — 8000 Гц, звук пересэмплируется' })}
        ${this.field('audio.rx_gain', 'Усиление собеседник → агент', { type: 'number', step: 0.1, min: 0.1, max: 8 })}
        ${this.field('audio.tx_gain', 'Усиление агент → собеседник', { type: 'number', step: 0.1, min: 0.1, max: 8 })}
        <h3 class="mt">Перебивание агента</h3>
        ${this.field('audio.barge_in_ms', 'Перебить агента можно, если говорить дольше, мс', { type: 'number', min: 150, max: 1500, step: 50, hint: 'короткие «а», «ага», «алло» не обрывают агента — его голос лишь приглушается' })}
        ${this.field('audio.speech_level', 'Порог речи на линии (RMS)', { type: 'number', min: 50, max: 3000, step: 50, hint: 'ниже — тише голоса считаются речью; выше — меньше реакции на шум' })}`, 'f2')}</div></div>`;
      this.bindSave(root, 'f1'); this.bindSave(root, 'f2');
      $('#tasks-backfill', root).onclick = guard(async () => {
        const b = $('#tasks-backfill', root), info = $('#tasks-backfill-info', root);
        b.disabled = true; info.textContent = 'Разбираю звонки… это может занять пару минут.';
        try {
          const r = await api('/tasks/backfill', { method: 'POST' });
          info.textContent = `Разобрано звонков: ${r.calls}, найдено дел: ${r.added}${r.failed ? `, не удалось: ${r.failed}` : ''}.`;
        } finally { b.disabled = false; }
      });
      const vol = $('[name="ambience.volume"]', root);
      vol.oninput = () => { $('#amb-vol', root).textContent = Math.round(vol.value * 100) + '%'; };
    } else if (this.tab === 'yandex') {
      p.innerHTML = `<div class="grid grid-2"><div class="card"><div class="card-head"><h2>Yandex AI Studio · Realtime API</h2></div>${this.form(`
        ${this.field('yandex.folder_id', 'ID каталога (folder_id)')}
        ${this.field('yandex.api_key', 'API-ключ сервисного аккаунта', { type: 'password', hint: 'Api-Key; IAM-токен (t1.…) тоже подойдёт' })}
        ${this.field('yandex.model', 'Модель', { hint: 'speech-realtime-250923 → gpt://&lt;folder&gt;/&lt;model&gt;' })}
        ${this.field('yandex.ws_url', 'WebSocket URL')}`)}</div>
        <div class="card"><div class="card-head"><h2>Как получить доступ</h2></div><ol class="small muted" style="padding-left:18px;line-height:1.8">
          <li>В консоли Yandex Cloud создайте сервисный аккаунт в нужном каталоге.</li>
          <li>Выдайте роли <code>ai.models.user</code>, <code>ai.languageModels.user</code>, <code>ai.speechkit-stt.user</code>, <code>ai.speechkit-tts.user</code>.</li>
          <li>Создайте API-ключ с областью <code>yc.ai.foundationModels.execute</code>.</li>
          <li>Укажите ID каталога и ключ слева. Голос, роль и промпт задаются в разделе «Агенты».</li></ol></div></div>
        <div class="mt" id="usage-card"></div>`;
      this.bindSave(root);
      providerUsage($('#usage-card', p), 'yandex');
    } else if (this.tab === 'telegram') {
      let st = {};
      try { st = await api('/telegram'); } catch { /* shown below */ }
      const state_ = !st.configured ? '<span class="badge">не настроен</span>'
        : st.running ? `<span class="badge ok">работает</span> <a href="https://t.me/${esc(st.bot)}" target="_blank" rel="noopener">@${esc(st.bot)}</a>`
        : `<span class="badge err">не подключён</span> <span class="small muted">${esc(st.error || 'подключается…')}</span>`;
      p.innerHTML = `<div class="grid grid-2"><div class="card"><div class="card-head"><h2>Бот</h2><span class="actions">${state_}</span></div>${this.form(`
        ${this.field('telegram.token', 'Токен бота', { type: 'password', hint: 'У @BotFather: /newbot → имя → токен вида 123456:ABC…' })}
        ${this.field('telegram.enabled', 'Бот включён', { type: 'switch' })}
        <h3 class="mt">Присылать без вопроса</h3>
        ${this.field('telegram.notify_tasks', 'Новые дела после звонка', { type: 'switch' })}
        ${this.field('telegram.notify_missed', 'Пропущенные звонки', { type: 'switch' })}
        ${this.field('telegram.notify_sms', 'Входящие SMS', { type: 'switch' })}`, 'tgform')}</div>
        <div class="card"><div class="card-head"><h2>Кто может пользоваться</h2></div>
          <p class="small muted" style="margin-top:0">Бот отвечает только привязанным аккаунтам: он видит контакты и дела и умеет звонить. Чтобы привязать аккаунт, получите код и отправьте его боту — код одноразовый и действует 30 минут.</p>
          <div class="row" style="gap:10px"><button type="button" class="btn btn-primary" id="tg-code" ${st.configured ? '' : 'disabled'}>${icon('key')} Получить код привязки</button>
            <span id="tg-code-out" class="mono" style="font-size:20px;letter-spacing:.12em"></span></div>
          <div class="small muted" id="tg-code-hint" style="margin-top:6px"></div>
          <h3 class="mt">Привязанные аккаунты</h3>
          <div id="tg-users">${(st.users || []).map((u) => `<div class="row tg-user" style="gap:10px;padding:8px 0;border-top:1px solid var(--border)">
            <div class="avatar sm"${avatarStyle(u.name || '#')}>${esc(initials(u.name || '#'))}</div>
            <div style="flex:1;min-width:0"><div>${esc(u.name || 'Без имени')}</div><div class="small muted">${u.username ? '@' + esc(u.username) + ' · ' : ''}с ${fmtDate(u.created_at)}</div></div>
            <button type="button" class="btn btn-ghost btn-sm danger-text" data-unlink="${u.id}">Отвязать</button></div>`).join('') || '<div class="muted small">Пока никого</div>'}</div>
          <h3 class="mt">Что умеет</h3>
          <ul class="small muted" style="padding-left:18px;line-height:1.7;margin:0">
            <li>Всё, что ассистент в правой панели: контакты, дела, встречи, звонки, места на карте, «позвони…» с подтверждением кнопкой.</li>
            <li>Голосовые сообщения — распознаются и выполняются как текст.</li>
            <li>▶ под звонком — присылает запись разговора.</li>
            <li>/new — новый разговор. Разговоры из Telegram видны в списке чатов ассистента.</li></ul></div></div>`;
      this.bindSave(root, 'tgform');
      $('#tgform', root).addEventListener('submit', () => setTimeout(() => this.tab === 'telegram' && this.pane(root), 3000));  // the bot's status after a new token
      $('#tg-code', root).onclick = guard(async () => {
        const r = await api('/telegram/pair-code', { method: 'POST' });
        $('#tg-code-out', root).textContent = r.code;
        $('#tg-code-hint', root).innerHTML = `Отправьте этот код боту${r.bot ? ` <a href="https://t.me/${esc(r.bot)}" target="_blank" rel="noopener">@${esc(r.bot)}</a>` : ''} в течение 30 минут.`;
      });
      $$('[data-unlink]', root).forEach((b) => b.onclick = () => confirmBox('Отвязать аккаунт? Бот перестанет ему отвечать.', async () => {
        await api('/telegram/users/' + b.dataset.unlink, { method: 'DELETE' }); this.pane(root);
      }, 'Отвязать'));
    } else if (this.tab === 'maps') {
      p.innerHTML = `<div class="grid grid-2"><div class="card"><div class="card-head"><h2>Яндекс Карты</h2></div>${this.form(`
        ${this.field('maps.api_key', 'Ключ API', { hint: 'JavaScript API и HTTP Геокодер' })}
        <div class="row" style="gap:10px"><button type="button" class="btn" id="maps-check">${icon('pin')} Проверить ключ</button><span class="small muted" id="maps-check-info"></span></div>`, 'mform')}</div>
        <div class="card"><div class="card-head"><h2>Зачем и где взять</h2></div><ol class="small muted" style="padding-left:18px;line-height:1.8">
          <li>Карта нужна разделу «Дела»: вкладка «Карта» и форма «Отметить на карте» находят адрес из разговора и ставят точку.</li>
          <li>Откройте <a href="https://developer.tech.yandex.ru/services" target="_blank" rel="noopener">Кабинет разработчика Яндекса</a> → «Подключить API» → «JavaScript API и HTTP Геокодер».</li>
          <li>Для личного некоммерческого использования бесплатно (до 1000 запросов геокодера в сутки).</li>
          <li>Ключ начинает работать в течение 15 минут после выпуска.</li></ol></div></div>`;
      this.bindSave(root, 'mform');
      $('#maps-check', root).onclick = async () => {
        const info = $('#maps-check-info', root), key = $('[name="maps.api_key"]', root).value.trim();
        if (!key) { info.textContent = 'Введите ключ'; return; }
        info.textContent = 'Проверяю…';
        try {
          if (window.ymaps && state.mapsKey !== key) { info.textContent = 'Сохраните ключ и обновите страницу, чтобы проверить новый ключ.'; return; }
          const ym = await loadYmaps(key);
          const res = await ym.geocode('Москва, Красная площадь', { results: 1 });
          const obj = res.geoObjects.get(0);
          info.textContent = obj ? `Ключ работает: геокодер нашёл «${obj.getAddressLine()}»` : 'Карты загрузились, но геокодер ничего не нашёл';
        } catch (e) { info.textContent = 'Не работает: ' + (e?.message || e); }
      };
    } else if (this.tab === 'fish') {
      p.innerHTML = `<div class="grid grid-2"><div class="card"><div class="card-head"><h2>Fish Audio · Kitta</h2></div>${this.form(`
        ${this.field('fish.api_key', 'API-ключ', { type: 'password', hint: 'fishaudio.org → API-ключи' })}
        ${this.field('fish.ws_url', 'WebSocket URL (Realtime TTS v3)')}
        ${this.field('fish.api_url', 'REST API URL')}`)}</div>
        <div class="card"><div class="card-head"><h2>Как это работает</h2></div><ol class="small muted" style="padding-left:18px;line-height:1.8">
          <li>У агента на вкладке «Голос» выберите Fish Audio и голос из библиотеки.</li>
          <li>Yandex Realtime API распознаёт речь и ведёт диалог, но отвечает текстом; каждую фразу озвучивает Fish (WAV → 8 кГц).</li>
          <li>Ответ звучит примерно на секунду позже, чем голосом Яндекса; паузу заполняет заготовка («Ммм...») тем же голосом.</li>
          <li>Kitta разрешает <b>одно</b> соединение на ключ: не запускайте демостенд <code>fish_demo</code> с тем же ключом во время звонков.</li>
          <li>Расход: около 0,25 кредита за символ ответа (S2.1 Pro Flash).</li></ol></div></div>
        <div class="mt" id="usage-card"></div>`;
      this.bindSave(root);
      providerUsage($('#usage-card', p), 'fish');
    } else if (this.tab === 'power') {
      p.innerHTML = LOADER;
      const sys = await api('/system').catch(() => null);
      const pw = sys?.power || {}, can = !!sys?.helper;
      const govs = pw.governors || [];
      p.innerHTML = `<div class="grid grid-2"><div class="card"><div class="card-head"><h2>Энергосбережение</h2></div><form class="form" id="pwf">
        <div class="field"><label>Энергосбережение Wi-Fi</label>
          <select id="pw-wifi" ${can && pw.wifi_powersave != null ? '' : 'disabled'}>
            <option value="off" ${pw.wifi_powersave === false ? 'selected' : ''}>Выключено — стабильная связь (рекомендуется)</option>
            <option value="on" ${pw.wifi_powersave === true ? 'selected' : ''}>Включено — экономия энергии</option></select>
          <span class="hint">У Raspberry Pi 3 включённое энергосбережение Wi-Fi часто приводит к тому, что Pi «пропадает» из сети: не открывается интерфейс, не отвечает ping. Для сервера лучше выключить.</span></div>
        <div class="field"><label>Режим процессора</label>
          <select id="pw-gov" ${can && govs.length ? '' : 'disabled'}>${govs.map((g) => `<option value="${g}" ${pw.cpu_governor === g ? 'selected' : ''}>${esc(GOVERNOR_LABEL[g] || g)}</option>`).join('')}</select>
          <span class="hint">По нагрузке (ondemand) — частота растёт, когда нужно; максимальная — чуть быстрее реакция, но горячее; минимальная — экономнее, но звонки могут подтормаживать.</span></div>
        ${can ? '' : '<p class="muted small" style="margin:0">Настройки доступны только на Raspberry Pi после установки через deploy/install.sh.</p>'}
        <div class="row"><button class="btn btn-primary" type="submit" ${can ? '' : 'disabled'}>Применить</button></div></form></div>
        <div class="card"><div class="card-head"><h2>Как это работает</h2></div><ul class="small muted" style="padding-left:18px;line-height:1.8;margin:0">
          <li>Энергосбережение Wi-Fi сохраняется в настройках сети Raspberry Pi и действует после перезагрузки.</li>
          <li>Режим процессора после перезагрузки сбрасывается — Caller выставляет выбранный при каждом запуске.</li>
          <li>Текущее состояние видно в разделе «Система».</li></ul></div></div>`;
      $('#pwf', p).onsubmit = guard(async (e) => {
        e.preventDefault();
        const body = {};
        if (!$('#pw-wifi', p).disabled) body.wifi_powersave = $('#pw-wifi', p).value === 'on';
        if (!$('#pw-gov', p).disabled) body.cpu_governor = $('#pw-gov', p).value;
        await api('/system/power', { method: 'PUT', body });
        toast('Настройки применены', 'ok');
      });
    } else if (this.tab === 'ui') {
      // stored in this browser (localStorage), not on the server
      const lang = I18N.lang, theme = localStorage.getItem('caller.theme') || 'dark';
      p.innerHTML = `<div class="grid grid-2"><div class="card"><div class="card-head"><h2>Интерфейс</h2></div><form class="form" id="uif">
        <div class="field"><label>Язык интерфейса</label>
          <select id="ui-lang"><option value="ru" ${lang === 'ru' ? 'selected' : ''}>Русский</option><option value="en" ${lang === 'en' ? 'selected' : ''}>English</option></select>
          <span class="hint">Страница перезагрузится. Имена, промпты, контакты и расшифровки звонков не переводятся.</span></div>
        <div class="field"><label>Тема</label>
          <select id="ui-theme"><option value="dark" ${theme === 'dark' ? 'selected' : ''}>Тёмная</option><option value="light" ${theme === 'light' ? 'selected' : ''}>Светлая</option><option value="system" ${theme === 'system' ? 'selected' : ''}>Как в системе</option></select></div>
        <p class="muted small" style="margin:0">Настройки сохраняются в этом браузере.</p></form></div></div>`;
      $('#ui-lang', p).onchange = (e) => { localStorage.setItem('caller.lang', e.target.value); location.reload(); };
      $('#ui-theme', p).onchange = (e) => applyTheme(e.target.value);
    } else if (this.tab === 'security') {
      const u = state.user || {};
      p.innerHTML = `<div class="grid grid-2">
        <div class="card"><div class="card-head"><h2>Учётная запись</h2>${u.default_password ? '<span class="badge warn">пароль по умолчанию</span>' : ''}</div>
          <form class="form" id="pwf">
            <div class="field"><label>Логин</label><input name="new_username" value="${esc(u.username)}" autocomplete="username" required></div>
            <div class="field"><label>Текущий пароль</label><input name="current_password" type="password" autocomplete="current-password" required></div>
            <div class="form-2"><div class="field"><label>Новый пароль</label><input name="new_password" type="password" autocomplete="new-password" minlength="5" required>
                <span class="hint">Не короче 5 символов. После смены пароля сессии на других устройствах завершатся.</span></div>
              <div class="field"><label>Повторите пароль</label><input name="repeat" type="password" autocomplete="new-password" required></div></div>
            <div><button class="btn btn-lg btn-primary" type="submit">${icon('key')} Сменить пароль</button></div>
          </form></div>
        <div class="card"><div class="card-head"><h2>Доступ к API для внешних программ</h2></div>${this.form(`
          ${this.field('security.api_token', 'Статический API-токен', { type: 'password', hint: 'Для скриптов и интеграций: заголовок Authorization: Bearer &lt;токен&gt; или X-API-Key. Пусто — только вход по логину (POST /api/auth/login).' })}
          <div class="row"><button type="button" class="btn" id="gen">Сгенерировать</button><a class="btn btn-ghost" href="/docs" target="_blank">Документация API (Swagger)</a></div>`)}</div></div>`;
      $('#gen', p).onclick = () => { const t = [...crypto.getRandomValues(new Uint8Array(24))].map((b) => b.toString(16).padStart(2, '0')).join(''); const i = $('[name="security.api_token"]', p); i.type = 'text'; i.value = t; };
      this.bindSave(root);
      $('#pwf', p).onsubmit = guard(async (e) => {
        e.preventDefault();
        const f = formData(e.target);
        if (f.new_password !== f.repeat) throw new Error('Пароли не совпадают');
        const r = await api('/auth/password', { method: 'POST', body: { current_password: f.current_password, new_password: f.new_password, new_username: f.new_username } });
        state.user = r.user; renderUser();
        e.target.reset(); $('[name=new_username]', e.target).value = r.user.username;
        toast('Пароль изменён', 'ok');
        this.pane(root);
      });
    } else if (this.tab === 'console') {
      p.innerHTML = `<div class="grid grid-2"><div class="card"><div class="card-head"><h2>AT-консоль</h2></div>
          <div class="console" id="con"></div>
          <form class="row mt" id="atf"><input id="atc" placeholder="AT+CSQ" autocomplete="off"><button class="btn btn-primary">${icon('terminal')}</button></form>
          <div class="row wrap mt">${['AT+CSQ', 'AT+CPSI?', 'AT+COPS?', 'AT+CREG?', 'AT+CNMP?', 'AT+CPIN?', 'AT+CLCC', 'AT+CPMS?'].map((c) => `<button class="btn btn-ghost btn-sm mono" data-c="${c}">${c}</button>`).join('')}</div></div>
        <div class="card"><div class="card-head"><h2>События модема (URC)</h2></div><div class="console" id="urc"></div></div></div>`;
      const con = $('#con', p);
      const run = guard(async (cmd) => {
        con.insertAdjacentHTML('beforeend', `<div class="cmd">&gt; ${esc(cmd)}</div>`);
        try { const r = await api('/modem/at', { method: 'POST', body: { command: cmd } }); con.insertAdjacentHTML('beforeend', `${r.lines.map((l) => `<div>${esc(l)}</div>`).join('')}<div class="${r.final === 'OK' ? 'okc' : 'err'}">${esc(r.final || '(нет ответа)')}</div>`); }
        catch (e) { con.insertAdjacentHTML('beforeend', `<div class="err">${esc(e.message)}</div>`); }
        con.scrollTop = con.scrollHeight;
      });
      $('#atf', p).onsubmit = (e) => { e.preventDefault(); const c = $('#atc', p).value.trim(); if (c) run(c); $('#atc', p).value = ''; };
      $$('[data-c]', p).forEach((b) => b.onclick = () => run(b.dataset.c));
      api('/modem/urc').then((list) => { $('#urc', p).innerHTML = list.map((u) => `<div><span class="faint">${new Date(u.t).toLocaleTimeString(I18N.locale)}</span> ${esc(u.line)}</div>`).join(''); });
    }
  },
  onEvent(ev, root) {
    if (ev.event === 'modem.urc' && this.tab === 'console') {
      const u = $('#urc', root); if (u) { u.insertAdjacentHTML('beforeend', `<div><span class="faint">${new Date().toLocaleTimeString(I18N.locale)}</span> ${esc(ev.data)}</div>`); u.scrollTop = u.scrollHeight; }
    }
  },
};

// ------------------------------------------------------------------ browser handset (laptop mic/speakers)
// Audio is exchanged with the server as 8 kHz mono PCM16 in 20 ms frames — the modem's native format.
const HANDSET_WORKLET = `
class Mic extends AudioWorkletProcessor {
  constructor() { super(); this.ratio = sampleRate / 8000; this.pos = 0; this.acc = 0; this.n = 0;
    this.out = new Int16Array(160); this.i = 0; this.muted = false;
    this.port.onmessage = (e) => { this.muted = !!e.data.muted; }; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0]; if (!ch) return true;
    for (let k = 0; k < ch.length; k++) {
      this.acc += ch[k]; this.n++; this.pos += 1;
      if (this.pos >= this.ratio) {           // average ~6 input samples -> one 8 kHz sample
        this.pos -= this.ratio;
        let v = this.muted ? 0 : this.acc / this.n; this.acc = 0; this.n = 0;
        v = v > 1 ? 1 : v < -1 ? -1 : v;
        this.out[this.i++] = v * 32767;
        if (this.i === 160) { this.port.postMessage(this.out.buffer.slice(0)); this.i = 0; }
      }
    }
    return true;
  }
}
class Player extends AudioWorkletProcessor {
  constructor() { super(); this.q = []; this.buffered = 0; this.cur = null; this.ci = 0;
    this.step = 8000 / sampleRate; this.frac = 0; this.a = 0; this.b = 0; this.playing = false;
    this.port.onmessage = (e) => {
      const f = new Int16Array(e.data); this.q.push(f); this.buffered += f.length;
      while (this.buffered > 8000 * 0.35) { const d = this.q.shift(); this.buffered -= d.length; }  // cap latency
    }; }
  next() {
    if (!this.cur || this.ci >= this.cur.length) { this.cur = this.q.shift() || null; this.ci = 0; if (this.cur) this.buffered -= this.cur.length; }
    return this.cur ? this.cur[this.ci++] / 32768 : null;
  }
  process(_, outputs) {
    const out = outputs[0];
    if (!this.playing && this.buffered >= 480) this.playing = true;    // 60 ms jitter buffer
    for (let k = 0; k < out[0].length; k++) {
      let v = 0;
      if (this.playing) {
        this.frac += this.step;
        while (this.frac >= 1) { this.frac -= 1; this.a = this.b; const s = this.next();
          if (s === null) { this.playing = false; this.b *= 0.5; } else this.b = s; }
        v = this.a + (this.b - this.a) * this.frac;                      // linear upsampling
      }
      for (let c = 0; c < out.length; c++) out[c][k] = v;
    }
    return true;
  }
}
registerProcessor('handset-mic', Mic);
registerProcessor('handset-player', Player);`;

function httpsUrl() {
  return `https://${location.hostname}:${state.sslPort || 8443}/${location.hash}`;
}

const softphone = {
  active: false, muted: false, ws: null, ctx: null, stream: null, mic: null,
  async start() {
    if (this.active) return;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      throw new Error(`Микрофон доступен только по HTTPS — откройте ${httpsUrl()}`);
    }
    try {
      this.stream = await Promise.race([
        navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('браузер не ответил на запрос микрофона')), 30000)),
      ]);
    } catch (e) {
      throw new Error('Нет доступа к микрофону: ' + (e.name === 'NotAllowedError' ? 'разрешите его в браузере' : e.message));
    }
    this.ctx = new AudioContext();
    await this.ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([HANDSET_WORKLET], { type: 'application/javascript' })));
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.mic = new AudioWorkletNode(this.ctx, 'handset-mic');
    const player = new AudioWorkletNode(this.ctx, 'handset-player', { outputChannelCount: [2] });
    const silent = this.ctx.createGain(); silent.gain.value = 0;   // keeps the mic node running
    src.connect(this.mic).connect(silent).connect(this.ctx.destination);
    player.connect(this.ctx.destination);
    await this.ctx.resume();

    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = this.ws = new WebSocket(`${proto}://${location.host}/api/calls/audio`);
    ws.binaryType = 'arraybuffer';
    ws.onmessage = (e) => player.port.postMessage(e.data, [e.data]);
    this.mic.port.onmessage = (e) => { if (ws.readyState === 1) ws.send(e.data); };
    ws.onclose = (e) => {
      if (this.ws !== ws) return;
      if (e.code === 4409) toast('Звук звонка перехвачен другой вкладкой', 'warn');
      this.stop();
    };
    this.active = true; this.muted = false;
  },
  setMuted(m) { this.muted = m; this.mic?.port.postMessage({ muted: m }); },
  stop() {
    const ws = this.ws; this.ws = null;
    if (ws && ws.readyState <= 1) ws.close();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close().catch(() => {});
    this.stream = this.ctx = this.mic = null;
    const was = this.active; this.active = false; this.muted = false;
    if (was) renderCallBar();
  },
};

// ------------------------------------------------------------------ global call bar (incoming / active)
let timerInt = null;
function renderCallBar() {
  const bar = $('#call-bar'), a = state.active;
  clearInterval(timerInt);
  // keep the operator's choice across re-renders (each RING re-renders the bar)
  const picked = { agent: $('#cb-agent')?.value, script: $('#cb-script')?.value };
  if (!a) { bar.innerHTML = ''; state.callStart = null; return; }
  if (a.state === 'active' && !state.callStart) state.callStart = Date.now();
  const ringing = a.direction === 'in' && a.state === 'ringing';
  const who = contactName(a.number) || a.number || 'Неизвестный номер';
  const label = { ringing: 'Входящий звонок', dialing: 'Набор номера', answering: 'Соединение…', active: 'Разговор' }[a.state] || a.state;
  bar.innerHTML = `<div class="call-bar ${ringing ? 'ringing' : ''}"><span class="dot ${ringing ? 'ok' : 'warn'} pulse"></span>
    <div><div class="small muted">${label}${ringing && a.rings ? ` · гудков: ${a.rings}` : ''}</div><div class="who">${esc(who)} <span class="mono muted small">${esc(a.number !== who ? a.number : '')}</span></div></div>
    <span class="mono" data-timer></span>
    <div class="actions">
      ${ringing ? `<select id="cb-agent" class="input-sm">${agentOptions(a.agent_id, '— агент —')}</select><select id="cb-script" class="input-sm">${scriptOptions(a.script_id, 'inbound')}</select>
        <button class="btn btn-ok btn-sm" id="cb-answer">${icon('bot')} Ответить агентом</button>
        <button class="btn btn-ok btn-sm" id="cb-answer-browser">${icon('mic')} Ответить в браузере</button>` : ''}
      ${a.browser && !ringing ? (softphone.active
        ? `<span class="badge ${softphone.muted ? 'warn' : 'ok'}">${icon('mic')} ${softphone.muted ? 'микрофон выкл.' : 'вы на линии'}</span>
           <button class="btn btn-sm" id="cb-mute">${icon(softphone.muted ? 'mic' : 'micOff')} ${softphone.muted ? 'Включить микрофон' : 'Выключить микрофон'}</button>`
        : `<button class="btn btn-sm btn-primary" id="cb-connect">${icon('mic')} Подключить звук</button>`) : ''}
      ${location.hash.startsWith('#/calls') ? '' : '<a class="btn btn-sm" href="#/calls">Открыть</a>'}
      <button class="btn btn-danger btn-sm" id="cb-hangup">${icon('phoneOff')} ${ringing ? 'Отклонить' : 'Завершить'}</button></div></div>`;
  $('#cb-hangup').onclick = guard(() => api('/calls/active/hangup', { method: 'POST' }));
  if (picked.agent !== undefined && $('#cb-agent')) $('#cb-agent').value = picked.agent;
  if (picked.script !== undefined && $('#cb-script')) $('#cb-script').value = picked.script;
  const ans = $('#cb-answer');
  if (ans) ans.onclick = guard(() => api('/calls/active/answer', { method: 'POST', body: { agent_id: +$('#cb-agent').value || null, script_id: +$('#cb-script').value || null } }));
  const ansB = $('#cb-answer-browser');
  if (ansB) ansB.onclick = guard(async () => {
    await softphone.start();
    try { await api('/calls/active/answer', { method: 'POST', body: { browser: true } }); } catch (e) { softphone.stop(); throw e; }
  });
  const mute = $('#cb-mute');
  if (mute) mute.onclick = () => { softphone.setMuted(!softphone.muted); renderCallBar(); };
  const conn = $('#cb-connect');
  if (conn) conn.onclick = guard(async () => { await softphone.start(); renderCallBar(); });
  const tick = () => $$('[data-timer]').forEach((el) => { el.textContent = state.callStart ? fmtDur((Date.now() - state.callStart) / 1000) : ''; });
  tick(); timerInt = setInterval(tick, 1000);
}

// ------------------------------------------------------------------ shell: nav, router, websocket
// '|' — разделитель групп в меню
const ORDER = ['calls', 'sms', 'tasks', 'contacts', '|', 'scripts', 'skills', 'agents', 'voices', '|', 'dashboard', 'system', 'providers', '|', 'settings'];
function renderNav() {
  const cur = (location.hash.slice(2).split('?')[0]) || 'calls';
  $('#nav').innerHTML = ORDER.map((k) => k === '|' ? '<div class="nav-sep" role="separator"></div>' : `<a href="#/${k}" class="${cur === k ? 'active' : ''}">${icon(VIEWS[k].icon)}<span>${VIEWS[k].title}</span>${k === 'sms' && state.stats?.sms_unread ? `<span class="count" title="Непрочитанные SMS">${state.stats.sms_unread}</span>` : ''}${k === 'calls' && state.stats?.calls_new ? `<span class="count" title="Новые звонки">${state.stats.calls_new}</span>` : ''}${k === 'calls' && state.active ? `<span class="dot ok pulse" style="margin-left:${state.stats?.calls_new ? '8px' : 'auto'}"></span>` : ''}${k === 'dashboard' ? modemDot() : ''}</a>`).join('');
}
async function refreshBadges() {
  try { state.stats = await api('/stats'); } catch { return; }
  renderNav();
}
// a person's calls are seen when their feed is opened: the «new» badges (person, tag, menu) go away
async function markCallsSeen(thread) {
  try { state.stats = { ...(state.stats || {}), ...(await api('/calls/seen?thread=' + encodeURIComponent(thread), { method: 'POST' })) }; } catch { return; }
  renderNav();
}

// the modem status dot at the right of «Модем» in the menu; hover — the network
function modemDot() {
  const m = state.modem;
  if (!m) return '';
  const s = m.status || {};
  const text = m.connected ? [s.operator || 'Модем', s.network_type, s.signal_percent != null ? `${s.signal_percent}%` : ''].filter(Boolean).join(' · ') : 'Модем не подключён';
  return `<span class="nav-status has-tip" data-tip="${esc(text)}" aria-label="${esc(text)}"><span class="dot ${m.connected ? 'ok' : 'err'}"></span></span>`;
}
const renderModemPill = () => renderNav();

async function route() {
  const [name, qs] = location.hash.slice(2).split('?');
  const key = VIEWS[name] ? name : 'calls';  // the start page
  const view = VIEWS[key];
  state.view = view;
  // SMS has its send button where the assistant's round button sits: it slides off the right edge there
  document.body.classList.toggle('fab-away', key === 'sms');
  $('#page-title').innerHTML = esc(view.title)
    + (view.hint ? ` <span class="help" tabindex="0" role="note" aria-label="${esc(view.hint)}" data-tip="${esc(view.hint)}">?</span>` : '');
  $('#sidebar').classList.remove('open');
  $('#modal-root').innerHTML = '';
  closeMenu();
  setActions('');
  renderNav(); renderCallBar();
  const root = $('#view');
  root.innerHTML = LOADER;
  const token = {};
  route.token = token;
  // the content stays hidden (a spinner instead) until its first data has come — at most PAGE_WAIT ms
  root.classList.add('view-loading');
  pageLoad.on = true; pageLoad.n = 0;
  try { await view.render(root, new URLSearchParams(qs || '')); }
  catch (e) { root.innerHTML = `<div class="card empty">${icon('alert')}<div>${esc(e.message)}</div></div>`; }
  finally { pageLoad.on = false; }
  if (pageLoad.n) await new Promise((ok) => { pageLoad.idle = ok; setTimeout(ok, PAGE_WAIT); });
  pageLoad.idle = null;
  if (route.token === token) root.classList.remove('view-loading');
}
const PAGE_WAIT = 4000;
const LOADER = '<div class="page-loader" role="status" aria-label="Загрузка"><span class="spin"></span></div>';

function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/api/events`);
  ws.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    if (ev.event === 'hello') { state.active = ev.data.active; state.modem = ev.data.modem; renderModemPill(); renderCallBar(); renderNav(); return; }
    if (ev.event === 'modem.status') { state.modem = { ...(state.modem || {}), connected: ev.data.connected, error: ev.data.error, status: ev.data.status }; renderModemPill(); }
    if (ev.event === 'call.state' && !ev.data.active && softphone.active) softphone.stop();
    if (ev.event === 'call.state') { const prev = state.active; state.active = ev.data.active; if (!prev || !state.active || prev.state !== state.active.state) { if (state.active?.state !== 'active') state.callStart = null; } renderCallBar(); renderNav(); }
    if (ev.event === 'call.incoming') toast(`Входящий звонок: ${ev.data.contact || ev.data.number}`, 'info', 6000);
    if (ev.event === 'call.summary') {
      toast(`Готова суммаризация звонка #${ev.data.call_id}`, 'ok');
      const box = document.querySelector('#call-summary');  // the call's drawer is open
      if (box && box.closest('.modal')?.querySelector('h2')?.textContent === `Звонок #${ev.data.call_id}`) box.innerHTML = summaryHtml({ summary_record: ev.data });
    }
    if (ev.event === 'call.ended') {
      const d = ev.data;
      if (d.status === 'failed' && d.error) toast(d.error, 'err');  // e.g. the agent wasn't ready — the number wasn't dialed
      else toast(`Звонок завершён: ${STATUS[d.status]?.[1] || d.status}`, d.status === 'completed' ? 'ok' : 'warn');
      refreshBadges();
    }
    if (ev.event === 'sms.new' && ev.data.direction === 'in') { toast(`SMS от ${contactName(ev.data.number) || ev.data.number}: ${ev.data.text.slice(0, 80)}`, 'info', 6000); refreshBadges(); }
    try { state.view?.onEvent?.(ev, $('#view')); } catch (err) { console.error(err); }
  };
  ws.onclose = (e) => { if (e.code === 4401) { showLogin(); return; } setTimeout(connectWS, 3000); };
}

// theme: dark | light | system (follows the OS and switches with it)
const systemDark = window.matchMedia('(prefers-color-scheme: dark)');
function applyTheme(pref) {
  localStorage.setItem('caller.theme', pref);
  const t = pref === 'system' ? (systemDark.matches ? 'dark' : 'light') : pref;
  document.documentElement.dataset.theme = t;
}
systemDark.addEventListener('change', () => { if (localStorage.getItem('caller.theme') === 'system') applyTheme('system'); });

// ------------------------------------------------------------------ custom select
// Every <select> gets a trigger button + a dropdown styled like the contact suggest. The native select stays
// (hidden) as the source of truth: forms, .value, onchange and innerHTML updates keep working as before.
// Remote mode: set `select._remote = async (query) => [{ value, label, title }]` — the dropdown then lists
// what it returns (the first page on open, server-side search while typing, with a spinner) instead of
// the <option>s; a picked value is added to the select as an <option>.
const SELECT_SEARCH_MIN = 12;  // longer lists get a search field on top
const CHEVRON = '<svg class="select-chevron" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>';
const nativeValue = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
const nativeIndex = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'selectedIndex');
let openSelect = null;  // { close }

function enhanceSelect(sel) {
  if (sel._custom || sel.multiple || sel.dataset.native !== undefined) return;
  const wrap = document.createElement('div');
  wrap.className = 'select';
  wrap.style.cssText = sel.style.cssText;  // max-width etc. set on the select
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'select-trigger ' + [...sel.classList].join(' ');
  btn.setAttribute('aria-haspopup', 'listbox');
  if (sel.title) btn.title = sel.title;
  sel.replaceWith(wrap);
  wrap.append(sel, btn);
  sel.classList.add('select-native');
  sel.tabIndex = -1;
  sel.setAttribute('aria-hidden', 'true');

  const refresh = () => {
    const o = sel.selectedOptions[0];
    btn.innerHTML = `<span class="select-label ${o && o.value === '' ? 'faint' : ''}">${esc(o ? o.textContent : '')}</span>${CHEVRON}`;
    btn.disabled = sel.disabled;
  };
  // programmatic .value / .selectedIndex changes don't fire events — keep the trigger in sync anyway
  Object.defineProperty(sel, 'value', { configurable: true, get() { return nativeValue.get.call(this); }, set(v) { nativeValue.set.call(this, v); refresh(); } });
  Object.defineProperty(sel, 'selectedIndex', { configurable: true, get() { return nativeIndex.get.call(this); }, set(v) { nativeIndex.set.call(this, v); refresh(); } });
  // characterData: the interface translation rewrites option texts in place
  new MutationObserver(refresh).observe(sel, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['disabled'] });
  sel.addEventListener('change', refresh);
  sel._custom = { refresh, open: () => open() };
  refresh();

  function open() {
    if (sel.disabled) return;
    openSelect?.close();
    const menu = document.createElement('div');
    menu.className = 'suggest select-menu';
    menu.setAttribute('role', 'listbox');
    const remote = sel._remote;
    let opts = [...sel.options], loading = false, req = 0, timer;
    const withSearch = remote || opts.length >= SELECT_SEARCH_MIN;
    // remote results look like options for render()/choose()
    const asOpts = (list) => list.map((x) => ({ value: x.value, textContent: x.label, title: x.title || '', disabled: false,
      get selected() { return x.value === sel.value; }, parentElement: { tagName: '' } }));
    const fetchRemote = async (q) => {
      const my = ++req;
      loading = true; $('.select-search', menu)?.classList.add('loading');
      if (!opts.length) render();
      try {
        const list = await remote(q);
        if (my !== req) return;
        opts = asOpts(list);
        if (!q) sel._remoteFirst = opts;  // the first page is reused on the next open
      } catch (e) {
        if (my !== req) return;
        opts = []; toast(e.message, 'err', 5000);
      }
      loading = false; $('.select-search', menu)?.classList.remove('loading');
      idx = opts.findIndex((o) => o.selected); if (idx < 0 && opts.length) idx = 0;
      render(); place(); scrollToActive();
    };
    menu.innerHTML = (withSearch ? '<div class="select-search"><input type="search" placeholder="Поиск" autocomplete="off"></div>' : '') + '<div class="select-list"></div>';
    document.body.appendChild(menu);
    const list = $('.select-list', menu), search = $('.select-search input', menu);
    let items = [], idx = -1;

    const mark = (text, q) => {
      const i = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
      return i < 0 ? esc(text) : `${esc(text.slice(0, i))}<mark>${esc(text.slice(i, i + q.length))}</mark>${esc(text.slice(i + q.length))}`;
    };
    const render = () => {
      const q = (search?.value || '').trim();
      items = remote ? opts : opts.filter((o) => !q || o.textContent.toLowerCase().includes(q.toLowerCase()));
      let html = '', group = null;
      items.forEach((o, i) => {
        const g = o.parentElement.tagName === 'OPTGROUP' ? o.parentElement.label : null;
        if (g !== group) { group = g; if (g) html += `<div class="select-group">${esc(g)}</div>`; }
        html += `<div class="suggest-item ${o.selected ? 'selected' : ''} ${i === idx ? 'active' : ''} ${o.disabled ? 'disabled' : ''}" role="option" aria-selected="${o.selected}" data-i="${i}" title="${esc(o.title || '')}">
          <span class="ellipsis" style="flex:1">${mark(o.textContent, q)}</span>${o.selected ? icon('check') : ''}</div>`;
      });
      list.innerHTML = html || `<div class="select-empty muted small">${loading ? 'Загрузка…' : 'Ничего не найдено'}</div>`;
      $$('.suggest-item', list).forEach((el) => {
        el.onmousedown = (e) => { e.preventDefault(); choose(items[+el.dataset.i]); };
        el.onmousemove = () => { if (idx !== +el.dataset.i) { idx = +el.dataset.i; mark_active(); } };
      });
    };
    const mark_active = () => $$('.suggest-item', list).forEach((el) => el.classList.toggle('active', +el.dataset.i === idx));
    const scrollToActive = () => $(`.suggest-item[data-i="${idx}"]`, list)?.scrollIntoView({ block: 'nearest' });
    const place = () => {
      const r = btn.getBoundingClientRect(), vh = window.innerHeight;
      menu.style.minWidth = r.width + 'px';
      menu.style.left = Math.min(r.left, window.innerWidth - menu.offsetWidth - 8) + 'px';
      const below = vh - r.bottom - 8, above = r.top - 8, h = Math.min(menu.scrollHeight, 320);
      const up = below < Math.min(h, 220) && above > below;
      menu.style.maxHeight = Math.max(120, Math.min(320, up ? above : below)) + 'px';
      menu.style.top = up ? '' : (r.bottom + 4) + 'px';
      menu.style.bottom = up ? (vh - r.top + 4) + 'px' : '';
    };
    const choose = (o) => {
      if (!o || o.disabled) return;
      close();
      if (remote && ![...sel.options].some((x) => x.value === o.value)) sel.add(new Option(o.textContent, o.value));
      if (sel.value !== o.value) {
        sel.value = o.value;
        sel.dispatchEvent(new Event('input', { bubbles: true }));
        sel.dispatchEvent(new Event('change', { bubbles: true }));
      }
      btn.focus();
    };
    const onKey = (e) => {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const n = items.length;
        if (!n) return;
        do { idx = (idx + (e.key === 'ArrowDown' ? 1 : -1) + n) % n; } while (items[idx].disabled && items.some((o) => !o.disabled));
        mark_active(); scrollToActive();
      } else if (e.key === 'Enter') {
        e.preventDefault(); choose(items[idx]);
      } else if (e.key === 'Escape' || e.key === 'Tab') {
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); }  // close the menu, not the drawer
        close(); if (e.key === 'Escape') btn.focus();
      }
    };
    const onOutside = (e) => { if (!menu.contains(e.target) && !wrap.contains(e.target)) close(); };
    const onScroll = (e) => { if (!menu.contains(e.target)) close(); };
    // the drawer that holds the select went away (closed / re-rendered)
    const gone = new MutationObserver(() => { if (!wrap.isConnected) close(); });
    function close() {
      gone.disconnect();
      menu.remove(); wrap.classList.remove('open'); btn.setAttribute('aria-expanded', 'false');
      document.removeEventListener('mousedown', onOutside, true);
      document.removeEventListener('keydown', onKey, true);
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', close);
      if (openSelect?.menu === menu) openSelect = null;
    }
    render();
    idx = items.findIndex((o) => o.selected);
    mark_active();
    place();
    scrollToActive();
    wrap.classList.add('open'); btn.setAttribute('aria-expanded', 'true');
    openSelect = { close, menu };
    document.addEventListener('mousedown', onOutside, true);
    document.addEventListener('keydown', onKey, true);
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', close);
    gone.observe(document.body, { childList: true, subtree: true });
    if (search) {
      search.placeholder = remote ? 'Поиск по библиотеке…' : 'Поиск…';
      search.oninput = remote
        ? () => { clearTimeout(timer); $('.select-search', menu).classList.add('loading'); timer = setTimeout(() => fetchRemote(search.value.trim()), 350); }
        : () => { idx = 0; render(); place(); };
      search.focus();
    }
    if (remote) {
      if (sel._remoteFirst) { opts = sel._remoteFirst; idx = opts.findIndex((o) => o.selected); render(); place(); scrollToActive(); }
      else { opts = []; fetchRemote(''); }
    }
  }

  btn.onclick = () => (wrap.classList.contains('open') ? openSelect?.close() : open());
  btn.onkeydown = (e) => {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key) && !wrap.classList.contains('open')) { e.preventDefault(); open(); }
  };
}

function enhanceSelects(root = document) {
  (root.matches?.('select') ? [root] : [...root.querySelectorAll('select')]).forEach(enhanceSelect);
}
new MutationObserver((muts) => {
  for (const m of muts) for (const n of m.addedNodes) if (n.nodeType === 1) enhanceSelects(n);
}).observe(document.body, { childList: true, subtree: true });

let started = false;
// ------------------------------------------------------------------ the assistant: round button → a side panel
// A chat with the AI that works with contacts, «Дела» and calls. The panel sits to the right of the interface
// (which shrinks); the bar between them resizes both. Several chats: «+» starts a new one, the title switches.
// Calls are never dialed by the AI: it shows a card, and the number is dialed only on «Позвонить» there.
const assistantUI = {
  open: localStorage.getItem('caller.assistant.open') === '1',
  width: +localStorage.getItem('caller.assistant.width') || 420,
  chatId: +localStorage.getItem('caller.assistant.chat') || null,
  chats: [],
  messages: [],
  busy: false,
  mount() {
    if ($('#assistant')) return;
    const fab = document.createElement('button');
    fab.id = 'assistant-fab'; fab.className = 'assistant-fab'; fab.type = 'button';
    fab.title = 'Ассистент'; fab.setAttribute('aria-label', 'Ассистент');
    fab.innerHTML = icon('sparkle');
    fab.onclick = () => this.toggle(true);
    document.body.append(fab);
    const layout = $('.layout');
    layout.insertAdjacentHTML('beforeend', `<div class="assistant-resizer" id="assistant-resizer" role="separator" aria-orientation="vertical" title="Потяните, чтобы изменить ширину"></div>
      <aside class="assistant" id="assistant" aria-label="Ассистент">
        <div class="asst-head"><button type="button" class="btn btn-ghost asst-title" id="asst-chats" title="Чаты"><span class="ellipsis" id="asst-title">Ассистент</span>${icon('menu')}</button>
          <button type="button" class="btn btn-ghost btn-icon btn-sm" id="asst-new" title="Новый чат">${icon('plus')}</button>
          <span class="spacer"></span>
          <button type="button" class="btn btn-ghost btn-icon btn-sm" id="asst-close" title="Закрыть">${icon('x')}</button></div>
        <div class="asst-feed" id="asst-feed"></div>
        <form class="asst-compose" id="asst-form"><textarea id="asst-q" rows="1" placeholder="Спросите ассистента…"></textarea>
          <button class="btn btn-primary btn-icon" type="submit" title="Отправить">${icon('send')}</button></form>
      </aside>`);
    $('#asst-close').onclick = () => this.toggle(false);
    $('#asst-new').onclick = guard(() => this.newChat());
    $('#asst-chats').onclick = (e) => { e.stopPropagation(); this.chatMenu(e.currentTarget); };
    const q = $('#asst-q');
    q.oninput = () => { q.style.height = 'auto'; q.style.height = Math.min(q.scrollHeight, 160) + 'px'; };
    q.onkeydown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#asst-form').requestSubmit(); } };
    $('#asst-form').onsubmit = (e) => { e.preventDefault(); this.send(q.value); };
    this.bindResizer();
    this.apply();
    if (this.open) this.load();
  },
  apply() {
    document.body.classList.toggle('assistant-open', this.open);
    document.body.style.setProperty('--asst-w', this.width + 'px');
  },
  toggle(open) {
    this.open = open;
    localStorage.setItem('caller.assistant.open', open ? '1' : '0');
    this.apply();
    if (open) { this.load(); setTimeout(() => $('#asst-q')?.focus(), 50); }
  },
  bindResizer() {
    const bar = $('#assistant-resizer');
    bar.onpointerdown = (e) => {
      e.preventDefault();
      bar.setPointerCapture(e.pointerId);
      document.body.classList.add('resizing');
      const move = (ev) => {
        const max = Math.max(360, Math.min(window.innerWidth - 480, 1100));
        this.width = Math.round(Math.min(max, Math.max(320, window.innerWidth - ev.clientX)));
        this.apply();
      };
      const up = () => {
        bar.removeEventListener('pointermove', move);
        document.body.classList.remove('resizing');
        localStorage.setItem('caller.assistant.width', this.width);
      };
      bar.addEventListener('pointermove', move);
      bar.addEventListener('pointerup', up, { once: true });
    };
    bar.ondblclick = () => { this.width = 420; this.apply(); localStorage.setItem('caller.assistant.width', 420); };
  },
  async load() {
    this.chats = await api('/assistant/chats');
    if (!this.chats.some((c) => c.id === this.chatId)) this.chatId = this.chats[0]?.id || null;
    await this.openChat(this.chatId);
  },
  async openChat(id) {
    this.chatId = id;
    if (id) localStorage.setItem('caller.assistant.chat', id); else localStorage.removeItem('caller.assistant.chat');
    this.messages = id ? await api(`/assistant/chats/${id}/messages`) : [];
    this.render();
  },
  async newChat() {
    // an empty chat is reused instead of piling up «Новый чат»s
    const empty = this.chats.find((c) => c.id === this.chatId) && !this.messages.length;
    if (!empty) { const c = await api('/assistant/chats', { method: 'POST' }); this.chats.unshift(c); this.chatId = c.id; }
    await this.openChat(this.chatId);
    $('#asst-q').focus();
  },
  chatMenu(anchor) {
    openMenu(anchor, [
      ...this.chats.slice(0, 15).map((c) => ({ label: (c.id === this.chatId ? '• ' : '') + c.title, icon: 'message', run: () => this.openChat(c.id) })),
      this.chats.length ? '-' : null,
      { label: 'Новый чат', icon: 'plus', run: () => this.newChat() },
      this.chatId ? { label: 'Удалить этот чат', icon: 'trash', danger: true, run: () => confirmBox('Удалить чат? Дела и звонки останутся.', async () => {
        await api('/assistant/chats/' + this.chatId, { method: 'DELETE' });
        this.chats = this.chats.filter((c) => c.id !== this.chatId);
        await this.openChat(this.chats[0]?.id || null);
      }) } : null,
    ]);
  },
  render() {
    const chat = this.chats.find((c) => c.id === this.chatId);
    $('#asst-title').textContent = chat ? chat.title : 'Ассистент';
    const feed = $('#asst-feed');
    if (!this.messages.length) {
      const hints = ['Что мне просили напомнить?', 'Какие ближайшие встречи запланированы?', 'Что просрочено?', 'Найди номер мамы'];
      feed.innerHTML = `<div class="asst-empty">${icon('sparkle')}<div>Я знаю ваши контакты, дела, встречи и могу подготовить звонок.</div>
        <div class="asst-hints">${hints.map((h) => `<button type="button" class="chip-btn" data-hint="${esc(h)}">${esc(h)}</button>`).join('')}</div></div>`;
      $$('[data-hint]', feed).forEach((b) => b.onclick = () => this.send(b.dataset.hint));
      return;
    }
    feed.innerHTML = this.messages.map((m) => this.item(m)).join('') + (this.busy ? '<div class="asst-typing"><span></span><span></span><span></span></div>' : '');
    this.bindCards(feed);
    feed.scrollTop = feed.scrollHeight;
  },
  item(m) {
    if (m.role === 'user') return `<div class="bubble me">${esc(m.text)}</div>`;
    if (m.role === 'assistant') {
      const link = m.data?.link;
      return `<div class="bubble ai">${esc(m.text)}</div>${m.objects?.length ? `<div class="asst-objs">${m.objects.map((o, i) => this.object(o, m.id, i)).join('')}</div>` : ''}`
        + (link ? `<a class="asst-link" href="${esc(link.href)}" title="Открыть в разделе слева">${esc(link.label)} ${icon('arrowRight')}</a>` : '');
    }
    const d = m.data || {};
    if (d.type === 'task_done') {
      return `<div class="asst-card ${d.status === 'done' ? 'ok' : 'muted'}" data-msg="${m.id}">${icon(d.status === 'done' ? 'check' : 'refresh')}
        <div class="asst-card-main"><b>${esc(d.title)}</b><span class="small muted">${d.status === 'done' ? 'Отмечено выполненным' : 'Выполнение отменено — дело снова в работе'}</span></div>
        ${d.status === 'done' ? '<button type="button" class="btn btn-ghost btn-sm" data-undo>Отменить</button>' : ''}</div>`;
    }
    if (d.type === 'place') {
      const link = d.lat ? `https://yandex.ru/maps/?pt=${d.lon},${d.lat}&z=16&l=map` : `https://yandex.ru/maps/?text=${encodeURIComponent(d.query)}`;
      return `<div class="asst-card place" data-msg="${m.id}">
        <div class="row" style="gap:10px;flex-wrap:nowrap">${icon('pin')}<div class="asst-card-main"><b>${esc(d.title || d.address || d.query)}</b>
          <span class="small muted" data-place-line>${esc(d.address || (d.title ? d.query : '') || 'Ищем на карте…')}</span></div>
          <a class="btn btn-ghost btn-sm" href="${esc(link)}" target="_blank" rel="noopener" title="Открыть в Яндекс Картах">${icon('eye')}</a></div>
        <div class="map-box asst-map" data-place-map></div></div>`;
    }
    if (d.type === 'call') {
      const who = d.name ? `${esc(d.name)}${d.relation ? ` <span class="muted">· ${esc(d.relation)}</span>` : ''}` : esc(d.number);
      if (d.status !== 'pending') {
        return `<div class="asst-card ${d.status === 'dialed' ? 'ok' : 'muted'}" data-msg="${m.id}">${icon('phoneOut')}
          <div class="asst-card-main"><b>${who}</b><span class="small muted">${d.status === 'dialed' ? 'Звонок начат' + (d.prompt ? ` · ${esc(d.prompt)}` : '') : 'Звонок отменён'}</span></div>
          ${d.call_id ? `<button type="button" class="btn btn-ghost btn-sm" data-open-call="${d.call_id}">Открыть</button>` : ''}</div>`;
      }
      const outScripts = state.scripts.filter((x) => x.direction === 'any' || x.direction === 'outbound');
      return `<div class="asst-card call" data-msg="${m.id}">
        <div class="row" style="gap:10px;flex-wrap:nowrap">${icon('phoneOut')}<div class="asst-card-main"><b>${who}</b><span class="small muted mono">${esc(d.number)}</span></div></div>
        <div class="form-2"><div class="field"><label>Агент</label><select data-agent>${state.agents.map((a) => `<option value="${a.id}" ${a.id === d.agent_id ? 'selected' : ''}>${esc(a.name)}</option>`).join('')}</select></div>
          <div class="field"><label>Сценарий</label><select data-script>${outScripts.map((x) => `<option value="${x.id}" ${x.id === d.script_id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}<option value="" ${d.script_id ? '' : 'selected'}>— без сценария —</option></select></div></div>
        <div class="field"><label>Поручение агенту</label><textarea data-prompt rows="2" placeholder="Что узнать или сообщить в разговоре — необязательно">${esc(d.prompt || '')}</textarea></div>
        <div class="row" style="gap:8px"><button type="button" class="btn btn-primary" data-call>${icon('phoneOut')} Позвонить</button>
          <button type="button" class="btn btn-ghost" data-cancel>Отмена</button></div></div>`;
    }
    return '';
  },
  // the widgets under an answer: the contacts, tasks and calls it talks about
  object(o, msgId, i) {
    const x = o.item, ref = `data-obj="${msgId}:${i}"`;
    if (o.type === 'contact') {
      const name = x.label || x.name || x.phone;
      return `<div class="asst-obj contact" ${ref}><div class="avatar sm"${avatarStyle(name || '#')}>${esc(initials(name || '#'))}</div>
        <div class="asst-card-main"><b class="ellipsis">${esc(name)}</b><span class="small muted ellipsis">${esc([x.relation, x.phone, x.company].filter(Boolean).join(' · '))}</span></div>${KEBAB}</div>`;
    }
    if (o.type === 'task') {
      const done = x.status === 'done';
      return `<div class="asst-obj task ${done ? 'done' : ''}" ${ref}><span class="task-dot ${done ? 'ok' : isOverdue(x) ? 'err' : ''}">${icon(done ? 'check' : 'tasks')}</span>
        <div class="asst-card-main"><b class="ellipsis">${esc(x.title)}</b><span class="small muted ellipsis">${[x.due_at ? fmtDue(x) : '', esc(x.contact_name || '')].filter(Boolean).join(' · ') || (done ? 'выполнено' : 'без срока')}</span></div>
        ${x.event ? `<span class="faint" title="Есть событие в календаре">${icon('calendar')}</span>` : ''}${x.geo ? `<span class="faint" title="Есть место на карте">${icon('pin')}</span>` : ''}${KEBAB}</div>`;
    }
    if (o.type === 'call') return `<div class="asst-obj call" ${ref}>${VIEWS.calls.card(x)}</div>`;
    return '';
  },
  bindObjects(feed) {
    const refresh = () => this.openChat(this.chatId);  // the widgets show the objects as they are now
    $$('[data-obj]', feed).forEach((el) => {
      const [mid, i] = el.dataset.obj.split(':').map(Number);
      const o = this.messages.find((m) => m.id === mid)?.objects?.[i];
      if (!o) return;
      const x = o.item, k = $('.kebab', el);
      if (o.type === 'call') {
        $$('.call-summary', el).forEach((n) => n.remove());
        if (k) k.onclick = (e) => { e.stopPropagation(); openMenu(k, [
          { label: 'Открыть звонок', icon: 'eye', run: () => showCall(x.id) },
          x.recording ? { label: 'Скачать аудиофайл', icon: 'download', run: () => downloadRecording(x) } : null,
        ]); };
        return;
      }
      if (o.type === 'contact') {
        el.onclick = (e) => { if (!e.target.closest('.kebab')) editContact(x, refresh, 1); };
        if (k) k.onclick = (e) => { e.stopPropagation(); personMenu(k, x.phone, { changed: refresh }); };
      } else {
        el.onclick = (e) => { if (!e.target.closest('.kebab')) openTask(x, 'task', refresh); };
        if (k) k.onclick = (e) => { e.stopPropagation(); openMenu(k, [{ label: 'Открыть', icon: 'eye', run: () => openTask(x, 'task', refresh) }, ...taskActions(x, refresh)]); };
      }
    });
  },
  // a map card: the point is known (a task's place) or found here by the Yandex geocoder
  async drawPlace(card, d) {
    const box = $('[data-place-map]', card), line = $('[data-place-line]', card);
    const key = await mapsKey();
    const fail = (text) => { box.innerHTML = `<div class="asst-map-msg small muted">${text}</div>`; if (!d.lat) line.textContent = d.query; };
    if (!key) return fail('Карта появится, когда будет ключ: <a href="#/settings?tab=maps">Настройки → Яндекс Карты</a>. Пока — ссылка справа.');
    let ym;
    try { ym = await loadYmaps(key); } catch (e) { return fail(esc(e.message)); }
    let point = d.lat ? [d.lat, d.lon] : null, address = d.address || '';
    if (!point) {
      try {
        const res = await ym.geocode(d.query, { results: 1 });
        const obj = res.geoObjects.get(0);
        if (!obj) return fail('На карте ничего не нашлось — уточните адрес.');
        point = obj.geometry.getCoordinates(); address = obj.getAddressLine();
      } catch (e) { return fail('Геокодер не ответил: ' + esc(e?.message || String(e))); }
    }
    if (!card.isConnected) return;
    line.textContent = address || d.query;
    const map = new ym.Map(box, { center: point, zoom: 15, controls: ['zoomControl'] });
    map.geoObjects.add(new ym.Placemark(point, { hintContent: esc(d.title || address) }, { preset: 'islands#violetDotIcon' }));
  },
  bindCards(feed) {
    this.bindObjects(feed);
    $$('.asst-card.place', feed).forEach((card) => this.drawPlace(card, this.messages.find((x) => x.id === +card.dataset.msg)?.data || {}));
    const replace = (msg) => { const i = this.messages.findIndex((x) => x.id === msg.id); if (i >= 0) this.messages[i] = msg; this.render(); };
    $$('.asst-card', feed).forEach((card) => {
      const id = +card.dataset.msg;
      $('[data-undo]', card)?.addEventListener('click', guard(async () => { replace(await api(`/assistant/actions/${id}/undo`, { method: 'POST' })); toast('Дело снова в работе', 'ok'); }));
      $('[data-cancel]', card)?.addEventListener('click', guard(async () => replace(await api(`/assistant/actions/${id}/cancel`, { method: 'POST' }))));
      $('[data-open-call]', card)?.addEventListener('click', () => showCall(+$('[data-open-call]', card).dataset.openCall));
      const call = $('[data-call]', card);
      if (call) call.onclick = guard(async () => {
        const label = call.innerHTML; call.disabled = true; call.innerHTML = '<span class="spin"></span> Готовим агента…';
        try {
          replace(await api(`/assistant/actions/${id}/confirm`, { method: 'POST', body: {
            prompt: $('[data-prompt]', card).value, agent_id: +$('[data-agent]', card).value || null, script_id: +$('[data-script]', card).value || 0 } }));
          toast('Набираем номер…', 'ok');
        } finally { if (call.isConnected) { call.disabled = false; call.innerHTML = label; } }
      });
    });
  },
  async send(text) {
    text = (text || '').trim();
    if (!text || this.busy) return;
    if (!this.chatId) { const c = await api('/assistant/chats', { method: 'POST' }); this.chats.unshift(c); this.chatId = c.id; localStorage.setItem('caller.assistant.chat', c.id); }
    const q = $('#asst-q'); q.value = ''; q.style.height = 'auto';
    this.busy = true;
    this.messages.push({ id: -1, role: 'user', text });
    this.render();
    try {
      const fresh = await api(`/assistant/chats/${this.chatId}/messages`, { method: 'POST', body: { text } });
      this.messages = this.messages.filter((m) => m.id !== -1).concat(fresh);
      const chat = this.chats.find((c) => c.id === this.chatId);
      if (chat && chat.title === 'Новый чат') chat.title = text.slice(0, 60);
    } catch (e) {
      this.messages = this.messages.filter((m) => m.id !== -1);
      q.value = text;
      toast(e.message, 'err', 6000);
    } finally {
      this.busy = false;
      this.render();
    }
  },
};

async function start() {
  renderUser();
  try { await loadRefs(); } catch { /* shown per view */ }
  refreshBadges();
  if (!started) { started = true; connectWS(); window.addEventListener('hashchange', route); }
  assistantUI.mount();
  route();
}

(async function init() {
  $('#brand-logo').innerHTML = icon('phone');
  $('#menu-btn').innerHTML = icon('menu');
  $('#menu-btn').onclick = () => $('#sidebar').classList.toggle('open');
  applyTheme(localStorage.getItem('caller.theme') || 'dark');
  api('/health').then((h) => {
    state.sslPort = h.ssl_port;
    state.version = h;
    $$('[data-version]').forEach((el) => { el.textContent = versionLabel(); el.title = 'Версия и время сборки'; });
  }).catch(() => {});
  try {
    state.user = await api('/auth/me');
  } catch {
    showLogin();
    return;
  }
  start();
})();
