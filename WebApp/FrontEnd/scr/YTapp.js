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

// Создает блок с видео
const createResultItem = ({ title, url }) => {
    const item = document.createElement('div');
    item.className = 'result-item';

    // Вставляем iframe для видео
    const videoId = url.split('v=')[1]; // Получаем videoId из ссылки
    const iframeUrl = `https://www.youtube.com/embed/${videoId}`;

    item.innerHTML = `
        <div class="video-box">
            <h3><a href="${url}" target="_blank" rel="noopener noreferrer">${title || url}</a></h3>
            <iframe width="560" height="315" 
                    src="${iframeUrl}" 
                    title="${title || 'YouTube video'}" 
                    frameborder="0" 
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
                    allowfullscreen>
            </iframe>
            <div class="button-group" style="margin-top: 10px;">
                <button class="download-button" data-url="${url}">Скачать</button>
                <button class="edit-button" data-url="${url}">Редактировать</button>
            </div>
        </div>
    `;

    // Добавляем обработчик на кнопку "Скачать"
    const downloadButton = item.querySelector('.download-button');
    downloadButton.addEventListener('click', () => {
        const downloadUrl = `/download/yt?url=${encodeURIComponent(url)}`;
        window.location.href = downloadUrl;
    });

    // Обработчик на кнопку "Редактировать" — пока просто вывод в консоль
    const editButton = item.querySelector('.edit-button');
    editButton.addEventListener('click', () => {
        console.log('Редактировать видео:', url);
        // тут можно будет открывать форму или модалку
    });

    return item;
};


// Отправка запроса
const performSearch = async (query) => {
    toggleLoading(true);
    resultsContainer.innerHTML = '';

    try {
        const response = await fetch(`/search/YT?tag=${encodeURIComponent(query)}`);

        const data = await response.json();

        if (!response.ok) {
            showError(data.error || 'Произошла ошибка при выполнении запроса');
            return;
        }

        if (!data.length) {
            resultsContainer.innerHTML = `<div class="no-results">Ничего не найдено 😕</div>`;
            return;
        }

        data.forEach(item => {
            resultsContainer.appendChild(createResultItem(item));
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
