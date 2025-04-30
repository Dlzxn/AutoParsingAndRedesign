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

const createResultItem = (postData) => {
    const { type, summary, post_url, blog_name, timestamp, tags, id} = postData;
    const item = document.createElement('div');
    item.className = 'result-item';

    // Форматируем дату
    const postDate = new Date(timestamp * 1000).toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'long',
        year: 'numeric'
    });

    // Создаем блок с постом
    const embedUrl = `https://embed.tumblr.com/embed/post/${blog_name}/${id}`;
    console.log(embedUrl)

item.innerHTML = `
    <div class="tumblr-post-container">
        <iframe src="${embedUrl}" 
                class="tumblr-iframe" 
                frameborder="0" 
                allowfullscreen
                scrolling="no"
                width="100%"
                height="500">
        </iframe>
        
        <div class="post-controls">
            <button class="copy-button" data-summary="${encodeURIComponent(summary)}">
                📋 Копировать текст
            </button>
            <button class="edit-button" data-summary="${encodeURIComponent(summary)}">
                ✏️ Редактировать
            </button>
        </div>
    </div>
`;


    // Обработчики для кнопок
    const copyButton = item.querySelector('.copy-button');
    const editButton = item.querySelector('.edit-button');

    // Копирование текста
    copyButton.addEventListener('click', () => {
        navigator.clipboard.writeText(summary)
            .then(() => {
                const originalText = copyButton.textContent;
                copyButton.textContent = 'Скопировано!';
                setTimeout(() => {
                    copyButton.textContent = originalText;
                }, 2000);
            })
            .catch(err => console.error('Ошибка копирования:', err));
    });

    // Редактирование поста
    editButton.addEventListener('click', () => {
        window.location.href = `/editor?text=${encodeURIComponent(summary)}`;
    });

    return item;
};

// Обновленная функция выполнения поиска
const performSearch = async (query) => {
    toggleLoading(true);
    resultsContainer.innerHTML = '';

    try {
        const response = await fetch(`/search/tumblr?tag=${encodeURIComponent(query)}`);

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Ошибка при загрузке данных');
        }

        const posts = await response.json();

        if (!posts.length) {
            resultsContainer.innerHTML = `<div class="no-results">Посты не найдены 😕</div>`;
            return;
        }

        posts.forEach(post => {
            resultsContainer.appendChild(createResultItem(post));
        });

    } catch (err) {
        console.error('Error:', err);
        showError(err.message || 'Ошибка при загрузке данных');
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