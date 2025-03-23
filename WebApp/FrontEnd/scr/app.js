const API_ENDPOINT = '/search'; // Заменить на реальный эндпоинт

// Элементы DOM
const searchInput = document.getElementById('searchInput');
const resultsContainer = document.getElementById('results');
const loadingContainer = document.getElementById('loading');

// Декоративные элементы
const floatingShapes = document.createElement('div');
floatingShapes.className = 'floating-shapes';
document.body.appendChild(floatingShapes);

const searchButton = document.getElementById('searchButton');
const settingsBtn = document.getElementById('settingsBtn');
const settingsDropdown = document.getElementById('settingsDropdown');
const deleteDataBtn = document.getElementById('deleteDataBtn');

// Новые элементы DOM
const openFolderBtn = document.getElementById('openFolderBtn');
const fileModal = document.getElementById('fileModal');
const closeModal = document.querySelector('.close');
const fileList = document.getElementById('fileList');

// app.js

document.getElementById('openFolderBtn').addEventListener('click', async () => {
    try {
        const response = await fetch('/files');
        if (!response.ok) {
            throw new Error(`Ошибка: ${response.status} ${response.statusText}`);
        }
    } catch (error) {
        showNotification(error.message, 'error');
    }
});


async function getFilesFromDirectory(directoryHandle) {
    const files = [];
    for await (const entry of directoryHandle.values()) {
        if (entry.kind === 'file') {
            files.push({
                name: entry.name,
                type: entry.name.split('.').pop().toUpperCase()
            });
        }
    }
    return files;
}

function showFilesInModal(files) {
    const fileList = document.getElementById('fileList');
    fileList.innerHTML = files.map(file => `
        <div class="file-item">
            <span class="material-icons">description</span>
            <div class="file-info">
                <span class="file-name">${file.name}</span>
                <span class="file-type">${file.type}</span>
            </div>
        </div>
    `).join('');

    document.getElementById('fileModal').style.display = 'block';
}

// Закрытие модального окна
document.querySelector('.close').addEventListener('click', () => {
    document.getElementById('fileModal').style.display = 'none';
});

function showFilesInModal(files) {
    const fileList = document.getElementById('fileList');
    fileList.innerHTML = files.map(file => `
        <div class="file-item">
            <span class="material-icons">description</span>
            <span>${file}</span>
        </div>
    `).join('');

    document.getElementById('fileModal').style.display = 'block';
}

// Обработчик открытия папки
openFolderBtn.addEventListener('click', async () => {
    try {
        const directoryHandle = await window.showDirectoryPicker();
        const files = await readDirectory(directoryHandle);
        showFiles(files);
        fileModal.style.display = 'block';
    } catch (error) {
        if (error.name !== 'AbortError') {
            showNotification('Ошибка доступа к папке', 'error');
        }
    }
});

// Чтение содержимого папки
async function readDirectory(directoryHandle) {
    const files = [];
    for await (const entry of directoryHandle.values()) {
        if (entry.kind === 'file') {
            files.push({
                name: entry.name,
                handle: entry
            });
        }
    }
    return files;
}

// Отображение файлов
function showFiles(files) {
    fileList.innerHTML = files.map(file => `
        <div class="file-item">
            <span class="material-icons">description</span>
            <span>${file.name}</span>
        </div>
    `).join('');
}

// Закрытие модального окна
closeModal.addEventListener('click', () => {
    fileModal.style.display = 'none';
});

window.onclick = (event) => {
    if (event.target === fileModal) {
        fileModal.style.display = 'none';
    }
}

// Обработчик кнопки поиска
searchButton.addEventListener('click', (e) => {
    handleSearch({ target: searchInput });
});

// Переключение настроек
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

// Анимация ввода
searchInput.addEventListener('focus', () => {
    searchInput.parentElement.style.boxShadow = '0 4px 6px -1px rgba(99, 102, 241, 0.3)';
});

searchInput.addEventListener('blur', () => {
    searchInput.parentElement.style.boxShadow = 'var(--shadow)';
});

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

        fetch(`/api/${videoId}`)
            .then(response => {
                // Получаем имя файла из заголовка Content-Disposition
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = 'video.mp4';

                if (contentDisposition) {
                    const filenameMatch = contentDisposition.match(/filename\*?=["']?(?:UTF-\d['"]*)?([^;"']*)["']?/i);
                    if (filenameMatch && filenameMatch[1]) {
                        filename = filenameMatch[1];
                    }
                }

                return Promise.all([response.blob(), filename]);
            })
            .then(([blob, filename]) => {
                // Создаем временную ссылку для скачивания
                const url = window.URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = filename;
                link.style.display = 'none';

                document.body.appendChild(link);
                link.click();

                // Очистка
                window.URL.revokeObjectURL(url);
                document.body.removeChild(link);
            })
            .catch(error => {
                console.error('Ошибка скачивания видео:', error);
                alert('Произошла ошибка при скачивании файла');
            });
    });

    return item;
};



// Улучшенный обработчик копирования
const handleCopy = async (url) => {
    try {
        if (navigator.clipboard) {
            await navigator.clipboard.writeText(url);
        } else {
            // Fallback для старых браузеров
            const textarea = document.createElement('textarea');
            textarea.value = url;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
        }
        showNotification('Ссылка скопирована!', 'success');
    } catch (err) {
        console.error('Ошибка копирования:', err);
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

// Исправленный обработчик событий
document.addEventListener('click', async (e) => {
    // Обработчик копирования
    if (e.target.closest('.copy-btn')) {
        const btn = e.target.closest('.copy-btn');
        const url = btn.dataset.url;
        handleCopy(url);
        return; // Добавляем return для предотвращения конфликтов
    }

    // Обработчик скачивания
    if (e.target.closest('.download-btn')) {
        const btn = e.target.closest('.download-btn');
        const url = btn.dataset.url;
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


