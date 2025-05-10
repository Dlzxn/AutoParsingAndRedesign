let currentState = {
  page: 1,
  perPage: 10,
  sortField: 'id',
  sortOrder: 'asc',
  totalPages: 1,
  currentEditingId: null,
  currentAction: null
};

async function loadUsers() {
  showLoader();
  try {
    const params = new URLSearchParams({
      page: currentState.page,
      per_page: currentState.perPage,
      sort: currentState.sortField,
      order: currentState.sortOrder,
      search: document.getElementById('searchInput').value
    });

    const response = await fetch(`/api/users?${params}`);
    if (!response.ok) throw new Error('Ошибка загрузки');

    const { users, total } = await response.json();

    currentState.totalPages = Math.ceil(total / currentState.perPage);
    updatePagination();
    renderUsers(users);
    updateSortHeaders();
  } catch (error) {
    showError(error.message);
  } finally {
    hideLoader();
  }
}

function renderUsers(users) {
  const tbody = document.getElementById('usersBody');
  tbody.innerHTML = '';

  users.forEach(user => {
    const row = document.createElement('tr');

    row.innerHTML = `
      <td class="editable-cell" data-field="id">${user.id}</td>
      <td class="editable-cell" data-field="email">${user.email}</td>
      <td class="editable-cell" data-field="subscribe_status">
        <select class="cell-select" data-value="${user.subscribe_status}">
          <option value="Free">Free</option>
          <option value="Premium">Premium</option>
          <option value="VIP">VIP</option>
        </select>
      </td>
      <td class="editable-cell" data-field="date_end">
        <input type="date" class="cell-date" value="${user.date_end?.split('T')[0] || ''}">
      </td>
      <td class="editable-cell" data-field="token_today">
        <input type="number" class="cell-number" value="${user.token_today}">
      </td>
      <td class="editable-cell" data-field="is_admin">
        <input type="checkbox" class="cell-checkbox" ${user.is_admin ? 'checked' : ''}>
      </td>
      <td>
        <button class="btn-save" onclick="saveRow(this)">💾</button>
        <button class="btn-delete" onclick="confirmDelete(${user.id})">🗑️</button>
      </td>
    `;

    // Инициализация значений
    const statusSelect = row.querySelector('.cell-select');
    statusSelect.value = user.subscribe_status;

    tbody.appendChild(row);
  });

  initInlineEditing();
}

function initInlineEditing() {
  document.querySelectorAll('.editable-cell').forEach(cell => {
    cell.addEventListener('click', function(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      const field = this.dataset.field;
      const value = this.innerText;

      if (field === 'email') {
        this.innerHTML = `<input class="cell-edit-input" value="${value}">`;
        this.querySelector('input').focus();
      }
    });
  });
}

async function saveRow(button) {
  const row = button.closest('tr');
  const userId = row.querySelector('[data-field="id"]').innerText;
  const data = {
    email: row.querySelector('[data-field="email"]').innerText,
    subscribe_status: row.querySelector('.cell-select').value,
    date_end: row.querySelector('.cell-date').value || null,
    token_today: parseInt(row.querySelector('.cell-number').value),
    is_admin: row.querySelector('.cell-checkbox').checked
  };

  try {
    const response = await fetch(`/api/users/${userId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });

    if (!response.ok) throw new Error('Ошибка сохранения');
    showSuccess('Данные сохранены');
    loadUsers();
  } catch (error) {
    showError(error.message);
  }
}

async function confirmDelete(userId) {
  currentState.currentAction = { type: 'delete', userId };
  document.getElementById('confirmMessage').textContent = `Удалить пользователя #${userId}?`;
  showModal('confirmModal');
}

async function deleteUser(userId) {
  try {
    const response = await fetch(`/api/users/${userId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Ошибка удаления');
    showSuccess('Пользователь удален');
    loadUsers();
  } catch (error) {
    showError(error.message);
  }
}

// Пагинация и сортировка
function changePage(delta) {
  currentState.page = Math.max(1, currentState.page + delta);
  loadUsers();
}

function sortTable(field) {
  if (currentState.sortField === field) {
    currentState.sortOrder = currentState.sortOrder === 'asc' ? 'desc' : 'asc';
  } else {
    currentState.sortField = field;
    currentState.sortOrder = 'asc';
  }
  loadUsers();
}

// Вспомогательные функции
function showLoader() {
  document.getElementById('loader').style.display = 'block';
}

function hideLoader() {
  document.getElementById('loader').style.display = 'none';
}

function updatePagination() {
  document.getElementById('currentPage').textContent = currentState.page;
  document.getElementById('totalPages').textContent = currentState.totalPages;
  document.getElementById('prevPage').disabled = currentState.page === 1;
  document.getElementById('nextPage').disabled = currentState.page === currentState.totalPages;
}

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('perPage').value = currentState.perPage;
  loadUsers();

  // Обработчик поиска
  let searchTimeout;
  document.getElementById('searchInput').addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(loadUsers, 500);
  });
});
function openCreateModal() {
  document.getElementById('createModal').style.display = 'flex';
}

function closeCreateModal() {
  document.getElementById('createModal').style.display = 'none';
}

async function createUser(event) {
  event.preventDefault();

  const userData = {
    email: document.getElementById('createEmail').value,
    password: document.getElementById('createPassword').value,
    subscribe_status: document.getElementById('createSubscribeStatus').value,
    date_end: document.getElementById('createDateEnd').value || null,
    token_today: parseInt(document.getElementById('createTokenToday').value),
    is_admin: document.getElementById('createIsAdmin').checked
  };

  try {
    const response = await fetch('/api/users', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(userData)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Ошибка создания');
    }

    closeCreateModal();
    loadUsers();
    showSuccess('Пользователь успешно создан!');
  } catch (error) {
    showError(error.message);
  }
}