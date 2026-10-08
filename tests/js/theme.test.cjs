const test = require('node:test');
const assert = require('node:assert/strict');
const { createContext, load, makeElement } = require('./helpers.cjs');

function setup(stored) {
  const button = makeElement();
  const meta = makeElement({ content: '#f6f6f9' });
  const ctx = createContext({
    storage: stored ? { theme: stored } : {},
    elements: { '[data-theme-toggle]': [button], 'meta[name="theme-color"]': [meta] },
  });
  // Так делает встроенный скрипт в <head> до загрузки theme.js
  ctx.document.documentElement.setAttribute('data-theme', stored === 'dark' ? 'dark' : 'light');
  load(ctx, 'theme.js');
  return { ctx, button, meta, root: ctx.document.documentElement };
}

test('по умолчанию светлая тема', () => {
  const { root, meta } = setup();
  assert.equal(root.getAttribute('data-theme'), 'light');
  assert.equal(meta.getAttribute('content'), '#f6f6f9');
});

test('сохранённая тёмная тема применяется', () => {
  const { root, meta } = setup('dark');
  assert.equal(root.getAttribute('data-theme'), 'dark');
  assert.equal(meta.getAttribute('content'), '#07080c');
});

test('переключатель меняет тему и запоминает выбор', () => {
  const { root, button, ctx } = setup();
  button.dispatch('click');
  assert.equal(root.getAttribute('data-theme'), 'dark');
  assert.equal(ctx.__store.theme, 'dark');
  button.dispatch('click');
  assert.equal(root.getAttribute('data-theme'), 'light');
  assert.equal(ctx.__store.theme, 'light');
});
