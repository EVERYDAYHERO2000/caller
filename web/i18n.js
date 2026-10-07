// Interface language (Настройки → Интерфейс). The app is written in Russian; with English selected every
// text that appears on the page — text nodes and the placeholder / title / aria-label / data-tip attributes —
// is looked up in EN (exact phrase), then in PATTERNS (phrases with numbers), then piece by piece around " · ".
// User data (names, prompts, transcripts) is left alone unless it happens to equal a UI phrase; inputs and
// textareas are never touched. I18N.missing collects Russian phrases without a translation (for developers).
(function () {
  const LANG = localStorage.getItem('caller.lang') === 'en' ? 'en' : 'ru';
  const LOCALE = LANG === 'en' ? 'en-GB' : 'ru-RU';
  document.documentElement.lang = LANG;
  const CYR = /[А-Яа-яЁё]/;
  const ATTRS = ['placeholder', 'title', 'aria-label', 'data-tip'];
  const SKIP = 'textarea, input, script, style, [data-i18n-skip], .console, .code';
  const missing = new Set();
  const EN = window.I18N_EN || {};
  const PATTERNS = window.I18N_PATTERNS || [];

  const byPattern = (key) => {
    for (const [re, rep] of PATTERNS) {
      const m = key.match(re);
      if (m) return typeof rep === 'function' ? rep(...m) : key.replace(re, rep);
    }
    return null;
  };
  const one = (key) => EN[key] ?? byPattern(key);

  function t(s) {
    if (LANG !== 'en' || !s || !CYR.test(s)) return s;
    const lead = s.match(/^\s*/)[0], trail = s.match(/\s*$/)[0];
    const key = s.replace(/\s+/g, ' ').trim();
    let out = one(key);
    if (out == null && key.includes(' · ')) {  // "Yandex SpeechKit · женский", "12 кредитов · 3 с"
      const parts = key.split(' · ').map((p) => (CYR.test(p) ? one(p) ?? p : p));
      if (parts.some((p, i) => p !== key.split(' · ')[i])) out = parts.join(' · ');
    }
    if (out == null) {
      // a label with a trailing colon / asterisk / question mark: "Имя *", "Голос:"
      const m = key.match(/^(.*?)(\s*[*:?…]+)$/);
      const base = m && one(m[1]);
      if (base != null) out = base + m[2];
    }
    if (out == null) { missing.add(key); return s; }
    return lead + out + trail;
  }

  function translateNode(node) {
    if (node.nodeType === 3) {
      if (!CYR.test(node.nodeValue) || node.parentElement?.closest(SKIP)) return;
      const v = t(node.nodeValue);
      if (v !== node.nodeValue) node.nodeValue = v;
      return;
    }
    if (node.nodeType !== 1 || node.closest?.(SKIP) && !node.matches('input, textarea')) return;
    for (const a of ATTRS) {
      const v = node.getAttribute?.(a);
      if (v && CYR.test(v)) { const tv = t(v); if (tv !== v) node.setAttribute(a, tv); }
    }
    if (node.matches?.('input, textarea')) return;
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let n = walker.nextNode();
    while (n) {
      if (n.nodeType === 1) {
        if (n.matches(SKIP) && !n.matches('input, textarea')) { n = nextOutside(walker, n); continue; }
        for (const a of ATTRS) {
          const v = n.getAttribute(a);
          if (v && CYR.test(v)) { const tv = t(v); if (tv !== v) n.setAttribute(a, tv); }
        }
      } else if (CYR.test(n.nodeValue)) {
        const v = t(n.nodeValue);
        if (v !== n.nodeValue) n.nodeValue = v;
      }
      n = walker.nextNode();
    }
  }
  function nextOutside(walker, el) {  // skip a whole subtree
    let n = el;
    while (n && !n.nextSibling) n = n.parentNode;
    if (!n) return null;
    walker.currentNode = n.nextSibling;
    return walker.currentNode;
  }

  if (LANG === 'en') {
    const run = () => {
      translateNode(document.body);
      document.title = t(document.title);
      new MutationObserver((muts) => {
        for (const m of muts) {
          if (m.type === 'characterData') translateNode(m.target);
          else if (m.type === 'attributes') translateNode(m.target);
          else m.addedNodes.forEach(translateNode);
        }
      }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    };
    if (document.body) run(); else document.addEventListener('DOMContentLoaded', run);
  }

  window.I18N = { lang: LANG, locale: LOCALE, t, missing };
})();
