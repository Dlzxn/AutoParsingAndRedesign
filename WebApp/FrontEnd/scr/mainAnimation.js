document.addEventListener('DOMContentLoaded', () => {
    // Обработка выбора типа контента
    const selectors = document.querySelectorAll('.type-selector');
    const contentBoxes = document.querySelectorAll('.content-box');

    selectors.forEach(selector => {
        selector.addEventListener('click', () => {
            // Удаляем активный класс у всех
            selectors.forEach(s => s.classList.remove('active'));
            selector.classList.add('active');

            // Показываем соответствующий контент
            const type = selector.dataset.type;
            contentBoxes.forEach(box => {
                box.classList.remove('show'));
                if(box.id === `${type}-content`) {
                    setTimeout(() => box.classList.add('show'), 300);
                }
            });
        });
    });

    // Анимация карточек цен при скролле
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if(entry.isIntersecting) {
                entry.target.style.animation = 'cardAppear 1s forwards';
            }
        });
    }, { threshold: 0.2 });

    document.querySelectorAll('.pricing-card').forEach(card => {
        observer.observe(card);
    });

    // Инициализация анимации заголовка
    const titleParts = document.querySelectorAll('.title-part');
    titleParts.forEach(part => {
        part.style.animationPlayState = 'running';
    });
});