from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Aspect = Literal["original", "9:16", "1:1", "4:5", "16:9"]
Fit = Literal["crop", "blur", "pad"]
Resolution = Literal["original", "480", "720", "1080"]
Quality = Literal["draft", "standard", "high"]
Position = Literal["top", "center", "bottom"]
Corner = Literal["top-left", "top-right", "bottom-left", "bottom-right", "center"]
TextSize = Literal["small", "medium", "large"]

MAX_TEXT_LENGTH = 300


class EditParams(BaseModel):
    """Параметры монтажа. Все поля необязательные — по умолчанию видео не меняется."""

    model_config = {"extra": "forbid"}

    # Время
    trim_start: float = Field(0.0, ge=0)
    trim_end: float | None = Field(None, gt=0)
    speed: float = Field(1.0, ge=0.25, le=4.0)

    # Кадр
    aspect: Aspect = "original"
    fit: Fit = "crop"
    resolution: Resolution = "original"
    rotate: Literal[0, 90, 180, 270] = 0
    flip_h: bool = False
    flip_v: bool = False

    # Цвет
    brightness: float = Field(0.0, ge=-0.5, le=0.5)
    contrast: float = Field(1.0, ge=0.5, le=2.0)
    saturation: float = Field(1.0, ge=0.0, le=3.0)
    grayscale: bool = False

    # Плавные переходы, секунды
    fade_in: float = Field(0.0, ge=0, le=5)
    fade_out: float = Field(0.0, ge=0, le=5)

    # Текст
    text: str = Field("", max_length=MAX_TEXT_LENGTH)
    text_position: Position = "bottom"
    text_size: TextSize = "medium"
    text_color: str = Field("#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    text_background: bool = True

    # Логотип / водяной знак (файл передаётся отдельно)
    logo_position: Corner = "top-right"
    logo_scale: int = Field(20, ge=5, le=60)  # % ширины кадра
    logo_opacity: float = Field(1.0, ge=0.1, le=1.0)

    # Звук
    volume: int = Field(100, ge=0, le=300)  # %
    mute: bool = False
    music_volume: int = Field(60, ge=0, le=300)  # % (файл музыки передаётся отдельно)
    music_replace: bool = False  # True — заменить оригинальный звук музыкой

    # Экспорт
    quality: Quality = "standard"

    @field_validator("text")
    @classmethod
    def _clean_text(cls, value: str) -> str:
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = "".join(ch for ch in value if ch == "\n" or ch.isprintable())
        return "\n".join(line.rstrip() for line in value.split("\n")).strip()

    @model_validator(mode="after")
    def _check_trim(self) -> "EditParams":
        if self.trim_end is not None and self.trim_end <= self.trim_start:
            raise ValueError("Конец фрагмента должен быть позже начала")
        return self


class SourceOut(BaseModel):
    id: str
    duration: float
    width: int
    height: int
    has_audio: bool
    size_bytes: int
    original_name: str | None = None
    origin_url: str | None = None
    preview_url: str


class JobOut(BaseModel):
    id: str
    source_id: str
    status: str
    progress: float
    error: str | None = None
    result_url: str | None = None
    download_url: str | None = None
    output_size: int | None = None
    output_duration: float | None = None
    params: dict
