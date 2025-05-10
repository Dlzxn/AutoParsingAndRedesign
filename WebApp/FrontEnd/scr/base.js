
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


// Функция для обновления информации профиля
function updateProfileInfo() {
    const usernameElement = document.querySelector('.username');
    const planElement = document.querySelector('.plan');
    const dropdownMenu = document.querySelector('.dropdown-menu');

    fetch('/api/user/user_data')
        .then(response => {
            if (!response.ok) throw new Error('Ошибка сети');
            return response.json();
        })
        .then(data => {
            // Обновление основной информации
            if (usernameElement) {
                usernameElement.textContent = data.name || 'Пользователь';
            }
            if (planElement) {
                planElement.textContent = data.subscriptionPlan || 'Бесплатный';
                planElement.className = 'plan ' + (data.subscriptionPlan?.toLowerCase() || 'free');
            }

            // Динамическое обновление меню
            if (dropdownMenu) {
                if (data) {
                    console.log(data.name)
                    if ( data.subscriptionPlan == "Administrator" ) {
                        dropdownMenu.innerHTML = `
                        <a href="/profile" class="dropdown-item">Перейти в профиль</a>
                        <a href="/admin" class="dropdown-item">Админ панель</a>
                        <a href="/tariffs" class="dropdown-item">Тарифы</a>
                        <a href="/logout" class="dropdown-item logout-btn">Выйти</a>
                    `;
                    }
                    else {
                        dropdownMenu.innerHTML = `
                        <a href="/profile" class="dropdown-item">Перейти в профиль</a>
                        <a href="/tariffs" class="dropdown-item">Тарифы</a>
                        <a href="/logout" class="dropdown-item logout-btn">Выйти</a>
                    `;
                    }
                }
                else {
                    dropdownMenu.innerHTML = `
                        <a href="/login" class="dropdown-item">Войти</a>
                        <a href="/register" class="dropdown-item">Зарегистрироваться</a>
                    `;
                }
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки профиля:', error);
            if (usernameElement) usernameElement.textContent = 'Гость';
            if (planElement) planElement.textContent = 'Неавторизован';
            if (dropdownMenu) {
                dropdownMenu.innerHTML = `
                    <a href="/login" class="dropdown-item">Войти</a>
                    <a href="/register" class="dropdown-item">Зарегистрироваться</a>
                `;
            }
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
