/* Страница поиска клипов/постов (общая для всех площадок). */
(function () {
  'use strict';

  const page = document.querySelector('[data-search-page]');
  if (!page) return;

  const platform = page.dataset.platform;
  const kind = page.dataset.kind;
  const form = page.querySelector('[data-search-form]');
  const input = page.querySelector('[data-search-input]');
  const button = page.querySelector('[data-search-button]');
  const results = page.querySelector('[data-results]');
  const meta = page.querySelector('[data-results-meta]');
  const modal = window.ClipEditorModal ? window.ClipEditorModal.init() : null;
  const { escapeHtml, toast, request, formatTime, icon } = window.App;
  let controller = null;

  function setLoading(state) {
    button.disabled = state;
    button.classList.toggle('is-loading', state);
    if (state) {
      meta.hidden = true;
      results.innerHTML = Array.from({ length: kind === 'text' ? 6 : 8 }, () => kind === 'text'
        ? '<div class="skeleton"><div class="sk-line"></div><div class="sk-line"></div><div class="sk-line"></div><div class="sk-line short"></div></div>'
        : '<div class="skeleton"><div class="sk-media"></div><div class="sk-line"></div><div class="sk-line short"></div></div>').join('');
    }
  }

  function markSeen(url) {
    request('/api/history', { method: 'POST', json: { url, platform }, redirectOn401: false }).catch(() => {});
  }

  function emptyState(iconName, title, text) {
    results.innerHTML = `<div class="empty"><div class="empty-icon">${icon(iconName, 'icon-lg')}</div>` +
      `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(text || '')}</span></div>`;
  }

  /* ---------- Видео ---------- */

  function mountPlayer(card, item) {
    const media = card.querySelector('.clip-media');
    if (media.dataset.mounted) return;
    media.dataset.mounted = '1';
    if (item.preview_url) {
      media.innerHTML = `<video src="${escapeHtml(item.preview_url)}" controls autoplay playsinline loop></video>`;
    } else if (item.embed_url) {
      const src = item.embed_url + (item.embed_url.includes('?') ? '&' : '?') + 'autoplay=1';
      media.innerHTML = `<iframe src="${escapeHtml(src)}" allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowfullscreen></iframe>`;
    }
    markSeen(item.url);
  }

  async function download(btn, card, item) {
    btn.disabled = true;
    btn.classList.add('is-loading');
    const original = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span>';
    try {
      const response = await fetch(`/api/download?url=${encodeURIComponent(item.url)}`, { credentials: 'same-origin' });
      if (response.status === 401) return App.goToLogin();
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Не удалось скачать видео');
      }
      const disposition = response.headers.get('content-disposition') || '';
      const match = /filename\*=utf-8''([^;]+)/i.exec(disposition) || /filename="?([^";]+)"?/i.exec(disposition);
      const blob = await response.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = match ? decodeURIComponent(match[1]) : `${platform}_clip.mp4`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(link.href), 60_000);
      card.classList.add('is-seen');
      toast('Видео скачано', 'success', 2500);
    } catch (err) {
      toast(err.message);
    } finally {
      btn.disabled = false;
      btn.classList.remove('is-loading');
      btn.innerHTML = original;
    }
  }

  function renderVideo(item, index) {
    const el = document.createElement('article');
    el.className = 'clip';
    el.style.animationDelay = `${Math.min(index, 12) * 35}ms`;
    const thumb = item.thumbnail
      ? `<img src="${escapeHtml(item.thumbnail)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`
      : '<div class="clip-thumb-empty"></div>';
    const duration = item.duration ? `<span class="clip-duration">${formatTime(item.duration, 0)}</span>` : '';
    el.innerHTML = `
      <div class="clip-media ${item.height > item.width ? 'is-vertical' : ''}">
        <button type="button" class="clip-thumb" aria-label="Смотреть">
          ${thumb}<span class="clip-play">${icon('play')}</span>${duration}
        </button>
      </div>
      <div class="clip-body">
        <h3 class="clip-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title || 'Без названия')}</h3>
        ${item.author ? `<div class="clip-author">${escapeHtml(item.author)}</div>` : ''}
        <div class="clip-actions">
          <button type="button" class="btn btn-primary btn-sm" data-action="edit">${icon('scissors', 'icon-sm')} Монтаж</button>
          <button type="button" class="btn btn-sm btn-icon" data-action="download" title="Скачать MP4">${icon('download', 'icon-sm')}</button>
          ${item.page_url ? `<a class="btn btn-sm btn-icon" href="${escapeHtml(item.page_url)}" target="_blank" rel="noopener noreferrer" title="Открыть оригинал">${icon('external', 'icon-sm')}</a>` : ''}
        </div>
      </div>`;
    el.querySelector('.clip-thumb').addEventListener('click', () => mountPlayer(el, item));
    el.querySelector('[data-action="download"]').addEventListener('click', (e) => download(e.currentTarget, el, item));
    el.querySelector('[data-action="edit"]').addEventListener('click', () => {
      el.querySelector('video')?.pause();
      if (modal) modal.open(item.url, item.title);
    });
    return el;
  }

  /* ---------- Текст (Tumblr) ---------- */

  function renderText(item, index) {
    const el = document.createElement('article');
    el.className = 'clip post';
    el.style.animationDelay = `${Math.min(index, 12) * 35}ms`;
    const date = item.published_at
      ? new Date(item.published_at * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
      : '';
    const tags = (item.tags || []).slice(0, 6).map((t) => `<span class="tag">#${escapeHtml(t)}</span>`).join('');
    el.innerHTML = `
      <div class="post-head">
        <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>
        <span class="clip-author">${escapeHtml(date)}</span>
      </div>
      <p class="post-text">${escapeHtml(item.text || item.summary || '')}</p>
      <div class="tags">${tags}</div>
      <div class="clip-actions">
        <button type="button" class="btn btn-sm" data-action="copy">${icon('copy', 'icon-sm')} Копировать</button>
        <button type="button" class="btn btn-primary btn-sm" data-action="edit">${icon('edit', 'icon-sm')} В редактор</button>
      </div>`;
    el.querySelector('[data-action="copy"]').addEventListener('click', async (e) => {
      try {
        await navigator.clipboard.writeText(item.text || item.summary || '');
        e.currentTarget.innerHTML = `${icon('check', 'icon-sm')} Скопировано`;
        markSeen(item.url);
      } catch (_) {
        toast('Не удалось скопировать текст');
      }
    });
    el.querySelector('[data-action="edit"]').addEventListener('click', () => {
      try {
        sessionStorage.setItem('textEditorContent', item.text || item.summary || '');
        sessionStorage.setItem('textEditorSource', item.url);
      } catch (_) { /* приватный режим */ }
      markSeen(item.url);
      location.href = '/text-editor';
    });
    return el;
  }

  /* ---------- Поиск ---------- */

  async function search(query) {
    if (controller) controller.abort();
    controller = new AbortController();
    setLoading(true);
    try {
      const data = await request(`/api/search/${platform}?q=${encodeURIComponent(query)}`, { signal: controller.signal });
      const items = data.items || [];
      if (!items.length) {
        emptyState('search', 'Ничего не нашлось', 'Попробуйте другой тег или более общее слово.');
        return;
      }
      const fragment = document.createDocumentFragment();
      items.forEach((item, i) => fragment.appendChild(kind === 'text' ? renderText(item, i) : renderVideo(item, i)));
      results.innerHTML = '';
      results.appendChild(fragment);
      meta.hidden = false;
      meta.textContent = `Найдено: ${items.length}${data.cached ? ' · из кэша' : ''}`;
    } catch (err) {
      if (err.name === 'AbortError') return;
      emptyState('alert', 'Поиск не удался', err.message);
    } finally {
      setLoading(false);
    }
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = input.value.trim();
    if (query.length < 2) return toast('Введите хотя бы 2 символа', 'info', 3000);
    const url = new URL(location.href);
    url.searchParams.set('q', query);
    history.replaceState(null, '', url);
    search(query);
  });

  const initial = new URLSearchParams(location.search).get('q');
  if (initial) {
    input.value = initial;
    search(initial.trim());
  }
})();
