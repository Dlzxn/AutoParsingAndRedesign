document.getElementById('loginForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const identity = document.getElementById('loginIdentity').value;
    const password = document.getElementById('loginPassword').value;
    const errorElement = document.getElementById('loginError');
    const successElement = document.getElementById('loginSuccess');
    const submitButton = this.querySelector('button[type="submit"]');

    errorElement.style.display = 'none';
    successElement.style.display = 'none';

    // Валидация полей
    if(!identity || !password) {
        showError(errorElement, 'Все поля обязательны для заполнения');
        return;
    }

    if(!validateIdentity(identity)) {
        showError(errorElement, 'Введите корректный email или телефон');
        return;
    }

    submitButton.disabled = true;
    submitButton.textContent = 'Вход...';

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                identity,
                password
            })
        });

        const data = await response.json();

        if(!response.ok) {
            throw new Error(data.message || 'Ошибка авторизации');
        }

        // Сохранение токена и перенаправление
        localStorage.setItem('authToken', data.token);
        showSuccess(successElement, 'Вход выполнен!');

        setTimeout(() => {
            window.location.href = '/'; // Перенаправление на главную
        }, 1500);
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