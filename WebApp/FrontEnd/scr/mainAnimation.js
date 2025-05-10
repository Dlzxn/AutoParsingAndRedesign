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
                box.classList.remove('show');
                if (box.id === `${type}-content`) {
                    setTimeout(() => box.classList.add('show'), 300);
                }
            });
        });
    }); // ← закрытие forEach(selector)
}); // ← закрытие DOMContentLoaded


document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('/api/user/pricing');
        const pricingData = await response.json();
        renderPricingCards(pricingData);
    } catch (error) {
        console.error('Ошибка загрузки тарифов:', error);
    }
});

function renderPricingCards(data) {
    const container = document.getElementById('pricingContainer');
    const tariffs = {
        standard: data.standard,
        pro: data.pro,
        premium: data.premium
    };

    for (const [tariffName, tariffData] of Object.entries(tariffs)) {
        const card = document.createElement('a');
        card.href = `/subscribe/${tariffName}`;
        card.className = `pricing-card ${tariffName === 'pro' ? 'featured' : ''} slide-in`;

        const price = parseInt(tariffData.price);
        const saleActive = tariffData.sale === "True";
        const newPrice = parseInt(tariffData.new_price);

        card.innerHTML = `
            <h3>${tariffName.charAt(0).toUpperCase() + tariffName.slice(1)}</h3>
            <div class="price-container">
                ${saleActive ? `
                    <div class="price-discount">
                        <span class="old-price">₽${price}</span>
                        <span class="new-price">₽${newPrice}</span>
                        <span class="discount-badge">-${Math.round((1 - newPrice/price)*100)}%</span>
                    </div>
                ` : `<div class="price">₽${price}</div>`}
            </div>
            <ul>
                ${getTariffFeatures(tariffName)}
            </ul>
            <div class="btn">Выбрать</div>
        `;

        container.appendChild(card);
    }
}

function getTariffFeatures(tariffName) {
    const features = {
        standard: [
            'До 10 000 запросов',
            '5 источников',
            'Базовая аналитика'
        ],
        pro: [
            'До 50 000 запросов',
            '20 источников',
            'Расширенная аналитика',
            'Приоритетная поддержка'
        ],
        premium: [
            'Неограниченные запросы',
            '50+ источников',
            'Персональный менеджер',
            'Кастомные решения'
        ]
    };
    return features[tariffName].map(item => `<li>${item}</li>`).join('');
}