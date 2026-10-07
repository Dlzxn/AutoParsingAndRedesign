/* Страница /editor: выбор исходника и список готовых роликов. */
(function () {
  'use strict';

  const page = document.querySelector('[data-editor-page]');
  if (!page) return;
  const { request, escapeHtml, formatSize, formatTime, icon } = window.App;
  const newVideo = page.querySelector('[data-new-video]');
  const editor = new window.ClipEditor(page.querySelector('[data-clip-editor]'), {
    onSourceReady: () => { newVideo.hidden = false; },
  });

  const STATUS = {
    queued: ['badge-muted', 'В очереди'],
    processing: ['', 'Обработка'],
    done: ['badge-success', 'Готово'],
    failed: ['badge-danger', 'Ошибка'],
  };
  const ASPECT_NAMES = { original: 'исходный формат', '9:16': '9:16', '1:1': '1:1', '4:5': '4:5', '16:9': '16:9' };

  async function loadJobs() {
    let jobs;
    try {
      jobs = await request('/api/editor/jobs');
    } catch (_) {
      return;
    }
    const box = page.querySelector('[data-my-clips]');
    const list = page.querySelector('[data-my-clips-list]');
    box.hidden = !jobs.length;
    list.innerHTML = jobs.map((job) => {
      const p = job.params || {};
      const [badge, label] = STATUS[job.status] || ['badge-muted', job.status];
      const details = [
        ASPECT_NAMES[p.aspect] || '',
        job.output_duration ? formatTime(job.output_duration) : '',
        formatSize(job.output_size),
      ].filter(Boolean).join(' · ');
      const actions = job.status === 'done'
        ? `<a class="btn btn-sm" href="${escapeHtml(job.result_url)}" target="_blank" rel="noopener">${icon('play', 'icon-sm')} Смотреть</a>
           <a class="btn btn-primary btn-sm" href="${escapeHtml(job.download_url)}">${icon('download', 'icon-sm')} Скачать</a>`
        : '';
      const progress = job.status === 'processing' ? ` ${Math.round(job.progress * 100)}%` : '';
      return `<article class="my-clip">
        <div class="my-clip-icon">${icon(job.status === 'failed' ? 'alert' : 'film')}</div>
        <div class="my-clip-info">
          <strong>${p.text ? escapeHtml(p.text.split('\n')[0].slice(0, 60)) : 'Клип без подписи'}</strong>
          <span>${escapeHtml(details)}${job.error ? ` · ${escapeHtml(job.error)}` : ''}</span>
        </div>
        <span class="badge ${badge}">${label}${progress}</span>
        <div class="my-clip-actions">${actions}</div>
      </article>`;
    }).join('');
    if (jobs.some((j) => j.status === 'queued' || j.status === 'processing')) setTimeout(loadJobs, 3000);
  }

  newVideo.addEventListener('click', () => {
    newVideo.hidden = true;
    editor.showPicker();
  });
  document.addEventListener('clip-editor:done', loadJobs);

  const initialUrl = page.dataset.initialUrl;
  if (initialUrl) {
    page.querySelector('[data-ce-picker]').dataset.available = '1';
    editor.loadFromUrl(initialUrl);
  } else {
    editor.showPicker();
  }
  loadJobs();
})();
