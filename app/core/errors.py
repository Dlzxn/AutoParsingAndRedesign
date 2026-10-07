"""Понятные пользователю сообщения об ошибках валидации (pydantic отдаёт их на английском)."""

FIELD_LABELS = {
    "trim_start": "Начало фрагмента",
    "trim_end": "Конец фрагмента",
    "speed": "Скорость",
    "aspect": "Формат кадра",
    "fit": "Заполнение кадра",
    "resolution": "Разрешение",
    "rotate": "Поворот",
    "brightness": "Яркость",
    "contrast": "Контраст",
    "saturation": "Насыщенность",
    "fade_in": "Плавное появление",
    "fade_out": "Плавное затухание",
    "text": "Текст",
    "text_color": "Цвет текста",
    "logo_scale": "Размер логотипа",
    "logo_opacity": "Непрозрачность логотипа",
    "volume": "Громкость",
    "music_volume": "Громкость музыки",
    "quality": "Качество",
    "identity": "Логин",
    "password": "Пароль",
    "email": "Email",
    "q": "Запрос",
    "url": "Ссылка",
}


def _num(value) -> str:
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def _message(error: dict) -> str:
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}
    if kind in ("less_than_equal", "less_than"):
        return f"должно быть не больше {_num(ctx.get('le', ctx.get('lt')))}"
    if kind in ("greater_than_equal", "greater_than"):
        return f"должно быть не меньше {_num(ctx.get('ge', ctx.get('gt')))}"
    if kind == "string_too_long":
        return f"не длиннее {ctx.get('max_length')} символов"
    if kind == "string_too_short":
        return f"не короче {ctx.get('min_length')} символов"
    if kind == "missing":
        return "обязательное поле"
    if kind in ("literal_error", "enum"):
        return "недопустимое значение"
    if kind == "string_pattern_mismatch":
        return "неверный формат"
    if kind in ("float_parsing", "int_parsing", "float_type", "int_type", "bool_parsing"):
        return "неверное число"
    if kind == "extra_forbidden":
        return "неизвестный параметр"
    if kind == "value_error":
        return str(error.get("msg", "")).removeprefix("Value error, ")
    return str(error.get("msg", "некорректное значение"))


def humanize_validation_error(error: dict) -> str:
    loc = [str(p) for p in error.get("loc", ()) if p not in ("body", "query", "path", "form")]
    message = _message(error)
    if error.get("type") == "value_error" or not loc:
        return message
    field = loc[-1]
    return f"{FIELD_LABELS.get(field, field)}: {message}"
