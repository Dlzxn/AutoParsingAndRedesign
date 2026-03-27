document.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.admin-card');
  const modal = document.getElementById('confirmationModal');
  const modalText = document.getElementById('modalText');
  const confirmBtn = document.getElementById('confirmAction');
  const closeModal = document.querySelector('.close');

  const actions = {
    promocode: () => window.location.href = '/admin/promocode',
    users: () => window.location.href = '/admin/users',
    export: () => window.location.href = '/admin/export',
    pricing: () => window.location.href = '/admin/pricing',
    shutdown: () => window.location.href = '/admin/platforms',
    stats: () => window.location.href = '/admin/stats'
  };

  cards.forEach(card => {
    card.addEventListener('click', () => {
      const action = card.dataset.action;
      if (actions[action]) actions[action]();
    });
  });

  closeModal.addEventListener('click', () => {
    modal.style.display = 'none';
  });

  confirmBtn.addEventListener('click', () => {
    // Здесь должна быть логика закрытия платформы
    alert('Платформа успешно закрыта!');
    modal.style.display = 'none';
  });

  window.onclick = (event) => {
    if (event.target === modal) {
      modal.style.display = 'none';
    }
  };
});