"""Фронтенд: JS-тесты (node:test) и сверка расчётов превью с серверным рендером."""
import itertools
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.editor.pipeline import output_size
from app.editor.schemas import EditParams

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js не установлен")


def _node(script: str) -> str:
    # Скрипт передаётся через stdin: длина командной строки в Windows ограничена
    result = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                            timeout=60)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_js_unit_tests():
    files = sorted(str(p) for p in (ROOT / "tests" / "js").glob("*.test.cjs"))
    result = subprocess.run([NODE, "--test", *files], capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                            timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr


def test_all_static_js_is_valid_syntax():
    for path in (ROOT / "app" / "web" / "static" / "js").glob("*.js"):
        _node(f"new Function(require('fs').readFileSync({json.dumps(str(path))}, 'utf8'))")


def test_preview_frame_size_matches_server():
    """Размер кадра в превью (clip-editor.js) обязан совпадать с серверным output_size()."""
    sources = [(1920, 1080), (1080, 1920), (1280, 720), (640, 480), (720, 1280), (641, 361), (3840, 2160), (400, 400)]
    aspects = ["original", "9:16", "1:1", "4:5", "16:9"]
    fits = ["crop", "blur", "pad"]
    resolutions = ["original", "480", "720", "1080"]
    cases = [
        {"w": w, "h": h, "p": {"aspect": a, "fit": f, "resolution": r}}
        for (w, h), a, f, r in itertools.product(sources, aspects, fits, resolutions)
    ]
    script = f"""
const {{ createContext, load }} = require('./tests/js/helpers.cjs');
const core = load(createContext(), 'api.js', 'clip-editor.js').ClipEditorCore;
const cases = {json.dumps(cases)};
console.log(JSON.stringify(cases.map((c) => [...core.outputSize(c.w, c.h, c.p)])));
"""
    js_sizes = json.loads(_node(script))
    mismatches = []
    for case, js in zip(cases, js_sizes):
        py = list(output_size(case["w"], case["h"], EditParams(**case["p"])))
        if py != js:
            mismatches.append((case, py, js))
    assert len(cases) == 480
    assert mismatches == []
