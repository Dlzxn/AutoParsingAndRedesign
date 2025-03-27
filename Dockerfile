# Используем официальный Python образ
FROM python:3.13-slim

# Устанавливаем зависимости для работы с Chromium
RUN apt-get update && \
    apt-get install -y \
    wget \
    curl \
    unzip \
    ca-certificates \
    libx11-dev \
    libx265-dev \
    libgtk-3-dev \
    libnss3-dev \
    libxss1 \
    libasound2 \
    fonts-liberation \
    libappindicator3-1 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libnspr4 \
    libgdk-pixbuf2.0-0 \
    libxrandr2 \
    xdg-utils \
    libvulkan1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем meson для сборки
RUN apt-get update && apt-get install -y meson

# Скачать и установить Chromium
RUN CHROME_VERSION=113.0.5672.93 && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb

# Установим ChromeDriver для работы с Selenium
RUN LATEST_CHROMEDRIVER=$(curl -sSL https://chromedriver.storage.googleapis.com/LATEST_RELEASE) && \
    wget https://chromedriver.storage.googleapis.com/$LATEST_CHROMEDRIVER/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && \
    mv chromedriver /usr/local/bin/ && \
    rm chromedriver_linux64.zip

# Устанавливаем зависимости для работы с PostgreSQL
RUN apt-get update && apt-get install -y \
    libpq-dev \
    postgresql-client

# Устанавливаем зависимости для Python
WORKDIR /

COPY requirements.txt .
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Uvicorn и Gunicorn
RUN pip install uvicorn

# Открываем порт 8000 для доступа к приложению
EXPOSE 8000

# Запускаем Uvicorn через Gunicorn, слушая все интерфейсы на порту 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]