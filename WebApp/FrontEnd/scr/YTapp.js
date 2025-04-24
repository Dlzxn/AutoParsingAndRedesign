const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const resultsContainer = document.getElementById('results');
const loadingContainer = document.getElementById('loading');

// Показывает или скрывает индикатор загрузки
const toggleLoading = (show) => {
    loadingContainer.style.display = show ? 'block' : 'none';
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
            <h3>${title || url}</h3>
            <iframe width="560" height="315" 
                    src="${iframeUrl}" 
                    title="${title || 'YouTube video'}" 
                    frameborder="0" 
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
                    allowfullscreen>
            </iframe>
        </div>
    `;

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
