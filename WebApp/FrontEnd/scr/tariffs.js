document.addEventListener('DOMContentLoaded', () => {
    const capabilitiesGrid = document.getElementById('capabilitiesGrid');
    const modal = document.getElementById('confirmationModal');

    // Пример данных (в реальном проекте - запрос к API)
    const capabilitiesData = [
        {
            id: 1,
            name: "Аналитика данных",
            description: "Расширенная аналитика в реальном времени",
            icon: "📊"
        },
        {
            id: 2,
            name: "Интеграции",
            description: "Подключение внешних сервисов и API",
            icon: "🔌"
        },
        {
            id: 3,
            name: "Безопасность",
            description: "Защита данных и соответствие стандартам",
            icon: "🔒"
        },
        {
            id: 4,
            name: "Кастомизация",
            description: "Настройка под бизнес-процессы",
            icon: "⚙️"
        }
    ];

    // Генерация карточек возможностей
    function renderCapabilities() {
        capabilitiesGrid.innerHTML = '';

        capabilitiesData.forEach(capability => {
            const card = document.createElement('div');
            card.className = 'capability-card';
            card.innerHTML = `
                <div class="capability-icon">${capability.icon}</div>
                <h3 class="capability-name">${capability.name}</h3>
                <p class="capability-description">${capability.description}</p>
            `;
            card.addEventListener('click', () => showModal(capability));
            capabilitiesGrid.appendChild(card);
        });
    }

    // Показать модальное окно
    function showModal(capability) {
        const message = modal.querySelector('#modalMessage');
        message.textContent = `Выбрана функция: ${capability.name}`;
        modal.style.display = 'flex';
    }

    // Закрыть модальное окно
    function closeModal() {
        modal.style.display = 'none';
    }

    // Обработчики событий для модального окна
    modal.querySelector('.modal-cancel').addEventListener('click', closeModal);
    modal.querySelector('.modal-confirm').addEventListener('click', () => {
        alert('Действие подтверждено!');
        closeModal();
    });

    // Клик вне модального окна
    window.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    renderCapabilities();
});