import moviepy
from WebApp.BackEnd.castomization.editor import VideoEditor

print("MoviePy version:", moviepy.__version__)  # >= 2.0.0.post0

# Создаём редактор
editor = VideoEditor("uploads/test.mp4")

# Папка для промежуточных файлов
import os
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def save_step(editor, name):
    path = os.path.join(OUTPUT_DIR, name)
    editor.export(path)
    print(f"{name}: Сделано — отлично")

# Trim
editor.trim((0, 5))
save_step(editor, "step_trim.mp4")

# Speed
editor.speed(1.5)
save_step(editor, "step_speed.mp4")

# Rotate
editor.rotate(90)
save_step(editor, "step_rotate.mp4")

# Scale
editor.scale(50)  # 50%
save_step(editor, "step_scale.mp4")

# Adjust volume
editor.adjust_volume(50)
save_step(editor, "step_volume.mp4")

# Add text
editor.add_text("Test Text")
save_step(editor, "step_text.mp4")

# Overlay image
editor.overlay_image("uploads/sample_overlay.png")
save_step(editor, "step_overlay.mp4")

# Background audio
editor.add_background_audio("uploads/sample_audio.mp3")
save_step(editor, "step_bg_audio.mp4")


# Финальный экспорт
output_final = os.path.join(OUTPUT_DIR, "test_final.mp4")
editor.export(output_final)
print("Final export:", output_final, "- Сделано — отлично")
