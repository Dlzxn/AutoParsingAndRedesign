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
function downloadVideo(url) {
    const downloadUrl = `/download/imgur?url=${encodeURIComponent(url)}`;

    fetch(downloadUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error('Ошибка сети');
            }
            return response.blob();
        })
        .then(blob => {
            const blobUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = 'video.mp4'; // можно сделать имя динамическим
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(blobUrl);
        })
        .catch(error => {
            console.error('Ошибка при скачивании файла:', error);
        });
}



const createResultItem = (title, url, description) => {
    if (!url || typeof url !== 'string') {
        console.warn('Некорректный URL:', url);
        return document.createElement('div'); // пустой элемент вместо ошибки
    }

    const item = document.createElement('div');
    item.className = 'result-item';

    const postId = url.match(/i\.imgur\.com\/([a-zA-Z0-9]+)\.mp4/);
    if (postId && postId[1]) {
        // Если это видео из Imgur, создаем embed-код
        const embedCode = postId[1];

        item.innerHTML = `
            <div class="video-box">
                <h3>
                    <span class="video-title" title="${title}">
                        ${title.slice(0, 25)}${title.length > 22 ? '...' : ''}
                    </span>
                </h3>

                <!-- Вставляем embed-код для видео -->
                <blockquote class="imgur-embed-pub" lang="en" data-id="${embedCode}" data-context="false">
                    <a href="https://imgur.com/${embedCode}"></a>
                </blockquote>
                <script async src="//s.imgur.com/min/embed.js" charset="utf-8"></script>

                <div class="button-group" style="margin-top: 10px;">
                    <button class="download-button" data-url="/download/imgur?url=${url}">Скачать</button>
                    <button class="edit-button" data-url="${url}">Редактировать</button>
                </div>
            </div>
        `;}
    // Вставляем скрипт для рендеринга эмбед-кода
    const script = document.createElement('script');
    script.src = '//s.imgur.com/min/embed.js';
    script.charset = 'utf-8';
    item.appendChild(script);  // Добавляем скрипт для выполнения

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

document.addEventListener('click', function (event) {
    if (event.target.classList.contains('download-button')) {
        const url = event.target.getAttribute('data-url');

        const a = document.createElement('a');
        a.href = url;
        a.setAttribute('download', '');
        a.setAttribute('target', '_blank');

        // Обход CORS и запрета Content-Disposition
        fetch(url)
            .then(res => res.blob())
            .then(blob => {
                const blobUrl = URL.createObjectURL(blob);
                a.href = blobUrl;
                a.download = 'video.mp4';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(blobUrl);
            })
            .catch(err => {
                alert("Не удалось скачать файл.");
                console.error(err);
            });
    }
});





// Отправка запроса для получения списка видео
const performSearch = async (query) => {
    toggleLoading(true);
    resultsContainer.innerHTML = '';

    try {
        const response = await fetch(`/search/Imgur?tag=${encodeURIComponent(query)}`);

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
        data.forEach(item => {
  resultsContainer.appendChild(createResultItem(item.title, item.url));
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
