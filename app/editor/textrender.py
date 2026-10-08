"""Отрисовка текста для видео в прозрачный PNG (Pillow).

Почему не drawtext ffmpeg: он не умеет подставлять второй шрифт, поэтому эмодзи превращались в квадраты,
и не рисует скруглённые подложки. Здесь текст рисуется основным шрифтом, эмодзи — цветным
эмодзи-шрифтом; алгоритм переноса строк совпадает с превью в браузере (static/js/clip-editor.js).
"""
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

TEXT_SCALE = {"small": 0.055, "medium": 0.075, "large": 0.10}
LINE_HEIGHT = 1.3
MAX_WIDTH = 0.9
MAX_LINES = 6
EMOJI_ADVANCE = 1.2  # ширина эмодзи в долях кегля (так же считает превью)

# Символы эмодзи (основные блоки) и служебные символы, которые не рисуются отдельно
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\u2190-\u21FF\u3030\u303D\u3297\u3299"
    "\u00A9\u00AE\u203C\u2049\u2122\u2139]"
)
_INVISIBLE = {"\u200d", "\ufe0f", "\ufe0e"} | {chr(c) for c in range(0x1F3FB, 0x1F400)}

EMOJI_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    "C:/Windows/Fonts/seguiemj.ttf",
    "/System/Library/Fonts/Apple Color Emoji.ttc",
)


@dataclass(frozen=True)
class Token:
    text: str
    emoji: bool


def is_emoji(ch: str) -> bool:
    return bool(_EMOJI_RE.match(ch))


def tokenize(line: str) -> list[Token]:
    """Делит строку на куски обычного текста и отдельные эмодзи."""
    tokens: list[Token] = []
    buf = ""
    for ch in line:
        if ch in _INVISIBLE:
            continue
        if is_emoji(ch):
            if buf:
                tokens.append(Token(buf, False))
                buf = ""
            tokens.append(Token(ch, True))
        else:
            buf += ch
    if buf:
        tokens.append(Token(buf, False))
    return tokens


def find_emoji_font(configured: str = "") -> str | None:
    for candidate in ((configured,) if configured else ()) + EMOJI_FONT_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


@lru_cache(maxsize=32)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


@lru_cache(maxsize=4)
def _emoji_font(path: str) -> tuple[ImageFont.FreeTypeFont, int]:
    """Шрифт эмодзи. Битмап-шрифты (Noto Color Emoji) открываются только в размере 109."""
    try:
        return ImageFont.truetype(path, 128), 128
    except OSError:
        return ImageFont.truetype(path, 109), 109


class Measurer:
    def __init__(self, font_path: str, size: int) -> None:
        self.font = _font(font_path, size)
        self.size = size

    def width(self, text: str) -> float:
        total = 0.0
        for token in tokenize(text):
            total += self.size * EMOJI_ADVANCE if token.emoji else self.font.getlength(token.text)
        return total


def wrap_lines(text: str, max_width: float, measure: Measurer) -> list[str]:
    """Перенос по словам с учётом реальной ширины глифов; длинные слова режутся по символам."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = ""
        for word in words:
            candidate = f"{current} {word}" if current else word
            if measure.width(candidate) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = ""
            for ch in word:  # слово длиннее строки
                if measure.width(current + ch) > max_width and current:
                    lines.append(current)
                    current = ""
                current += ch
        lines.append(current)
    while lines and not lines[-1]:
        lines.pop()
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES]
        last = lines[-1]
        while last and measure.width(last + "…") > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines


def font_size_for(frame_w: int, frame_h: int, size: str) -> int:
    return max(14, int(min(frame_w, frame_h) * TEXT_SCALE[size]))


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _paste_emoji(canvas: Image.Image, ch: str, x: float, y_top: float, size: int, emoji_path: str | None) -> None:
    if not emoji_path:
        return
    try:
        font, native = _emoji_font(emoji_path)
        glyph = Image.new("RGBA", (int(native * 1.6), int(native * 1.6)), (0, 0, 0, 0))
        ImageDraw.Draw(glyph).text((native * 0.1, native * 0.1), ch, font=font, embedded_color=True)
        bbox = glyph.getbbox()
        if not bbox:
            return
        glyph = glyph.crop(bbox)
        target = int(size * 1.05)
        scale = target / max(glyph.width, glyph.height)
        glyph = glyph.resize((max(1, int(glyph.width * scale)), max(1, int(glyph.height * scale))), Image.LANCZOS)
        offset_x = (size * EMOJI_ADVANCE - glyph.width) / 2
        offset_y = (size * LINE_HEIGHT - glyph.height) / 2
        canvas.alpha_composite(glyph, (int(x + offset_x), int(y_top + offset_y)))
    except OSError as exc:  # повреждённый/неподдерживаемый шрифт эмодзи — просто пропускаем эмодзи
        log.warning("Emoji render failed: %s", exc)


def render_text_image(
    text: str,
    frame_w: int,
    frame_h: int,
    *,
    position: str,
    size: str,
    color: str,
    background: bool,
    font_path: str,
    emoji_font_path: str | None,
) -> Image.Image:
    """Прозрачное изображение размером с кадр с отрисованным текстом."""
    canvas = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    font_size = font_size_for(frame_w, frame_h, size)
    measure = Measurer(font_path, font_size)
    lines = wrap_lines(text, frame_w * MAX_WIDTH, measure)
    if not lines:
        return canvas

    line_h = font_size * LINE_HEIGHT
    block = line_h * len(lines)
    if position == "top":
        y0 = frame_h * 0.08
    elif position == "center":
        y0 = (frame_h - block) / 2
    else:
        y0 = frame_h * 0.88 - block

    rgb = _hex_to_rgb(color)
    draw = ImageDraw.Draw(canvas)
    font = measure.font
    ascent, descent = font.getmetrics()
    pad_x, pad_y, radius = font_size * 0.3, font_size * 0.06, font_size * 0.28
    stroke = max(2, font_size // 14)

    for i, line in enumerate(lines):
        if not line.strip():
            continue
        width = measure.width(line)
        x = (frame_w - width) / 2
        top = y0 + i * line_h
        if background:
            draw.rounded_rectangle(
                (x - pad_x, top - pad_y, x + width + pad_x, top + line_h + pad_y),
                radius=radius,
                fill=(0, 0, 0, 150),
            )
        text_y = top + (line_h - (ascent + descent)) / 2
        cursor = x
        for token in tokenize(line):
            if token.emoji:
                _paste_emoji(canvas, token.text, cursor, top, font_size, emoji_font_path)
                cursor += font_size * EMOJI_ADVANCE
                continue
            if not background:
                draw.text((cursor + stroke, text_y + stroke * 1.5), token.text, font=font, fill=(0, 0, 0, 110))
            draw.text(
                (cursor, text_y),
                token.text,
                font=font,
                fill=rgb + (255,),
                stroke_width=0 if background else stroke,
                stroke_fill=(0, 0, 0, 230),
            )
            cursor += font.getlength(token.text)
    return canvas
