/* Шапка: выпадающее меню профиля. Данные пользователя рендерятся сервером в шаблоне. */
document.addEventListener('DOMContentLoaded', () => {
  const profile = document.getElementById('profileDropdown');
  if (!profile) return;
  const menu = profile.querySelector('.dropdown-menu');

  profile.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.classList.toggle('show');
  });
  document.addEventListener('click', () => menu.classList.remove('show'));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') menu.classList.remove('show');
  });
});
