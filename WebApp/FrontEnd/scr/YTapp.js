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
const trimInput = document.getElementById('trimInput');
const durationHint = document.getElementById('videoDurationHint');

// Элементы для живого предпросмотра
const videoPreview = document.getElementById('videoPreview');
const textOverlay = document.getElementById('textOverlay');
const previewContainer = document.getElementById('previewContainer');

// Поля ввода для эффектов (по ID из HTML)
const rotateInp = document.getElementById('rotateInp');
const scaleInp = document.getElementById('scaleInp');
const textInp = document.getElementById('textInp');
const speedInp = document.getElementById('speedInp');

// --- 1. ФУНКЦИЯ ЖИВОГО ОБНОВЛЕНИЯ ПРЕДПРОСМОТРА ---
const updateLivePreview = () => {
    if (!videoPreview) return;

    const rotate = rotateInp.value || 0;
    const scale = (scaleInp.value || 100) / 100;
    const text = textInp.value || "";
    const speed = speedInp.value || 1.0;

    // Применяем визуальные трансформации к тегу <video>
    videoPreview.style.transform = `rotate(${rotate}deg) scale(${scale})`;
    
    // Обновляем текст на оверлее
    if (textOverlay) {
        textOverlay.innerText = text;
    }
    
    // Меняем скорость воспроизведения самого превью
    videoPreview.playbackRate = parseFloat(speed) || 1.0;
};

// Привязываем функцию к событиям ввода
[rotateInp, scaleInp, textInp, speedInp].forEach(el => {
    if (el) el.addEventListener('input', updateLivePreview);
});

// --- 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
const toggleLoading = (show) => {
    loadingOverlay.style.display = show ? 'flex' : 'none';
};

// Открытие редактора и загрузка потока видео
const openEditorWithInfo = async (url) => {
    modalVideoUrl.value = url;
    modal.style.display = "flex";
    modalStatus.innerText = "⏳ Загрузка информации о видео...";
    modalStatus.style.color = "#ffa500";
    durationHint.style.display = 'none';

    // Сброс старого видео
    if (videoPreview) {
        videoPreview.pause();
        videoPreview.src = "";
        if (previewContainer) previewContainer.style.display = 'none';
    }

    try {
        const response = await fetch(`/get-video-info?url=${encodeURIComponent(url)}`);
        if (response.ok) {
            const data = await response.json();
            
            // Если сервер вернул прямую ссылку на поток для превью
            if (data.stream_url && videoPreview) {
                videoPreview.src = data.stream_url;
                if (previewContainer) previewContainer.style.display = 'block';
                videoPreview.play();
            }

            const totalSec = Math.floor(data.duration);
            durationHint.innerText = `Длительность видео: ${totalSec} сек.`;
            durationHint.style.display = 'block';
            
            modalStatus.innerText = "✅ Видео готово к настройке";
            modalStatus.style.color = "#4CAF50";
            
            // Сбрасываем эффекты под новое видео
            updateLivePreview();
        }
    } catch (e) {
        modalStatus.innerText = "✅ Видео прикреплено (ошибка превью)";
        modalStatus.style.color = "#4CAF50";
    }
};

// Обработка пресетов обрезки
document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.onclick = () => { trimInput.value = btn.dataset.range; };
});

// Создание карточки видео в результатах
const createResultItem = ({ title, url }) => {
    const item = document.createElement('div');
    item.className = 'video-box';
    
    let videoId = url.includes('v=') ? url.split('v=')[1].split('&')[0] : url.split('/').pop();
    const iframeUrl = `https://www.youtube.com/embed/${videoId}`;

    item.innerHTML = `
    <div class="video-container">
        <h3>${title || 'YouTube Video'}</h3>
        <iframe class="video-iframe" width="100%" height="250" src="${iframeUrl}" frameborder="0" allowfullscreen></iframe>
        <div class="actions" style="margin-top:10px; display:flex; gap:10px;">
            <button class="edit-btn-trigger" style="background:#4CAF50; color:white; border:none; padding:10px; cursor:pointer; border-radius:5px; flex:1; font-weight:bold;">
                🛠 Редактировать
            </button>
        </div>
    </div>`;

    item.querySelector('.edit-btn-trigger').onclick = () => openEditorWithInfo(url);
    return item;
};

// --- 3. ОТПРАВКА НА СЕРВЕР ---
modalForm.onsubmit = async (e) => {
    e.preventDefault();
    renderBtn.disabled = true;
    renderBtn.innerText = "⚙️ Рендеринг...";
    modalStatus.innerText = "⏳ Идет обработка, это может занять минуту...";
    modalStatus.style.color = "#ffa500";
    
    const formData = new FormData(modalForm);
    try {
        const response = await fetch('/process-video', { 
            method: 'POST', 
            body: formData 
        });

        if (response.ok) {
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = "edited_video.mp4";
            document.body.appendChild(a);
            a.click();
            a.remove();
            
            modalStatus.innerText = "✅ Готово! Видео скачано.";
            modalStatus.style.color = "#4CAF50";
        } else {
            const err = await response.json();
            modalStatus.innerText = "❌ Ошибка: " + (err.message || "Ошибка сервера");
            modalStatus.style.color = "#ff4444";
        }
    } catch (err) {
        modalStatus.innerText = "❌ Ошибка сети";
        modalStatus.style.color = "#ff4444";
    } finally {
        renderBtn.disabled = false;
        renderBtn.innerText = "Редактировать";
    }
};

// --- 4. ПОИСК И ИНИЦИАЛИЗАЦИЯ ---
const performSearch = async (query) => {
    if (!query) return;
    toggleLoading(true);
    resultsContainer.innerHTML = '';
    try {
        const response = await fetch(`/search/YT?tag=${encodeURIComponent(query)}`);
        const data = await response.json();
        if (data && data.length > 0) {
            data.forEach(item => resultsContainer.appendChild(createResultItem(item)));
        } else {
            resultsContainer.innerHTML = '<p style="color:white; text-align:center;">Ничего не найдено</p>';
        }
    } catch (err) {
        resultsContainer.innerHTML = '<p style="color:red; text-align:center;">Ошибка загрузки</p>';
    } finally {
        toggleLoading(false);
    }
};

searchButton.onclick = () => performSearch(searchInput.value.trim());

searchInput.onkeypress = (e) => {
    if (e.key === 'Enter') performSearch(searchInput.value.trim());
};

closeModal.onclick = () => {
    modal.style.display = "none";
    if (videoPreview) videoPreview.pause();
};

window.onclick = (e) => {
    if (e.target == modal) {
        modal.style.display = "none";
        if (videoPreview) videoPreview.pause();
    }
};