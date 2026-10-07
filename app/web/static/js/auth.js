/* Формы входа и регистрации. */
(function () {
  'use strict';

  const form = document.getElementById('authForm');
  if (!form) return;
  const errorBox = document.getElementById('authError');
  const successBox = document.getElementById('authSuccess');
  const submit = form.querySelector('button[type="submit"]');
  const isRegistration = !!form.elements.passwordConfirm;
  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const PHONE_RE = /^\d{10,15}$/;

  function show(box, message) {
    errorBox.style.display = 'none';
    successBox.style.display = 'none';
    box.textContent = message;
    box.style.display = 'block';
  }

  function validate(identity, password) {
    if (!identity || !password) return 'Заполните все поля';
    if (!EMAIL_RE.test(identity) && !PHONE_RE.test(identity)) return 'Введите корректный email или телефон (10–15 цифр)';
    if (isRegistration) {
      if (password.length < 6) return 'Пароль должен содержать минимум 6 символов';
      if (password !== form.elements.passwordConfirm.value) return 'Пароли не совпадают';
    }
    return null;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const identity = form.elements.identity.value.trim();
    const password = form.elements.password.value;
    const problem = validate(identity, password);
    if (problem) return show(errorBox, problem);

    submit.disabled = true;
    const label = submit.textContent;
    submit.textContent = isRegistration ? 'Регистрация…' : 'Вход…';
    try {
      const response = await fetch(form.dataset.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ identity, password }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : 'Проверьте введённые данные';
        throw new Error(detail);
      }
      show(successBox, isRegistration ? 'Готово! Аккаунт создан.' : 'Вход выполнен!');
      location.href = form.dataset.next || '/';
    } catch (err) {
      show(errorBox, err.message === 'Failed to fetch' ? 'Нет связи с сервером' : err.message);
      submit.disabled = false;
      submit.textContent = label;
    }
  });
})();
