"""Run with the venv Python after installing requirements.txt."""
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
name = '口袋妖怪-PC移植开发版0.2'
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--windowed', '--onedir',
           '--name', name, '--distpath', str(root/'outputs'),
           '--workpath', str(root/'build'),
           '--hidden-import', 'battle', '--hidden-import', 'battle_ui',
           '--hidden-import', 'pet_factory']
for library in ['ffi.dll', 'tcl86t.dll', 'tk86t.dll', 'yaml.dll', 'zlib.dll',
                'libexpat.dll', 'libssl-3-x64.dll', 'libcrypto-3-x64.dll']:
    candidate = Path(sys.base_prefix)/'Library/bin'/library
    if candidate.exists():
        command += ['--add-binary', str(candidate)+';.']
command.append(str(root/'src/pc_game.py'))
subprocess.run(command, cwd=root, check=True)
output = root/'outputs'/name
data = output/'data'
if data.exists() and data.resolve() != (root/'original-1.20.4').resolve():
    shutil.rmtree(data)
shutil.copytree(root/'original-1.20.4', data, dirs_exist_ok=True)
for filename in ['README.md', 'DEEPSEEK接续提示词.md']:
    source = root/filename
    if source.exists():
        shutil.copy2(source, output/('使用说明.md' if filename == 'README.md' else filename))
research = root/'research/资源搜索与版本核验.md'
if research.exists():
    shutil.copy2(research, output/research.name)
print(output)