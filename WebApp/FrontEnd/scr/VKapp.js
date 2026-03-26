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
    const notification = errorClone.querySelector('.error-notification');

    errorMessage.textContent = message;

    retryButton.addEventListener('click', () => {
        notification.remove();
    });

    document.body.appendChild(errorClone);

    setTimeout(() => {
        if (notification.parentNode) notification.remove();
    }, 5000);
};

const createResultItem = ({ title, url }) => {
    const item = document.createElement('div');
    item.className = 'result-item';

    const match = url.match(/video(-?\d+)_(\d+)/);
    let embedUrl = '';
    if (match) {
        const ownerId = match[1];
        const videoId = match[2];
        embedUrl = `https://vk.com/video_ext.php?oid=${ownerId}&id=${videoId}`;
    }

    item.innerHTML = `
    <div class="video-box">
        <div class="video-container">
            <iframe class="video-iframe" 
                    src="${embedUrl}" 
                    width="100%" 
                    height="180" 
                    style="max-width: 320px; max-height: 180px;" 
                    frameborder="0" 
                    allowfullscreen="true"></iframe>
        </div>
        <div class="video-info">
            <h3 class="video-title"><a href="${url}" target="_blank" rel="noopener noreferrer"></a></h3>
            <div class="actions">
                <button class="download-button" data-url="${url}">Скачать</button>
                <button class="edit-button" data-url="${url}">Редактировать</button>
            </div>
        </div>
    </div>`;

    item.querySelector('.video-title a').textContent = title || url;

    item.addEventListener('click', () => {
        fetch(`/view?url=${encodeURIComponent(url)}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' },
        })
        .catch(error => console.error(error));
    });

    item.querySelector('.download-button').addEventListener('click', (e) => {
        e.stopPropagation();
        window.location.href = `/download/vkvideo?url=${encodeURIComponent(url)}`;
    });

    item.querySelector('.edit-button').addEventListener('click', (e) => {
        e.stopPropagation();
        const modal = document.getElementById('editorModal');
        const modalVideoUrl = document.getElementById('modalVideoUrl');
        const modalStatus = document.getElementById('modalStatus');

        if (modal && modalVideoUrl) {
            modalVideoUrl.value = url;
            modalStatus.innerText = "✅ Видео VK выбрано";
            modalStatus.style.color = "#4CAF50";
            modal.style.display = "flex";
        }
    });

    return item;
};

const performSearch = async () => {
    const query = searchInput.value.trim();
    if (query.length <= 2) {
        showError('Введите хотя бы 3 символа');
        return;
    }

    toggleLoading(true);
    resultsContainer.innerHTML = '';

    try {
        const response = await fetch(`/search/Vk?tag=${encodeURIComponent(query)}`);

        if (!response.ok) {
            const data = await response.json();
            showError(data.error || 'Ошибка запроса');
            return;
        }

        const data = await response.json();

        if (!data.length) {
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

searchButton.addEventListener('click', performSearch);

searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        performSearch();
    }
});

function initModalLogic() {
    const modal = document.getElementById('editorModal');
    const closeBtn = document.getElementById('closeModal');
    const form = document.getElementById('modalEditorForm');
    const renderBtn = document.getElementById('renderBtn');
    const status = document.getElementById('modalStatus');

    if (closeBtn) {
        closeBtn.onclick = () => { modal.style.display = "none"; };
    }

    window.onclick = (e) => {
        if (e.target == modal) modal.style.display = "none";
    };

    if (form) {
        form.onsubmit = async (e) => {
            e.preventDefault();
            
            renderBtn.disabled = true;
            renderBtn.innerText = "Обработка...";
            status.innerText = "⏳ Рендеринг запущен. Пожалуйста, подождите...";
            status.style.color = "#ffa500";

            try {
                const response = await fetch('/process-video', {
                    method: 'POST',
                    body: new FormData(form)
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const dUrl = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = dUrl;
                    a.download = "edited_vk_video.mp4";
                    document.body.appendChild(a);
                    a.click();
                    
                    setTimeout(() => {
                        a.remove();
                        window.URL.revokeObjectURL(dUrl);
                    }, 100);

                    status.innerText = "✅ Видео успешно обработано!";
                    status.style.color = "#4CAF50";
                } else {
                    const errData = await response.json();
                    status.innerText = "❌ Ошибка: " + (errData.message || "сервер отклонил запрос");
                    status.style.color = "#ff4444";
                }
            } catch (err) {
                status.innerText = "❌ Ошибка связи с сервером";
                status.style.color = "#ff4444";
            } finally {
                renderBtn.disabled = false;
                renderBtn.innerText = "Редактировать";
            }
        };
    }
}

initModalLogic();