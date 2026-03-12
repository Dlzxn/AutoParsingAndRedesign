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

const createResultItem = (title, url) => {
    if (!url || typeof url !== 'string') return document.createElement('div');

    const item = document.createElement('div');
    item.className = 'result-item';

    item.innerHTML = `
    <div class="video-box">
        <h3>
            <span class="video-title" title="${title}">
                ${title.slice(0, 25)}${title.length > 22 ? '...' : ''}
            </span>
        </h3>
        <video width="100%" height="auto" controls preload="none" style="max-width: 560px; border-radius: 10px;">
            <source src="${url}" type="video/mp4">
        </video>
        <div class="button-group" style="margin-top: 10px;">
            <button class="download-button" data-url="${url}">Скачать</button>
            <button class="edit-button">Редактировать</button>
        </div>
    </div>`;

    // Трекинг просмотров
    item.addEventListener('click', () => {
        fetch(`/view?url=${encodeURIComponent(url)}`).catch(err => console.error(err));
    });

    // Редактирование
    item.querySelector('.edit-button').onclick = (e) => {
        e.stopPropagation();
        const modal = document.getElementById('editorModal');
        document.getElementById('modalVideoUrl').value = url;
        document.getElementById('modalStatus').innerText = "✅ Видео Reddit прикреплено";
        document.getElementById('modalStatus').style.color = "#4CAF50";
        modal.style.display = "flex";
    };

    return item;
};

// Глобальный делегат для скачивания (твой оригинальный метод)
document.addEventListener('click', function (event) {
    if (event.target.classList.contains('download-button')) {
        const url = event.target.getAttribute('data-url');
        fetch(url)
            .then(res => res.blob())
            .then(blob => {
                const a = document.createElement('a');
                const blobUrl = URL.createObjectURL(blob);
                a.href = blobUrl;
                a.download = 'reddit_video.mp4';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(blobUrl);
            })
            .catch(() => alert("Ошибка скачивания"));
    }
});

const performSearch = async (query) => {
    toggleLoading(true);
    resultsContainer.innerHTML = '';
    try {
        const response = await fetch(`/search/Reddit?tag=${encodeURIComponent(query)}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error);
        if (!data.length) {
            resultsContainer.innerHTML = `<div class="no-results">Ничего не найдено 😕</div>`;
            return;
        }
        data.forEach(item => resultsContainer.appendChild(createResultItem(item.title, item.url)));
    } catch (err) {
        showError('Ошибка сервера');
    } finally {
        toggleLoading(false);
    }
};

searchButton.onclick = () => {
    const query = searchInput.value.trim();
    if (query.length > 2) performSearch(query);
};

// Инициализация логики формы модалки
function initModal() {
    const modal = document.getElementById('editorModal');
    const closeBtn = document.getElementById('closeModal');
    const form = document.getElementById('modalEditorForm');
    const renderBtn = document.getElementById('renderBtn');
    const status = document.getElementById('modalStatus');

    closeBtn.onclick = () => modal.style.display = "none";
    window.onclick = (e) => { if (e.target == modal) modal.style.display = "none"; };

    form.onsubmit = async (e) => {
        e.preventDefault();
        renderBtn.disabled = true;
        renderBtn.innerText = "Обработка...";
        status.innerText = "⏳ Рендеринг видео...";
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
                a.download = "reddit_edited.mp4";
                a.click();
                status.innerText = "✅ Видео готово!";
                status.style.color = "#4CAF50";
            } else {
                status.innerText = "❌ Ошибка при обработке";
                status.style.color = "#ff4444";
            }
        } catch (err) {
            status.innerText = "❌ Ошибка связи";
        } finally {
            renderBtn.disabled = false;
            renderBtn.innerText = "Начать рендеринг";
        }
    };
}

initModal();