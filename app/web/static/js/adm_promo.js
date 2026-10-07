/* Админка: промокоды. */
let currentEditingId = null;
const esc = (v) => App.escapeHtml(v);

async function loadPromoCodes() {
  try {
    renderPromocodes(await App.request('/api/admin/promocodes'));
  } catch (err) {
    App.toast(err.message);
  }
}

function renderPromocodes(items) {
  const tbody = document.getElementById('promoBody');
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#6b7785;padding:2rem">Промокодов пока нет</td></tr>';
    return;
  }
  tbody.innerHTML = items.map((p) => `
    <tr data-id="${p.id}">
      <td>${esc(p.name)}</td>
      <td>${esc(p.type)}</td>
      <td>${p.status ? 'Активен' : 'Неактивен'}</td>
      <td>${p.count_activated}</td>
      <td>${p.bonus_count}</td>
      <td>${p.date_ended ? new Date(p.date_ended).toLocaleString('ru-RU') : 'Нет'}</td>
      <td>
        <button class="action-btn edit-btn" data-action="edit" title="Изменить">✏️</button>
        <button class="action-btn delete-btn" data-action="delete" title="Удалить">🗑️</button>
      </td>
    </tr>`).join('');
}

function openModal() {
  currentEditingId = null;
  document.getElementById('modalTitle').textContent = 'Новый промокод';
  document.getElementById('promoForm').reset();
  document.getElementById('status').checked = true;
  document.getElementById('promoModal').style.display = 'block';
}

function closeModal() {
  document.getElementById('promoModal').style.display = 'none';
}

async function editPromo(id) {
  try {
    const promo = await App.request(`/api/admin/promocodes/${id}`);
    currentEditingId = id;
    document.getElementById('modalTitle').textContent = 'Редактирование промокода';
    document.getElementById('name').value = promo.name;
    document.getElementById('type').value = promo.type;
    document.getElementById('status').checked = promo.status;
    const picker = document.getElementById('date_ended')._flatpickr;
    if (picker) picker.setDate(promo.date_ended || null); else document.getElementById('date_ended').value = promo.date_ended || '';
    document.getElementById('count_activated').value = promo.count_activated;
    document.getElementById('bonus_count').value = promo.bonus_count;
    document.getElementById('description').value = promo.description || '';
    document.getElementById('promoModal').style.display = 'block';
  } catch (err) {
    App.toast(err.message);
  }
}

async function deletePromo(id) {
  if (!window.confirm('Удалить промокод?')) return;
  try {
    await App.request(`/api/admin/promocodes/${id}`, { method: 'DELETE' });
    App.toast('Промокод удалён', 'success', 2500);
    loadPromoCodes();
  } catch (err) {
    App.toast(err.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (window.flatpickr) {
    flatpickr('#date_ended', { enableTime: true, dateFormat: 'Y-m-d H:i', time_24hr: true });
  }
  document.querySelector('#promoModal .close').addEventListener('click', closeModal);
  window.addEventListener('click', (e) => { if (e.target.id === 'promoModal') closeModal(); });

  document.getElementById('promoBody').addEventListener('click', (e) => {
    const button = e.target.closest('button[data-action]');
    if (!button) return;
    const id = button.closest('tr').dataset.id;
    if (button.dataset.action === 'edit') editPromo(id);
    if (button.dataset.action === 'delete') deletePromo(id);
  });

  document.getElementById('promoForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const dateValue = document.getElementById('date_ended').value.trim();
    const payload = {
      name: document.getElementById('name').value.trim(),
      type: document.getElementById('type').value,
      status: document.getElementById('status').checked,
      date_ended: dateValue ? dateValue.replace(' ', 'T') : null,
      count_activated: Number(document.getElementById('count_activated').value) || 0,
      bonus_count: Number(document.getElementById('bonus_count').value) || 0,
      description: document.getElementById('description').value.trim() || null,
    };
    try {
      await App.request(currentEditingId ? `/api/admin/promocodes/${currentEditingId}` : '/api/admin/promocodes', {
        method: currentEditingId ? 'PUT' : 'POST',
        json: payload,
      });
      closeModal();
      App.toast('Промокод сохранён', 'success', 2500);
      loadPromoCodes();
    } catch (err) {
      App.toast(err.message);
    }
  });

  loadPromoCodes();
});
