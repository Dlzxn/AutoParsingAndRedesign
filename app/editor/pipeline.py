"""Сборка команды ffmpeg из параметров монтажа.

Модуль не выполняет ffmpeg и не трогает диск — только рассчитывает граф фильтров, поэтому
полностью покрывается unit-тестами. ffmpeg запускается с рабочим каталогом задачи (cwd),
а вспомогательные файлы (шрифт, текст, субтитры) лежат в нём под фиксированными именами —
так не нужно экранировать пути в графе фильтров (особенно важно для путей Windows).
"""
import textwrap
from dataclasses import dataclass, field

from app.editor.schemas import EditParams
from app.media.ffmpeg import MediaError, MediaInfo

FONT_FILE = "font.ttf"
SUBTITLES_FILE = "subs.srt"
MIN_DURATION = 0.3
MAX_SIDE = 3840
MAX_TEXT_LINES = 6

ASPECTS = {"9:16": 9 / 16, "1:1": 1.0, "4:5": 4 / 5, "16:9": 16 / 9}
QUALITY = {
    "draft": ("veryfast", 27, "128k"),
    "standard": ("faster", 22, "160k"),
    "high": ("medium", 19, "192k"),
}
TEXT_SCALE = {"small": 0.055, "medium": 0.075, "large": 0.10}


@dataclass
class RenderInputs:
    source: str  # путь к исходнику (аргумент командной строки — экранирование не требуется)
    output: str
    logo: str | None = None
    music: str | None = None
    subtitles: bool = False  # файл SUBTITLES_FILE лежит в рабочем каталоге


@dataclass
class RenderPlan:
    args: list[str]
    output_duration: float
    width: int
    height: int
    text_files: dict[str, str] = field(default_factory=dict)  # имя файла -> содержимое
    needs_font: bool = False


def _even(value: float) -> int:
    """Округление вниз до чётного (yuv420p требует чётных размеров; кадр не выходит за исходник)."""
    return max(2, int(value + 1e-6) // 2 * 2)


def output_size(width: int, height: int, p: EditParams) -> tuple[int, int]:
    """Размер кадра на выходе (ширина и высота уже с учётом поворота)."""
    src_ratio = width / height
    ratio = src_ratio if p.aspect == "original" else ASPECTS[p.aspect]
    if p.resolution == "original" and p.aspect == "original":
        out_w, out_h = float(width), float(height)
    elif p.resolution == "original" and p.fit == "crop":
        # Максимальная область кадра с нужными пропорциями — без увеличения
        if ratio < src_ratio:
            out_w, out_h = height * ratio, float(height)
        else:
            out_w, out_h = float(width), width / ratio
    else:
        short = float(min(width, height)) if p.resolution == "original" else float(p.resolution)
        out_w, out_h = (short, short / ratio) if ratio <= 1 else (short * ratio, short)
    biggest = max(out_w, out_h)
    if biggest > MAX_SIDE:
        out_w, out_h = out_w * MAX_SIDE / biggest, out_h * MAX_SIDE / biggest
    return _even(out_w), _even(out_h)


def atempo_chain(speed: float) -> list[str]:
    """atempo принимает 0.5..2.0 за один фильтр — для других значений строим цепочку."""
    filters = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    if abs(remaining - 1.0) > 1e-6:
        filters.append(f"atempo={remaining:.6g}")
    return filters


def wrap_text(text: str, width: int, font_size: int) -> list[str]:
    max_chars = max(8, int(width * 0.9 / (font_size * 0.56)))
    lines: list[str] = []
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, max_chars, break_long_words=True) or [""])
    while lines and not lines[-1]:
        lines.pop()
    if len(lines) > MAX_TEXT_LINES:
        lines = lines[:MAX_TEXT_LINES]
        lines[-1] = lines[-1][: max(1, max_chars - 1)].rstrip() + "…"
    return lines


def _fit_filters(p: EditParams, w: int, h: int, out_w: int, out_h: int, src: str, dst: str) -> list[str]:
    """Цепочки, приводящие кадр [src] к размеру out_w x out_h, результат в [dst]."""
    if p.aspect == "original" or p.fit == "crop":
        if p.aspect == "original":
            chain = f"scale={out_w}:{out_h}" if (out_w, out_h) != (w, h) else "null"
        else:
            chain = f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,crop={out_w}:{out_h}"
        return [f"[{src}]{chain},setsar=1[{dst}]"]
    fg = f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease:force_divisible_by=2"
    if p.fit == "pad":
        return [f"[{src}]{fg},pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[{dst}]"]
    radius = max(8, min(out_w, out_h) // 25)
    return [
        f"[{src}]split=2[fitbg][fitfg]",
        f"[fitbg]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,crop={out_w}:{out_h},"
        f"boxblur={radius}:2,eq=brightness=-0.08[fitbgb]",
        f"[fitfg]{fg}[fitfgs]",
        f"[fitbgb][fitfgs]overlay=(W-w)/2:(H-h)/2,setsar=1[{dst}]",
    ]


def _text_filters(p: EditParams, out_w: int, out_h: int) -> tuple[list[str], dict[str, str]]:
    font_size = max(14, int(min(out_w, out_h) * TEXT_SCALE[p.text_size]))
    lines = wrap_text(p.text, out_w, font_size)
    if not lines:
        return [], {}
    line_height = int(font_size * 1.3)
    block = line_height * len(lines)
    if p.text_position == "top":
        y0 = int(out_h * 0.08)
    elif p.text_position == "center":
        y0 = (out_h - block) // 2
    else:
        y0 = int(out_h * 0.88) - block
    color = p.text_color.lstrip("#")
    style = (
        f"box=1:boxcolor=black@0.55:boxborderw={max(4, font_size // 4)}"
        if p.text_background
        else f"borderw={max(2, font_size // 16)}:bordercolor=black@0.85:shadowcolor=black@0.5:shadowx=2:shadowy=2"
    )
    filters, files = [], {}
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        name = f"text_{i}.txt"
        files[name] = line
        filters.append(
            f"drawtext=fontfile={FONT_FILE}:textfile={name}:expansion=none:fontsize={font_size}"
            f":fontcolor=0x{color}:x=(w-text_w)/2:y={y0 + i * line_height}:{style}"
        )
    return filters, files


def plan_render(p: EditParams, info: MediaInfo, inputs: RenderInputs) -> RenderPlan:
    if not info.has_video:
        raise MediaError("В файле нет видеодорожки")
    duration = info.duration
    start = min(p.trim_start, max(0.0, duration - MIN_DURATION))
    end = min(p.trim_end, duration) if p.trim_end else duration
    segment = end - start
    if segment < MIN_DURATION:
        raise MediaError("Выбранный фрагмент слишком короткий")
    out_duration = segment / p.speed

    # --- входы ---
    args: list[str] = ["-ss", f"{start:.3f}", "-t", f"{segment:.3f}", "-i", inputs.source]
    next_index = 1
    logo_index = music_index = silence_index = None
    if inputs.logo:
        args += ["-loop", "1", "-t", f"{out_duration:.3f}", "-i", inputs.logo]
        logo_index, next_index = next_index, next_index + 1
    if inputs.music:
        args += ["-stream_loop", "-1", "-i", inputs.music]
        music_index, next_index = next_index, next_index + 1

    use_source_audio = info.has_audio and not p.mute and not (inputs.music and p.music_replace)
    if not use_source_audio and not inputs.music:
        args += ["-f", "lavfi", "-t", f"{out_duration:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        silence_index = next_index

    # --- видео ---
    graph: list[str] = []
    pre: list[str] = []
    if p.speed != 1.0:
        pre.append(f"setpts=PTS/{p.speed:.6g}")
    w, h = info.width, info.height
    if p.rotate == 90:
        pre.append("transpose=1")
    elif p.rotate == 270:
        pre.append("transpose=2")
    elif p.rotate == 180:
        pre += ["hflip", "vflip"]
    if p.rotate in (90, 270):
        w, h = h, w
    if p.flip_h:
        pre.append("hflip")
    if p.flip_v:
        pre.append("vflip")
    saturation = 0.0 if p.grayscale else p.saturation
    if p.brightness != 0 or p.contrast != 1 or saturation != 1:
        pre.append(f"eq=brightness={p.brightness:.3f}:contrast={p.contrast:.3f}:saturation={saturation:.3f}")
    if info.fps and info.fps > 60:
        pre.append("fps=60")
    graph.append(f"[0:v]{','.join(pre) or 'null'}[vpre]")

    out_w, out_h = output_size(w, h, p)
    graph += _fit_filters(p, w, h, out_w, out_h, "vpre", "vfit")

    post: list[str] = []
    fade_in = min(p.fade_in, out_duration / 2)
    fade_out = min(p.fade_out, out_duration / 2)
    if fade_in > 0:
        post.append(f"fade=t=in:st=0:d={fade_in:.3f}")
    if fade_out > 0:
        post.append(f"fade=t=out:st={out_duration - fade_out:.3f}:d={fade_out:.3f}")
    if inputs.subtitles:
        font_size = 11 if out_h > out_w else 16
        post.append(
            f"subtitles={SUBTITLES_FILE}:fontsdir=.:force_style='FontName=DejaVu Sans,Bold=1,"
            f"FontSize={font_size},Outline=2,Shadow=1,MarginV=25'"
        )
    text_filters, text_files = _text_filters(p, out_w, out_h) if p.text else ([], {})
    post += text_filters
    last = "vfit"
    if post:
        graph.append(f"[vfit]{','.join(post)}[vpost]")
        last = "vpost"

    if logo_index is not None:
        logo_w = _even(out_w * p.logo_scale / 100)
        margin = max(8, int(min(out_w, out_h) * 0.03))
        x, y = {
            "top-left": (f"{margin}", f"{margin}"),
            "top-right": (f"W-w-{margin}", f"{margin}"),
            "bottom-left": (f"{margin}", f"H-h-{margin}"),
            "bottom-right": (f"W-w-{margin}", f"H-h-{margin}"),
            "center": ("(W-w)/2", "(H-h)/2"),
        }[p.logo_position]
        graph.append(
            f"[{logo_index}:v]scale={logo_w}:-2,format=rgba,colorchannelmixer=aa={p.logo_opacity:.3f}[logo]"
        )
        graph.append(f"[{last}][logo]overlay=x={x}:y={y}:shortest=1:format=auto[vlogo]")
        last = "vlogo"
    graph.append(f"[{last}]format=yuv420p[vout]")

    # --- звук ---
    audio_parts: list[str] = []
    if use_source_audio:
        chain = atempo_chain(p.speed)
        if p.volume != 100:
            chain.append(f"volume={p.volume / 100:.3f}")
        if fade_in > 0:
            chain.append(f"afade=t=in:st=0:d={fade_in:.3f}")
        if fade_out > 0:
            chain.append(f"afade=t=out:st={out_duration - fade_out:.3f}:d={fade_out:.3f}")
        graph.append(f"[0:a]{','.join(chain) or 'anull'}[asrc]")
        audio_parts.append("asrc")
    if music_index is not None:
        music_fade = min(1.5, out_duration / 3)
        graph.append(
            f"[{music_index}:a]atrim=duration={out_duration:.3f},asetpts=PTS-STARTPTS,"
            f"volume={p.music_volume / 100:.3f},afade=t=out:st={out_duration - music_fade:.3f}:d={music_fade:.3f}[amusic]"
        )
        audio_parts.append("amusic")
    if len(audio_parts) == 2:
        graph.append("[asrc][amusic]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[amix]")
        audio_label = "amix"
    elif audio_parts:
        audio_label = audio_parts[0]
    else:
        graph.append(f"[{silence_index}:a]anull[asil]")
        audio_label = "asil"
    graph.append(f"[{audio_label}]aresample=48000[aout]")

    preset, crf, audio_bitrate = QUALITY[p.quality]
    args += [
        "-filter_complex", ";".join(graph),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", audio_bitrate, "-ac", "2",
        "-t", f"{out_duration:.3f}",
        "-movflags", "+faststart",
        "-max_muxing_queue_size", "2048",
        inputs.output,
    ]
    return RenderPlan(
        args=args,
        output_duration=out_duration,
        width=out_w,
        height=out_h,
        text_files=text_files,
        needs_font=bool(text_files) or inputs.subtitles,
    )
