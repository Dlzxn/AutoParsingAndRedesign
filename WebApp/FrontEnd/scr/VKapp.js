const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const resultsContainer = document.getElementById('results');
const loadingOverlay = document.getElementById('loadingOverlay');
const errorTemplate = document.getElementById('errorTemplate');

const toggleLoading = (show) => {
    if (show) {
        loadingOverlay.style.display = 'flex';
        searchButton.querySelector('.button-text').style.opacity = '0';
        searchButton.querySelector('.button-loader').style.display = 'block';
    } else {
        loadingOverlay.style.display = 'none';
        searchButton.querySelector('.button-text').style.opacity = '1';
        searchButton.querySelector('.button-loader').style.display = 'none';
    }
    searchInput.disabled = show;
    searchButton.disabled = show;
};

const showError = (message) => {
    const errorClone = errorTemplate.content.cloneNode(true);
    const errorMessage = errorClone.querySelector('.error-message');
    const retryButton = errorClone.querySelector('.retry-button');

    errorMessage.textContent = message;

    retryButton.addEventListener('click', () => {
        document.querySelector('.error-notification')?.remove();
    });

    document.body.appendChild(errorClone);

    setTimeout(() => {
        document.querySelector('.error-notification')?.remove();
    }, 5000);
};

// Создает блок с видео
const createResultItem = ({ title, url }) => {
    const item = document.createElement('div');
    item.className = 'result-item';

    // Извлекаем ID видео из URL с учетом нового формата
    const match = url.match(/video(-?\d+)_(\d+)/);
    let embedUrl = '';
    if (match) {
        const ownerId = match[1];
        const videoId = match[2];

        // Формируем URL для встраивания через iframe
        embedUrl = `https://vk.com/video_ext.php?oid=${ownerId}&id=${videoId}`;
        console.log(`Embed URL: ${embedUrl}`); // Логируем embedUrl
    } else {
        console.warn(`Не удалось извлечь видео ID из URL: ${url}`); // Логируем ошибку
    }

    item.innerHTML = `
    <div class="video-box">
        <div class="video-container">
            <iframe class="video-iframe" 
                    src="${embedUrl}" 
                    width="100%" 
                    height="auto" 
                    style="max-width: 320px; max-height: 180px;" 
                    frameborder="0" 
                    allowfullscreen="true"></iframe>
        </div>
        <div class="video-info">
            <h3 class="video-title"><a href="${url}" target="_blank" rel="noopener noreferrer">${title || url}</a></h3>
            <div class="actions">
                <button class="download-button" data-url="${url}">Скачать</button>
                <button class="edit-button" data-url="${url}">Редактировать</button>
            </div>
        </div>
    </div>
`;



    // Добавляем обработчик на кнопку "Скачать"
    const downloadButton = item.querySelector('.download-button');
    downloadButton.addEventListener('click', () => {
        const downloadUrl = `/download/vkvideo?url=${encodeURIComponent(url)}`;
        window.location.href = downloadUrl;
    });

    // Обработчик на кнопку "Редактировать" — пока просто вывод в консоль
    const editButton = item.querySelector('.edit-button');
    editButton.addEventListener('click', () => {
        console.log('Редактировать видео:', url);
        // Здесь можно потом добавить открытие модалки или формы
    });

    return item;
};


// Отправка запроса
const performSearch = async (query) => {
    toggleLoading(true);
    resultsContainer.innerHTML = '';

    try {
        console.log(`Performing search for: ${query}`); // Логируем запрос
        const response = await fetch(`/search/Vk?tag=${encodeURIComponent(query)}`);

        // Проверка на успешность ответа
        if (!response.ok) {
            const data = await response.json();
            showError(data.error || 'Произошла ошибка при выполнении запроса');
            return;
        }

        const data = await response.json();

        if (!data.length) {
            resultsContainer.innerHTML = `<div class="no-results">Ничего не найдено 😕</div>`;
            return;
        }

        // Добавляем результаты в контейнер
        data.forEach(item => {
            resultsContainer.appendChild(createResultItem(item));
        });

    } catch (err) {
        console.error('Error during fetch: ', err); // Логируем ошибку при выполнении запроса
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