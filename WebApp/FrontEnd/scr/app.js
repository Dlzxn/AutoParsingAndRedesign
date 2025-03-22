const API_ENDPOINT = '/search'; // Заменить на реальный эндпоинт

// Элементы DOM
const searchInput = document.getElementById('searchInput');
const resultsContainer = document.getElementById('results');
const loadingContainer = document.getElementById('loading');

// Декоративные элементы
const floatingShapes = document.createElement('div');
floatingShapes.className = 'floating-shapes';
document.body.appendChild(floatingShapes);

// Дебаунс запросов (500ms)
const debounce = (func, delay = 500) => {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
};

// Анимация загрузки
const toggleLoading = (show) => {
    loadingContainer.style.display = show ? 'block' : 'none';
    searchInput.disabled = show;
};


// Генератор элементов результата
// Генератор элементов результата
const createResultItem = ({ title, url, id }) => {
    const item = document.createElement('div');
    item.className = 'result-item';

    item.innerHTML = `
        <div class="link-container" style="background-color: #f0f0f0; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);">
            <a href="${url}" target="_blank" class="link-title" style="color: #0073e6; font-size: 16px; text-decoration: none; font-weight: bold; transition: color 0.3s ease;" onmouseover="this.style.color='#005bb5'" onmouseout="this.style.color='#0073e6'">${title || url}</a>
            <div class="link-actions" style="margin-top: 10px;">
                <button class="copy-btn" data-url="${url}" title="Скопировать ссылку" style="background-color: #4CAF50; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; font-size: 14px; margin-right: 10px;" onmouseover="this.style.backgroundColor='#45a049'" onmouseout="this.style.backgroundColor='#4CAF50'">
                    <span class="material-icons" style="font-size: 20px;">content_copy</span>
                </button>
                <button class="download-btn" data-id="${id}" title="Скачать видео" style="background-color: #ff5722; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; font-size: 14px;" onmouseover="this.style.backgroundColor='#e64a19'" onmouseout="this.style.backgroundColor='#ff5722'">
                    <span class="material-icons" style="font-size: 20px;">download</span>
                </button>
            </div>
        </div>
    `;

    // Обработчик нажатия кнопки "Скачать"
    const downloadButton = item.querySelector('.download-btn');
    downloadButton.addEventListener('click', () => {
        const videoId = downloadButton.getAttribute('data-id');

        // Запрос к API для получения файла
        fetch(`/api/${videoId}`)
            .then(response => response.blob()) // получаем файл в формате Blob
            .then(blob => {
                // Здесь открываем файл в новом окне внутри приложения (например, в Electron)
                const fileURL = window.URL.createObjectURL(blob);
                const newWindow = window.open(fileURL, '_blank'); // открываем файл в новом окне

                // Закрытие URL после использования
                newWindow.onload = () => {
                    window.URL.revokeObjectURL(fileURL); // очищаем URL после того как файл загрузится в окно
                };
            })
            .catch(error => {
                console.error('Ошибка скачивания видео:', error);
            });
    });

    return item;
};



// Обработчик копирования
const handleCopy = async (url) => {
    try {
        await navigator.clipboard.writeText(url);
        showNotification('Ссылка скопирована!', 'success');
    } catch (err) {
        showNotification('Ошибка копирования', 'error');
    }
};

// Визуальное уведомление
const showNotification = (message, type = 'info') => {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
};

// Основной обработчик поиска
const performSearch = async (query) => {
    try {
        toggleLoading(true);

        const response = await fetch(`${API_ENDPOINT}?tag=${encodeURIComponent(query)}`);
        if (!response.ok) throw new Error('Ошибка API');

        const data = await response.json();

        resultsContainer.innerHTML = '';
        data.forEach(item => {
            resultsContainer.appendChild(createResultItem(item));
        });

    } catch (error) {
        showNotification('Ошибка получения данных', 'error');
        resultsContainer.innerHTML = `<div class="error-message">😞 Не удалось загрузить результаты</div>`;
    } finally {
        toggleLoading(false);
    }
};

// Обработчики событий
document.addEventListener('click', async (e) => {
    if (e.target.closest('.copy-btn')) {
        const url = e.target.closest('.copy-btn').dataset.url;
        handleCopy(url);
    }

    if (e.target.closest('.download-btn')) {
        const url = e.target.closest('.download-btn').dataset.url;
        window.open(`${url}?download=true`, '_blank');
    }
});

searchInput.addEventListener('input', debounce(e => {
    const query = e.target.value.trim();
    if (query.length > 2) performSearch(query);
}));

// Плавное появление элементов
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = 1;
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, { threshold: 0.1 });

document.querySelectorAll('.result-item').forEach(item => observer.observe(item));


// Переключение настроек// Переключение настроек
settingsBtn.addEventListener('click', () => {
    settingsDropdown.classList.toggle('active');
});

// Закрытие настроек при клике вне области
document.addEventListener('click', (e) => {
    if (!settingsBtn.contains(e.target) && !settingsDropdown.contains(e.target)) {
        settingsDropdown.classList.remove('active');
    }
});

// Обработчик удаления данных
deleteDataBtn.addEventListener('click', () => {
    if (confirm('Вы уверены что хотите удалить все сохраненные данные?')) {
        localStorage.clear();
        resultsContainer.innerHTML = '';
        searchInput.value = '';
        alert('Все данные успешно удалены!');
    }
});
settingsBtn.addEventListener('click', () => {
    settingsDropdown.classList.toggle('active');
});

// Закрытие настроек при клике вне области
document.addEventListener('click', (e) => {
    if (!settingsBtn.contains(e.target) && !settingsDropdown.contains(e.target)) {
        settingsDropdown.classList.remove('active');
    }
});

// Обработчик удаления данных
deleteDataBtn.addEventListener('click', () => {
    if (confirm('Вы уверены что хотите удалить все сохраненные данные?')) {
        localStorage.clear();
        resultsContainer.innerHTML = '';
        searchInput.value = '';
        alert('Все данные успешно удалены!');
    }
});