let currentTariffs = {};

async function loadTariffs() {
  try {
    const response = await fetch('/api/pricing');
    if (!response.ok) throw new Error('Ошибка загрузки');

    currentTariffs = await response.json();
    renderTariffs();
  } catch (error) {
    alert(error.message);
  }
}

function renderTariffs() {
  const container = document.getElementById('tariffsContainer');
  container.innerHTML = '';

  const template = document.getElementById('tariffTemplate');

  for (const [tariffName, data] of Object.entries(currentTariffs)) {
    const clone = template.content.cloneNode(true);

    clone.querySelector('.tariff-name').textContent = tariffName.toUpperCase();
    const inputs = {
      price: clone.querySelector('.price-input'),
      tokens: clone.querySelector('.tokens-input'),
      saleToggle: clone.querySelector('.sale-toggle'),
      newPrice: clone.querySelector('.new-price-input')
    };

    inputs.price.value = data.price;
    inputs.tokens.value = data.token_in_day;
    inputs.saleToggle.checked = data.sale === "True";
    inputs.newPrice.value = data.new_price;

    // Обработчики изменений
    inputs.saleToggle.addEventListener('change', () => {
      inputs.newPrice.disabled = !inputs.saleToggle.checked;
    });

    inputs.newPrice.disabled = !inputs.saleToggle.checked;

    container.appendChild(clone);
  }
}

async function saveAllTariffs() {
  const updatedTariffs = {};
  const cards = document.querySelectorAll('.tariff-card');

  cards.forEach(card => {
    const name = card.querySelector('.tariff-name').textContent.toLowerCase();
    updatedTariffs[name] = {
      price: parseInt(card.querySelector('.price-input').value),
      token_in_day: parseInt(card.querySelector('.tokens-input').value),
      sale: card.querySelector('.sale-toggle').checked ? "True" : "False",
      new_price: card.querySelector('.new-price-input').value || "0"
    };
  });

  try {
    const response = await fetch('/api/pricing', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedTariffs)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Ошибка сохранения');
    }

    alert('Настройки успешно сохранены!');
    loadTariffs();
  } catch (error) {
    alert(error.message);
  }
}

// Инициализация
document.addEventListener('DOMContentLoaded', loadTariffs);