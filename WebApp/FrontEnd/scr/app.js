// ... предыдущий код ...

// Добавляем обработчики для новых элементов
const searchButton = document.getElementById('searchButton');
const settingsBtn = document.getElementById('settingsBtn');
const settingsDropdown = document.getElementById('settingsDropdown');
const deleteDataBtn = document.getElementById('deleteDataBtn');

// Обработчик кнопки поиска
searchButton.addEventListener('click', (e) => {
    handleSearch({ target: searchInput });
});

// Переключение настроек
settingsBtn.addEventListener('click', () => {
    settingsDropdown.classList.toggle('active');
});

// Закрытие настроек при клике вне области
document.addEventListener('click', (e) => {
    if (!settingsBtn.contains(e.target) && !settingsDropdown.contains(e.target)) {
        settingsDropdown.classList.remove('active');
    }
});

// Обработчик удаления данных
deleteDataBtn.addEventListener('click', () => {
    if (confirm('Вы уверены что хотите удалить все сохраненные данные?')) {
        localStorage.clear();
        resultsContainer.innerHTML = '';
        searchInput.value = '';
        alert('Все данные успешно удалены!');
    }
});

// Анимация ввода
searchInput.addEventListener('focus', () => {
    searchInput.parentElement.style.boxShadow = '0 4px 6px -1px rgba(99, 102, 241, 0.3)';
});

searchInput.addEventListener('blur', () => {
    searchInput.parentElement.style.boxShadow = 'var(--shadow)';
});