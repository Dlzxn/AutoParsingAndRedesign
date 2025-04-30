// Функция для проверки, виден ли элемент
function isVisible(el) {
    const rect = el.getBoundingClientRect();
    return rect.top < window.innerHeight - 100; // 100px до низа
}

// Функция для анимации появления
function animateOnScroll() {
    const elements = document.querySelectorAll('.title, .platform-button');
    elements.forEach(el => {
        if (isVisible(el)) {
            el.classList.add('show');
        }
    });
}

// Сразу проверяем при загрузке
window.addEventListener('load', animateOnScroll);
// И проверяем при скролле
window.addEventListener('scroll', animateOnScroll);

