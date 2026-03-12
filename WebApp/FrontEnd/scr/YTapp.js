const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const resultsContainer = document.getElementById('results');
const loadingOverlay = document.getElementById('loadingOverlay');

const modal = document.getElementById('editorModal');
const closeModal = document.getElementById('closeModal');
const modalForm = document.getElementById('modalEditorForm');
const modalVideoUrl = document.getElementById('modalVideoUrl');
const modalStatus = document.getElementById('modalStatus');
const renderBtn = document.getElementById('renderBtn');

const toggleLoading = (show) => {
    loadingOverlay.style.display = show ? 'flex' : 'none';
};

const createResultItem = ({ title, url }) => {
    const item = document.createElement('div');
    item.className = 'result-item';

    let videoId = url.includes('v=') ? url.split('v=')[1].split('&')[0] : (url.includes('shorts/') ? url.split('shorts/')[1].split('?')[0] : url.split('/').pop());
    const iframeUrl = `https://www.youtube.com/embed/${videoId}`;

    item.innerHTML = `
    <div class="video-box">
        <h3><a href="${url}" target="_blank">${title || url}</a></h3>
        <iframe width="100%" height="315" src="${iframeUrl}" frameborder="0" allowfullscreen></iframe>
        <div class="button-group" style="margin-top: 10px; display: flex; gap: 10px;">
            <button class="download-button" style="padding: 8px 15px; cursor: pointer;">Скачать</button>
            <button class="edit-button" style="padding: 8px 15px; cursor: pointer; background-color: #4CAF50; color: white; border: none; border-radius: 4px;">Редактировать</button>
        </div>
    </div>`;

    item.querySelector('.download-button').onclick = () => window.location.href = `/download/yt?url=${encodeURIComponent(url)}`;
    
    item.querySelector('.edit-button').onclick = () => {
        modalVideoUrl.value = url;
        modalStatus.innerText = "✅ Видео прикреплено";
        modalStatus.style.color = "#4CAF50";
        modal.style.display = "flex";
    };

    return item;
};

closeModal.onclick = () => modal.style.display = "none";
window.onclick = (e) => { if (e.target == modal) modal.style.display = "none"; };

modalForm.onsubmit = async (e) => {
    e.preventDefault();
    renderBtn.disabled = true;
    renderBtn.innerText = "Обработка...";
    modalStatus.innerText = "⏳ Идет рендеринг видео...";
    modalStatus.style.color = "#ffa500";

    const formData = new FormData(modalForm);

    try {
        const response = await fetch('/process-video', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = "edited_video.mp4";
            document.body.appendChild(a);
            a.click();
            a.remove();
            modalStatus.innerText = "✅ Готово!";
            modalStatus.style.color = "#4CAF50";
        } else {
            const err = await response.json();
            modalStatus.innerText = "❌ Ошибка: " + err.message;
            modalStatus.style.color = "#ff4444";
        }
    } catch (err) {
        modalStatus.innerText = "❌ Ошибка связи";
        modalStatus.style.color = "#ff4444";
    } finally {
        renderBtn.disabled = false;
        renderBtn.innerText = "Редактировать";
    }
};

const performSearch = async (query) => {
    toggleLoading(true);
    resultsContainer.innerHTML = '';
    try {
        const response = await fetch(`/search/YT?tag=${encodeURIComponent(query)}`);
        const data = await response.json();
        if (data && data.length > 0) {
            data.forEach(item => resultsContainer.appendChild(createResultItem(item)));
        } else {
            resultsContainer.innerHTML = '<div class="no-results">Ничего не найдено</div>';
        }
    } catch (err) {
        resultsContainer.innerHTML = '<div class="error-message">Ошибка сервера</div>';
    } finally {
        toggleLoading(false);
    }
};

searchButton.onclick = () => {
    const query = searchInput.value.trim();
    if (query.length > 2) performSearch(query);
};

searchInput.onkeypress = (e) => {
    if (e.key === 'Enter') {
        const query = searchInput.value.trim();
        if (query.length > 2) performSearch(query);
    }
};