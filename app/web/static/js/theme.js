/* Переключатель светлой/тёмной темы. Выбор хранится в localStorage; по умолчанию — светлая. */
(function () {
  'use strict';
  const root = document.documentElement;
  const meta = document.querySelector('meta[name="theme-color"]');

  function apply(theme) {
    root.setAttribute('data-theme', theme);
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#07080c' : '#f6f6f9');
  }

  apply(root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light');
  document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.classList.add('theme-switching');
      apply(next);
      try { localStorage.setItem('theme', next); } catch (_) { /* приватный режим */ }
      setTimeout(() => root.classList.remove('theme-switching'), 300);
    });
  });
})();
