'use strict';

const $ = (id) => document.getElementById(id);
const DEFAULT_VOICE = '4b6d1ad3-97a4-4c60-bcae-c6a34537ad77'; // «Спокойный женский голос»
const RT_MODEL = 'fishaudio-s21pro-flash';
// кредитов за символ для русского текста (ставка для «прочих» символов = половина китайской)
const RATE = { 'fishaudio-s21pro-flash': 0.25, 'fishaudio-s21pro': 0.5 };
const PRESETS = [
  'Здравствуйте! Меня зовут Анна, я виртуальный помощник. Чем могу помочь?',
  'Да, конечно. Сейчас проверю ваш заказ, одну секунду.',
  'Ваша запись подтверждена на завтра, на двенадцать часов. Если планы изменятся, просто перезвоните нам.',
  'Алло?',
];

// ------------------------------------------------------------------ state
let ws;                      // браузер <-> наш сервер
let sess = { state: 'none', key: '', readyWaiters: [] };
let run = null;              // текущий запуск
let lastRun = null;
let pendingAudioMeta = null;
let quota = null;
let runCounter = 0;
const history = [];

const now = () => performance.now();
const rel = () => (run ? now() - run.t0 : 0);
const fmt = (ms) => (ms == null || isNaN(ms) ? '—' : ms >= 1000 ? (ms / 1000).toFixed(2) + ' с' : Math.round(ms) + ' мс');

function log(line, cls) {
  const el = $('log');
  const t = run ? `[${Math.round(rel()).toString().padStart(5)}] ` : '        ';
  el.insertAdjacentHTML('beforeend', `<span class="${cls || ''}">${t}${line.replace(/</g, '&lt;')}</span>\n`);
  el.scrollTop = el.scrollHeight;
}

// ------------------------------------------------------------------ server socket
function openSocket() {
  return new Promise((resolve) => {
    ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/tts`);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => resolve();
    ws.onmessage = onServerMessage;
    ws.onclose = () => {
      setSession('none');
      log('соединение с демо-сервером закрыто, переподключаюсь…', 'err');
      setTimeout(openSocket, 1000);
    };
  });
}

function send(obj) { ws.send(JSON.stringify(obj)); }

function onServerMessage(m) {
  if (typeof m.data !== 'string') {
    onAudio(m.data, pendingAudioMeta || {});
    pendingAudioMeta = null;
    return;
  }
  const ev = JSON.parse(m.data);
  if (ev.event === 'audio') { pendingAudioMeta = ev; return; }
  onEvent(ev);
}

function onEvent(ev) {
  const { event } = ev;
  if (event !== 'input_ack') log(`${event} ${short(ev)}`, event === 'error' ? 'err' : '');
  if (ev.quotaRemaining != null) setQuota(ev.quotaRemaining);
  if (ev.quota && ev.quota.remaining != null) setQuota(ev.quota.remaining);

  switch (event) {
    case 'ready':
      sess.connectMs = now() - sess.connectStarted;
      setSession('ready');
      sess.readyWaiters.splice(0).forEach((w) => w.resolve());
      break;
    case 'segment_completed':
      if (run && !run.done) {
        run.completed += 1;
        run.units += ev.units || 0;
        maybeFinish();
      }
      break;
    case 'error':
      if (ev.terminal) {
        sess.readyWaiters.splice(0).forEach((w) => w.reject(new Error(ev.message || ev.code)));
        if (run && !run.done) failRun(`${ev.code}: ${ev.message || ''}`);
      }
      break;
    case 'session_closed': {
      const lived = now() - (sess.connectStarted || 0);
      setSession('none');
      sess.readyWaiters.splice(0).forEach((w) => w.reject(new Error('сессия закрыта')));
      if (run && !run.done && run.mode !== 'http') failRun('сессия закрыта сервером');
      // держим соединение прогретым: переподключаемся, если сессия прожила дольше 5 с
      if ($('warm').checked && lived > 5000 && !(run && !run.done)) setTimeout(prewarm, 300);
      break;
    }
  }
}

function short(ev) {
  const skip = new Set(['type', 'event', 't']);
  const o = Object.fromEntries(Object.entries(ev).filter(([k]) => !skip.has(k)));
  const s = JSON.stringify(o);
  return s === '{}' ? '' : s.length > 180 ? s.slice(0, 180) + '…' : s;
}

// ------------------------------------------------------------------ session (upstream realtime)
function sessionKey() { return `${$('voice').value}|${$('latency').value}`; }

function setSession(state) {
  sess.state = state;
  const b = $('session-badge');
  b.className = 'badge ' + (state === 'ready' ? 'on' : state === 'connecting' ? 'busy' : 'off');
  b.textContent = state === 'ready' ? 'сессия: прогрета' : state === 'connecting' ? 'сессия: подключение…' : 'сессия: нет';
}

function connectSession() {
  const key = sessionKey();
  if (sess.state === 'ready' && sess.key === key) return Promise.resolve({ warm: true });
  if (sess.state === 'connecting' && sess.key === key) {
    return new Promise((resolve, reject) => sess.readyWaiters.push({ resolve: () => resolve({ warm: false }), reject }));
  }
  sess.key = key;
  sess.connectStarted = now();
  setSession('connecting');
  const p = new Promise((resolve, reject) => sess.readyWaiters.push({ resolve: () => resolve({ warm: false }), reject }));
  send({ type: 'connect', voiceId: $('voice').value, modelId: RT_MODEL, latency: $('latency').value });
  return p;
}

let prewarmTimer;
function prewarm() {
  clearTimeout(prewarmTimer);
  if (!$('warm').checked || (run && !run.done)) return;
  prewarmTimer = setTimeout(() => connectSession().catch((e) => log('прогрев: ' + e.message, 'err')), 150);
}

// ------------------------------------------------------------------ streaming player (MSE)
class StreamPlayer {
  // autoplay=false — звук копится, но играет только после start() (ждём конца заготовки)
  constructor(audio, autoplay = true) {
    this.autoplay = autoplay;
    this.audio = audio;
    this.queue = [];
    this.ended = false;
    this.useMse = window.MediaSource && MediaSource.isTypeSupported('audio/mpeg');
    this.parts = [];
    if (this.useMse) {
      this.ms = new MediaSource();
      audio.src = URL.createObjectURL(this.ms);
      this.ms.addEventListener('sourceopen', () => {
        this.sb = this.ms.addSourceBuffer('audio/mpeg');
        this.sb.addEventListener('updateend', () => this.pump());
        this.pump();
      }, { once: true });
      if (autoplay) this.start();
    }
  }
  start() {
    this.autoplay = true;
    if (this.useMse || this.ended) this.audio.play().catch(() => {});
  }
  push(buf) {
    if (!this.useMse) { this.parts.push(buf); return; }
    this.queue.push(buf);
    this.pump();
  }
  end() {
    this.ended = true;
    if (!this.useMse) {
      this.audio.src = URL.createObjectURL(new Blob(this.parts, { type: 'audio/mpeg' }));
      if (this.autoplay) this.audio.play().catch(() => {});
      return;
    }
    this.pump();
  }
  pump() {
    if (!this.sb || this.sb.updating) return;
    if (this.queue.length) { this.sb.appendBuffer(this.queue.shift()); return; }
    if (this.ended && this.ms.readyState === 'open') {
      try { this.ms.endOfStream(); } catch (_) { /* уже закрыт */ }
    }
  }
}

// ------------------------------------------------------------------ runs
function newRun(mode, text) {
  const player = $('player');
  player.pause();
  player.removeAttribute('src');
  const r = {
    id: ++runCounter, mode, text, chars: text.length, t0: now(),
    connectMs: null, warm: false, tTextStart: null,
    words: [], flushes: [], chunks: [], firstChunk: null, segTtfa: null,
    flushed: 0, completed: 0, llmDone: false, units: 0,
    playStart: null, playEnd: null, lastChunk: null, done: false, error: null,
  };
  run = r;
  lastRun = r;
  $('log').textContent = '';
  resetMetrics();
  return r;
}

function onAudio(buf, meta) {
  if (!run || run.done || run.mode === 'http') return;
  const t = rel();
  if (run.firstChunk == null) run.firstChunk = t;
  if (meta.segTtfa != null && run.segTtfa == null) {
    run.segTtfa = meta.segTtfa;
    $('m-ttfa').textContent = fmt(run.segTtfa);
  }
  run.lastChunk = t;
  run.chunks.push({ t, bytes: buf.byteLength, seg: meta.segmentId });
  run.player.push(buf);
  // ответ пришёл раньше, чем понадобилась заготовка, — играем сразу
  if (run.chunks.length === 1 && run.gated && !run.fillerPlaying) {
    clearTimeout(run.fillTimer);
    run.player.start();
  }
}

// ------------------------------------------------------------------ заготовки хезитаций
let fillers = [];
let lastFillerId = null;

async function loadFillers() {
  const voiceId = $('voice').value;
  const data = await (await fetch('/api/fillers?voiceId=' + encodeURIComponent(voiceId))).json();
  fillers = data.items.map((f) => {
    const el = new Audio(f.url + '?v=' + Date.now());
    el.preload = 'auto';
    const item = { ...f, el, durMs: null };
    el.addEventListener('loadedmetadata', () => { item.durMs = el.duration * 1000; renderFillers(); }, { once: true });
    return item;
  });
  const cost = Math.ceil(data.estimate * RATE[RT_MODEL]);
  $('btn-fill-gen').textContent = fillers.length ? `Перегенерировать (≈${cost} кр.)` : `Сгенерировать для голоса (≈${cost} кр.)`;
  $('fill-status').textContent = fillers.length ? '' : 'для этого голоса заготовок ещё нет';
  renderFillers();
}

function renderFillers() {
  const list = $('filler-list');
  list.innerHTML = '';
  fillers.forEach((f) => {
    const b = document.createElement('button');
    b.className = f.kind;
    b.innerHTML = `${f.text}<span class="d">${f.durMs ? (f.durMs / 1000).toFixed(1) + ' с' : ''}</span>`;
    b.title = f.kind === 'short' ? 'короткая' : 'длинная';
    b.onclick = () => { f.el.currentTime = 0; f.el.play(); };
    list.appendChild(b);
  });
}

async function generateFillers() {
  const btn = $('btn-fill-gen');
  if (!confirm(`${btn.textContent}: потратить кредиты API-квоты?`)) return;
  btn.disabled = true;
  $('fill-status').textContent = 'генерирую…';
  try {
    const resp = await fetch('/api/fillers/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voiceId: $('voice').value }),
    });
    const data = await resp.json();
    $('fill-status').textContent = `готово: ${data.items.length} шт., ${data.units} кр.` + (data.errors.length ? ` · ошибки: ${data.errors.join('; ')}` : '');
    await loadFillers();
  } catch (e) {
    $('fill-status').textContent = 'ошибка: ' + e.message;
  }
  btn.disabled = false;
  refreshQuota();
}

function pickFiller() {
  const kind = $('fill-kind').value;
  let pool = fillers.filter((f) => kind === 'any' || f.kind === kind);
  if (pool.length > 1) pool = pool.filter((f) => f.id !== lastFillerId);
  if (!pool.length) return null;
  const f = pool[Math.floor(Math.random() * pool.length)];
  lastFillerId = f.id;
  return f;
}

function playFiller(r) {
  if (r.done || r.firstChunk != null) return;
  const f = pickFiller();
  if (!f) { r.player.start(); return; }
  r.filler = f;
  r.fillerPlaying = true;
  f.el.currentTime = 0;
  f.el.addEventListener('playing', () => {
    r.fillerStart = now() - r.t0;
    updateFirst(r);
    tick();
  }, { once: true });
  f.el.addEventListener('ended', () => {
    r.fillerEnd = now() - r.t0;
    r.fillerPlaying = false;
    r.player.start(); // ответ играет сразу после заготовки (или как только придут данные)
  }, { once: true });
  f.el.play().catch(() => { r.fillerPlaying = false; r.player.start(); });
  log(`заготовка «${f.text}»`);
}

function updateFirst(r) {
  const first = [r.fillerStart, r.playStart].filter((x) => x != null);
  r.firstSound = first.length ? Math.min(...first) : null;
  $('m-first').textContent = fmt(r.firstSound);
  $('m-answer').textContent = fmt(r.playStart);
  if (r.fillerStart != null) {
    $('m-first-hint').textContent = `заготовка «${r.filler.text}»`;
  }
  if (r.playStart != null) {
    const parts = [];
    if (r.mode === 'llm' && r.flushes.length) parts.push(`от конца 1-й фразы — ${fmt(r.playStart - r.flushes[0])}`);
    if (r.fillerEnd != null) parts.push(`тишина после заготовки — ${fmt(Math.max(0, r.playStart - r.fillerEnd))}`);
    $('m-answer-hint').textContent = parts.join(' · ') || 'когда зазвучал сам ответ';
  }
  updateHistory(r);
}

function flush() {
  run.flushed += 1;
  run.flushes.push(rel());
  send({ type: 'flush' });
}

function maybeFinish() {
  if (run && run.llmDone && run.completed >= run.flushed && run.flushed > 0) finishRun();
}

function finishRun() {
  const r = run;
  r.done = true;
  r.genMs = (r.lastChunk ?? rel()) - r.tTextStart;
  r.player.end();
  if (!$('warm').checked) send({ type: 'stop' });
  $('m-gen').textContent = fmt(r.genMs);
  addHistory(r);
  setBusy(false);
  refreshQuota();
  if ($('warm').checked && sess.state !== 'ready') prewarm();
}

function failRun(msg) {
  if (!run || run.done) return;
  run.done = true;
  run.error = msg;
  clearTimeout(run.fillTimer);
  if (run.filler) run.filler.el.pause();
  run.player && run.player.end();
  log('запуск прерван: ' + msg, 'err');
  $('tl-note').textContent = 'ошибка: ' + msg;
  setBusy(false);
  refreshQuota();
}

async function startStream(mode) {
  const text = $('text').value.trim();
  if (!text || (run && !run.done)) return;
  if (!$('voice').value) return alert('Выберите голос');
  const r = newRun(mode, text);
  setBusy(true);
  // нажатие = абонент договорил; если ответа нет дольше fill-delay — играем заготовку
  r.gated = $('fill-on').checked && fillers.length > 0;
  r.player = new StreamPlayer($('player'), !r.gated);
  if (r.gated) r.fillTimer = setTimeout(() => playFiller(r), Number($('fill-delay').value) || 0);
  renderLlmText(r);

  try {
    const res = await connectSession();
    r.warm = res.warm;
    r.connectMs = res.warm ? 0 : rel();
  } catch (e) {
    return failRun('подключение: ' + e.message);
  }
  $('m-connect').textContent = r.warm ? '0 мс' : fmt(r.connectMs);
  $('m-connect-hint').textContent = r.warm
    ? `прогрето заранее (${fmt(sess.connectMs)})`
    : 'WebSocket + auth + ready';
  if (mode === 'llm') {
    // имитация «думания» LLM до первого токена (параллельно подключению)
    const wait = (Number($('ttft').value) || 0) - rel();
    if (wait > 0) await sleep(wait);
    if (r.done) return;
  }
  r.tTextStart = rel();

  if (mode === 'whole') {
    r.words.forEach((w) => { w.t = rel(); });
    send({ type: 'text', text });
    flush();
    r.llmDone = true;
    renderLlmText(r);
    return;
  }

  // «как LLM»: слова приходят потоком, сегмент отправляется в синтез на конце предложения
  const delay = 1000 / Number($('wps').value);
  let segChars = 0;
  for (let i = 0; i < r.words.length; i++) {
    if (r.done) return;
    const w = r.words[i];
    send({ type: 'text', text: w.text });
    w.t = rel();
    segChars += w.text.length;
    const trimmed = w.text.trim();
    const sentenceEnd = /[.!?…]["»)]*$/.test(trimmed);
    const earlyCut = $('early-flush').checked && r.flushed === 0 && /[,;:—]$/.test(trimmed) && segChars >= 8;
    if ((sentenceEnd || earlyCut) && i < r.words.length - 1) {
      flush();
      w.cut = true;
      segChars = 0;
    }
    renderLlmText(r);
    if (i < r.words.length - 1) await sleep(delay);
  }
  if (r.done) return;
  flush();
  r.llmDone = true;
  renderLlmText(r);
  maybeFinish();
}

async function startHttp() {
  const text = $('text').value.trim();
  if (!text || (run && !run.done)) return;
  const r = newRun('http', text);
  setBusy(true);
  renderLlmText(r);
  r.tTextStart = 0;
  $('m-connect').textContent = '—';
  $('m-connect-hint').textContent = 'обычный HTTP-запрос';
  try {
    const resp = await fetch('/api/http-tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voiceId: $('voice').value, modelId: $('http-model').value }),
    });
    if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`);
    r.firstChunk = rel();
    const blob = await resp.blob();
    r.lastChunk = rel();
    r.segTtfa = Number(resp.headers.get('X-Ttfb-Ms'));
    r.units = Number(resp.headers.get('X-Credits-Used')) || 0;
    const q = resp.headers.get('X-Quota-Remaining');
    if (q) setQuota(Number(q));
    r.chunks.push({ t: r.lastChunk, bytes: blob.size });
    r.flushes.push(0);
    r.words.forEach((w) => { w.t = 0; });
    $('m-ttfa').textContent = fmt(r.segTtfa);
    log(`HTTP: первый байт от API ${fmt(r.segTtfa)}, весь файл ${resp.headers.get('X-Total-Ms')} мс, ${blob.size} байт`);
    $('player').src = URL.createObjectURL(blob);
    $('player').play().catch(() => {});
    r.done = true;
    r.genMs = r.lastChunk;
    $('m-gen').textContent = fmt(r.genMs);
    addHistory(r);
  } catch (e) {
    r.done = true;
    r.error = e.message;
    log('HTTP ошибка: ' + e.message, 'err');
  }
  setBusy(false);
  renderLlmText(r);
}

function stopAll() {
  if (run && !run.done) {
    send({ type: 'close' });
    failRun('остановлено');
  }
  $('player').pause();
}

// события плеера — момент реального начала/конца звучания
$('player').addEventListener('playing', () => {
  const r = lastRun;
  if (!r || r.playStart != null) return;
  r.playStart = now() - r.t0;
  updateFirst(r);
});
$('player').addEventListener('ended', () => {
  const r = lastRun;
  if (r && r.playEnd == null) r.playEnd = now() - r.t0;
});
$('player').addEventListener('durationchange', () => {
  const r = lastRun;
  const d = $('player').duration;
  if (!r || !isFinite(d)) return;
  r.audioMs = d * 1000;
  $('m-dur').textContent = fmt(r.audioMs);
  updateRtf(r);
  updateHistory(r);
});
// «паузы» — плеер остановился в ожидании данных уже после начала звучания
$('player').addEventListener('waiting', () => {
  const r = lastRun;
  if (!r || r.playStart == null || r.playEnd != null) return;
  r.stallStart = now();
});
$('player').addEventListener('playing', () => {
  const r = lastRun;
  if (!r || r.stallStart == null) return;
  r.stalls = (r.stalls || 0) + 1;
  r.stallMs = (r.stallMs || 0) + (now() - r.stallStart);
  r.stallStart = null;
  updateRtf(r);
});

function updateRtf(r) {
  if (r !== lastRun || !r.audioMs) return;
  const parts = [];
  const streamMs = r.genMs - (r.firstChunk - r.tTextStart); // от первого до последнего чанка
  if (r.mode !== 'http' && r.chunks.length > 2 && streamMs > 300) {
    const k = r.audioMs / streamMs;
    parts.push(k >= 0.95 ? `поток успевает за звуком (${k.toFixed(1)}×)` : `поток медленнее звука (${k.toFixed(1)}×)`);
  }
  parts.push(r.stalls ? `паузы: ${r.stalls} (${fmt(r.stallMs)})` : 'без пауз');
  $('m-rtf').textContent = parts.join(' · ');
}

// ------------------------------------------------------------------ UI: metrics / history
function resetMetrics() {
  ['m-first', 'm-answer', 'm-ttfa', 'm-connect', 'm-gen', 'm-dur'].forEach((id) => { $(id).textContent = '—'; });
  $('m-rtf').innerHTML = '&nbsp;';
  $('m-first-hint').textContent = 'от конца реплики абонента (нажатия) до звука';
  $('m-answer-hint').textContent = 'когда зазвучал сам ответ';
  $('tl-note').textContent = '';
}

const MODE_NAME = { whole: 'стрим · весь текст', llm: 'стрим · как LLM', http: 'HTTP целиком' };

function addHistory(r) {
  history.unshift(r);
  renderHistory();
}
function updateHistory(r) { if (history.includes(r)) renderHistory(); }

function renderHistory() {
  history.forEach((r) => { if (r.firstSound == null) r.firstSound = r.playStart; });
  const firsts = history.map((r) => r.firstSound).filter((x) => x != null);
  const best = firsts.length ? Math.min(...firsts) : null;
  $('history').querySelector('tbody').innerHTML = history.map((r) => {
    let mode = MODE_NAME[r.mode];
    if (r.mode !== 'http') mode += r.warm ? ' (прогрето)' : ' (холодный)';
    if (r.mode === 'http') mode += ` · ${$('http-model').selectedOptions[0].text}`;
    return `<tr>
      <td>${r.id}</td><td>${mode}</td><td>${r.chars}</td>
      <td>${r.mode === 'http' ? '—' : fmt(r.connectMs)}</td>
      <td class="${r.firstSound === best ? 'best' : ''}">${fmt(r.firstSound)}</td>
      <td>${r.filler ? r.filler.text : '—'}</td><td>${fmt(r.playStart)}</td>
      <td>${fmt(r.segTtfa)}</td><td>${fmt(r.genMs)}</td><td>${fmt(r.audioMs)}</td><td>${r.units || '—'}</td>
    </tr>`;
  }).join('');
}

function setBusy(b) {
  ['btn-whole', 'btn-llm', 'btn-http'].forEach((id) => { $(id).disabled = b; });
  if (b) tick();
}

// ------------------------------------------------------------------ UI: text + timeline
function renderLlmText(r) {
  if (!r.words.length) {
    r.words = r.text.split(/(?<=\s)/).map((text) => ({ text, t: null, cut: false }));
  }
  $('llm-text').innerHTML = r.words.map((w) => {
    const cls = 'w' + (w.t != null ? ' sent' : '');
    return `<span class="${cls}">${w.text.replace(/</g, '&lt;')}</span>${w.cut ? '<span class="cut" title="сегмент отправлен в синтез">⏎</span>' : ''}`;
  }).join('');
}

function tick() {
  drawTimeline(lastRun);
  const player = $('player');
  if ((run && !run.done) || (!player.paused && !player.ended)) requestAnimationFrame(tick);
  else setTimeout(() => drawTimeline(lastRun), 50);
}
$('player').addEventListener('play', () => tick());

function drawTimeline(r) {
  const svg = $('timeline');
  if (!r) { svg.innerHTML = ''; return; }
  const W = svg.clientWidth || 900;
  const L = 130, R = 16;
  const player = $('player');
  const playing = r.playStart != null && r.playEnd == null && !player.paused;
  const tNow = run === r && !r.done ? rel() : 0;
  const playEnd = r.playEnd ?? (playing ? now() - r.t0 : r.playStart != null && r.audioMs ? r.playStart + r.audioMs : null);
  const tMax = Math.max(1000, tNow, r.lastChunk || 0, playEnd || 0, r.playStart || 0) * 1.05;
  const x = (t) => L + (t / tMax) * (W - L - R);
  const rows = { text: 28, audio: 70, play: 112 };
  let s = '';

  // оси
  const step = tMax > 8000 ? 2000 : tMax > 4000 ? 1000 : 500;
  for (let t = 0; t <= tMax; t += step) {
    s += `<line class="axis" x1="${x(t)}" x2="${x(t)}" y1="10" y2="130"/>`;
    s += `<text x="${x(t)}" y="145" text-anchor="middle">${t >= 1000 ? t / 1000 + ' с' : t}</text>`;
  }
  s += `<text x="8" y="${rows.text + 4}">текст → API</text>`;
  s += `<text x="8" y="${rows.audio + 4}">аудио-чанки</text>`;
  s += `<text x="8" y="${rows.play + 4}">воспроизведение</text>`;

  // подключение
  if (r.connectMs) {
    s += `<rect x="${x(0)}" y="${rows.text - 7}" width="${x(r.connectMs) - x(0)}" height="14" rx="3" fill="var(--muted)" opacity=".25"/>`;
    s += `<text x="${x(0) + 4}" y="${rows.text + 4}">подключение</text>`;
  }
  // слова и точки отсечения
  r.words.forEach((w) => {
    if (w.t != null) s += `<circle cx="${x(w.t)}" cy="${rows.text}" r="3" fill="var(--text-dot)"/>`;
  });
  r.flushes.forEach((t) => {
    s += `<line x1="${x(t)}" x2="${x(t)}" y1="${rows.text - 12}" y2="${rows.audio + 10}" stroke="var(--flush)" stroke-width="2" stroke-dasharray="3 2"/>`;
  });
  // чанки
  const maxB = Math.max(1, ...r.chunks.map((c) => c.bytes));
  r.chunks.forEach((c) => {
    const h = 6 + 24 * Math.sqrt(c.bytes / maxB);
    s += `<rect x="${x(c.t) - 1.5}" y="${rows.audio - h / 2}" width="3" height="${h}" fill="var(--chunk)"><title>${c.bytes} байт @ ${Math.round(c.t)} мс</title></rect>`;
  });
  if (r.firstChunk != null) {
    s += `<text x="${x(r.firstChunk) + 5}" y="${rows.audio - 16}" fill="var(--chunk)" style="fill:var(--chunk)">1-й чанк ${fmt(r.firstChunk)}</text>`;
  }
  // заготовка
  if (r.fillerStart != null) {
    const fe = r.fillerEnd ?? (now() - r.t0);
    s += `<rect x="${x(r.fillerStart)}" y="${rows.play - 7}" width="${Math.max(2, x(fe) - x(r.fillerStart))}" height="14" rx="3" fill="var(--filler)" opacity=".85"><title>${r.filler.text}</title></rect>`;
    s += `<text x="${x(r.fillerStart)}" y="${rows.play - 11}" style="fill:var(--filler)">«${r.filler.text}»</text>`;
  }
  // воспроизведение
  if (r.playStart != null) {
    const end = playEnd ?? r.playStart;
    s += `<rect x="${x(r.playStart)}" y="${rows.play - 7}" width="${Math.max(2, x(end) - x(r.playStart))}" height="14" rx="3" fill="var(--play)" opacity=".8"/>`;
    s += `<text x="${x(r.playStart) + 4}" y="${rows.play + 22}" style="fill:var(--play)">звук с ${fmt(r.playStart)}</text>`;
  }
  if (tNow) s += `<line x1="${x(tNow)}" x2="${x(tNow)}" y1="10" y2="130" stroke="var(--fg)" opacity=".3"/>`;
  svg.innerHTML = s;
  $('tl-note').textContent = r.error ? 'ошибка: ' + r.error : `${r.chunks.length} чанков · ${(r.chunks.reduce((a, c) => a + c.bytes, 0) / 1024).toFixed(1)} КБ`;
}

// ------------------------------------------------------------------ quota, voices, cost
function setQuota(q) {
  quota = q;
  const b = $('quota-badge');
  b.textContent = `API-квота: ${q} кр.`;
  b.className = 'badge' + (q < 40 ? ' low' : '');
  updateCost();
}

async function refreshQuota() {
  try {
    const p = await (await fetch('/api/profile')).json();
    if (p.api_quota_remaining != null) setQuota(p.api_quota_remaining);
  } catch (_) { /* не критично */ }
}

function updateCost() {
  const n = $('text').value.trim().length;
  const s = Math.ceil(n * RATE[RT_MODEL]);
  const h = Math.ceil(n * RATE[$('http-model').value]);
  $('cost').textContent = `${n} симв. · ≈${s} кр. стрим / ≈${h} кр. HTTP` + (quota != null ? ` · осталось ${quota}` : '');
}

async function loadVoices(search = '') {
  const sel = $('voice');
  const prev = sel.value || DEFAULT_VOICE;
  const data = await (await fetch('/api/voices?search=' + encodeURIComponent(search))).json();
  const items = (data.items || []).filter((v) => (v.modelIds || []).includes(RT_MODEL));
  items.sort((a, b) => (b.primaryLanguage === 'ru') - (a.primaryLanguage === 'ru'));
  sel.innerHTML = items.map((v) => `<option value="${v.voiceId}">${v.isPersonal ? '★ ' : ''}${v.name} · ${v.primaryLanguage}</option>`).join('');
  if (!search && !items.some((v) => v.voiceId === DEFAULT_VOICE)) {
    sel.insertAdjacentHTML('afterbegin', `<option value="${DEFAULT_VOICE}">Спокойный женский голос · ru</option>`);
  }
  if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ------------------------------------------------------------------ init
function init() {
  PRESETS.forEach((p) => {
    const b = document.createElement('button');
    b.textContent = p.length > 40 ? p.slice(0, 40) + '…' : p;
    b.title = p;
    b.onclick = () => { $('text').value = p; updateCost(); };
    $('presets').appendChild(b);
  });
  $('text').value = PRESETS[0];
  $('text').addEventListener('input', updateCost);
  $('http-model').addEventListener('change', updateCost);
  $('wps').addEventListener('input', () => { $('wps-val').textContent = $('wps').value; });
  $('btn-whole').onclick = () => startStream('whole');
  $('btn-llm').onclick = () => startStream('llm');
  $('btn-http').onclick = startHttp;
  $('btn-stop').onclick = stopAll;
  $('voice').addEventListener('change', () => { prewarm(); loadFillers(); });
  $('btn-fill-gen').onclick = generateFillers;
  $('latency').addEventListener('change', prewarm);
  $('warm').addEventListener('change', () => {
    if ($('warm').checked) prewarm();
    else if (sess.state === 'ready') send({ type: 'close' }), setSession('none');
  });
  let st;
  $('voice-search').addEventListener('input', () => {
    clearTimeout(st);
    st = setTimeout(() => loadVoices($('voice-search').value.trim()).then(() => { prewarm(); loadFillers(); }), 350);
  });
  window.addEventListener('resize', () => drawTimeline(lastRun));
  updateCost();

  openSocket().then(async () => {
    await Promise.all([loadVoices(), refreshQuota()]);
    prewarm();
    loadFillers();
  });
}

init();
