import pytest

from app.config import get_settings
from app.editor.textrender import (
    MAX_LINES,
    Measurer,
    find_emoji_font,
    font_size_for,
    render_text_image,
    tokenize,
    wrap_lines,
)

FONT = str(get_settings().font_path)


def test_tokenize_splits_emoji_and_drops_modifiers():
    tokens = tokenize("Привет 🔥👍🏽 мир❤️")
    assert [(t.text, t.emoji) for t in tokens] == [
        ("Привет ", False), ("🔥", True), ("👍", True), (" мир", False), ("❤", True),
    ]


def test_wrap_respects_pixel_width():
    measure = Measurer(FONT, 54)
    lines = wrap_lines("Очень длинная подпись для вертикального ролика с множеством слов", 400, measure)
    assert len(lines) > 1
    assert all(measure.width(line) <= 400 for line in lines)


def test_wrap_keeps_manual_breaks_and_breaks_long_words():
    measure = Measurer(FONT, 40)
    assert wrap_lines("Раз\nДва", 1000, measure) == ["Раз", "Два"]
    long_word = wrap_lines("А" * 80, 300, measure)
    assert len(long_word) > 1 and all(measure.width(line) <= 300 for line in long_word)


def test_wrap_limits_lines():
    lines = wrap_lines("слово " * 300, 300, Measurer(FONT, 40))
    assert len(lines) == MAX_LINES and lines[-1].endswith("…")


def test_font_size_scales_with_frame():
    assert font_size_for(1080, 1920, "medium") == 81
    assert font_size_for(1080, 1920, "large") > font_size_for(1080, 1920, "small")
    assert font_size_for(100, 100, "small") == 14


@pytest.mark.parametrize("background", [True, False])
@pytest.mark.parametrize("position", ["top", "center", "bottom"])
def test_render_places_text_in_expected_area(position, background):
    image = render_text_image("Привет, мир!", 720, 1280, position=position, size="medium", color="#ff0000",
                              background=background, font_path=FONT, emoji_font_path=None)
    assert image.size == (720, 1280) and image.mode == "RGBA"
    bbox = image.getbbox()
    assert bbox is not None
    center_y = (bbox[1] + bbox[3]) / 2
    expected = {"top": (0, 1280 * 0.3), "center": (1280 * 0.35, 1280 * 0.65), "bottom": (1280 * 0.7, 1280)}[position]
    assert expected[0] <= center_y <= expected[1]
    assert abs((bbox[0] + bbox[2]) / 2 - 360) < 10  # по центру
    red = sum(1 for r, g, b, a in image.get_flattened_data() if a > 200 and r > 200 and g < 60)
    assert red > 500  # цвет текста применён


def test_empty_text_gives_transparent_image():
    image = render_text_image("  \n ", 320, 240, position="top", size="small", color="#ffffff", background=True,
                              font_path=FONT, emoji_font_path=None)
    assert image.getbbox() is None


@pytest.mark.skipif(find_emoji_font() is None, reason="В системе нет цветного шрифта эмодзи")
def test_emoji_rendered_in_color():
    image = render_text_image("🔥", 400, 400, position="center", size="large", color="#ffffff", background=False,
                              font_path=FONT, emoji_font_path=find_emoji_font())
    colored = sum(1 for r, g, b, a in image.get_flattened_data() if a > 200 and r > 180 and g < 160 and b < 80)
    assert colored > 50  # оранжево-красные пиксели огня, а не белый квадрат


def test_missing_emoji_font_skips_emoji_gracefully():
    image = render_text_image("Текст 🔥", 400, 400, position="center", size="medium", color="#ffffff",
                              background=True, font_path=FONT, emoji_font_path=None)
    assert image.getbbox() is not None
