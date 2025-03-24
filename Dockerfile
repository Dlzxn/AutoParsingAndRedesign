FROM python:3.12

# Устанавливаем системные зависимости для PyGObject
RUN apt-get update && apt-get install -y \
    libgirepository1.0-dev \
    pkg-config \
    cmake \
    && rm -rf /var/lib/apt/lists/*

LABEL authors="alex"

# Копируем код в контейнер
COPY . .

# Обновляем pip
RUN pip install --upgrade pip

# Устанавливаем Python зависимости
RUN pip install -r requirements.txt

# Открываем порты
EXPOSE 0000

# Запускаем приложение
CMD ["python", "main.py"]
