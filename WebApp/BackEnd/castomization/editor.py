# video_editor.py
import os, math
import tempfile
import subprocess
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import TextClip, ImageClip
from moviepy import CompositeVideoClip, CompositeAudioClip
from moviepy.audio.io.AudioFileClip import AudioFileClip


class VideoEditor:
    """
    Класс для пошаговой трансформации видео.
    У каждого метода ровно один параметр (param) — UI может подать разные типы:
      - str (путь, текст, "1280x720", "720p")
      - int/float (высота, speed factor)
      - tuple (например для trim: (start, end) или для overlay: (path, pos, start, end, size))
    Методы возвращают self, поэтому можно цепочить вызовы.
    В конце вызывайте export(output_path).
    """

    def __init__(self, input_path: str):
        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"Input not found: {input_path}")
        self.input_path = input_path
        self.clip = VideoFileClip(input_path)

    def resize(self, param):
        if isinstance(param, (int, float)):
            self.clip = self.clip.resized(height=int(param))
        elif isinstance(param, tuple) and len(param) == 2:
            self.clip = self.clip.resized(newsize=(int(param[0]), int(param[1])))
        elif isinstance(param, str):
            s = param.lower()
            if "x" in s:
                w, h = map(int, s.split("x"))
                self.clip = self.clip.resized(newsize=(w, h))
            elif s.endswith("p") and s[:-1].isdigit():
                h = int(s[:-1])
                self.clip = self.clip.resized(height=h)
            else:
                raise ValueError("Непонятный формат размера. Примеры: 1280x720, 720p, 720")
        else:
            raise ValueError("unsupported param for resize")
        return self

    def add_text(self, param):
        """
        Добавляет текст:
          - str -> весь ролик
          - tuple -> (text, start, end, pos, fontsize)
        """
        font_name = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

        if isinstance(param, str):
            txt = TextClip(
                text=param,
                size=self.clip.size,
                color='white',
                method='label',
                font = font_name
            ).with_position(("center", "bottom")).with_duration(self.clip.duration)
        elif isinstance(param, tuple) and len(param) >= 1:
            text = param[0]
            start = float(param[1]) if len(param) > 1 else 0
            end = float(param[2]) if len(param) > 2 else self.clip.duration
            pos = param[3] if len(param) > 3 else ("center", "bottom")
            fontsize = int(param[4]) if len(param) > 4 else 48
            txt = TextClip(text, font='Arial', font_size=fontsize, color='white', method='caption', size=self.clip.size)
            txt = txt.with_start(start).set_end(end).set_pos(pos)
        else:
            raise ValueError("unsupported param for add_text")

        self.clip = CompositeVideoClip([self.clip, txt.with_duration(self.clip.duration)])
        print("Text added — отлично")
        return self

    def grayscale(self, param):
        if param:
            self.clip = self.clip.fx("blackwhite")
        return self

    def mirror(self, param):
        if param:
            self.clip = self.clip.fx("mirror_x")
        return self

    def speed(self, param):
        try:
            factor = float(param)
        except Exception:
            raise ValueError("speed expects a number-like parameter")
        if factor <= 0:
            raise ValueError("speed factor must be > 0")
        self.clip = self.clip.with_speed_scaled(factor)
        return self

    def trim(self, param):
        if isinstance(param, str):
            if "-" not in param:
                raise ValueError("trim expects 'start-end' string or tuple(start, end)")
            start, end = param.split("-", 1)
            start, end = float(start.strip()), float(end.strip())
        elif isinstance(param, (tuple, list)) and len(param) == 2:
            start, end = float(param[0]), float(param[1])
        else:
            raise ValueError("trim expects (start, end)")
        self.clip = self.clip.subclipped(start, end)
        return self

    def overlay_image(self, param):
        if isinstance(param, str):
            img = ImageClip(param).with_duration(self.clip.duration).with_position(("center", "center"))
        elif isinstance(param, tuple) and len(param) >= 1:
            path = param[0]
            pos = param[1] if len(param) > 1 else ("center", "center")
            start = float(param[2]) if len(param) > 2 else 0
            end = float(param[3]) if len(param) > 3 else self.clip.duration
            size = param[4] if len(param) > 4 else None
            img = ImageClip(path)
            if size:
                img = img.resized(newsize=(int(size[0]), int(size[1])))
            img = img.set_start(start).set_end(end).set_pos(pos).set_duration(end - start)
        else:
            raise ValueError("unsupported param for overlay_image")
        self.clip = CompositeVideoClip([self.clip, img])
        return self

    def set_audio(self, param):
        if not isinstance(param, str) or not os.path.isfile(param):
            raise ValueError("set_audio expects a valid audio filepath")
        audio = AudioFileClip(param).set_duration(self.clip.duration)
        self.clip = self.clip.set_audio(audio)
        return self

    def add_subtitles(self, param):
        srt_path = param
        if not isinstance(srt_path, str) or not os.path.isfile(srt_path):
            raise ValueError("add_subtitles expects a valid .srt filepath")

        tmp_in = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp_in.close()
        tmp_out = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp_out.close()

        self.clip.write_videofile(tmp_in.name, codec="libx264", audio_codec="aac", logger=None, verbose=False)

        cmd = [
            "ffmpeg", "-y", "-i", tmp_in.name,
            "-vf", f"subtitles={srt_path}",
            "-c:a", "copy", tmp_out.name
        ]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            os.unlink(tmp_in.name)
            os.unlink(tmp_out.name)
            raise RuntimeError("ffmpeg failed to burn subtitles") from e

        self.clip.close()
        self.clip = VideoFileClip(tmp_out.name)
        os.unlink(tmp_in.name)
        return self

    def export(self, param):
        out = param
        if not isinstance(out, str):
            raise ValueError("export expects an output filepath string")
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        self.clip.write_videofile(out, codec="libx264", audio_codec="aac")
        return self

    def rotate(self, param):
        try:
            angle = float(param)
            self.clip = self.clip.rotated(angle)
        except Exception:
            raise ValueError("rotate expects a number")
        return self

    def scale(self, param):
        try:
            pct = float(param)
            factor = pct / 100.0
            self.clip = self.clip.resized(factor)
        except Exception:
            raise ValueError("scale expects a number")
        return self

    def adjust_volume(self, param):
        try:
            pct = float(param)
            factor = pct / 100.0
            self.clip = self.clip.with_volume_scaled(factor)
        except Exception:
            raise ValueError("volume expects a number")
        return self

    def add_background_audio(self, param, volume=1.0):
        if not param or not os.path.isfile(param):
            raise ValueError("add_background_audio expects a valid file path")

        bg = AudioFileClip(param).with_volume_scaled(volume)

        # повторяем аудио до длины видео
        clips = []
        n = math.ceil(self.clip.duration / bg.duration)

        for i in range(n):
            clips.append(bg)

        # Склеиваем
        bg_full = CompositeAudioClip(clips).subclipped(0, self.clip.duration)

        # Микшируем
        if self.clip.audio:
            audio = CompositeAudioClip([self.clip.audio, bg_full])
        else:
            audio = bg_full

        self.clip = self.clip.with_audio(audio)
        return self

    def close(self):
        try:
            self.clip.close()
        except Exception:
            pass

    def __del__(self):
        self.close()
