// Загрузка браузерных скриптов (static/js) в изолированный контекст Node с минимальными заглушками DOM.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const STATIC = path.join(__dirname, '..', '..', 'app', 'web', 'static', 'js');

// Ширина символа = 0.5 кегля: предсказуемая метрика для тестов переноса строк
function fakeCanvasContext() {
  return {
    font: '16px x',
    measureText(text) {
      const size = Number((/(\d+(?:\.\d+)?)px/.exec(this.font) || [0, 16])[1]);
      return { width: [...text].length * size * 0.5 };
    },
  };
}

function makeElement(attrs = {}) {
  const listeners = {};
  return {
    attrs: { ...attrs },
    style: { setProperty() {} },
    classList: { _s: new Set(), add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); }, toggle(c, on) { (on ?? !this._s.has(c)) ? this._s.add(c) : this._s.delete(c); }, contains(c) { return this._s.has(c); } },
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return this.attrs[k] ?? null; },
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
    dispatch(type, event = {}) { (listeners[type] || []).forEach((fn) => fn(event)); },
  };
}

function createContext({ fetchImpl, storage = {}, elements = {} } = {}) {
  const documentElement = makeElement();
  const docListeners = {};
  const store = { ...storage };
  const window = {
    __ICONS__: { check: '<path d="M1"/>', alert: '<path d="M2"/>', sparkles: '<path d="M3"/>' },
    location: { pathname: '/editor', search: '?x=1', href: '' },
    localStorage: {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    },
    fetch: fetchImpl || (async () => { throw new Error('fetch not mocked'); }),
    setTimeout: (fn) => { fn(); return 0; },
    clearTimeout() {},
    console,
  };
  const document = {
    documentElement,
    body: { appendChild() {}, classList: documentElement.classList },
    createElement(tag) {
      if (tag === 'canvas') return { getContext: () => fakeCanvasContext() };
      const el = makeElement();
      el.appendChild = () => {};
      el.remove = () => {};
      return el;
    },
    querySelector(sel) { return elements[sel]?.[0] ?? null; },
    querySelectorAll(sel) { return elements[sel] ?? []; },
    addEventListener(type, fn) { (docListeners[type] ||= []).push(fn); },
  };
  // Глобальный объект контекста и есть window (как в браузере)
  const context = vm.createContext({ ...window, document, Intl, URL, URLSearchParams, TextDecoder, console });
  context.window = context;
  context.__store = store;
  return context;
}

function load(context, ...files) {
  for (const file of files) {
    vm.runInContext(fs.readFileSync(path.join(STATIC, file), 'utf8'), context, { filename: file });
  }
  return context;
}

function response(status, body, contentType = 'application/json') {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: { get: (name) => (name.toLowerCase() === 'content-type' ? contentType : null) },
    json: async () => (typeof body === 'string' ? JSON.parse(body) : body),
  };
}

module.exports = { createContext, load, response, makeElement };
