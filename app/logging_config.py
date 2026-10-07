import logging
import logging.config

from app.config import Settings


def setup_logging(settings: Settings) -> None:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {"format": "%(asctime)s %(levelname)-7s %(name)s: %(message)s"},
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "default"},
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "default",
                    "filename": str(settings.logs_dir / "app.log"),
                    "maxBytes": 10 * 1024 * 1024,
                    "backupCount": 5,
                    "encoding": "utf-8",
                },
            },
            "root": {"level": settings.log_level, "handlers": ["console", "file"]},
            "loggers": {
                "uvicorn.access": {"level": "WARNING"},
                "sqlalchemy.engine": {"level": "INFO" if settings.db_echo else "WARNING"},
                "selenium": {"level": "WARNING"},
                "urllib3": {"level": "WARNING"},
            },
        }
    )
