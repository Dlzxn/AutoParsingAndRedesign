/* Главная админ-панели: переходы по разделам. */
document.addEventListener('DOMContentLoaded', () => {
  const routes = {
    promocode: '/admin/promocode',
    users: '/admin/users',
    export: '/admin/export',
    pricing: '/admin/pricing',
    shutdown: '/admin/platforms',
    stats: '/admin/stats',
  };
  document.querySelectorAll('.admin-card').forEach((card) => {
    card.setAttribute('role', 'link');
    card.tabIndex = 0;
    const go = () => { if (routes[card.dataset.action]) location.href = routes[card.dataset.action]; };
    card.addEventListener('click', go);
    card.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
  });
});
