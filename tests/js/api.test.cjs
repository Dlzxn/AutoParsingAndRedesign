const test = require('node:test');
const assert = require('node:assert/strict');
const { createContext, load, response } = require('./helpers.cjs');

function app(options) {
  return load(createContext(options), 'api.js').App;
}

test('formatTime: минуты, секунды, десятые', () => {
  const App = app();
  assert.equal(App.formatTime(0), '0:00.0');
  assert.equal(App.formatTime(8.5), '0:08.5');
  assert.equal(App.formatTime(75.25), '1:15.3');
  assert.equal(App.formatTime(600), '10:00.0');
  assert.equal(App.formatTime(9.9, 0), '0:09');
  assert.equal(App.formatTime(-3), '-0:03.0');
  assert.equal(App.formatTime(NaN), '—');
});

test('parseTime: разные форматы ввода', () => {
  const App = app();
  assert.equal(App.parseTime('0:08.5'), 8.5);
  assert.equal(App.parseTime('1:15'), 75);
  assert.equal(App.parseTime('8,5'), 8.5);
  assert.equal(App.parseTime(' 12 '), 12);
  for (const bad of ['', 'abc', '1:2:3', '-5', '1:xx', ':5']) assert.ok(Number.isNaN(App.parseTime(bad)), bad);
});

test('parseTime и formatTime согласованы', () => {
  const App = app();
  for (const value of [0, 0.1, 9.9, 59.9, 61.2, 125.7]) {
    assert.equal(App.parseTime(App.formatTime(value)), Math.round(value * 10) / 10);
  }
});

test('escapeHtml экранирует опасные символы', () => {
  const App = app();
  assert.equal(App.escapeHtml('<img src=x onerror="a(\'1\')">&'), '&lt;img src=x onerror=&quot;a(&#39;1&#39;)&quot;&gt;&amp;');
  assert.equal(App.escapeHtml(null), '');
});

test('formatSize', () => {
  const App = app();
  assert.equal(App.formatSize(0), '');
  assert.equal(App.formatSize(2048), '2 КБ');
  assert.equal(App.formatSize(5.5 * 1024 * 1024), '5.5 МБ');
});

test('icon подставляет SVG из набора', () => {
  const App = app();
  assert.match(App.icon('check', 'icon-sm'), /<svg class="icon icon-sm".*<path d="M1"\/><\/svg>/);
  assert.match(App.icon('unknown'), /<svg[^>]*><\/svg>/);
});

test('request: JSON, 204 и тело запроса', async () => {
  const calls = [];
  const App = app({ fetchImpl: async (url, opts) => { calls.push([url, opts]); return url === '/empty' ? response(204) : response(200, { ok: 1 }); } });
  assert.deepEqual({ ...(await App.request('/api/x', { method: 'POST', json: { a: 1 } })) }, { ok: 1 });
  assert.equal(calls[0][1].body, '{"a":1}');
  assert.equal(calls[0][1].headers['Content-Type'], 'application/json');
  assert.equal(calls[0][1].credentials, 'same-origin');
  assert.equal(await App.request('/empty'), null);
});

test('request: текст ошибки из detail', async () => {
  const App = app({ fetchImpl: async () => response(400, { detail: 'Ссылка не поддерживается' }) });
  await assert.rejects(App.request('/x'), (err) => err.message === 'Ссылка не поддерживается' && err.status === 400);
});

test('request: нестроковый detail и пустой ответ', async () => {
  let App = app({ fetchImpl: async () => response(422, { detail: [{ msg: 'x' }] }) });
  await assert.rejects(App.request('/x'), /Некорректные данные/);
  App = app({ fetchImpl: async () => response(502, '', 'text/html') });
  await assert.rejects(App.request('/x'), /Ошибка сервера \(502\)/);
});

test('request: нет сети', async () => {
  const App = app({ fetchImpl: async () => { throw new TypeError('Failed to fetch'); } });
  await assert.rejects(App.request('/x'), (err) => err.status === 0 && /Нет связи/.test(err.message));
});

test('request: отмена запроса пробрасывается как есть', async () => {
  const abort = Object.assign(new Error('aborted'), { name: 'AbortError' });
  const App = app({ fetchImpl: async () => { throw abort; } });
  await assert.rejects(App.request('/x'), (err) => err === abort);
});

test('request: 401 ведёт на вход с возвратом на текущую страницу', async () => {
  const ctx = createContext({ fetchImpl: async () => response(401, { detail: 'нужен вход' }) });
  const App = load(ctx, 'api.js').App;
  await assert.rejects(App.request('/x'), (err) => err.status === 401);
  assert.equal(ctx.window.location.href, '/login?next=%2Feditor%3Fx%3D1');
});

test('request: 401 без перехода, если redirectOn401=false', async () => {
  const ctx = createContext({ fetchImpl: async () => response(401, { detail: 'нужен вход' }) });
  const App = load(ctx, 'api.js').App;
  await assert.rejects(App.request('/x', { redirectOn401: false }), /нужен вход/);
  assert.equal(ctx.window.location.href, '');
});
