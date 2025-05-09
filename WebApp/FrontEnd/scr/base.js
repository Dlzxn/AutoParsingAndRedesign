
document.addEventListener('DOMContentLoaded', function() {
      const profile = document.getElementById('profileDropdown');
      const dropdown = profile.querySelector('.dropdown-menu');

      profile.addEventListener('click', function(e) {
        e.stopPropagation();
        dropdown.classList.toggle('show');
      });

      document.addEventListener('click', function() {
        dropdown.classList.remove('show');
      });
    });

// base.js - Динамическое обновление профиля и управление выпадающим меню

// Функция для обновления информации профиля
function updateProfileInfo() {
    // Получаем элементы DOM
    const usernameElement = document.querySelector('.username');
    const planElement = document.querySelector('.plan');

    fetch('/api/user/user_data')
        .then(response => {
            if (!response.ok) throw new Error('Ошибка сети');
            return response.json();
        })
        .then(data => {
            // Обновляем данные только если элементы существуют
            if (usernameElement) {
                usernameElement.textContent = data.name || 'Пользователь';
            }
            if (planElement) {
                planElement.textContent = data.subscriptionPlan || 'Бесплатный';
                // Добавляем класс для стилизации плана
                planElement.className = 'plan ' + (data.subscriptionPlan?.toLowerCase() || 'free');
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки профиля:', error);
            // Устанавливаем значения по умолчанию при ошибке
            if (usernameElement) usernameElement.textContent = 'Гость';
            if (planElement) planElement.textContent = 'Неавторизован';
        });
}

// Обработчик для выпадающего меню профиля
document.addEventListener('DOMContentLoaded', function() {
    // Инициализация профиля
    updateProfileInfo();

    // Получаем элементы меню
    const profileDropdown = document.getElementById('profileDropdown');
    const dropdownMenu = profileDropdown?.querySelector('.dropdown-menu');

    // Обработчик клика по профилю
    if (profileDropdown) {
        profileDropdown.addEventListener('click', function(e) {
            e.stopPropagation();
            this.classList.toggle('active');
        });
    }

    // Закрытие меню при клике вне области
    document.addEventListener('click', function(e) {
        if (profileDropdown && !profileDropdown.contains(e.target)) {
            profileDropdown.classList.remove('active');
        }
    });

    // Закрытие меню при нажатии ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && profileDropdown) {
            profileDropdown.classList.remove('active');
        }
    });
});
