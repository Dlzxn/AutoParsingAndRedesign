const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const resultsContainer = document.getElementById('results');
const loadingOverlay = document.getElementById('loadingOverlay');

const toggleLoading = (show) => {
    loadingOverlay.style.display = show ? 'flex' : 'none';
    searchInput.disabled = show;
    searchButton.disabled = show;
};

// Показывает уведомление об ошибке
const showError = (message) => {
    resultsContainer.innerHTML = `<div class="error-message">❌ ${message}</div>`;
};

const createResultItem = (url) => {
    if (!url || typeof url !== 'string') {
        console.warn('Некорректный URL:', url);
        return document.createElement('div'); // пустой элемент вместо ошибки
    }

    const item = document.createElement('div');
    item.className = 'result-item';

    item.innerHTML = `
    <div class="video-box">
        <h3>
            <span class="video-title" title="${url}">
                ${url.slice(0, 25)}${url.length > 22 ? '...' : ''}
            </span>
        </h3>

        <video width="100%" height="auto" controls preload="none" style="max-width: 560px; border-radius: 10px;">
            <source src="${url}" type="video/mp4">
            Ваш браузер не поддерживает воспроизведение видео.
        </video>

        <div class="button-group" style="margin-top: 10px;">
            <a href="${url}" target="_blank">
                <button class="download-button">Скачать</button>
            </a>
            <button class="edit-button" data-url="${url}">Редактировать</button>
        </div>
    </div>
`;
    item.addEventListener('click', (event) => {
    const videoUrl = url; // Сохраняем URL

    // Отправляем запрос на сервер при любом клике в контейнере
    fetch(`/view?url=${encodeURIComponent(videoUrl)}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        console.log('Ответ от сервера:', data);
    })
    .catch(error => {
        console.error('Ошибка при отправке запроса:', error);
    });
});



    const editButton = item.querySelector('.edit-button');
    editButton.addEventListener('click', () => {
        console.log('Редактировать видео:', url);
    });

    return item;
};




// Отправка запроса для получения списка видео
const performSearch = async (query) => {
    toggleLoading(true);
    resultsContainer.innerHTML = '';

    try {
        const response = await fetch(`/search/Coub?tag=${encodeURIComponent(query)}`);

        const data = await response.json();

        if (!response.ok) {
            showError(data.error || 'Произошла ошибка при выполнении запроса');
            return;
        }

        if (!data.length) {
            resultsContainer.innerHTML = `<div class="no-results">Ничего не найдено 😕</div>`;
            return;
        }

        // Теперь data - это массив, и можно использовать .forEach для обработки
        data.forEach(url => {
    resultsContainer.appendChild(createResultItem(url));
});


    } catch (err) {
        console.error(err);
        showError('Сервер не отвечает или возникла непредвиденная ошибка');
    } finally {
        toggleLoading(false);
    }
};


// Слушатель кнопки
searchButton.addEventListener('click', () => {
    const query = searchInput.value.trim();
    if (query.length > 2) {
        performSearch(query);
    } else {
        showError('Введите хотя бы 3 символа для поиска');
    }
});
