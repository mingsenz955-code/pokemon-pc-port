"""Launch the packaged EXE, prove a real window renders, capture its first frame."""
import argparse
import ctypes
import subprocess
import time
from pathlib import Path

from PIL import ImageGrab, ImageStat

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--version', default='0.2.50')
version = parser.parse_args().version
name = f'口袋妖怪-PC移植开发版{version}'
exe = ROOT/f'outputs/{name}/{name}.exe'
assert exe.exists(), exe
out = ROOT/f'outputs/verification/packaged-{version}-boot.png'
out.parent.mkdir(parents=True, exist_ok=True)
process = subprocess.Popen([str(exe)], cwd=exe.parent)
try:
    time.sleep(8)
    title = f'口袋妖怪 · 原生 PC 移植开发版 {version}（全系统还原进行中）'
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
