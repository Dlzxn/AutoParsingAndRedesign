"""Unit-тесты сборки команды ffmpeg (без запуска ffmpeg)."""
import math

import pytest
from pydantic import ValidationError

from app.editor.pipeline import (
    TEXT_IMAGE,
    RenderInputs,
    atempo_chain,
    output_size,
    plan_render,
)
from app.editor.schemas import EditParams
from app.media.ffmpeg import MediaError, MediaInfo

LANDSCAPE = MediaInfo(duration=10.0, width=1920, height=1080, has_audio=True, has_video=True, fps=30.0)
SILENT_VERTICAL = MediaInfo(duration=6.0, width=720, height=1280, has_audio=False, has_video=True, fps=60.0)
INPUTS = RenderInputs(source="/abs/source.mp4", output="output.mp4")


def P(**kwargs) -> EditParams:
    return EditParams(**kwargs)


def graph(plan) -> str:
    return plan.args[plan.args.index("-filter_complex") + 1]


def arg(plan, name: str) -> str:
    return plan.args[plan.args.index(name) + 1]


# ---------- Параметры ----------

def test_defaults_do_not_change_video():
    plan = plan_render(P(), LANDSCAPE, INPUTS)
    assert (plan.width, plan.height) == (1920, 1080)
    assert plan.output_duration == pytest.approx(10.0)
    assert "[0:v]null[vpre]" in graph(plan)
    assert "[vpre]null,setsar=1[vfit]" in graph(plan)
    assert plan.needs_font is False


@pytest.mark.parametrize(
    "bad",
    [{"speed": 0.1}, {"speed": 5}, {"rotate": 45}, {"aspect": "3:2"}, {"text_color": "red"}, {"volume": 500},
     {"trim_start": -1}, {"trim_start": 5, "trim_end": 3}, {"text": "x" * 301}, {"unknown_field": 1},
     {"logo_scale": 100}, {"quality": "ultra"}],
)
def test_invalid_params_rejected(bad):
    with pytest.raises(ValidationError):
        EditParams(**bad)


def test_text_is_cleaned():
    assert P(text="  Привет\r\nмир \x07 ").text == "Привет\nмир"


# ---------- Размер кадра ----------

@pytest.mark.parametrize(
    ("src", "params", "expected"),
    [
        ((1920, 1080), {}, (1920, 1080)),
        ((1920, 1080), {"aspect": "9:16", "fit": "crop"}, (606, 1080)),
        ((1920, 1080), {"aspect": "9:16", "fit": "blur"}, (1080, 1920)),
        ((1920, 1080), {"aspect": "9:16", "fit": "pad", "resolution": "720"}, (720, 1280)),
        ((1920, 1080), {"aspect": "1:1", "fit": "crop"}, (1080, 1080)),
        ((720, 1280), {"aspect": "16:9", "fit": "crop"}, (720, 404)),
        ((720, 1280), {"aspect": "4:5", "resolution": "1080"}, (1080, 1350)),
        ((1920, 1080), {"resolution": "720"}, (1280, 720)),
        ((641, 361), {}, (640, 360)),  # нечётные размеры недопустимы для yuv420p
    ],
)
def test_output_size(src, params, expected):
    assert output_size(*src, P(**params)) == expected


def test_output_size_is_capped():
    w, h = output_size(8000, 4000, P())
    assert max(w, h) <= 3840 and w % 2 == 0 and h % 2 == 0


def test_rotation_swaps_dimensions():
    plan = plan_render(P(rotate=90), LANDSCAPE, INPUTS)
    assert (plan.width, plan.height) == (1080, 1920)
    assert "transpose=1" in graph(plan)
    assert "transpose=2" in graph(plan_render(P(rotate=270), LANDSCAPE, INPUTS))
    assert "hflip,vflip" in graph(plan_render(P(rotate=180), LANDSCAPE, INPUTS))


# ---------- Время ----------

def test_trim_and_speed():
    plan = plan_render(P(trim_start=2, trim_end=8, speed=2), LANDSCAPE, INPUTS)
    assert arg(plan, "-ss") == "2.000"
    assert arg(plan, "-t") == "6.000"  # длительность фрагмента исходника
    assert plan.output_duration == pytest.approx(3.0)
    assert "setpts=PTS/2" in graph(plan)
    assert "atempo=2" in graph(plan)
    assert plan.args[-3:-1] == ["-max_muxing_queue_size", "2048"]
    assert plan.args[plan.args.index("-movflags") - 1] == "3.000"  # -t на выходе


def test_trim_end_beyond_duration_is_clamped():
    plan = plan_render(P(trim_start=8, trim_end=60), LANDSCAPE, INPUTS)
    assert plan.output_duration == pytest.approx(2.0)


def test_trim_start_beyond_duration_keeps_minimal_tail():
    plan = plan_render(P(trim_start=100), LANDSCAPE, INPUTS)
    assert plan.output_duration == pytest.approx(0.3)


def test_too_short_fragment():
    with pytest.raises(MediaError, match="короткий"):
        plan_render(P(trim_start=1.0, trim_end=1.1), LANDSCAPE, INPUTS)


def test_no_video_stream():
    audio_only = MediaInfo(duration=5, width=0, height=0, has_audio=True, has_video=False)
    with pytest.raises(MediaError, match="видеодорожки"):
        plan_render(P(), audio_only, INPUTS)


@pytest.mark.parametrize(
    ("speed", "expected"),
    [(1.0, []), (1.5, ["atempo=1.5"]), (0.5, ["atempo=0.5"]), (0.25, ["atempo=0.5", "atempo=0.5"]),
     (3.0, ["atempo=2.0", "atempo=1.5"]), (4.0, ["atempo=2.0", "atempo=2"])],
)
def test_atempo_chain(speed, expected):
    chain = atempo_chain(speed)
    assert chain == expected
    product = math.prod(float(f.split("=")[1]) for f in chain) if chain else 1.0
    assert product == pytest.approx(speed)


def test_fades_are_limited_by_duration():
    plan = plan_render(P(trim_end=2, fade_in=5, fade_out=5), LANDSCAPE, INPUTS)
    g = graph(plan)
    assert "fade=t=in:st=0:d=1.000" in g
    assert "fade=t=out:st=1.000:d=1.000" in g
    assert "afade=t=in" in g and "afade=t=out" in g


# ---------- Кадр и цвет ----------

@pytest.mark.parametrize(
    ("fit", "snippet"),
    [("crop", "force_original_aspect_ratio=increase,crop=1080:1080"),
     ("pad", "pad=1080:1080:(ow-iw)/2:(oh-ih)/2:color=black"),
     ("blur", "boxblur=")],
)
def test_fit_modes(fit, snippet):
    plan = plan_render(P(aspect="1:1", fit=fit, resolution="1080"), LANDSCAPE, INPUTS)
    assert snippet in graph(plan)
    assert (plan.width, plan.height) == (1080, 1080)


def test_color_and_flip():
    g = graph(plan_render(P(brightness=0.1, contrast=1.2, saturation=0.5, flip_h=True, flip_v=True), LANDSCAPE, INPUTS))
    assert "eq=brightness=0.100:contrast=1.200:saturation=0.500" in g
    assert "hflip" in g and "vflip" in g


def test_grayscale_overrides_saturation():
    assert "saturation=0.000" in graph(plan_render(P(grayscale=True, saturation=2), LANDSCAPE, INPUTS))


def test_high_fps_is_capped():
    assert "fps=60" in graph(plan_render(P(), MediaInfo(5, 640, 360, True, True, fps=120), INPUTS))
    assert "fps=60" not in graph(plan_render(P(), SILENT_VERTICAL, INPUTS))


# ---------- Текст ----------

def test_text_is_overlaid_as_image():
    inputs = RenderInputs(source="/s.mp4", output="o.mp4", text_image=True)
    plan = plan_render(P(text="Привет: 100% 'кавычки' и \слэш"), LANDSCAPE, inputs)
    g = graph(plan)
    i = plan.args.index(TEXT_IMAGE)
    assert plan.args[i - 5: i] == ["-loop", "1", "-t", "10.000", "-i"]
    assert "[vfit][1:v]overlay=0:0" in g
    assert "Привет" not in g  # текст не попадает в граф фильтров — нечего экранировать
    assert plan.needs_font is False


def test_text_image_ignored_without_text():
    inputs = RenderInputs(source="/s.mp4", output="o.mp4", text_image=True)
    assert TEXT_IMAGE not in plan_render(P(), LANDSCAPE, inputs).args


def test_fades_applied_after_overlays():
    inputs = RenderInputs(source="/s.mp4", output="o.mp4", logo="logo.png", text_image=True, subtitles=True)
    g = graph(plan_render(P(text="x", fade_in=1, fade_out=1), LANDSCAPE, inputs))
    assert g.index("subtitles=") < g.index("overlay=0:0") < g.index("[logo]overlay") < g.index("fade=t=in")
    assert "[vlogo]fade=t=in:st=0:d=1.000,fade=t=out:st=9.000:d=1.000,format=yuv420p[vout]" in g


# ---------- Логотип, звук, субтитры ----------

@pytest.mark.parametrize(
    ("position", "xy"),
    [("top-left", "x=32:y=32"), ("bottom-right", "x=W-w-32:y=H-h-32"), ("center", "x=(W-w)/2:y=(H-h)/2")],
)
def test_logo_overlay(position, xy):
    inputs = RenderInputs(source="/s.mp4", output="o.mp4", logo="logo.png")
    plan = plan_render(P(logo_position=position, logo_scale=10, logo_opacity=0.5), LANDSCAPE, inputs)
    g = graph(plan)
    assert plan.args[plan.args.index("logo.png") - 5: plan.args.index("logo.png")] == ["-loop", "1", "-t", "10.000", "-i"]
    assert "[1:v]scale=192:-2,format=rgba,colorchannelmixer=aa=0.500[logo]" in g
    assert f"overlay={xy}" in g


def test_music_is_mixed_with_original():
    inputs = RenderInputs(source="/s.mp4", output="o.mp4", music="music.mp3")
    plan = plan_render(P(volume=50, music_volume=80), LANDSCAPE, inputs)
    g = graph(plan)
    assert plan.args[plan.args.index("music.mp3") - 3: plan.args.index("music.mp3")] == ["-stream_loop", "-1", "-i"]
    assert "volume=0.500" in g and "volume=0.800" in g
    assert "amix=inputs=2:duration=first" in g and "normalize=0" in g


def test_music_replaces_original():
    inputs = RenderInputs(source="/s.mp4", output="o.mp4", music="music.mp3")
    g = graph(plan_render(P(music_replace=True), LANDSCAPE, inputs))
    assert "[0:a]" not in g and "amix" not in g
    assert "[amusic]aresample=48000[aout]" in g


def test_mute_without_music_adds_silence():
    plan = plan_render(P(mute=True), LANDSCAPE, INPUTS)
    assert "anullsrc=r=48000:cl=stereo" in plan.args
    assert "[0:a]" not in graph(plan)


def test_source_without_audio_gets_silent_track():
    plan = plan_render(P(), SILENT_VERTICAL, INPUTS)
    assert "anullsrc=r=48000:cl=stereo" in plan.args
    assert "-map" in plan.args and "[aout]" in plan.args


def test_subtitles_use_relative_file():
    inputs = RenderInputs(source="/s.mp4", output="o.mp4", subtitles=True)
    plan = plan_render(P(), SILENT_VERTICAL, inputs)
    assert "subtitles=subs.srt:fontsdir=.:force_style='FontName=Inter Display" in graph(plan)
    assert "FontSize=11" in graph(plan)  # вертикальное видео
    assert plan.needs_font is True


@pytest.mark.parametrize(("quality", "crf"), [("draft", "27"), ("standard", "22"), ("high", "19")])
def test_quality(quality, crf):
    plan = plan_render(P(quality=quality), LANDSCAPE, INPUTS)
    assert arg(plan, "-crf") == crf
    assert arg(plan, "-c:v") == "libx264" and arg(plan, "-pix_fmt") == "yuv420p"
    assert "+faststart" in plan.args
    assert plan.args[-1] == "output.mp4"
