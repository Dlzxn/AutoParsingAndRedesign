"""Настройки приложения. Все значения читаются из переменных окружения / файла .env."""
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
WEB_DIR = APP_DIR / "web"
# APP_ENV_FILE позволяет указать другой .env (пустое значение — не читать файл, используется в тестах)
ENV_FILE = os.environ.get("APP_ENV_FILE", str(BASE_DIR / ".env")) or None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # --- Общие ---
    environment: str = "development"  # development | production | test
    debug: bool = False
    log_level: str = "INFO"
    var_dir: Path = BASE_DIR / "var"

    # --- База данных ---
    database_url: str = ""  # пусто -> SQLite в var/app.db
    db_echo: bool = False

    # --- Авторизация ---
    session_cookie_name: str = "session"
    session_ttl_days: int = 30
    cookie_secure: bool = False  # включить в production за HTTPS
    auth_required: bool = True  # требовать вход для поиска, скачивания и редактора
    login_rate_limit: int = 10  # попыток входа в минуту с одного IP

    # --- Поиск ---
    search_cache_ttl: int = 600  # секунд
    search_timeout: float = 25.0
    search_rate_limit: int = 30  # запросов поиска в минуту на пользователя
    max_clip_duration: int = 180  # макс. длительность клипа в выдаче YouTube/VK (Shorts сейчас до 3 минут)
    youtube_api_key: str = ""
    imgur_client_id: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "AutoParsing/1.0"
    tumblr_api_keys: str = ""  # через запятую; несколько ключей = резерв при исчерпании лимита
    vk_access_token: str = ""  # если задан — поиск через VK API, иначе через Google + Chrome
    vk_search_timeout: float = 60.0
    vk_max_browsers: int = 2
    chrome_binary: str = ""

    # --- Медиа и редактор ---
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    ytdlp_proxy: str = ""
    ytdlp_js_runtimes: str = "deno,node"  # нужен для YouTube (deno или node должен быть установлен)
    max_upload_mb: int = 500
    max_source_duration: int = 15 * 60  # секунд
    download_timeout: int = 300
    render_workers: int = 2
    render_timeout_factor: float = 8.0  # таймаут рендера = длительность * фактор (не меньше 120 с)
    media_ttl_hours: int = 24
    font_path: Path = WEB_DIR / "static" / "fonts" / "InterDisplay-ExtraBold.ttf"
    emoji_font_path: str = ""  # пусто — поиск системного (Noto Color Emoji / Segoe UI Emoji)

    @property
    def tumblr_keys(self) -> list[str]:
        return [k.strip() for k in self.tumblr_api_keys.split(",") if k.strip()]

    @property
    def storage_dir(self) -> Path:
        return self.var_dir / "storage"

    @property
    def logs_dir(self) -> Path:
        return self.var_dir / "logs"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            url = self.database_url
            # Совместимость со старыми DSN вида postgresql://
            if url.startswith("postgresql://") or url.startswith("postgres://"):
                url = "postgresql+asyncpg://" + url.split("://", 1)[1]
            return url
        self.var_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{(self.var_dir / 'app.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
