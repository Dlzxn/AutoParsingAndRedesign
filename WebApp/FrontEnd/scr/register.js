document.getElementById('registerForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const identity = document.getElementById('regIdentity').value;
    const password = document.getElementById('regPassword').value;
    const confirmPassword = document.getElementById('regConfirmPassword').value;
    const errorElement = document.getElementById('regError');
    const successElement = document.getElementById('regSuccess');
    const submitButton = this.querySelector('button[type="submit"]');

    errorElement.style.display = 'none';
    successElement.style.display = 'none';

    // Валидация полей
    if(!identity || !password || !confirmPassword) {
        showError(errorElement, 'Все поля обязательны для заполнения');
        return;
    }

    if(password !== confirmPassword) {
        showError(errorElement, 'Пароли не совпадают');
        return;
    }

    if(password.length < 6) {
        showError(errorElement, 'Пароль должен содержать минимум 6 символов');
        return;
    }

    if(!validateIdentity(identity)) {
        showError(errorElement, 'Введите корректный email или телефон');
        return;
    }

    // Блокировка кнопки
    submitButton.disabled = true;
    submitButton.textContent = 'Регистрация...';

    try {
        const response = await fetch('/api/registration', {
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
            throw new Error(data.message || 'Ошибка регистрации');
        }

        showSuccess(successElement, 'Регистрация успешна!');
        setTimeout(() => {
            window.location.href = '/'; // Перенаправление на главную
        }, 1500);
    } catch (error) {
        showError(errorElement, error.message);
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = 'Зарегистрироваться';
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