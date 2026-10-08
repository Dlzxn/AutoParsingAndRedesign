/* Админка: тарифы. */
async function loadTariffs() {
  try {
    renderTariffs(await App.request('/api/admin/pricing'));
  } catch (err) {
    App.toast(err.message);
  }
}

function renderTariffs(tariffs) {
  const container = document.getElementById('tariffsContainer');
  const template = document.getElementById('tariffTemplate');
  container.innerHTML = '';
  for (const [key, data] of Object.entries(tariffs)) {
    const clone = template.content.cloneNode(true);
    const card = clone.querySelector('.tariff-card');
    card.dataset.key = key;
    clone.querySelector('.tariff-name').textContent = key.toUpperCase();
    const price = clone.querySelector('.price-input');
    const tokens = clone.querySelector('.tokens-input');
    const sale = clone.querySelector('.sale-toggle');
    const newPrice = clone.querySelector('.new-price-input');
    price.value = data.price;
    tokens.value = data.token_in_day ?? '';
    tokens.placeholder = 'без лимита';
    sale.checked = !!data.sale;
    newPrice.value = data.new_price;
    newPrice.disabled = !sale.checked;
    sale.addEventListener('change', () => { newPrice.disabled = !sale.checked; });
    container.appendChild(clone);
  }
}

async function saveAllTariffs() {
  const payload = {};
  document.querySelectorAll('.tariff-card').forEach((card) => {
    const tokens = card.querySelector('.tokens-input').value;
    payload[card.dataset.key] = {
      price: Number(card.querySelector('.price-input').value) || 0,
      token_in_day: tokens === '' ? null : Number(tokens),
      sale: card.querySelector('.sale-toggle').checked,
      new_price: Number(card.querySelector('.new-price-input').value) || 0,
    };
  });
  try {
    renderTariffs(await App.request('/api/admin/pricing', { method: 'PUT', json: payload }));
    App.toast('Тарифы сохранены', 'success', 2500);
  } catch (err) {
    App.toast(err.message);
  }
}

document.addEventListener('DOMContentLoaded', loadTariffs);
