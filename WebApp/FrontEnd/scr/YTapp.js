const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const resultsContainer = document.getElementById('results');
const loadingOverlay = document.getElementById('loadingOverlay');

const toggleLoading = (show) => {
    loadingOverlay.style.display = show ? 'flex' : 'none';
    searchInput.disabled = show;
    searchButton.disabled = show;
};

const showError = (message) => {
    resultsContainer.innerHTML = `<div class="error-message">❌ ${message}</div>`;
};

const createResultItem = ({ title, url }) => {
    const item = document.createElement('div');
    item.className = 'result-item';

    let videoId = '';
    if (url.includes('v=')) {
        videoId = url.split('v=')[1].split('&')[0];
    } else if (url.includes('shorts/')) {
        videoId = url.split('shorts/')[1].split('?')[0];
    } else {
        videoId = url.split('/').pop();
    }

    const iframeUrl = `https://www.youtube.com/embed/${videoId}`;

    item.innerHTML = `
    <div class="video-box">
        <h3><a href="${url}" target="_blank" rel="noopener noreferrer">${title || url}</a></h3>
        <iframe width="100%" height="315" 
                src="${iframeUrl}" 
                title="${title || 'YouTube video'}" 
                frameborder="0" 
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
                allowfullscreen 
                loading="lazy">
        </iframe>
        <div class="button-group" style="margin-top: 10px; display: flex; gap: 10px;">
            <button class="download-button" style="padding: 8px 15px; cursor: pointer;">Скачать</button>
            <button class="edit-button" style="padding: 8px 15px; cursor: pointer; background-color: #4CAF50; color: white; border: none; border-radius: 4px;">Редактировать</button>
        </div>
    </div>`;

    const downloadButton = item.querySelector('.download-button');
    downloadButton.addEventListener('click', (event) => {
        event.stopPropagation();
        window.location.href = `/download/yt?url=${encodeURIComponent(url)}`;
    });

    const editButton = item.querySelector('.edit-button');
    editButton.addEventListener('click', (event) => {
        event.stopPropagation();
        const editUrl = `/VideoEditor/editor/${encodeURIComponent(url)}`;
        window.location.href = editUrl;
    });

    return item;
};

const performSearch = async (query) => {
    toggleLoading(true);
    resultsContainer.innerHTML = '';

    try {
        const response = await fetch(`/search/YT?tag=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (!response.ok) {
            showError(data.error || 'Ошибка запроса');
            return;
        }

        if (!data || data.length === 0) {
            resultsContainer.innerHTML = `<div class="no-results">Ничего не найдено 😕</div>`;
            return;
        }

        data.forEach(item => {
            resultsContainer.appendChild(createResultItem(item));
        });

    } catch (err) {
        showError('Сервер не отвечает');
    } finally {
        toggleLoading(false);
    }
};

searchButton.addEventListener('click', () => {
    const query = searchInput.value.trim();
    if (query.length > 2) {
        performSearch(query);
    } else {
        showError('Введите хотя бы 3 символа для поиска');
    }
});

searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        const query = searchInput.value.trim();
        if (query.length > 2) performSearch(query);
    }
});