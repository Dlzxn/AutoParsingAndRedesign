/* Шапка (меню аккаунта, мобильная навигация, фон при прокрутке) и анимации появления. */
(function () {
  'use strict';

  const header = document.querySelector('[data-header]');
  const onScroll = () => header && header.classList.toggle('is-scrolled', window.scrollY > 8);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  const accountButton = document.querySelector('[data-account-button]');
  const accountMenu = document.querySelector('[data-account-menu]');
  const navToggle = document.querySelector('[data-nav-toggle]');
  const nav = document.querySelector('[data-nav]');

  function closeAll() {
    accountMenu?.classList.remove('open');
    accountButton?.setAttribute('aria-expanded', 'false');
    nav?.classList.remove('open');
  }

  accountButton?.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = !accountMenu.classList.contains('open');
    closeAll();
    accountMenu.classList.toggle('open', open);
    accountButton.setAttribute('aria-expanded', String(open));
  });

  navToggle?.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = !nav.classList.contains('open');
    closeAll();
    nav.classList.toggle('open', open);
    header.classList.toggle('is-solid', open);
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('[data-account-menu], [data-nav]')) {
      closeAll();
      header?.classList.remove('is-solid');
    }
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeAll(); });

  // Плавное появление блоков при прокрутке
  const revealables = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && revealables.length) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px' });
    revealables.forEach((el) => observer.observe(el));
  } else {
    revealables.forEach((el) => el.classList.add('visible'));
  }
})();
