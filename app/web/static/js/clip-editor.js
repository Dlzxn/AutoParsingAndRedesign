/* Редактор клипов: превью в браузере + серверный рендер через очередь задач.
 *
 * Превью повторяет серверный рендер:
 *  - размер кадра — как output_size() в app/editor/pipeline.py;
 *  - раскладка текста — как app/editor/textrender.py (тот же шрифт, перенос по ширине, отступы);
 *  - цвет — SVG-фильтр с той же формулой, что ffmpeg eq (контраст вокруг 0.5 + сдвиг яркости).
 */
(function () {
  'use strict';

  const ASPECTS = { '9:16': 9 / 16, '1:1': 1, '4:5': 4 / 5, '16:9': 16 / 9 };
  const TEXT_SCALE = { small: 0.055, medium: 0.075, large: 0.10 };
  const LINE_HEIGHT = 1.3;
  const MAX_TEXT_WIDTH = 0.9;
  const MAX_LINES = 6;
  const EMOJI_ADVANCE = 1.2;
  const EMOJI_RE = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{2300}-\u{23FF}\u{2190}-\u{21FF}\u{3030}\u{303D}\u{3297}\u{3299}\u{00A9}\u{00AE}\u{203C}\u{2049}\u{2122}\u{2139}]/u;
  const INVISIBLE_RE = /[‍️︎\u{1F3FB}-\u{1F3FF}]/u;
  const DEFAULTS = {
    trim_start: '0:00.0', speed: 1, fade_in: 0, fade_out: 0, aspect: 'original', fit: 'crop', resolution: 'original',
    rotate: 0, flip_h: false, flip_v: false, brightness: 0, contrast: 1, saturation: 1, grayscale: false,
    text: '', text_position: 'bottom', text_size: 'medium', text_color: '#ffffff', text_background: true,
    logo_position: 'top-right', logo_scale: 20, logo_opacity: 1, volume: 100, mute: false,
    music_volume: 60, music_replace: false, quality: 'standard',
  };
  const POLL_INTERVAL = 1000;
  let uid = 0;

  const even = (v) => Math.max(2, Math.floor((v + 1e-6) / 2) * 2);
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const { icon, formatTime, parseTime, formatSize, escapeHtml } = window.App;

  /* Тот же расчёт размера кадра, что и на сервере. */
  function outputSize(w, h, p) {
    const srcRatio = w / h;
    const ratio = p.aspect === 'original' ? srcRatio : ASPECTS[p.aspect];
    let ow, oh;
    if (p.resolution === 'original' && p.aspect === 'original') {
      ow = w; oh = h;
    } else if (p.resolution === 'original' && p.fit === 'crop') {
      if (ratio < srcRatio) { ow = h * ratio; oh = h; } else { ow = w; oh = w / ratio; }
    } else {
      const short = p.resolution === 'original' ? Math.min(w, h) : Number(p.resolution);
      if (ratio <= 1) { ow = short; oh = short / ratio; } else { ow = short * ratio; oh = short; }
    }
    const big = Math.max(ow, oh);
    if (big > 3840) { ow = ow * 3840 / big; oh = oh * 3840 / big; }
    return [even(ow), even(oh)];
  }

  /* ---------- Раскладка текста (как textrender.py) ---------- */

  const measureCtx = document.createElement('canvas').getContext('2d');

  function tokenize(line) {
    const tokens = [];
    let buf = '';
    for (const ch of line) {
      if (INVISIBLE_RE.test(ch)) continue;
      if (EMOJI_RE.test(ch)) {
        if (buf) { tokens.push({ text: buf, emoji: false }); buf = ''; }
        tokens.push({ text: ch, emoji: true });
      } else {
        buf += ch;
      }
    }
    if (buf) tokens.push({ text: buf, emoji: false });
    return tokens;
  }

  function textWidth(text, size) {
    measureCtx.font = `800 ${size}px "Inter Display"`;
    return tokenize(text).reduce((sum, t) => sum + (t.emoji ? size * EMOJI_ADVANCE : measureCtx.measureText(t.text).width), 0);
  }

  function wrapLines(text, maxWidth, size) {
    const lines = [];
    for (const paragraph of text.split('\n')) {
      const words = paragraph.split(/\s+/).filter(Boolean);
      if (!words.length) { lines.push(''); continue; }
      let current = '';
      for (const word of words) {
        const candidate = current ? `${current} ${word}` : word;
        if (textWidth(candidate, size) <= maxWidth) { current = candidate; continue; }
        if (current) lines.push(current);
        current = '';
        for (const ch of word) {
          if (current && textWidth(current + ch, size) > maxWidth) { lines.push(current); current = ''; }
          current += ch;
        }
      }
      lines.push(current);
    }
    while (lines.length && !lines[lines.length - 1]) lines.pop();
    if (lines.length > MAX_LINES) {
      lines.length = MAX_LINES;
      let last = lines[MAX_LINES - 1];
      while (last && textWidth(`${last}…`, size) > maxWidth) last = last.slice(0, -1);
      lines[MAX_LINES - 1] = `${last.trimEnd()}…`;
    }
    return lines;
  }

  /* ---------- Субтитры .srt ---------- */

  function parseSrt(text) {
    const toSec = (t) => {
      const m = /(\d+):(\d+):(\d+)[,.](\d+)/.exec(t);
      return m ? Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]) + Number(m[4]) / 1000 : NaN;
    };
    return text.replace(/\r/g, '').split(/\n\s*\n/).map((block) => {
      const lines = block.trim().split('\n');
      const timeIdx = lines.findIndex((l) => l.includes('-->'));
      if (timeIdx < 0) return null;
      const [a, b] = lines[timeIdx].split('-->');
      return { start: toSec(a), end: toSec(b), text: lines.slice(timeIdx + 1).join('\n').replace(/<[^>]+>/g, '') };
    }).filter((c) => c && Number.isFinite(c.start) && Number.isFinite(c.end));
  }

  async function readSubtitles(file) {
    const buffer = await file.arrayBuffer();
    let text;
    try { text = new TextDecoder('utf-8', { fatal: true }).decode(buffer); } catch (_) { text = new TextDecoder('windows-1251').decode(buffer); }
    return parseSrt(text);
  }

  class ClipEditor {
    constructor(root, { onSourceReady, onClose } = {}) {
      this.root = root;
      this.form = root.querySelector('[data-ce-form]');
      this.q = (sel) => root.querySelector(sel);
      this.qa = (sel) => Array.from(root.querySelectorAll(sel));
      this.video = this.q('[data-ce-video]');
      this.videoBg = this.q('[data-ce-video-bg]');
      this.frame = this.q('[data-ce-frame]');
      this.musicPreview = this.q('[data-ce-music-preview]');
      this.source = null;
      this.job = null;
      this.pollTimer = null;
      this.objectUrls = {};
      this.subtitles = [];
      this.onSourceReady = onSourceReady;
      this.onClose = onClose;
      this.loadToken = 0;
      this.lastLoad = null;
      this.layout = null;
      this.filterId = `ce-color-${++uid}`;
      this.q('[data-ce-color-filter]').id = this.filterId;
      this._bind();
      document.fonts?.load('800 20px "Inter Display"').then(() => this.update());
    }

    /* ---------- Состояния сцены ---------- */

    _view(name) {
      for (const [key, sel] of [['picker', '[data-ce-picker]'], ['loading', '[data-ce-loading]'],
        ['workspace', '[data-ce-workspace]'], ['result', '[data-ce-result]']]) {
        this.q(sel).hidden = key !== name;
      }
      this.view = name;
      this.root.classList.toggle('ce-no-source', name !== 'workspace' && name !== 'result');
    }

    _loading(title, text, { progress = null, error = false } = {}) {
      this._view('loading');
      this.q('[data-ce-loading-title]').textContent = title;
      this.q('[data-ce-loading-text]').textContent = text || '';
      this.q('[data-ce-spinner]').hidden = error;
      this.q('[data-ce-error-icon]').hidden = !error;
      this.q('[data-ce-load-actions]').hidden = !error;
      this.q('[data-ce-choose-other]').hidden = !this.q('[data-ce-picker]').dataset.available;
      const box = this.q('[data-ce-load-progress]');
      box.hidden = error || progress === null;
      if (!box.hidden) this._loadProgress(progress);
    }

    _loadProgress(value) {
      const box = this.q('[data-ce-load-progress]');
      box.hidden = false;
      const indeterminate = value === undefined || value <= 0;
      box.querySelector('.progress').classList.toggle('progress-indeterminate', indeterminate);
      box.querySelector('.progress-bar').style.width = indeterminate ? '' : `${Math.round(value * 100)}%`;
      this.q('[data-ce-load-percent]').textContent = indeterminate ? '' : `${Math.round(value * 100)}%`;
    }

    showPicker() {
      this._reset(true);
      this.q('[data-ce-picker]').dataset.available = '1';
      this._view('picker');
    }

    /* ---------- Загрузка исходника ---------- */

    async loadFromUrl(url) {
      const token = ++this.loadToken;
      this.lastLoad = () => this.loadFromUrl(url);
      this._reset(true);
      this._loading('Загружаем видео с площадки', 'Обычно это занимает 5–30 секунд.', { progress: 0 });
      const progressKey = `p${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
      const poll = setInterval(async () => {
        try {
          const data = await App.request(`/api/editor/downloads/${progressKey}`, { redirectOn401: false });
          if (token === this.loadToken && data && data.progress !== null) this._loadProgress(data.progress);
        } catch (_) { /* прогресс не критичен */ }
      }, 700);
      try {
        const source = await App.request('/api/editor/sources/url', { method: 'POST', json: { url, token: progressKey } });
        if (token !== this.loadToken) return;
        this._setSource(source);
      } catch (err) {
        if (token !== this.loadToken) return;
        this._loading('Не удалось загрузить видео', err.message, { error: true });
      } finally {
        clearInterval(poll);
      }
    }

    loadFromFile(file) {
      const token = ++this.loadToken;
      this.lastLoad = () => this.loadFromFile(file);
      this._reset(true);
      this._loading(`Загружаем «${file.name}»`, formatSize(file.size), { progress: 0 });
      const form = new FormData();
      form.append('file', file);
      const xhr = new XMLHttpRequest();
      this.xhr = xhr;
      xhr.open('POST', '/api/editor/sources/upload');
      xhr.setRequestHeader('Accept', 'application/json');
      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable || token !== this.loadToken) return;
        const value = e.loaded / e.total;
        this._loadProgress(value);
        if (value >= 1) {
          this.q('[data-ce-loading-title]').textContent = 'Проверяем видео';
          this._loadProgress(0);
        }
      };
      xhr.onload = () => {
        if (token !== this.loadToken) return;
        let data = null;
        try { data = JSON.parse(xhr.responseText); } catch (_) { /* ignore */ }
        if (xhr.status === 401) return App.goToLogin();
        if (xhr.status >= 200 && xhr.status < 300 && data) return this._setSource(data);
        this._loading('Не удалось загрузить файл', (data && data.detail) || `Ошибка сервера (${xhr.status})`, { error: true });
      };
      xhr.onerror = () => {
        if (token === this.loadToken) this._loading('Нет связи с сервером', 'Проверьте интернет и попробуйте ещё раз.', { error: true });
      };
      xhr.send(form);
    }

    _setSource(source) {
      this.source = source;
      this.video.src = source.preview_url;
      this.videoBg.src = source.preview_url;
      const f = this.form.elements;
      f.trim_start.value = formatTime(0);
      f.trim_end.value = formatTime(source.duration);
      for (const r of [this.q('[data-ce-range-start]'), this.q('[data-ce-range-end]')]) r.max = source.duration;
      this._view('workspace');
      this.q('[data-ce-render]').disabled = false;
      this.update();
      if (this.onSourceReady) this.onSourceReady(source);
    }

    /* ---------- Параметры ---------- */

    _trimValues() {
      const f = this.form.elements;
      const duration = this.source ? this.source.duration : 0;
      let start = parseTime(f.trim_start.value);
      let end = parseTime(f.trim_end.value);
      f.trim_start.classList.toggle('invalid', !Number.isFinite(start) || start >= duration);
      f.trim_end.classList.toggle('invalid', !Number.isFinite(end) || (Number.isFinite(start) && end <= start));
      start = Number.isFinite(start) ? clamp(start, 0, duration) : 0;
      end = Number.isFinite(end) ? clamp(end, 0, duration) : duration;
      if (end <= start) end = duration;
      return [start, end];
    }

    params() {
      const f = this.form.elements;
      const num = (name) => Number(f[name].value);
      const [start, end] = this._trimValues();
      const p = {
        trim_start: Math.round(start * 100) / 100,
        speed: num('speed'),
        fade_in: clamp(num('fade_in') || 0, 0, 5),
        fade_out: clamp(num('fade_out') || 0, 0, 5),
        aspect: f.aspect.value,
        fit: f.fit.value,
        resolution: f.resolution.value,
        rotate: ((num('rotate') % 360) + 360) % 360,
        flip_h: f.flip_h.checked,
        flip_v: f.flip_v.checked,
        brightness: num('brightness'),
        contrast: num('contrast'),
        saturation: num('saturation'),
        grayscale: f.grayscale.checked,
        text: f.text.value.trim(),
        text_position: f.text_position.value,
        text_size: f.text_size.value,
        text_color: f.text_color.value,
        text_background: f.text_background.checked,
        logo_position: f.logo_position.value,
        logo_scale: num('logo_scale'),
        logo_opacity: num('logo_opacity'),
        volume: num('volume'),
        mute: f.mute.checked,
        music_volume: num('music_volume'),
        music_replace: f.music_replace.checked,
        quality: f.quality.value,
      };
      if (this.source && end < this.source.duration - 0.05) p.trim_end = Math.round(end * 100) / 100;
      return p;
    }

    /* ---------- Превью ---------- */

    update() {
      if (!this.source) return;
      const p = this.params();
      const f = this.form.elements;
      const set = (name, text) => { const o = this.q(`[data-out="${name}"]`); if (o) o.textContent = text; };
      set('speed', `${p.speed}×`);
      set('brightness', p.brightness > 0 ? `+${p.brightness.toFixed(2)}` : p.brightness.toFixed(2));
      set('contrast', p.contrast.toFixed(2));
      set('saturation', p.saturation.toFixed(2));
      set('volume', `${p.volume}%`);
      set('music_volume', `${p.music_volume}%`);
      set('logo_scale', `${p.logo_scale}%`);
      set('logo_opacity', `${Math.round(p.logo_opacity * 100)}%`);
      this.q('[data-ce-text-count]').textContent = `${f.text.value.length}/300`;
      this.q('[data-ce-fit-field]').hidden = p.aspect === 'original';
      this.qa('[data-segmented]').forEach((group) => {
        const value = f[group.dataset.segmented].value;
        group.querySelectorAll('button[data-value]').forEach((b) => b.classList.toggle('active', b.dataset.value === value));
      });
      this.qa('[data-chips-for]').forEach((group) => {
        const value = Number(f[group.dataset.chipsFor].value);
        group.querySelectorAll('button').forEach((b) => b.classList.toggle('active', Number(b.dataset.value) === value));
      });
      this.qa('.ce-swatch[data-color]').forEach((s) => s.classList.toggle('active', s.dataset.color === p.text_color.toLowerCase()));
      App.paintAll();

      let w = this.source.width, h = this.source.height;
      if (p.rotate === 90 || p.rotate === 270) [w, h] = [h, w];
      const [ow, oh] = outputSize(w, h, p);
      this.layout = { p, w, h, ow, oh };
      this._sizeFrame(ow / oh);
      this._layoutVideo();
      this._applyColor(p);

      this.videoBg.hidden = !(p.aspect !== 'original' && p.fit === 'blur');
      this.video.playbackRate = p.speed;
      this.videoBg.playbackRate = p.speed;
      this.video.muted = p.mute || (p.music_replace && !!this.objectUrls.music);
      this.musicPreview.volume = clamp(p.music_volume / 100, 0, 1);

      this._renderText();
      this._renderLogo(p);
      this._renderTimeline();
      this._renderOverlaysAtTime();

      const [start, end] = this._trimValues();
      const outDuration = (end - start) / p.speed;
      this.q('[data-ce-summary]').innerHTML =
        `Итог: <b>${ow}×${oh}</b> · <b>${formatTime(outDuration)}</b> &nbsp;·&nbsp; исходник ${this.source.width}×${this.source.height}, ` +
        `${formatTime(this.source.duration)}${this.source.has_audio ? '' : ' · без звука'}`;
    }

    _sizeFrame(ratio) {
      const wrap = this.frame.parentElement;
      const availW = wrap.clientWidth, availH = wrap.clientHeight;
      if (!availW || !availH) return;
      const [fw, fh] = availW / availH > ratio ? [availH * ratio, availH] : [availW, availW / ratio];
      this.frame.style.width = `${Math.floor(fw)}px`;
      this.frame.style.height = `${Math.floor(fh)}px`;
    }

    _layoutVideo() {
      const { p, w, h } = this.layout;
      const frameW = this.frame.clientWidth, frameH = this.frame.clientHeight;
      if (!frameW || !frameH) return;
      const fill = p.aspect === 'original' || p.fit === 'crop';
      const scale = fill ? Math.max(frameW / w, frameH / h) : Math.min(frameW / w, frameH / h);
      const rotated = p.rotate === 90 || p.rotate === 270;
      const flip = `scale(${p.flip_h ? -1 : 1}, ${p.flip_v ? -1 : 1})`;
      const place = (el, s) => {
        const elW = (rotated ? h : w) * s, elH = (rotated ? w : h) * s;
        Object.assign(el.style, {
          width: `${elW}px`, height: `${elH}px`,
          left: `${(frameW - elW) / 2}px`, top: `${(frameH - elH) / 2}px`,
          transform: `rotate(${p.rotate}deg) ${flip}`,
        });
      };
      place(this.video, scale);
      place(this.videoBg, Math.max(frameW / w, frameH / h) * 1.06);
    }

    _applyColor(p) {
      // ffmpeg eq: y = (x - 0.5) * contrast + 0.5 + brightness; насыщенность — отдельно
      const slope = p.contrast;
      const intercept = 0.5 - 0.5 * p.contrast + p.brightness;
      this.q('[data-ce-color-filter]').querySelectorAll('feFuncR, feFuncG, feFuncB').forEach((fn) => {
        fn.setAttribute('slope', slope);
        fn.setAttribute('intercept', intercept);
      });
      this.q('[data-ce-color-filter] feColorMatrix').setAttribute('values', p.grayscale ? 0 : p.saturation);
      const neutral = p.contrast === 1 && p.brightness === 0 && p.saturation === 1 && !p.grayscale;
      this.video.style.filter = neutral ? '' : `url(#${this.filterId})`;
      this.videoBg.style.filter = `${neutral ? '' : `url(#${this.filterId}) `}blur(20px) brightness(0.84)`;
    }

    _renderText() {
      const layer = this.q('[data-ce-text-layer]');
      const { p, ow, oh } = this.layout;
      const frameW = this.frame.clientWidth;
      if (!p.text || !frameW) { layer.innerHTML = ''; return; }
      const size = Math.max(14, Math.floor(Math.min(ow, oh) * TEXT_SCALE[p.text_size]));
      const lines = wrapLines(p.text, ow * MAX_TEXT_WIDTH, size);
      const lineH = size * LINE_HEIGHT;
      const block = lineH * lines.length;
      const y0 = p.text_position === 'top' ? oh * 0.08 : p.text_position === 'center' ? (oh - block) / 2 : oh * 0.88 - block;
      const padX = size * 0.3, padY = size * 0.06, radius = size * 0.28, stroke = Math.max(2, Math.floor(size / 14));
      const html = [];
      lines.forEach((line, i) => {
        if (!line.trim()) return;
        const width = textWidth(line, size);
        const x = (ow - width) / 2, top = y0 + i * lineH;
        if (p.text_background) {
          html.push(`<div class="ce-text-box" style="left:${x - padX}px;top:${top - padY}px;width:${width + 2 * padX}px;` +
            `height:${lineH + 2 * padY}px;border-radius:${radius}px"></div>`);
        }
        const parts = tokenize(line).map((t) => t.emoji
          ? `<span class="ce-emoji" style="width:${size * EMOJI_ADVANCE}px;font-size:${size * 0.92}px">${t.text}</span>`
          : escapeHtml(t.text)).join('');
        const style = p.text_background ? '' :
          `-webkit-text-stroke-width:${stroke * 2}px;text-shadow:${stroke}px ${stroke * 1.5}px 0 rgba(0,0,0,0.43);`;
        html.push(`<div class="ce-text-line${p.text_background ? '' : ' outline'}" style="left:${x}px;top:${top}px;` +
          `height:${lineH}px;line-height:${lineH}px;font-size:${size}px;color:${p.text_color};${style}">${parts}</div>`);
      });
      layer.innerHTML = html.join('');
      Object.assign(layer.style, { width: `${ow}px`, height: `${oh}px`, transform: `scale(${frameW / ow})` });
    }

    _renderLogo(p) {
      const img = this.q('[data-ce-logo-preview]');
      if (!this.objectUrls.logo) { img.hidden = true; return; }
      img.hidden = false;
      if (img.dataset.src !== this.objectUrls.logo) { img.src = this.objectUrls.logo; img.dataset.src = this.objectUrls.logo; }
      img.style.width = `${p.logo_scale}%`;
      img.style.opacity = p.logo_opacity;
      img.className = `ce-logo ce-logo-${p.logo_position}`;
    }

    _renderTimeline() {
      if (!this.source) return;
      const [start, end] = this._trimValues();
      const d = this.source.duration || 1;
      const sel = this.q('[data-ce-selection]');
      sel.style.left = `${(start / d) * 100}%`;
      sel.style.width = `${((end - start) / d) * 100}%`;
      if (document.activeElement !== this.q('[data-ce-range-start]')) this.q('[data-ce-range-start]').value = start;
      if (document.activeElement !== this.q('[data-ce-range-end]')) this.q('[data-ce-range-end]').value = end;
      this._renderCursor();
    }

    _renderCursor() {
      if (!this.source) return;
      const d = this.source.duration || 1;
      this.q('[data-ce-cursor]').style.left = `${(this.video.currentTime / d) * 100}%`;
      this.q('[data-ce-time]').textContent = formatTime(this.video.currentTime);
    }

    /* Переходы и субтитры зависят от времени в готовом ролике */
    _renderOverlaysAtTime() {
      if (!this.layout) return;
      const { p, oh } = this.layout;
      const [start, end] = this._trimValues();
      const outDuration = (end - start) / p.speed;
      const t = clamp((this.video.currentTime - start) / p.speed, 0, outDuration);
      const fadeIn = Math.min(p.fade_in, outDuration / 2), fadeOut = Math.min(p.fade_out, outDuration / 2);
      let darkness = 0;
      if (fadeIn > 0 && t < fadeIn) darkness = 1 - t / fadeIn;
      else if (fadeOut > 0 && t > outDuration - fadeOut) darkness = (t - (outDuration - fadeOut)) / fadeOut;
      darkness = clamp(darkness, 0, 1);
      this.q('[data-ce-fade]').style.opacity = darkness;
      const volume = clamp(p.volume / 100, 0, 1) * (1 - darkness);
      this.video.volume = volume;

      const subtitle = this.q('[data-ce-subtitle]');
      const cue = this.subtitles.find((c) => t >= c.start && t <= c.end);
      subtitle.hidden = !cue;
      if (cue) {
        const frameH = this.frame.clientHeight;
        const portrait = this.layout.oh > this.layout.ow;
        subtitle.textContent = cue.text;
        subtitle.style.fontSize = `${((portrait ? 11 : 16) / 288) * frameH * 1.25}px`;
        subtitle.style.bottom = `${(25 / 288) * frameH}px`;
      }
      void oh;
    }

    /* ---------- Воспроизведение в пределах фрагмента ---------- */

    _onTimeUpdate() {
      const [start, end] = this._trimValues();
      if (this.video.currentTime >= end - 0.03 || this.video.currentTime < start - 0.3) {
        this.video.currentTime = start;
        this.videoBg.currentTime = start;
        this.musicPreview.currentTime = 0;
      }
      if (Math.abs(this.videoBg.currentTime - this.video.currentTime) > 0.3) this.videoBg.currentTime = this.video.currentTime;
      this._renderCursor();
      this._renderOverlaysAtTime();
    }

    _tick() {
      if (this.video.paused) return;
      this._onTimeUpdate();
      requestAnimationFrame(() => this._tick());
    }

    togglePlay() {
      if (this.video.paused) {
        const [start, end] = this._trimValues();
        if (this.video.currentTime < start || this.video.currentTime >= end - 0.05) this.video.currentTime = start;
        this.video.play().catch(() => {});
      } else {
        this.video.pause();
      }
    }

    pause() { this.video.pause(); }

    /* ---------- Рендер ---------- */

    async render() {
      if (!this.source) return;
      const f = this.form.elements;
      if (f.trim_start.classList.contains('invalid') || f.trim_end.classList.contains('invalid')) {
        this._tab('time');
        return this._status('Проверьте время начала и конца фрагмента', 'error');
      }
      const params = this.params();
      const end = params.trim_end ?? this.source.duration;
      if (end - params.trim_start < 0.3) return this._status('Фрагмент слишком короткий — минимум 0.3 секунды', 'error');
      const form = new FormData();
      form.append('source_id', this.source.id);
      form.append('params', JSON.stringify(params));
      for (const name of ['logo', 'music', 'subtitles']) {
        const file = f[name].files[0];
        if (file) form.append(name, file);
      }
      this.pause();
      this._busy(true);
      this._status('Отправляем задачу…');
      this._progress(0);
      try {
        this.job = await App.request('/api/editor/jobs', { method: 'POST', form });
        this._poll();
      } catch (err) {
        this._busy(false);
        this._progress(null);
        this._status(err.message, 'error');
      }
    }

    async _poll() {
      clearTimeout(this.pollTimer);
      if (!this.job) return;
      let job;
      try {
        job = await App.request(`/api/editor/jobs/${this.job.id}`);
      } catch (err) {
        if (err.status === 404) {
          this._busy(false);
          this._progress(null);
          return this._status('Задача не найдена', 'error');
        }
        this.pollTimer = setTimeout(() => this._poll(), POLL_INTERVAL * 3);
        return;
      }
      this.job = job;
      if (job.status === 'queued') {
        this._status('В очереди на обработку…');
        this._progress(0);
      } else if (job.status === 'processing') {
        this._status(`Собираем ролик… ${Math.round(job.progress * 100)}%`);
        this._progress(job.progress);
      } else if (job.status === 'done') {
        this._busy(false);
        this._progress(null);
        this._status('');
        return this._showResult(job);
      } else {
        this._busy(false);
        this._progress(null);
        return this._status(job.error || 'Не удалось обработать видео', 'error');
      }
      this.pollTimer = setTimeout(() => this._poll(), POLL_INTERVAL);
    }

    _showResult(job) {
      this._view('result');
      const video = this.q('[data-ce-result-video]');
      video.src = `${job.result_url}?t=${Date.now()}`;
      this.q('[data-ce-download]').href = job.download_url;
      this.q('[data-ce-result-info]').textContent =
        [job.output_duration ? formatTime(job.output_duration) : '', formatSize(job.output_size)].filter(Boolean).join(' · ');
      this.root.scrollIntoView({ behavior: 'smooth', block: 'start' });
      document.dispatchEvent(new CustomEvent('clip-editor:done', { detail: job }));
    }

    _busy(busy) {
      const btn = this.q('[data-ce-render]');
      btn.disabled = busy || !this.source;
      btn.querySelector('span').textContent = busy ? 'Обработка…' : 'Создать клип';
      this.root.classList.toggle('ce-busy', busy);
    }

    _status(message, type = 'info') {
      const el = this.q('[data-ce-status]');
      el.textContent = message || '';
      el.dataset.type = type;
    }

    _progress(value) {
      const box = this.q('[data-ce-progress]');
      if (value === null) { box.hidden = true; return; }
      box.hidden = false;
      box.querySelector('.progress').classList.toggle('progress-indeterminate', value <= 0);
      box.querySelector('.progress-bar').style.width = value > 0 ? `${Math.round(value * 100)}%` : '';
    }

    _tab(name) {
      this.qa('.ce-tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
      this.qa('.ce-section').forEach((s) => s.classList.toggle('active', s.dataset.section === name));
    }

    /* ---------- Файлы и сброс ---------- */

    _fileLabel(name, file) {
      const label = this.q(`[data-ce-file-label="${name}"]`);
      if (!label.dataset.placeholder) label.dataset.placeholder = label.querySelector('[data-ce-file-name]').textContent;
      label.classList.toggle('has-file', !!file);
      label.querySelector('[data-ce-file-name]').textContent = file ? file.name : label.dataset.placeholder;
    }

    resetSettings() {
      const f = this.form.elements;
      for (const [name, value] of Object.entries(DEFAULTS)) {
        const el = f[name];
        if (!el) continue;
        if (el.type === 'checkbox') el.checked = value; else el.value = value;
      }
      if (this.source) f.trim_end.value = formatTime(this.source.duration);
      ['logo', 'music', 'subtitles'].forEach((n) => this._clearFile(n));
      this.update();
    }

    _clearFile(name) {
      const input = this.form.elements[name];
      input.value = '';
      if (this.objectUrls[name]) URL.revokeObjectURL(this.objectUrls[name]);
      delete this.objectUrls[name];
      this._fileLabel(name, null);
      if (name === 'logo') this.q('[data-ce-logo-settings]').hidden = true;
      if (name === 'music') {
        this.q('[data-ce-music-settings]').hidden = true;
        this.musicPreview.pause();
        this.musicPreview.removeAttribute('src');
      }
      if (name === 'subtitles') {
        this.subtitles = [];
        this.q('[data-ce-clear="subtitles"]').hidden = true;
      }
      this.update();
    }

    _reset(full) {
      clearTimeout(this.pollTimer);
      this.job = null;
      this._busy(false);
      this._progress(null);
      this._status('');
      this.q('[data-ce-result-video]').removeAttribute('src');
      if (full) {
        if (this.xhr) { this.xhr.abort(); this.xhr = null; }
        this.source = null;
        this.layout = null;
        this.video.pause();
        this.video.removeAttribute('src');
        this.videoBg.removeAttribute('src');
        this.q('[data-ce-render]').disabled = true;
      }
    }

    close() {
      this.loadToken++;
      if (this.xhr) { this.xhr.abort(); this.xhr = null; }
      this.pause();
      this.musicPreview.pause();
      clearTimeout(this.pollTimer);
    }

    /* ---------- События ---------- */

    _bind() {
      const f = this.form.elements;
      this.form.addEventListener('input', () => this.update());
      this.form.addEventListener('change', () => this.update());
      this.form.addEventListener('submit', (e) => { e.preventDefault(); this.render(); });

      this.qa('.ce-tab').forEach((tab) => tab.addEventListener('click', () => this._tab(tab.dataset.tab)));

      this.qa('[data-segmented]').forEach((group) => group.addEventListener('click', (e) => {
        const button = e.target.closest('button[data-value]');
        if (!button) return;
        f[group.dataset.segmented].value = button.dataset.value;
        this.update();
      }));
      this.qa('[data-chips-for]').forEach((group) => group.addEventListener('click', (e) => {
        const button = e.target.closest('button[data-value]');
        if (!button) return;
        f[group.dataset.chipsFor].value = button.dataset.value;
        this.update();
      }));
      this.q('[data-ce-swatches]').addEventListener('click', (e) => {
        const swatch = e.target.closest('.ce-swatch[data-color]');
        if (!swatch) return;
        f.text_color.value = swatch.dataset.color;
        this.update();
      });
      this.qa('[data-ce-rotate]').forEach((b) => b.addEventListener('click', () => {
        f.rotate.value = (((Number(f.rotate.value) + Number(b.dataset.ceRotate)) % 360) + 360) % 360;
        this.update();
      }));

      // Время: при уходе с поля приводим к виду 0:08.5
      for (const name of ['trim_start', 'trim_end']) {
        f[name].addEventListener('blur', () => {
          if (!this.source) return;
          const value = parseTime(f[name].value);
          if (Number.isFinite(value)) f[name].value = formatTime(clamp(value, 0, this.source.duration));
          this.update();
        });
        f[name].addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); f[name].blur(); } });
      }
      this.q('[data-ce-set-start]').addEventListener('click', () => {
        f.trim_start.value = formatTime(this.video.currentTime);
        const [, end] = this._trimValues();
        if (end <= this.video.currentTime + 0.3) f.trim_end.value = formatTime(this.source.duration);
        this.update();
      });
      this.q('[data-ce-set-end]').addEventListener('click', () => {
        const t = this.video.currentTime;
        if (t <= parseTime(f.trim_start.value) + 0.3) return App.toast('Конец должен быть позже начала', 'error', 3000);
        f.trim_end.value = formatTime(t);
        this.update();
      });

      const startRange = this.q('[data-ce-range-start]');
      const endRange = this.q('[data-ce-range-end]');
      startRange.addEventListener('input', () => {
        const v = Math.max(0, Math.min(Number(startRange.value), Number(endRange.value) - 0.3));
        f.trim_start.value = formatTime(v);
        this.video.currentTime = v;
        this.update();
      });
      endRange.addEventListener('input', () => {
        const v = Math.min(this.source.duration, Math.max(Number(endRange.value), Number(startRange.value) + 0.3));
        f.trim_end.value = formatTime(v);
        this.video.currentTime = v;
        this.update();
      });

      this.q('[data-ce-play]').addEventListener('click', () => this.togglePlay());
      this.video.addEventListener('click', () => this.togglePlay());
      this.video.addEventListener('timeupdate', () => this._onTimeUpdate());
      this.video.addEventListener('seeked', () => {
        this.videoBg.currentTime = this.video.currentTime;
        this._renderCursor();
        this._renderOverlaysAtTime();
      });
      this.video.addEventListener('play', () => {
        this.q('[data-ce-play]').innerHTML = icon('pause');
        this.videoBg.play().catch(() => {});
        if (this.objectUrls.music) this.musicPreview.play().catch(() => {});
        this._tick();
      });
      this.video.addEventListener('pause', () => {
        this.q('[data-ce-play]').innerHTML = icon('play');
        this.videoBg.pause();
        this.musicPreview.pause();
      });
      this.video.addEventListener('loadedmetadata', () => {
        const [start] = this._trimValues();
        this.video.currentTime = start;
        this.update();
      });
      this.video.addEventListener('error', () => {
        if (this.source) this._status('Браузер не может показать превью этого формата — рендер всё равно сработает', 'info');
      });
      window.addEventListener('resize', () => this.update());

      // Пробел — пуск/пауза (если фокус не в поле ввода)
      document.addEventListener('keydown', (e) => {
        if (e.code !== 'Space' || this.view !== 'workspace' || !this.root.offsetParent) return;
        if (e.target.closest('input, textarea, select, button, [contenteditable]')) return;
        e.preventDefault();
        this.togglePlay();
      });

      this.q('[data-ce-logo-input]').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (this.objectUrls.logo) URL.revokeObjectURL(this.objectUrls.logo);
        delete this.objectUrls.logo;
        if (file) this.objectUrls.logo = URL.createObjectURL(file);
        this._fileLabel('logo', file);
        this.q('[data-ce-logo-settings]').hidden = !file;
        this.update();
      });
      this.q('[data-ce-music-input]').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (this.objectUrls.music) URL.revokeObjectURL(this.objectUrls.music);
        delete this.objectUrls.music;
        if (file) {
          this.objectUrls.music = URL.createObjectURL(file);
          this.musicPreview.src = this.objectUrls.music;
          this.musicPreview.loop = true;
        }
        this._fileLabel('music', file);
        this.q('[data-ce-music-settings]').hidden = !file;
        this.update();
      });
      this.q('[data-ce-subs-input]').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        this._fileLabel('subtitles', file);
        this.q('[data-ce-clear="subtitles"]').hidden = !file;
        this.subtitles = file ? await readSubtitles(file) : [];
        if (file && !this.subtitles.length) App.toast('В файле не найдено ни одного субтитра', 'error', 4000);
        this.update();
      });
      this.qa('[data-ce-clear]').forEach((b) => b.addEventListener('click', () => this._clearFile(b.dataset.ceClear)));
      this.q('[data-ce-reset]').addEventListener('click', () => this.resetSettings());
      this.q('[data-ce-back]').addEventListener('click', () => {
        this.q('[data-ce-result-video]').pause();
        this._view('workspace');
        this.update();
      });
      this.q('[data-ce-retry]').addEventListener('click', () => this.lastLoad && this.lastLoad());
      this.q('[data-ce-choose-other]').addEventListener('click', () => this.showPicker());

      // Выбор исходника (страница редактора)
      const fileInput = this.q('[data-ce-file]');
      fileInput.addEventListener('change', () => { if (fileInput.files[0]) this.loadFromFile(fileInput.files[0]); fileInput.value = ''; });
      const drop = this.q('[data-ce-drop]');
      ['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('ce-drop-active'); }));
      ['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove('ce-drop-active'); }));
      drop.addEventListener('drop', (e) => { const file = e.dataTransfer.files[0]; if (file) this.loadFromFile(file); });
      this.q('[data-ce-url-form]').addEventListener('submit', (e) => {
        e.preventDefault();
        const url = this.q('[data-ce-url]').value.trim();
        if (url) this.loadFromUrl(url);
      });
    }
  }

  /* Модальное окно с редактором для страниц поиска. */
  function initModal() {
    const modal = document.querySelector('[data-ce-modal]');
    if (!modal) return null;
    const editor = new ClipEditor(modal.querySelector('[data-clip-editor]'));
    const close = () => {
      modal.hidden = true;
      document.body.classList.remove('modal-open');
      editor.close();
    };
    modal.querySelector('[data-ce-close]').addEventListener('click', close);
    modal.addEventListener('mousedown', (e) => { if (e.target === modal) close(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) close(); });
    return {
      editor,
      open(url, title) {
        modal.hidden = false;
        document.body.classList.add('modal-open');
        modal.querySelector('[data-ce-modal-title]').textContent = title || 'Редактор клипа';
        editor.loadFromUrl(url);
      },
      close,
    };
  }

  window.ClipEditor = ClipEditor;
  // Чистые функции — для тестов (tests/js) и сверки с серверной реализацией
  window.ClipEditorCore = { outputSize, tokenize, wrapLines, textWidth, parseSrt };
  window.ClipEditorModal = { init: initModal };
})();
