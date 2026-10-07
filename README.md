# AutoParsing — поиск коротких видео и редактор клипов

Веб-сервис для авторов контента:

- **поиск коротких роликов** по тегу: VK Клипы, YouTube Shorts, Coub, Reddit, Imgur; текстовые посты Tumblr;
- **без повторов**: просмотренные и скачанные ролики больше не попадают в выдачу пользователя;
- **скачивание** роликов в MP4 со звуком;
- **редактор клипов** в браузере: обрезка, скорость, форматы 9:16 / 1:1 / 4:5 / 16:9 (обрезка, размытый фон или поля), поворот и отражение, яркость/контраст/насыщенность, текст на кириллице, логотип, субтитры .srt, фоновая музыка, плавные переходы, выбор качества. Превью настроек — сразу в браузере, рендер — в фоне через ffmpeg;
- **админ-панель**: пользователи, тарифы, промокоды, включение/отключение платформ, статистика, выгрузка в CSV.

## Стек

FastAPI · SQLAlchemy 2 (async) · Alembic · PostgreSQL (SQLite для разработки) · ffmpeg · Pillow · yt-dlp · aiohttp · Jinja2 + чистый JS (без сборки).

## Структура

```
app/
  main.py            сборка приложения, обработчики ошибок, healthcheck
  config.py          настройки (переменные окружения / .env)
  auth/              регистрация, вход, сессии в БД
  search/            сервис поиска (кэш, таймауты) и провайдеры платформ
  media/             ffmpeg/ffprobe, скачивание через yt-dlp, файловое хранилище
  editor/            параметры монтажа, сборка команды ffmpeg, рендер текста (Pillow), очередь, API
  history/           история просмотренных клипов, скачивание
  admin/             админ-панель и её API
  catalog/           справочники: платформы, тарифы
  db/                модели, подключение, начальные данные
  web/               шаблоны, статика, дизайн-система (static/css/app.css), иконки
migrations/          миграции Alembic
tests/               тесты (pytest)
```

## Быстрый старт (разработка)

Нужны Python 3.12+, ffmpeg (вместе с ffprobe) и Node.js или Deno (yt-dlp использует их для YouTube).
Для цветных эмодзи в подписях нужен системный шрифт эмодзи (Windows — есть по умолчанию; Linux — пакет
`fonts-noto-color-emoji`; в Docker-образе ставится автоматически). Без него эмодзи просто не рисуются.

```bash
python -m venv .venv
.venv/Scripts/activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # заполнить ключи платформ
python -m app.cli create-admin admin@example.com 'сложный-пароль'
uvicorn app.asgi:app --reload
```

Без `DATABASE_URL` используется SQLite (`var/app.db`). Миграции применяются автоматически при старте.

## Продакшен (Docker)

```bash
cp .env.example .env            # ENVIRONMENT=production, COOKIE_SECURE=true, ключи, POSTGRES_PASSWORD
docker compose up -d --build
docker compose exec app python -m app.cli create-admin admin@example.com 'сложный-пароль'
```

Приложение слушает `127.0.0.1:8000`; перед ним нужен reverse proxy с HTTPS (nginx, Caddy) — с лимитом на размер
загрузки не меньше `MAX_UPLOAD_MB` (`client_max_body_size 600m;` для nginx) и таймаутом чтения ≥ 120 с
(скачивание длинных роликов по ссылке).

Важно: приложение запускается **с одним воркером uvicorn** — очередь рендера живёт в процессе,
а сам рендер (ffmpeg) и так использует все ядра. Параллельность рендера задаёт `RENDER_WORKERS`.

Проверка состояния: `GET /healthz` (БД и ffmpeg).

## Перенос данных со старой версии

Старая версия хранила пароли открытым текстом, историю клипов — в `Data/clips_history.json`,
тарифы и статусы платформ — в JSON-файлах. Чтобы перенести всё в БД:

1. Укажите в `.env` `DATABASE_URL` старой базы PostgreSQL (сделайте резервную копию!).
2. Положите в один каталог `clips_history.json`, `tarifs.json`, `platforms.json` из старой версии.
3. Выполните:
   ```bash
   python -m app.cli import-legacy путь/к/каталогу
   ```
   Команда применит миграции (существующие таблицы `users` и `promo` сохраняются), захеширует все пароли
   и перенесёт историю, тарифы и статусы платформ. Повторный запуск безопасен.

Пароли старых пользователей продолжают работать — они также автоматически хешируются при первом входе.

## Ключи платформ

| Переменная | Где получить |
|---|---|
| `YOUTUBE_API_KEY` | Google Cloud Console → YouTube Data API v3 |
| `IMGUR_CLIENT_ID` | https://api.imgur.com/oauth2/addclient |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | https://www.reddit.com/prefs/apps (тип script) |
| `TUMBLR_API_KEYS` | https://www.tumblr.com/oauth/apps (consumer key; можно несколько через запятую) |
| `VK_ACCESS_TOKEN` | пользовательский токен VK с доступом к видео (VK ID) |

**VK:** без `VK_ACCESS_TOKEN` поиск идёт через Google и headless-Chrome — Google часто отвечает капчей,
поэтому для стабильной работы нужен токен VK API.

## Тесты

```bash
pytest                    # все тесты (~3 минуты, включая реальный рендер через ffmpeg)
pytest -m "not ffmpeg and not live"   # быстрые тесты без рендера (~40 с)
pytest -m live            # проверка реальных API платформ (нужен .env с ключами)
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/test_db pytest   # на PostgreSQL
```

`TEST_DATABASE_URL` — отдельная пустая база: она очищается перед каждым тестом.
