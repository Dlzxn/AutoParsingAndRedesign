/* Карточки тарифов (главная страница и /tariffs). Цены берутся из БД через /api/user/pricing. */
(function () {
  'use strict';

  const container = document.getElementById('pricingContainer');
  if (!container) return;

  const TITLES = { standard: 'Standard', pro: 'Pro', premium: 'Premium' };
  const FEATURES = {
    standard: ['Безлимитный поиск по платформам', 'Скачивание роликов', 'Редактор клипов'],
    pro: ['Всё из Standard', 'Приоритетная обработка видео', 'Приоритетная поддержка'],
    premium: ['Всё из Pro', 'Персональный менеджер', 'Индивидуальные решения'],
  };
  const SUPPORT_EMAIL = 'support@parser.ru';

  function card(key, tariff) {
    const price = Number(tariff.price) || 0;
    const newPrice = Number(tariff.new_price) || 0;
    const onSale = tariff.sale && newPrice > 0 && newPrice < price;
    const discount = onSale && price > 0 ? Math.round((1 - newPrice / price) * 100) : 0;
    const limit = tariff.token_in_day === null || tariff.token_in_day === undefined
      ? 'Без ограничений по скачиваниям'
      : `${tariff.token_in_day} скачиваний в день`;
    const subject = encodeURIComponent(`Подключение тарифа ${TITLES[key] || key}`);
    const el = document.createElement('a');
    el.href = `mailto:${SUPPORT_EMAIL}?subject=${subject}`;
    el.className = `pricing-card ${key === 'pro' ? 'featured' : ''} slide-in`;
    el.innerHTML = `
      <h3>${App.escapeHtml(TITLES[key] || key)}</h3>
      <div class="price-container">
        ${onSale ? `
          <div class="price-discount">
            <span class="old-price">₽${price}</span>
            <span class="new-price">₽${newPrice}</span>
            ${discount ? `<span class="discount-badge">-${discount}%</span>` : ''}
          </div>` : `<div class="price">₽${price}</div>`}
      </div>
      <ul>${[limit, ...(FEATURES[key] || [])].map((f) => `<li>${App.escapeHtml(f)}</li>`).join('')}</ul>
      <div class="btn">Подключить</div>`;
    return el;
  }

  App.request('/api/user/pricing', { redirectOn401: false })
    .then((data) => {
      Object.entries(data)
        .filter(([key]) => key !== 'free')
        .forEach(([key, tariff]) => container.appendChild(card(key, tariff)));
    })
    .catch((err) => console.error('Не удалось загрузить тарифы:', err));
})();
