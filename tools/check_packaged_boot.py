"""Launch the packaged EXE, prove a real window renders, capture its first frame."""
import ctypes
import subprocess
import time
from pathlib import Path

from PIL import ImageGrab, ImageStat

ROOT = Path(__file__).resolve().parent.parent
exe = ROOT/'outputs/口袋妖怪-PC移植开发版0.2.19/口袋妖怪-PC移植开发版0.2.19.exe'
assert exe.exists(), exe
out = ROOT/'outputs/verification/packaged-0.2.19-boot.png'
out.parent.mkdir(parents=True, exist_ok=True)
process = subprocess.Popen([str(exe)], cwd=exe.parent)
try:
    time.sleep(8)
    title = '口袋妖怪 · 原生 PC 移植开发版 0.2.19（全系统还原进行中）'
    hwnd = ctypes.windll.user32.FindWindowW(None, title)
    assert hwnd, f'packaged window title not found: {title}'
    image = ImageGrab.grab()
    image.save(out)
    stat = ImageStat.Stat(image.convert('RGB'))
    assert max(stat.var) > 10, 'packaged window appears blank'
    assert process.poll() is None, f'packaged app exited early: {process.returncode}'
finally:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
print({'exe': str(exe), 'screenshot': str(out), 'size': image.size,
       'variance': [round(v, 2) for v in stat.var], 'title': title})
