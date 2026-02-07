const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const resultsContainer = document.getElementById('results');
const loadingOverlay = document.getElementById('loadingOverlay');

const toggleLoading = (show) => {
    loadingOverlay.style.display = show ? 'flex' : 'none';
    searchInput.disabled = show;
    searchButton.disabled = show;
};

window.openImgurEditor = (url) => {
    const modal = document.getElementById('editorModal');
    const modalInput = document.getElementById('modalVideoUrl');
    if (modal && modalInput) {
        modalInput.value = url;
        document.getElementById('modalStatus').innerText = "✅ Видео Imgur прикреплено";
        document.getElementById('modalStatus').style.color = "#1bb76e";
        modal.style.display = "flex";
    }
};

const createResultItem = (title, url) => {
    if (!url || typeof url !== 'string') return document.createElement('div');

    const item = document.createElement('div');
    item.className = 'result-item';

    const postIdMatch = url.match(/i\.imgur\.com\/([a-zA-Z0-9]+)\.mp4/);
    const embedCode = (postIdMatch && postIdMatch[1]) ? postIdMatch[1] : null;

    item.innerHTML = `
    <div class="video-box">
        <h3>
            <span class="video-title" title="${title}">
                ${title.slice(0, 25)}${title.length > 22 ? '...' : ''}
            </span>
        </h3>

        ${embedCode ? `
            <blockquote class="imgur-embed-pub" lang="en" data-id="${embedCode}" data-context="false">
                <a href="https://imgur.com/${embedCode}"></a>
            </blockquote>
        ` : `
            <video width="100%" height="auto" controls style="border-radius: 10px;">
                <source src="${url}" type="video/mp4">
            </video>
        `}

        <div class="button-group" style="margin-top: 10px;">
            <button class="download-button" data-url="${url}">Скачать</button>
            <button class="edit-button" onclick="window.openImgurEditor('${url}')">Редактировать</button>
        </div>
    </div>`;

    const script = document.createElement('script');
    script.src = '//s.imgur.com/min/embed.js';
    script.async = true;
    item.appendChild(script);

    item.addEventListener('click', () => {
        fetch(`/view?url=${encodeURIComponent(url)}`).catch(err => console.error(err));
    });

    return item;
};

// Глобальный слушатель для скачивания (твой метод)
document.addEventListener('click', function (event) {
    if (event.target.classList.contains('download-button')) {
        const url = event.target.getAttribute('data-url');
        fetch(url)
            .then(res => res.blob())
            .then(blob => {
                const blobUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = blobUrl;
                a.download = 'imgur_video.mp4';
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(blobUrl);
            })
            .catch(() => alert("Ошибка скачивания."));
    }
});

const performSearch = async (query) => {
    toggleLoading(true);
    resultsContainer.innerHTML = '';
    try {
        const response = await fetch(`/search/Imgur?tag=${encodeURIComponent(query)}`);
        const data = await response.json();
        if (data && data.length) {
            data.forEach(item => resultsContainer.appendChild(createResultItem(item.title, item.url)));
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

// Инициализация модалки
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
            status.innerText = "⏳ Рендеринг...";

            try {
                const response = await fetch('/process-video', {
                    method: 'POST',
                    body: new FormData(form)
                });
                if (response.ok) {
                    const blob = await response.blob();
                    const a = document.createElement('a');
                    a.href = window.URL.createObjectURL(blob);
                    a.download = "result.mp4";
                    a.click();
                    status.innerText = "✅ Готово!";
                }
            } catch (err) {
                status.innerText = "❌ Ошибка";
            } finally {
                btn.disabled = false;
            }
        };
    }
}

initModal();