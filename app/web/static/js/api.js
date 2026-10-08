/* Общие утилиты фронтенда: запросы к API, уведомления, иконки, форматирование. */
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
    if ((response.headers.get('content-type') || '').includes('application/json')) {
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

  function icon(name, cls = '') {
    const body = (window.__ICONS__ || {})[name] || '';
    return `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ` +
      `stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
  }

  const TOAST_ICONS = { error: 'alert', success: 'check', info: 'sparkles' };

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
    item.innerHTML = `${icon(TOAST_ICONS[type] || 'alert')}<span>${escapeHtml(message)}</span>`;
    item.addEventListener('click', () => item.remove());
    box.appendChild(item);
    setTimeout(() => item.classList.add('toast-hide'), timeout);
    setTimeout(() => item.remove(), timeout + 400);
  }

  /* 75.5 -> "1:15.5" */
  function formatTime(seconds, digits = 1) {
    if (!Number.isFinite(seconds)) return '—';
    const sign = seconds < 0 ? '-' : '';
    const value = Math.abs(seconds);
    const m = Math.floor(value / 60);
    const s = value - m * 60;
    const sec = digits ? s.toFixed(digits).padStart(3 + digits, '0') : String(Math.floor(s)).padStart(2, '0');
    return `${sign}${m}:${sec}`;
  }

  /* "1:15.5", "75,5", "75" -> 75.5; NaN при ошибке */
  function parseTime(text) {
    const value = String(text || '').trim().replace(',', '.');
    if (!value) return NaN;
    if (value.includes(':')) {
      const parts = value.split(':');
      if (parts.length !== 2) return NaN;
      const [m, s] = parts;
      if (!/^\d+$/.test(m) || !/^\d+(\.\d+)?$/.test(s)) return NaN;
      return Number(m) * 60 + Number(s);
    }
    return /^\d+(\.\d+)?$/.test(value) ? Number(value) : NaN;
  }

  function formatSize(bytes) {
    if (!bytes) return '';
    return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} МБ` : `${Math.round(bytes / 1024)} КБ`;
  }

  /* Заливка ползунков до текущего значения (WebKit) */
  function paintRange(input) {
    const min = Number(input.min || 0), max = Number(input.max || 100);
    input.style.setProperty('--fill', `${((Number(input.value) - min) / (max - min || 1)) * 100}%`);
  }
  document.addEventListener('input', (e) => { if (e.target.type === 'range') paintRange(e.target); });
  const paintAll = () => document.querySelectorAll('input[type="range"]').forEach(paintRange);
  document.addEventListener('DOMContentLoaded', paintAll);

  window.App = { request, ApiError, escapeHtml, icon, toast, formatTime, parseTime, formatSize, goToLogin, paintAll };
})();
