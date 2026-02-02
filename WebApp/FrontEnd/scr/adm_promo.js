
document.addEventListener('DOMContentLoaded', () => {
    loadPromoCodes();
    initModal();
    initDatePicker();
});

let currentEditingId = null;

async function loadPromoCodes() {
    try {
        const response = await fetch('/api/promocodes');
        const promocodes = await response.json();
        renderPromocodes(promocodes);
    } catch (error) {
        console.error('Ошибка загрузки промокодов:', error);
    }
}

function renderPromocodes(promocodes) {
    const tbody = document.getElementById('promoBody');
    tbody.innerHTML = '';
    
    promocodes.forEach(promo => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${promo.name}</td>
            <td>${promo.type}</td>
            <td>${promo.status ? 'Активен' : 'Неактивен'}</td>
            <td>${promo.count_activated}</td>
            <td>${promo.bonus_count}</td>
            <td>${promo.date_ended ? new Date(promo.date_ended).toLocaleDateString() : 'Нет'}</td>
            <td>
                <button class="action-btn edit-btn" onclick="editPromo('${promo.id}')">✏️</button>
                <button class="action-btn delete-btn" onclick="deletePromo('${promo.id}')">🗑️</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function initDatePicker() {
    flatpickr('#date_ended', {
        enableTime: true,
        dateFormat: "Y-m-d H:i",
        time_24hr: true
    });
}

function initModal() {
    const modal = document.getElementById('promoModal');
    const span = document.getElementsByClassName('close')[0];

    window.openModal = () => {
        currentEditingId = null;
        document.getElementById('modalTitle').textContent = 'Новый промокод';
        document.getElementById('promoForm').reset();
        modal.style.display = 'block';
    }

    span.onclick = () => modal.style.display = 'none';
    window.onclick = (event) => {
        if (event.target == modal) modal.style.display = 'none';
    }
}

async function editPromo(id) {
    try {
        const response = await fetch(`/api/promocodes/${id}`);
        const promo = await response.json();
        
        currentEditingId = id;
        document.getElementById('modalTitle').textContent = 'Редактирование промокода';
        document.getElementById('promoId').value = id;
        document.getElementById('name').value = promo.name;
        document.getElementById('type').value = promo.type;
        document.getElementById('status').checked = promo.status;
        document.getElementById('date_ended').value = promo.date_ended;
        document.getElementById('count_activated').value = promo.count_activated;
        document.getElementById('bonus_count').value = promo.bonus_count;
        document.getElementById('description').value = promo.description;
        
        document.getElementById('promoModal').style.display = 'block';
    } catch (error) {
        console.error('Ошибка редактирования:', error);
    }
}

document.getElementById('promoForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const promoData = {
        name: document.getElementById('name').value,
        type: document.getElementById('type').value,
        status: document.getElementById('status').checked,
        date_ended: document.getElementById('date_ended').value,
        count_activated: parseInt(document.getElementById('count_activated').value),
        bonus_count: parseInt(document.getElementById('bonus_count').value),
        description: document.getElementById('description').value
    };

    try {
        const url = currentEditingId ? `/api/promocodes/${currentEditingId}` : '/api/promocodes';
        const method = currentEditingId ? 'PUT' : 'POST';
        
        await fetch(url, {
            method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(promoData)
        });
        
        loadPromoCodes();
        document.getElementById('promoModal').style.display = 'none';
    } catch (error) {
        console.error('Ошибка сохранения:', error);
    }
});

async function deletePromo(id) {
    if (!confirm('Удалить промокод?')) return;
    
    try {
        await fetch(`/api/promocodes/${id}`, {method: 'DELETE'});
        loadPromoCodes();
    } catch (error) {
        console.error('Ошибка удаления:', error);
    }
}