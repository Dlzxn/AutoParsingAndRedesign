/* Страница поиска клипов/постов (общая для всех платформ). */
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
  const loading = page.querySelector('[data-loading]');
  const modal = window.ClipEditorModal ? window.ClipEditorModal.init() : null;
  const { escapeHtml, toast, request, formatTime } = window.App;
  let controller = null;

  function setLoading(state) {
    loading.hidden = !state;
    button.disabled = state;
    button.classList.toggle('is-loading', state);
  }

  function markSeen(url) {
    request('/api/history', { method: 'POST', json: { url, platform }, redirectOn401: false }).catch(() => {});
  }

  function emptyState(title, text) {
    results.innerHTML = `<div class="empty-state"><strong>${escapeHtml(title)}</strong>${escapeHtml(text || '')}</div>`;
  }

  /* ---------- Видео ---------- */

  function mountPlayer(card, item) {
    const media = card.querySelector('.card-media');
    if (media.dataset.mounted) return;
    media.dataset.mounted = '1';
    if (item.preview_url) {
      media.innerHTML = `<video src="${escapeHtml(item.preview_url)}" controls autoplay playsinline loop></video>`;
    } else if (item.embed_url) {
      const src = item.embed_url + (item.embed_url.includes('?') ? '&' : '?') + 'autoplay=1';
      media.innerHTML = `<iframe src="${escapeHtml(src)}" allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowfullscreen loading="lazy"></iframe>`;
    }
    markSeen(item.url);
  }

  async function download(btn, item) {
    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Готовим файл…';
    try {
      const response = await fetch(`/api/download?url=${encodeURIComponent(item.url)}`, { credentials: 'same-origin' });
      if (response.status === 401) return App.goToLogin();
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Не удалось скачать видео');
      }
      const blob = await response.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `${platform}_${(item.id || 'clip').toString().replace(/[^\w-]+/g, '_')}.mp4`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(link.href), 60_000);
      card(btn).classList.add('is-seen');
    } catch (err) {
      toast(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = original;
    }
  }

  const card = (el) => el.closest('.result-card');

  function renderVideo(item) {
    const el = document.createElement('article');
    el.className = 'result-card';
    const thumb = item.thumbnail
      ? `<img src="${escapeHtml(item.thumbnail)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : '<div class="card-thumb-placeholder"></div>';
    const duration = item.duration ? `<span class="card-duration">${formatTime(item.duration).replace(/\.\d$/, '')}</span>` : '';
    el.innerHTML = `
      <div class="card-media ${item.height > item.width ? 'is-vertical' : ''}">
        <button type="button" class="card-thumb" aria-label="Смотреть">
          ${thumb}<span class="card-play">▶</span>${duration}
        </button>
      </div>
      <div class="card-body">
        <h3 class="card-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title || 'Без названия')}</h3>
        ${item.author ? `<div class="card-author">${escapeHtml(item.author)}</div>` : ''}
        <div class="card-actions">
          <button type="button" class="btn btn-primary" data-action="edit">✂ Редактировать</button>
          <button type="button" class="btn" data-action="download">⬇ Скачать</button>
          ${item.page_url ? `<a class="btn btn-icon" href="${escapeHtml(item.page_url)}" target="_blank" rel="noopener noreferrer" title="Открыть оригинал">↗</a>` : ''}
        </div>
      </div>`;
    el.querySelector('.card-thumb').addEventListener('click', () => mountPlayer(el, item));
    el.querySelector('[data-action="download"]').addEventListener('click', (e) => download(e.currentTarget, item));
    el.querySelector('[data-action="edit"]').addEventListener('click', () => {
      el.querySelector('video')?.pause();
      if (modal) modal.open(item.url, item.title);
    });
    return el;
  }

  /* ---------- Текст (Tumblr) ---------- */

  function renderText(item) {
    const el = document.createElement('article');
    el.className = 'result-card result-text';
    const date = item.published_at
      ? new Date(item.published_at * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
      : '';
    const tags = (item.tags || []).slice(0, 6).map((t) => `<span class="tag">#${escapeHtml(t)}</span>`).join('');
    el.innerHTML = `
      <div class="card-body">
        <div class="text-head">
          <a class="card-title" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>
          <span class="card-author">${escapeHtml(date)}</span>
        </div>
        <p class="text-summary">${escapeHtml((item.text || item.summary || '').slice(0, 400))}${(item.text || '').length > 400 ? '…' : ''}</p>
        <div class="tags">${tags}</div>
        <div class="card-actions">
          <button type="button" class="btn" data-action="copy">📋 Копировать</button>
          <button type="button" class="btn btn-primary" data-action="edit">✏ В редактор</button>
        </div>
      </div>`;
    el.querySelector('[data-action="copy"]').addEventListener('click', async (e) => {
      try {
        await navigator.clipboard.writeText(item.text || item.summary || '');
        e.currentTarget.textContent = '✓ Скопировано';
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
    meta.hidden = true;
    results.innerHTML = '';
    try {
      const data = await request(`/api/search/${platform}?q=${encodeURIComponent(query)}`, { signal: controller.signal });
      const items = data.items || [];
      if (!items.length) {
        emptyState('Ничего не найдено', 'Попробуйте другой тег или более общее слово.');
        return;
      }
      const fragment = document.createDocumentFragment();
      items.forEach((item) => fragment.appendChild(kind === 'text' ? renderText(item) : renderVideo(item)));
      results.appendChild(fragment);
      meta.hidden = false;
      meta.textContent = `Найдено: ${items.length}`;
    } catch (err) {
      if (err.name === 'AbortError') return;
      emptyState('Поиск не удался', err.message);
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
