const API_ENDPOINT = '/search'; // Заменить на реальный эндпоинт

// Элементы DOM
const searchInput = document.getElementById('searchInput');
const resultsContainer = document.getElementById('results');
const loadingContainer = document.getElementById('loading');
const searchButton = document.getElementById('searchButton');

// Декоративные элементы
const floatingShapes = document.createElement('div');
floatingShapes.className = 'floating-shapes';
document.body.appendChild(floatingShapes);

// Анимация загрузки
const toggleLoading = (show) => {
    loadingContainer.style.display = show ? 'block' : 'none';
    searchInput.disabled = show;
    document.body.style.cursor = show ? 'progress' : 'default'; // Изменение курсора
};


// Дебаунс запросов (500ms)
const debounce = (func, delay = 5000) => {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
};

// Генератор элементов результата
const createResultItem = ({ title, url, id }) => {
    const item = document.createElement('div');
    item.className = 'result-item';

    item.innerHTML = `
        <div class="link-container" style="background-color: #f0f0f0; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);">
    <a href="${url}" target="_blank" class="link-title" style="color: #0073e6; font-size: 16px; text-decoration: none; font-weight: bold; transition: color 0.3s ease;" onmouseover="this.style.color='#005bb5'" onmouseout="this.style.color='#0073e6'">
        ${title || (url.length > 35 ? url.substring(0, 35) + '...' : url)}
    </a>
    <div class="link-actions" style="margin-top: 10px;">
        <button class="copy-btn" data-url="${url}" title="Скопировать ссылку" style="background-color: #4CAF50; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; font-size: 14px; margin-right: 10px;" onmouseover="this.style.backgroundColor='#45a049'" onmouseout="this.style.backgroundColor='#4CAF50'">
            <span class="material-icons" style="font-size: 20px;">content_copy</span>
        </button>
        <button class="download-btn" data-url="${url}" title="Скачать видео" style="background-color: #ff5722; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; font-size: 14px;" onmouseover="this.style.backgroundColor='#e64a19'" onmouseout="this.style.backgroundColor='#ff5722'">
            <span class="material-icons" style="font-size: 20px;">download</span>
        </button>
    </div>
</div>

    `;

    const copyButton = item.querySelector('.copy-btn');
    copyButton.addEventListener('click', () => {
        const videoUrl = copyButton.getAttribute('data-url');
        navigator.clipboard.writeText(videoUrl)
            .then(() => showNotification('Ссылка скопирована! ✅', 'success'))
            .catch(() => showNotification('Ошибка копирования 😞', 'error'));
    });

    const downloadButton = item.querySelector('.download-btn');
    downloadButton.addEventListener('click', () => {
        // Получаем URL из атрибута data-url кнопки
        const videoUrl = downloadButton.getAttribute('data-url');

        // Отправляем запрос на сервер
        fetch('/api/download', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'x-video-url': videoUrl  // Передаем URL в заголовке
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Ошибка при загрузке видео');
            }

            // Получаем имя файла из заголовка Content-Disposition
            const contentDisposition = response.headers.get('Content-Disposition');
            const fileName = contentDisposition ? contentDisposition.split('filename=')[1] : 'video.mp4';

            // Создаем ссылку для скачивания
            return response.blob().then(blob => {
                const downloadLink = document.createElement('a');
                downloadLink.href = URL.createObjectURL(blob);
                downloadLink.download = fileName;  // Имя файла для скачивания
                downloadLink.click();
            });
        })
        .catch(error => {
            console.error('Ошибка:', error);
            alert('Не удалось скачать видео');
        });
    });

    return item;
};



// Функция для скачивания видео
const downloadVideo = (videoUrl) => {
    fetch('/api/download', {
        method: 'GET',
        headers: {
            'x-video-url': videoUrl,  // Отправляем ссылку на видео в заголовке
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'video.mp4'; // Дефолтное название файла

        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename\*?=["']?(?:UTF-\d['"]*)?([^;"']*)["']?/i);
            if (filenameMatch && filenameMatch[1]) {
                filename = filenameMatch[1];
            }
        }

        return Promise.all([response.blob(), filename]);
    })
    .then(([blob, filename]) => {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';

        document.body.appendChild(link);
        link.click();

        window.URL.revokeObjectURL(url);
        document.body.removeChild(link);
    })
    .catch(error => {
        console.error('Ошибка скачивания видео:', error);
        alert('Произошла ошибка при скачивании файла');
    });
};

// Визуальное уведомление
const showNotification = (message, type = 'info') => {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
};

const performSearch = async (query) => {
    try {
        toggleLoading(true);

        // Убедись, что fetch всегда будет выполняться
        const response = await fetch(`${API_ENDPOINT}?tag=${encodeURIComponent(query)}`, {
            // Не добавляем никаких дополнительных ограничений или отмен (например, через AbortController)
        });

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


// Обработчик ввода
searchInput.addEventListener('input', debounce(e => {
    const query = e.target.value.trim();
    if (query.length > 2) performSearch(query);
}));

// Стиль для лоадера
const styleLoader = `
    .loading-container {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        display: none;
    }

    .floating-shapes {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: -1;
    }
`;

const styleElement = document.createElement('style');
styleElement.innerHTML = styleLoader;
document.head.appendChild(styleElement);
