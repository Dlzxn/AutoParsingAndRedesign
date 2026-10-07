/* Редактор клипов: превью в браузере + серверный рендер через очередь задач. */
(function () {
  'use strict';

  const ASPECTS = { '9:16': 9 / 16, '1:1': 1, '4:5': 4 / 5, '16:9': 16 / 9 };
  const TEXT_SCALE = { small: 0.055, medium: 0.075, large: 0.10 };
  const DEFAULTS = {
    trim_start: 0, speed: 1, fade_in: 0, fade_out: 0, aspect: 'original', fit: 'crop', resolution: 'original',
    rotate: 0, flip_h: false, flip_v: false, brightness: 0, contrast: 1, saturation: 1, grayscale: false,
    text: '', text_position: 'bottom', text_size: 'medium', text_color: '#ffffff', text_background: true,
    logo_position: 'top-right', logo_scale: 20, logo_opacity: 1, volume: 100, mute: false,
    music_volume: 60, music_replace: false, quality: 'standard',
  };
  const POLL_INTERVAL = 1000;

  const even = (v) => Math.max(2, Math.floor((v + 1e-6) / 2) * 2);
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  /* Тот же расчёт размера кадра, что и на сервере (app/editor/pipeline.py: output_size). */
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

  class ClipEditor {
    constructor(root, { onSourceReady } = {}) {
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
      this.sourceCache = new Map(); // url -> source (в рамках страницы)
      this.objectUrls = {};
      this.onSourceReady = onSourceReady;
      this.loadToken = 0;
      this._bind();
    }

    /* ---------- Загрузка исходника ---------- */

    showPicker() {
      this._reset(true);
      this._view('picker');
    }

    async loadFromUrl(url) {
      const token = ++this.loadToken;
      this._reset(true);
      this._view('loading', 'Загружаем видео с платформы… Обычно это занимает 5–30 секунд.');
      try {
        let source = this.sourceCache.get(url);
        if (!source) {
          source = await App.request('/api/editor/sources/url', { method: 'POST', json: { url } });
          this.sourceCache.set(url, source);
        }
        if (token !== this.loadToken) return;
        this._setSource(source);
      } catch (err) {
        if (token !== this.loadToken) return;
        this._view('error', err.message);
      }
    }

    loadFromFile(file) {
      const token = ++this.loadToken;
      this._reset(true);
      this._view('loading', `Загружаем «${file.name}»…`);
      const bar = this.q('[data-ce-upload-progress]');
      bar.hidden = false;
      const form = new FormData();
      form.append('file', file);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/editor/sources/upload');
      xhr.setRequestHeader('Accept', 'application/json');
      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        const pct = Math.round((e.loaded / e.total) * 100);
        bar.firstElementChild.style.width = `${pct}%`;
        if (pct >= 100) this.q('[data-ce-loading-text]').textContent = 'Проверяем видео…';
      };
      xhr.onload = () => {
        if (token !== this.loadToken) return;
        bar.hidden = true;
        let data = null;
        try { data = JSON.parse(xhr.responseText); } catch (_) { /* ignore */ }
        if (xhr.status === 401) return App.goToLogin();
        if (xhr.status >= 200 && xhr.status < 300 && data) return this._setSource(data);
        this._view('error', (data && data.detail) || `Не удалось загрузить файл (${xhr.status})`);
      };
      xhr.onerror = () => {
        if (token !== this.loadToken) return;
        bar.hidden = true;
        this._view('error', 'Нет связи с сервером');
      };
      xhr.send(form);
    }

    _setSource(source) {
      this.source = source;
      this.video.src = source.preview_url;
      this.videoBg.src = source.preview_url;
      const end = this.form.elements.trim_end;
      end.max = source.duration;
      this.form.elements.trim_start.max = source.duration;
      for (const r of [this.q('[data-ce-range-start]'), this.q('[data-ce-range-end]')]) r.max = source.duration;
      if (!end.value || Number(end.value) > source.duration) end.value = source.duration.toFixed(1);
      this._view('workspace');
      this.q('[data-ce-render]').disabled = false;
      this.update();
      if (this.onSourceReady) this.onSourceReady(source);
    }

    _view(name, message) {
      this.q('[data-ce-picker]').hidden = name !== 'picker';
      this.q('[data-ce-loading]').hidden = name !== 'loading';
      this.q('[data-ce-workspace]').hidden = name !== 'workspace';
      if (name === 'loading') {
        this.q('[data-ce-loading-text]').textContent = message || 'Загружаем видео…';
        this.q('[data-ce-upload-progress]').hidden = true;
      }
      if (name === 'error') {
        this.q('[data-ce-loading]').hidden = false;
        this.q('[data-ce-loading]').classList.add('ce-loading-error');
        this.q('[data-ce-loading-text]').textContent = message;
        this.q('[data-ce-upload-progress]').hidden = true;
      } else {
        this.q('[data-ce-loading]').classList.remove('ce-loading-error');
      }
    }

    /* ---------- Параметры ---------- */

    params() {
      const f = this.form.elements;
      const num = (name) => Number(f[name].value);
      const p = {
        trim_start: clamp(num('trim_start') || 0, 0, this.source ? this.source.duration : 1e9),
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
      const end = Number(f.trim_end.value);
      if (end && this.source && end < this.source.duration - 0.05) p.trim_end = end;
      return p;
    }

    _trimRange() {
      const p = this.params();
      const duration = this.source ? this.source.duration : 0;
      const start = Math.min(p.trim_start, duration);
      const end = p.trim_end ? Math.min(p.trim_end, duration) : duration;
      return [start, Math.max(start, end)];
    }

    /* ---------- Превью ---------- */

    update() {
      if (!this.source) return;
      const p = this.params();
      const f = this.form.elements;
      const set = (name, text) => { const o = this.q(`[data-out="${name}"]`); if (o) o.textContent = text; };
      set('speed', `${p.speed}×`);
      set('brightness', p.brightness.toFixed(2));
      set('contrast', p.contrast.toFixed(2));
      set('saturation', p.saturation.toFixed(2));
      set('volume', `${p.volume}%`);
      set('music_volume', `${p.music_volume}%`);
      set('logo_scale', `${p.logo_scale}%`);
      set('logo_opacity', `${Math.round(p.logo_opacity * 100)}%`);
      this.q('[data-ce-fit-field]').hidden = p.aspect === 'original';
      this.qa('[data-segmented]').forEach((group) => {
        const value = f[group.dataset.segmented].value;
        group.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.value === value));
      });

      // Размер кадра: исходник после поворота
      let w = this.source.width, h = this.source.height;
      if (p.rotate === 90 || p.rotate === 270) [w, h] = [h, w];
      const [ow, oh] = outputSize(w, h, p);
      this._sizeFrame(ow / oh);
      this._layoutVideo(p, w, h);

      const filter = [
        `brightness(${(1 + p.brightness * 1.6).toFixed(3)})`,
        `contrast(${p.contrast})`,
        `saturate(${p.grayscale ? 0 : p.saturation})`,
      ].join(' ');
      this.video.style.filter = filter;
      this.videoBg.style.filter = `${filter} blur(18px) brightness(0.85)`;
      this.videoBg.hidden = !(p.aspect !== 'original' && p.fit === 'blur');
      this.frame.classList.toggle('ce-frame-pad', p.aspect !== 'original' && p.fit === 'pad');

      this.video.playbackRate = p.speed;
      this.videoBg.playbackRate = p.speed;
      this.video.muted = p.mute || (p.music_replace && !!this.objectUrls.music);
      this.video.volume = clamp(p.volume / 100, 0, 1);
      this.musicPreview.volume = clamp(p.music_volume / 100, 0, 1);
      this.musicPreview.playbackRate = 1;

      this._renderText(p);
      this._renderLogo(p);
      this._renderTimeline();

      const [start, end] = this._trimRange();
      const outDuration = (end - start) / p.speed;
      this.q('[data-ce-summary]').textContent =
        `Итог: ${ow}×${oh} · ${App.formatTime(outDuration)} · исходник ${this.source.width}×${this.source.height}, ` +
        `${App.formatTime(this.source.duration)}${this.source.has_audio ? '' : ' · без звука'}`;
    }

    _sizeFrame(ratio) {
      const wrap = this.frame.parentElement;
      const availW = wrap.clientWidth, availH = wrap.clientHeight;
      if (!availW || !availH) return;
      const [fw, fh] = availW / availH > ratio ? [availH * ratio, availH] : [availW, availW / ratio];
      this.frame.style.width = `${Math.floor(fw)}px`;
      this.frame.style.height = `${Math.floor(fh)}px`;
    }

    _layoutVideo(p, w, h) {
      const frameW = this.frame.clientWidth;
      const frameH = this.frame.clientHeight;
      if (!frameW || !frameH) return;
      const fill = p.aspect === 'original' || p.fit === 'crop';
      const scale = fill ? Math.max(frameW / w, frameH / h) : Math.min(frameW / w, frameH / h);
      // Элемент <video> имеет исходную ориентацию; поворот делается через transform
      const rotated = p.rotate === 90 || p.rotate === 270;
      const elW = (rotated ? h : w) * scale;
      const elH = (rotated ? w : h) * scale;
      const flip = `scale(${p.flip_h ? -1 : 1}, ${p.flip_v ? -1 : 1})`;
      Object.assign(this.video.style, {
        width: `${elW}px`, height: `${elH}px`,
        left: `${(frameW - elW) / 2}px`, top: `${(frameH - elH) / 2}px`,
        transform: `rotate(${p.rotate}deg) ${flip}`,
      });
      const bgScale = Math.max(frameW / w, frameH / h) * 1.1;
      const bgW = (rotated ? h : w) * bgScale;
      const bgH = (rotated ? w : h) * bgScale;
      Object.assign(this.videoBg.style, {
        width: `${bgW}px`, height: `${bgH}px`,
        left: `${(frameW - bgW) / 2}px`, top: `${(frameH - bgH) / 2}px`,
        transform: `rotate(${p.rotate}deg) ${flip}`,
      });
      this._renderText(p);
    }

    _renderText(p) {
      const el = this.q('[data-ce-text-preview]');
      if (!p.text) { el.hidden = true; return; }
      const frameW = this.frame.clientWidth, frameH = this.frame.clientHeight;
      if (!frameW) return;
      el.hidden = false;
      const size = Math.max(8, Math.min(frameW, frameH) * TEXT_SCALE[p.text_size]);
      el.style.fontSize = `${size}px`;
      el.style.color = p.text_color;
      el.className = `ce-text ce-text-${p.text_position}${p.text_background ? ' ce-text-box' : ' ce-text-outline'}`;
      el.innerHTML = p.text.split('\n').map((line) => `<span>${App.escapeHtml(line) || '&nbsp;'}</span>`).join('<br>');
    }

    _renderLogo(p) {
      const img = this.q('[data-ce-logo-preview]');
      if (!this.objectUrls.logo) { img.hidden = true; return; }
      img.hidden = false;
      img.src = this.objectUrls.logo;
      img.style.width = `${p.logo_scale}%`;
      img.style.opacity = p.logo_opacity;
      img.className = `ce-logo ce-logo-${p.logo_position}`;
    }

    _renderTimeline() {
      if (!this.source) return;
      const [start, end] = this._trimRange();
      const d = this.source.duration || 1;
      const sel = this.q('[data-ce-selection]');
      sel.style.left = `${(start / d) * 100}%`;
      sel.style.width = `${((end - start) / d) * 100}%`;
      this.q('[data-ce-range-start]').value = start;
      this.q('[data-ce-range-end]').value = end;
      this._renderCursor();
    }

    _renderCursor() {
      if (!this.source) return;
      const d = this.source.duration || 1;
      this.q('[data-ce-cursor]').style.left = `${(this.video.currentTime / d) * 100}%`;
      this.q('[data-ce-time]').textContent = App.formatTime(this.video.currentTime);
    }

    /* ---------- Воспроизведение в пределах фрагмента ---------- */

    _onTimeUpdate() {
      const [start, end] = this._trimRange();
      if (this.video.currentTime >= end - 0.03 || this.video.currentTime < start - 0.3) {
        this.video.currentTime = start;
        this.videoBg.currentTime = start;
        this.musicPreview.currentTime = 0;
      }
      if (Math.abs(this.videoBg.currentTime - this.video.currentTime) > 0.3) {
        this.videoBg.currentTime = this.video.currentTime;
      }
      this._renderCursor();
    }

    togglePlay() {
      if (this.video.paused) {
        const [start, end] = this._trimRange();
        if (this.video.currentTime < start || this.video.currentTime >= end - 0.05) this.video.currentTime = start;
        this.video.play().catch(() => {});
      } else {
        this.video.pause();
      }
    }

    pause() {
      this.video.pause();
    }

    /* ---------- Рендер ---------- */

    async render() {
      if (!this.source) return;
      const params = this.params();
      if (params.trim_end !== undefined && params.trim_end - params.trim_start < 0.3) {
        return this._status('Фрагмент слишком короткий — минимум 0.3 секунды', 'error');
      }
      const form = new FormData();
      form.append('source_id', this.source.id);
      form.append('params', JSON.stringify(params));
      for (const name of ['logo', 'music', 'subtitles']) {
        const file = this.form.elements[name].files[0];
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
        this._status(`Обработка: ${Math.round(job.progress * 100)}%`);
        this._progress(job.progress);
      } else if (job.status === 'done') {
        this._busy(false);
        this._progress(null);
        this._status(`Готово! ${App.formatSize(job.output_size)}`, 'success');
        return this._showResult(job);
      } else {
        this._busy(false);
        this._progress(null);
        return this._status(job.error || 'Не удалось обработать видео', 'error');
      }
      this.pollTimer = setTimeout(() => this._poll(), POLL_INTERVAL);
    }

    _showResult(job) {
      const box = this.q('[data-ce-result]');
      box.hidden = false;
      const video = this.q('[data-ce-result-video]');
      video.src = `${job.result_url}?t=${Date.now()}`;
      this.q('[data-ce-download]').href = job.download_url;
      box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      document.dispatchEvent(new CustomEvent('clip-editor:done', { detail: job }));
    }

    _busy(busy) {
      const btn = this.q('[data-ce-render]');
      btn.disabled = busy || !this.source;
      btn.textContent = busy ? 'Обработка…' : 'Создать клип';
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
      box.firstElementChild.style.width = `${Math.round(value * 100)}%`;
    }

    /* ---------- Сброс ---------- */

    resetSettings() {
      const f = this.form.elements;
      for (const [name, value] of Object.entries(DEFAULTS)) {
        const el = f[name];
        if (!el) continue;
        if (el.type === 'checkbox') el.checked = value; else el.value = value;
      }
      if (this.source) f.trim_end.value = this.source.duration.toFixed(1);
      this._clearFile('logo');
      this._clearFile('music');
      f.subtitles.value = '';
      this.update();
    }

    _clearFile(name) {
      const input = this.form.elements[name];
      input.value = '';
      if (this.objectUrls[name]) URL.revokeObjectURL(this.objectUrls[name]);
      delete this.objectUrls[name];
      if (name === 'logo') this.q('[data-ce-logo-settings]').hidden = true;
      if (name === 'music') {
        this.q('[data-ce-music-settings]').hidden = true;
        this.musicPreview.removeAttribute('src');
      }
      this.update();
    }

    _reset(full) {
      clearTimeout(this.pollTimer);
      this.job = null;
      this._busy(false);
      this._progress(null);
      this._status('');
      this.q('[data-ce-result]').hidden = true;
      this.q('[data-ce-result-video]').removeAttribute('src');
      if (full) {
        this.source = null;
        this.video.pause();
        this.video.removeAttribute('src');
        this.videoBg.removeAttribute('src');
        this.q('[data-ce-render]').disabled = true;
      }
    }

    close() {
      this.loadToken++;
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

      this.qa('.ce-tab').forEach((tab) => tab.addEventListener('click', () => {
        this.qa('.ce-tab').forEach((t) => t.classList.toggle('active', t === tab));
        this.qa('.ce-section').forEach((s) => s.classList.toggle('active', s.dataset.section === tab.dataset.tab));
      }));

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

      this.qa('[data-ce-rotate]').forEach((b) => b.addEventListener('click', () => {
        f.rotate.value = (((Number(f.rotate.value) + Number(b.dataset.ceRotate)) % 360) + 360) % 360;
        this.update();
      }));

      this.q('[data-ce-set-start]').addEventListener('click', () => {
        f.trim_start.value = this.video.currentTime.toFixed(1);
        if (Number(f.trim_end.value) <= Number(f.trim_start.value)) f.trim_end.value = this.source.duration.toFixed(1);
        this.update();
      });
      this.q('[data-ce-set-end]').addEventListener('click', () => {
        const t = this.video.currentTime;
        if (t <= Number(f.trim_start.value) + 0.3) return App.toast('Конец должен быть позже начала', 'error', 3000);
        f.trim_end.value = t.toFixed(1);
        this.update();
      });

      const startRange = this.q('[data-ce-range-start]');
      const endRange = this.q('[data-ce-range-end]');
      startRange.addEventListener('input', () => {
        const v = Math.min(Number(startRange.value), Number(endRange.value) - 0.3);
        f.trim_start.value = Math.max(0, v).toFixed(2);
        this.video.currentTime = Math.max(0, v);
        this.update();
      });
      endRange.addEventListener('input', () => {
        const v = Math.max(Number(endRange.value), Number(startRange.value) + 0.3);
        f.trim_end.value = Math.min(this.source.duration, v).toFixed(2);
        this.video.currentTime = Math.min(this.source.duration, v);
        this.update();
      });

      this.q('[data-ce-play]').addEventListener('click', () => this.togglePlay());
      this.video.addEventListener('click', () => this.togglePlay());
      this.video.addEventListener('timeupdate', () => this._onTimeUpdate());
      this.video.addEventListener('seeked', () => { this.videoBg.currentTime = this.video.currentTime; this._renderCursor(); });
      this.video.addEventListener('play', () => {
        this.q('[data-ce-play]').textContent = '❚❚';
        this.videoBg.play().catch(() => {});
        if (this.objectUrls.music) this.musicPreview.play().catch(() => {});
      });
      this.video.addEventListener('pause', () => {
        this.q('[data-ce-play]').textContent = '▶';
        this.videoBg.pause();
        this.musicPreview.pause();
      });
      this.video.addEventListener('loadedmetadata', () => {
        const [start] = this._trimRange();
        this.video.currentTime = start;
        this.update();
      });
      this.video.addEventListener('error', () => {
        if (this.source) this._status('Браузер не может показать превью этого формата, но рендер будет работать', 'info');
      });
      window.addEventListener('resize', () => this.update());

      this.q('[data-ce-logo-input]').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (this.objectUrls.logo) URL.revokeObjectURL(this.objectUrls.logo);
        delete this.objectUrls.logo;
        if (file) this.objectUrls.logo = URL.createObjectURL(file);
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
        this.q('[data-ce-music-settings]').hidden = !file;
        this.update();
      });
      this.qa('[data-ce-clear]').forEach((b) => b.addEventListener('click', () => this._clearFile(b.dataset.ceClear)));
      this.q('[data-ce-reset]').addEventListener('click', () => this.resetSettings());
      this.q('[data-ce-back]').addEventListener('click', () => {
        this.q('[data-ce-result]').hidden = true;
        this._status('');
      });

      // Выбор исходника (страница редактора)
      const fileInput = this.q('[data-ce-file]');
      fileInput.addEventListener('change', () => { if (fileInput.files[0]) this.loadFromFile(fileInput.files[0]); });
      const drop = this.q('[data-ce-drop]');
      ['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.add('ce-drop-active');
      }));
      ['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.remove('ce-drop-active');
      }));
      drop.addEventListener('drop', (e) => {
        const file = e.dataTransfer.files[0];
        if (file) this.loadFromFile(file);
      });
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
      document.body.classList.remove('ce-modal-open');
      editor.close();
    };
    modal.querySelector('[data-ce-close]').addEventListener('click', close);
    modal.addEventListener('mousedown', (e) => { if (e.target === modal) close(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) close(); });
    return {
      editor,
      open(url, title) {
        modal.hidden = false;
        document.body.classList.add('ce-modal-open');
        modal.querySelector('[data-ce-modal-title]').textContent = title || 'Редактор клипа';
        editor.loadFromUrl(url);
      },
      close,
    };
  }

  window.ClipEditor = ClipEditor;
  window.ClipEditorModal = { init: initModal };
})();
