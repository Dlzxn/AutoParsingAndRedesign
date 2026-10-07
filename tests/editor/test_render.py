"""Рендер реальных видео через ffmpeg: каждая функция редактора и их комбинации."""
import shutil
import threading
from pathlib import Path

import pytest

from app.config import get_settings
from app.editor.pipeline import FONT_FILE, SUBTITLES_FILE, TEXT_IMAGE, RenderInputs, plan_render
from app.editor.schemas import EditParams
from app.editor.textrender import find_emoji_font, render_text_image
from app.media.ffmpeg import MediaError, probe, run_ffmpeg
from tests.conftest import requires_ffmpeg

pytestmark = [requires_ffmpeg, pytest.mark.ffmpeg]


def render(media_dir: Path, workdir: Path, source: str, params: dict, *, logo=False, music=False, subtitles=False):
    """Повторяет то, что делает воркер очереди: готовит каталог задачи и запускает ffmpeg."""
    info = probe(media_dir / source)
    if logo:
        shutil.copy(media_dir / "logo.png", workdir / "logo.png")
    if music:
        shutil.copy(media_dir / "music.mp3", workdir / "music.mp3")
    if subtitles:
        shutil.copy(media_dir / "subs.srt", workdir / SUBTITLES_FILE)
    inputs = RenderInputs(
        source=str(media_dir / source),
        output="out.mp4",
        logo="logo.png" if logo else None,
        music="music.mp3" if music else None,
        subtitles=subtitles,
        text_image=bool(params.get("text")),
    )
    edit = EditParams(**params)
    plan = plan_render(edit, info, inputs)
    if edit.text:
        render_text_image(edit.text, plan.width, plan.height, position=edit.text_position, size=edit.text_size,
                          color=edit.text_color, background=edit.text_background,
                          font_path=str(get_settings().font_path),
                          emoji_font_path=find_emoji_font()).save(workdir / TEXT_IMAGE)
    if plan.needs_font:
        shutil.copy(get_settings().font_path, workdir / FONT_FILE)
    progress: list[float] = []
    run_ffmpeg(plan.args, expected_duration=plan.output_duration, on_progress=progress.append, cwd=workdir, timeout=120)
    result = probe(workdir / "out.mp4")
    return plan, result, progress


def assert_matches(plan, result, tolerance=0.15):
    assert result.has_video and result.has_audio  # звуковая дорожка есть всегда
    assert (result.width, result.height) == (plan.width, plan.height)
    assert result.duration == pytest.approx(plan.output_duration, abs=tolerance)


SCENARIOS = {
    "без изменений": ({}, {}),
    "обрезка": ({"trim_start": 1, "trim_end": 3}, {}),
    "ускорение 2x": ({"speed": 2}, {}),
    "замедление 0.5x": ({"speed": 0.5, "trim_end": 2}, {}),
    "максимум 4x": ({"speed": 4}, {}),
    "минимум 0.25x": ({"speed": 0.25, "trim_end": 1}, {}),
    "9:16 обрезка": ({"aspect": "9:16", "fit": "crop"}, {}),
    "9:16 размытый фон 720p": ({"aspect": "9:16", "fit": "blur", "resolution": "720"}, {}),
    "1:1 поля": ({"aspect": "1:1", "fit": "pad"}, {}),
    "4:5 1080p": ({"aspect": "4:5", "resolution": "1080"}, {}),
    "поворот 90": ({"rotate": 90}, {}),
    "поворот 180 и отражения": ({"rotate": 180, "flip_h": True, "flip_v": True}, {}),
    "цвет": ({"brightness": 0.2, "contrast": 1.5, "saturation": 2}, {}),
    "чёрно-белое": ({"grayscale": True}, {}),
    "переходы": ({"fade_in": 1, "fade_out": 1}, {}),
    "текст сверху с подложкой": ({"text": "Привет, мир! 100% «кавычки» 'одинарные' : \\ ;", "text_position": "top"}, {}),
    "длинный текст без подложки": ({"text": "Очень длинный текст " * 10, "text_background": False, "text_size": "large"}, {}),
    "текст с эмодзи": ({"text": "Огонь 🔥🚀 и смех 😂", "text_position": "center"}, {}),
    "логотип": ({"logo_position": "bottom-left", "logo_scale": 30, "logo_opacity": 0.5}, {"logo": True}),
    "музыка поверх": ({"music_volume": 150, "volume": 50}, {"music": True}),
    "музыка вместо звука": ({"music_replace": True}, {"music": True}),
    "без звука": ({"mute": True}, {}),
    "громкость 300%": ({"volume": 300}, {}),
    "субтитры": ({}, {"subtitles": True}),
    "качество черновик": ({"quality": "draft"}, {}),
    "качество максимум": ({"quality": "high", "trim_end": 1.5}, {}),
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_landscape_scenarios(name, media_dir, tmp_path):
    params, assets = SCENARIOS[name]
    plan, result, progress = render(media_dir, tmp_path, "landscape.mp4", params, **assets)
    assert_matches(plan, result)
    assert progress and progress[-1] == 1.0


def test_everything_at_once(media_dir, tmp_path):
    params = {
        "trim_start": 0.5, "trim_end": 3.5, "speed": 1.5, "aspect": "9:16", "fit": "blur", "resolution": "720",
        "rotate": 0, "flip_h": True, "brightness": 0.05, "contrast": 1.1, "saturation": 1.2, "fade_in": 0.3,
        "fade_out": 0.3, "text": "Подпишись!\nВторая строка", "text_position": "center", "logo_position": "top-right",
        "volume": 120, "music_volume": 70, "quality": "draft",
    }
    plan, result, _ = render(media_dir, tmp_path, "landscape.mp4", params, logo=True, music=True, subtitles=True)
    assert (plan.width, plan.height) == (720, 1280)
    assert_matches(plan, result)


@pytest.mark.parametrize(
    "params",
    [{}, {"aspect": "16:9", "fit": "blur"}, {"rotate": 270}, {"music_replace": True}],
    ids=["как есть", "16:9 размытый фон", "поворот 270", "только музыка"],
)
def test_vertical_source_without_audio(media_dir, tmp_path, params):
    plan, result, _ = render(media_dir, tmp_path, "vertical_silent.mp4", params, music="music_replace" in params)
    assert_matches(plan, result)


def test_text_is_actually_drawn(media_dir, tmp_path):
    """Кадр с текстом должен отличаться от кадра без текста (drawtext действительно сработал)."""
    import subprocess

    def frame(directory: Path, params: dict) -> bytes:
        directory.mkdir()
        render(media_dir, directory, "landscape.mp4", {"trim_end": 1, **params})
        return subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(directory / "out.mp4"), "-frames:v", "1", "-f", "rawvideo",
             "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout

    plain = frame(tmp_path / "plain", {})
    with_text = frame(tmp_path / "text", {"text": "ТЕКСТ", "text_position": "center", "text_size": "large"})
    assert len(plain) == len(with_text)
    differing = sum(1 for a, b in zip(plain, with_text) if abs(a - b) > 40)
    assert differing > len(plain) * 0.01


def test_timeout_kills_ffmpeg(media_dir, tmp_path):
    args = ["-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=60", "-c:v", "libx264", "-preset", "veryslow",
            "-t", "600", str(tmp_path / "slow.mp4")]
    with pytest.raises(MediaError, match="слишком много времени"):
        run_ffmpeg(args, timeout=1)


def test_cancel_stops_ffmpeg(media_dir, tmp_path):
    cancel = threading.Event()
    timer = threading.Timer(0.5, cancel.set)
    timer.start()
    args = ["-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=60", "-c:v", "libx264", "-preset", "veryslow",
            "-t", "600", str(tmp_path / "slow.mp4")]
    with pytest.raises(MediaError, match="отменена"):
        run_ffmpeg(args, timeout=60, cancel=cancel)


def test_ffmpeg_error_is_reported(tmp_path):
    with pytest.raises(MediaError, match="Не удалось обработать"):
        run_ffmpeg(["-i", str(tmp_path / "missing.mp4"), str(tmp_path / "out.mp4")])
