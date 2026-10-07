/* Админка: управление пользователями. */
const STATUSES = ['Free', 'Standart', 'Pro', 'Premium'];
const state = { page: 1, perPage: 10, sort: 'id', order: 'asc', totalPages: 1, pendingDelete: null };
const esc = (v) => App.escapeHtml(v);

async function loadUsers() {
  const loader = document.getElementById('loader');
  loader.style.display = 'block';
  try {
    state.perPage = Number(document.getElementById('perPage').value);
    const params = new URLSearchParams({
      page: state.page, per_page: state.perPage, sort: state.sort, order: state.order,
      search: document.getElementById('searchInput').value.trim(),
    });
    const data = await App.request(`/api/admin/users?${params}`);
    state.totalPages = data.total_pages;
    if (state.page > state.totalPages) {
      state.page = state.totalPages;
      return loadUsers();
    }
    renderUsers(data.users);
    updatePagination(data.total);
    updateSortHeaders();
  } catch (err) {
    App.toast(err.message);
  } finally {
    loader.style.display = 'none';
  }
}

function renderUsers(users) {
  const tbody = document.getElementById('usersBody');
  if (!users.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-row">Пользователи не найдены</td></tr>';
    return;
  }
  tbody.innerHTML = users.map((u) => `
    <tr data-id="${u.id}">
      <td>${u.id}</td>
      <td><input class="cell-input" data-field="email" value="${esc(u.email)}"></td>
      <td>
        <select class="cell-select" data-field="subscribe_status">
          ${STATUSES.map((s) => `<option value="${s}" ${s === u.subscribe_status ? 'selected' : ''}>${s}</option>`).join('')}
        </select>
      </td>
      <td><input type="date" class="cell-date" data-field="date_end" value="${u.date_end ? esc(u.date_end.slice(0, 10)) : ''}"></td>
      <td><input type="number" class="cell-number" data-field="token_today" min="0" value="${u.token_today}"></td>
      <td><input type="checkbox" class="cell-checkbox" data-field="is_admin" ${u.is_admin ? 'checked' : ''}></td>
      <td class="row-actions">
        <button class="btn-save" title="Сохранить" data-action="save">💾</button>
        <button class="btn-delete" title="Удалить" data-action="delete">🗑️</button>
      </td>
    </tr>`).join('');
}

async function saveRow(row) {
  const get = (field) => row.querySelector(`[data-field="${field}"]`);
  const payload = {
    email: get('email').value.trim(),
    subscribe_status: get('subscribe_status').value,
    date_end: get('date_end').value || null,
    token_today: Number(get('token_today').value) || 0,
    is_admin: get('is_admin').checked,
  };
  try {
    await App.request(`/api/admin/users/${row.dataset.id}`, { method: 'PUT', json: payload });
    App.toast('Изменения сохранены', 'success', 2500);
  } catch (err) {
    App.toast(err.message);
  }
}

function askDelete(userId) {
  state.pendingDelete = userId;
  document.getElementById('confirmMessage').textContent = `Удалить пользователя #${userId}? Его ролики и история будут удалены.`;
  showModal('confirmModal');
}

async function confirmAction() {
  const userId = state.pendingDelete;
  closeConfirmModal();
  if (!userId) return;
  try {
    await App.request(`/api/admin/users/${userId}`, { method: 'DELETE' });
    App.toast('Пользователь удалён', 'success', 2500);
    loadUsers();
  } catch (err) {
    App.toast(err.message);
  }
}

function closeConfirmModal() {
  state.pendingDelete = null;
  hideModal('confirmModal');
}

function changePage(delta) {
  const next = Math.min(state.totalPages, Math.max(1, state.page + delta));
  if (next !== state.page) {
    state.page = next;
    loadUsers();
  }
}

function sortTable(field) {
  if (state.sort === field) state.order = state.order === 'asc' ? 'desc' : 'asc';
  else { state.sort = field; state.order = 'asc'; }
  loadUsers();
}

function updateSortHeaders() {
  document.querySelectorAll('th[data-column]').forEach((th) => {
    const base = th.textContent.replace(/ [▲▼]$/, '');
    th.textContent = th.dataset.column === state.sort ? `${base} ${state.order === 'asc' ? '▲' : '▼'}` : base;
  });
}

function updatePagination(total) {
  document.getElementById('currentPage').textContent = state.page;
  document.getElementById('totalPages').textContent = state.totalPages;
  document.getElementById('prevPage').disabled = state.page <= 1;
  document.getElementById('nextPage').disabled = state.page >= state.totalPages;
  const counter = document.getElementById('totalUsers');
  if (counter) counter.textContent = `Всего: ${total}`;
}

function showModal(id) { document.getElementById(id).style.display = 'block'; }
function hideModal(id) { document.getElementById(id).style.display = 'none'; }
function openCreateModal() { document.getElementById('createForm').reset(); showModal('createModal'); }
function closeCreateModal() { hideModal('createModal'); }
function exportCSV() { location.href = '/admin/export'; }

async function createUser(event) {
  event.preventDefault();
  const payload = {
    email: document.getElementById('createEmail').value.trim(),
    password: document.getElementById('createPassword').value,
    subscribe_status: document.getElementById('createSubscribeStatus').value,
    date_end: document.getElementById('createDateEnd').value || null,
    token_today: Number(document.getElementById('createTokenToday').value) || 0,
    is_admin: document.getElementById('createIsAdmin').checked,
  };
  try {
    await App.request('/api/admin/users', { method: 'POST', json: payload });
    closeCreateModal();
    App.toast('Пользователь создан', 'success', 2500);
    loadUsers();
  } catch (err) {
    App.toast(err.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  let searchTimer;
  document.getElementById('searchInput').addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.page = 1; loadUsers(); }, 400);
  });
  document.getElementById('perPage').addEventListener('change', () => { state.page = 1; loadUsers(); });
  document.getElementById('usersBody').addEventListener('click', (e) => {
    const button = e.target.closest('button[data-action]');
    if (!button) return;
    const row = button.closest('tr');
    if (button.dataset.action === 'save') saveRow(row);
    if (button.dataset.action === 'delete') askDelete(Number(row.dataset.id));
  });
  window.addEventListener('click', (e) => {
    if (e.target.classList && e.target.classList.contains('modal')) e.target.style.display = 'none';
  });
  loadUsers();
});
