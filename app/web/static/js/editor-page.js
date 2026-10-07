/* Страница /editor: выбор исходника и список готовых роликов. */
(function () {
  'use strict';

  const page = document.querySelector('[data-editor-page]');
  if (!page) return;
  const { request, escapeHtml, formatSize, formatTime } = window.App;
  const newVideo = page.querySelector('[data-new-video]');
  const editor = new window.ClipEditor(page.querySelector('[data-clip-editor]'), {
    onSourceReady: () => { newVideo.hidden = false; },
  });

  const STATUS = { queued: 'В очереди', processing: 'Обработка', done: 'Готово', failed: 'Ошибка' };

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
      const details = [
        p.aspect && p.aspect !== 'original' ? p.aspect : null,
        job.output_duration ? formatTime(job.output_duration) : null,
        formatSize(job.output_size) || null,
      ].filter(Boolean).join(' · ');
      const action = job.status === 'done'
        ? `<a class="ce-btn ce-btn-primary" href="${escapeHtml(job.download_url)}">⬇ Скачать</a>
           <a class="ce-btn" href="${escapeHtml(job.result_url)}" target="_blank" rel="noopener">Смотреть</a>`
        : `<span class="job-status job-${job.status}">${STATUS[job.status] || job.status}${job.status === 'processing' ? ` ${Math.round(job.progress * 100)}%` : ''}</span>`;
      return `<div class="my-clip">
        <div class="my-clip-info">
          <strong>${p.text ? escapeHtml(p.text.slice(0, 40)) : 'Клип'}</strong>
          <span>${escapeHtml(details)}${job.error ? ` · ${escapeHtml(job.error)}` : ''}</span>
        </div>
        <div class="my-clip-actions">${action}</div>
      </div>`;
    }).join('');
    if (jobs.some((j) => j.status === 'queued' || j.status === 'processing')) setTimeout(loadJobs, 3000);
  }

  newVideo.addEventListener('click', () => {
    newVideo.hidden = true;
    editor.showPicker();
  });
  document.addEventListener('clip-editor:done', loadJobs);

  const initialUrl = page.dataset.initialUrl;
  if (initialUrl) editor.loadFromUrl(initialUrl); else editor.showPicker();
  loadJobs();
})();
