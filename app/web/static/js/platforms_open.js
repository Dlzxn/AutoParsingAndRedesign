/* Админка: включение/отключение платформ. */
const ICONS = { vk: 'vk', yt: 'yt', coub: 'coub', reddit: 'reddit', imgur: 'imgur', tumblr: 'tumblr' };
let pending = null;

async function loadPlatforms() {
  try {
    renderPlatforms(await App.request('/api/admin/platforms'));
  } catch (err) {
    App.toast(err.message);
  }
}

function renderPlatforms(platforms) {
  const grid = document.getElementById('platformsGrid');
  grid.innerHTML = platforms.map((p) => `
    <div class="platform-card" data-key="${App.escapeHtml(p.key)}" data-title="${App.escapeHtml(p.title)}">
      <div class="platform-header">
        <img src="/static/img/${ICONS[p.key] || 'video'}.png" alt="" class="platform-icon">
        <span class="platform-name">${App.escapeHtml(p.title)}</span>
      </div>
      <div class="status-switch">
        <span class="status-label">${p.enabled ? 'Активна' : 'Отключена'}</span>
        <label class="switch">
          <input type="checkbox" ${p.enabled ? 'checked' : ''}>
          <span class="slider"></span>
        </label>
      </div>
    </div>`).join('');
}

function closeConfirm(revert) {
  document.getElementById('confirmationModal').style.display = 'none';
  if (revert && pending) pending.input.checked = !pending.enabled;
  pending = null;
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('platformsGrid').addEventListener('change', (e) => {
    if (e.target.type !== 'checkbox') return;
    const card = e.target.closest('.platform-card');
    pending = { key: card.dataset.key, enabled: e.target.checked, input: e.target };
    document.getElementById('modalMessage').textContent =
      `${pending.enabled ? 'Включить' : 'Отключить'} платформу «${card.dataset.title}»?` +
      (pending.enabled ? '' : ' Пользователи увидят страницу «Технические работы».');
    document.getElementById('confirmationModal').style.display = 'block';
  });

  document.querySelector('.modal-cancel').addEventListener('click', () => closeConfirm(true));
  document.querySelector('.modal-confirm').addEventListener('click', async () => {
    if (!pending) return;
    const { key, enabled } = pending;
    closeConfirm(false);
    try {
      await App.request(`/api/admin/platforms/${key}`, { method: 'PUT', json: { enabled } });
      App.toast('Статус платформы обновлён', 'success', 2500);
    } catch (err) {
      App.toast(err.message);
    }
    loadPlatforms();
  });
  window.addEventListener('click', (e) => { if (e.target.id === 'confirmationModal') closeConfirm(true); });

  loadPlatforms();
});
