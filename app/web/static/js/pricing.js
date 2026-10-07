/* Карточки тарифов (главная страница и /tariffs). Цены берутся из БД через /api/user/pricing. */
(function () {
  'use strict';

  const container = document.getElementById('pricingContainer');
  if (!container) return;

  const TITLES = { standard: 'Standard', pro: 'Pro', premium: 'Premium' };
  const FEATURES = {
    standard: ['Поиск по всем площадкам', 'Скачивание роликов в MP4', 'Редактор клипов'],
    pro: ['Всё из Standard', 'Приоритетная обработка видео', 'Приоритетная поддержка'],
    premium: ['Всё из Pro', 'Персональный менеджер', 'Индивидуальные решения'],
  };
  const SUPPORT_EMAIL = 'support@parser.ru';
  const fmt = (n) => new Intl.NumberFormat('ru-RU').format(n);

  function card(key, tariff) {
    const price = Number(tariff.price) || 0;
    const newPrice = Number(tariff.new_price) || 0;
    const onSale = tariff.sale && newPrice > 0 && newPrice < price;
    const discount = onSale && price > 0 ? Math.round((1 - newPrice / price) * 100) : 0;
    const limit = tariff.token_in_day === null || tariff.token_in_day === undefined
      ? 'Скачивания без ограничений'
      : `${tariff.token_in_day} скачиваний в день`;
    const subject = encodeURIComponent(`Подключение тарифа ${TITLES[key] || key}`);
    const el = document.createElement('article');
    el.className = `price-card reveal visible${key === 'pro' ? ' featured' : ''}`;
    el.innerHTML = `
      ${key === 'pro' ? '<span class="badge">Популярный</span>' : discount ? `<span class="badge badge-success">−${discount}%</span>` : ''}
      <div class="price-name">${App.escapeHtml(TITLES[key] || key)}</div>
      <div class="price-value">
        <strong>${fmt(onSale ? newPrice : price)} ₽</strong>
        ${onSale ? `<span class="price-old">${fmt(price)} ₽</span>` : ''}
      </div>
      <ul class="price-list">${[limit, ...(FEATURES[key] || [])]
        .map((f) => `<li>${App.icon('check', 'icon-sm')}<span>${App.escapeHtml(f)}</span></li>`).join('')}</ul>
      <a class="btn ${key === 'pro' ? 'btn-primary' : ''} btn-block" href="mailto:${SUPPORT_EMAIL}?subject=${subject}">Подключить</a>`;
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
