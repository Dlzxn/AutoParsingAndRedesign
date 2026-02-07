const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const resultsContainer = document.getElementById('results');
const loadingOverlay = document.getElementById('loadingOverlay');

const toggleLoading = (show) => {
    loadingOverlay.style.display = show ? 'flex' : 'none';
    searchInput.disabled = show;
    searchButton.disabled = show;
};

window.openCoubEditor = (url) => {
    const modal = document.getElementById('editorModal');
    const modalInput = document.getElementById('modalVideoUrl');
    if (modal && modalInput) {
        modalInput.value = url;
        document.getElementById('modalStatus').innerText = "✅ Видео Coub готово";
        document.getElementById('modalStatus').style.color = "#4CAF50";
        modal.style.display = "flex";
    }
};

const createResultItem = (url) => {
    if (!url || typeof url !== 'string') return document.createElement('div');

    const item = document.createElement('div');
    item.className = 'result-item';

    item.innerHTML = `
    <div class="video-box">
        <h3>
            <span class="video-title" title="${url}">
                ${url.split('/').pop().slice(0, 25)}...
            </span>
        </h3>
        <video width="100%" height="auto" controls preload="none" style="max-width: 560px; border-radius: 10px;">
            <source src="${url}" type="video/mp4">
        </video>
        <div class="button-group" style="margin-top: 10px;">
            <a href="${url}" target="_blank">
                <button class="download-button">Скачать</button>
            </a>
            <button class="edit-button" onclick="window.openCoubEditor('${url}')">Редактировать</button>
        </div>
    </div>`;

    item.querySelector('video').onplay = () => {
        fetch(`/view?url=${encodeURIComponent(url)}`).catch(err => console.error(err));
    };

    return item;
};

const performSearch = async (query) => {
    toggleLoading(true);
    resultsContainer.innerHTML = '';
    try {
        const response = await fetch(`/search/Coub?tag=${encodeURIComponent(query)}`);
        const data = await response.json();
        if (data && data.length) {
            data.forEach(videoUrl => resultsContainer.appendChild(createResultItem(videoUrl)));
        } else {
            resultsContainer.innerHTML = `<div class="no-results">Ничего не найдено 😕</div>`;
        }
    } catch (err) {
        console.error(err);
    } finally {
        toggleLoading(false);
    }
};

searchButton.onclick = () => {
    const query = searchInput.value.trim();
    if (query.length > 2) performSearch(query);
};

function initModal() {
    const modal = document.getElementById('editorModal');
    const closeBtn = document.getElementById('closeModal');
    const form = document.getElementById('modalEditorForm');

    if (closeBtn) closeBtn.onclick = () => modal.style.display = "none";
    window.onclick = (e) => { if (e.target == modal) modal.style.display = "none"; };

    if (form) {
        form.onsubmit = async (e) => {
            e.preventDefault();
            const btn = document.getElementById('renderBtn');
            const status = document.getElementById('modalStatus');
            btn.disabled = true;
            status.innerText = "⏳ Идет рендеринг...";
            status.style.color = "#ffa500";

            try {
                const response = await fetch('/process-video', {
                    method: 'POST',
                    body: new FormData(form)
                });
                if (response.ok) {
                    const blob = await response.blob();
                    const a = document.createElement('a');
                    a.href = window.URL.createObjectURL(blob);
                    a.download = "coub_edited.mp4";
                    a.click();
                    status.innerText = "✅ Видео готово и скачано!";
                    status.style.color = "#4CAF50";
                }
            } catch (err) {
                status.innerText = "❌ Ошибка сервера";
            } finally {
                btn.disabled = false;
            }
        };
    }
}

initModal();