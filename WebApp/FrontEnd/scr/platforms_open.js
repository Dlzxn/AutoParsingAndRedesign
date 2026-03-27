document.addEventListener('DOMContentLoaded', () => {
    loadPlatforms();
    initModal();
});

let currentPlatform = null;

async function loadPlatforms() {
    try {
        const response = await fetch('/api/platforms');
        const platforms = await response.json();
        renderPlatforms(platforms);
    } catch (error) {
        showError('Ошибка загрузки платформ');
    }
}

function renderPlatforms(platforms) {
    const grid = document.getElementById('platformsGrid');
    grid.innerHTML = '';

    Object.entries(platforms).forEach(([name, data]) => {
        const platformCard = document.createElement('div');
        platformCard.className = 'platform-card';
        platformCard.innerHTML = `
            <div class="platform-header">
                <img src="/WebApp/FrontEnd/images/${name}.png" alt="${name}" class="platform-icon">
                <span class="platform-name">${name.toUpperCase()}</span>
            </div>
            <div class="status-switch">
                <span class="status-label">${data.status === 'on' ? 'Активна' : 'Неактивна'}</span>
                <label class="switch">
                    <input type="checkbox" ${data.status === 'on' ? 'checked' : ''}>
                    <span class="slider"></span>
                </label>
            </div>
        `;

        platformCard.querySelector('input').addEventListener('change', handleStatusChange);
        grid.appendChild(platformCard);
    });
}

function handleStatusChange(e) {
    const platformCard = e.target.closest('.platform-card');
    const platformName = platformCard.querySelector('.platform-name').textContent.toLowerCase();
    const newStatus = e.target.checked ? 'on' : 'off';

    currentPlatform = { name: platformName, newStatus };
    showConfirmationModal(platformName, newStatus);
}

function showConfirmationModal(platform, status) {
    const modal = document.getElementById('confirmationModal');
    const message = document.getElementById('modalMessage');
    message.textContent = `Вы уверены, что хотите ${status === 'on' ? 'активировать' : 'деактивировать'} ${platform.toUpperCase()}?`;
    modal.style.display = 'block';
}

function initModal() {
    const modal = document.getElementById('confirmationModal');

    document.querySelector('.modal-cancel').addEventListener('click', () => {
        modal.style.display = 'none';
        currentPlatform = null;
    });

    document.querySelector('.modal-confirm').addEventListener('click', async () => {
        try {
            await fetch(`/api/platforms/${currentPlatform.name}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ status: currentPlatform.newStatus })
            });

            modal.style.display = 'none';
            loadPlatforms();
        } catch (error) {
            showError('Ошибка обновления статуса');
        }
    });

    window.onclick = (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
            currentPlatform = null;
        }
    }
}

function showError(message) {
    // Реализуйте вывод красивых уведомлений
    console.error(message);
}