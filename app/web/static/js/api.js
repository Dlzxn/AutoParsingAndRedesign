/* Общие утилиты фронтенда: запросы к API, уведомления, экранирование. */
(function () {
  'use strict';

  class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.status = status;
    }
  }

  function goToLogin() {
    const next = encodeURIComponent(location.pathname + location.search);
    location.href = `/login?next=${next}`;
  }

  async function request(url, { method = 'GET', json, form, signal, redirectOn401 = true } = {}) {
    const options = { method, signal, headers: { Accept: 'application/json' }, credentials: 'same-origin' };
    if (json !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(json);
    } else if (form !== undefined) {
      options.body = form;
    }
    let response;
    try {
      response = await fetch(url, options);
    } catch (err) {
      if (err.name === 'AbortError') throw err;
      throw new ApiError('Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.', 0);
    }
    if (response.status === 401 && redirectOn401) {
      goToLogin();
      throw new ApiError('Требуется вход в аккаунт', 401);
    }
    if (response.status === 204) return null;
    let data = null;
    const type = response.headers.get('content-type') || '';
    if (type.includes('application/json')) {
      data = await response.json().catch(() => null);
    }
    if (!response.ok) {
      let message = (data && data.detail) || `Ошибка сервера (${response.status})`;
      if (typeof message !== 'string') message = 'Некорректные данные запроса';
      throw new ApiError(message, response.status);
    }
    return data;
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch]));
  }

  function toast(message, type = 'error', timeout = 5000) {
    let box = document.querySelector('.toast-stack');
    if (!box) {
      box = document.createElement('div');
      box.className = 'toast-stack';
      document.body.appendChild(box);
    }
    const item = document.createElement('div');
    item.className = `toast toast-${type}`;
    item.setAttribute('role', type === 'error' ? 'alert' : 'status');
    item.textContent = message;
    item.addEventListener('click', () => item.remove());
    box.appendChild(item);
    setTimeout(() => item.classList.add('toast-hide'), timeout);
    setTimeout(() => item.remove(), timeout + 400);
  }

  function formatTime(seconds) {
    if (!Number.isFinite(seconds)) return '—';
    const m = Math.floor(seconds / 60);
    const s = seconds - m * 60;
    return `${m}:${s.toFixed(1).padStart(4, '0')}`;
  }

  function formatSize(bytes) {
    if (!bytes) return '';
    return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} МБ` : `${Math.round(bytes / 1024)} КБ`;
  }

  window.App = { request, ApiError, escapeHtml, toast, formatTime, formatSize, goToLogin };
})();
