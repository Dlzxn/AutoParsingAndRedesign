document.getElementById('loginForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const identity = document.getElementById('loginIdentity').value.trim();
    const password = document.getElementById('loginPassword').value.trim();
    const errorElement = document.getElementById('loginError');
    const successElement = document.getElementById('loginSuccess');
    const submitButton = this.querySelector('button[type="submit"]');

    errorElement.style.display = 'none';
    successElement.style.display = 'none';

    if (!identity || !password) {
        showError(errorElement, 'Все поля обязательны для заполнения');
        return;
    }

    if (!validateIdentity(identity)) {
        showError(errorElement, 'Введите корректный email или телефон');
        return;
    }

    submitButton.disabled = true;
    submitButton.textContent = 'Вход...';

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ identity, password })
        });

        let data;
        try {
            data = await response.json();
        } catch {
            throw new Error('Некорректный ответ сервера');
        }

        if (!response.ok) {
            throw new Error(data.message || 'Ошибка авторизации');
        }

        localStorage.setItem('authToken', data.token);
        showSuccess(successElement, 'Вход выполнен!');

        const redirectTimeout = setTimeout(() => {
            window.location.href = '/';
        }, 1500);

        window.addEventListener('beforeunload', () => clearTimeout(redirectTimeout));

    } catch (error) {
        showError(errorElement, error.message);
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = 'Войти';
    }
});

function validateIdentity(identity) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const phoneRegex = /^\d{10,15}$/;
    return emailRegex.test(identity) || phoneRegex.test(identity);
}

function showError(element, message) {
    element.textContent = message;
    element.style.display = 'block';
}

function showSuccess(element, message) {
    element.textContent = message;
    element.style.display = 'block';
}
