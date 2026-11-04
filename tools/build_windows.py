"""Run with the venv Python after installing requirements.txt."""
import shutil
import argparse
import subprocess
import sys
from install_launcher import install_launcher
from pathlib import Path

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--name', default='口袋妖怪-PC移植开发版0.2.89')
parser.add_argument('--dist-dir', type=Path, default=root/'outputs')
args = parser.parse_args()
name = args.name
if Path(name).name != name or '/' in name or '\\' in name:
    raise ValueError('Build name must be a single directory name')
subprocess.run([sys.executable, str(root/'tools/bake_lottery_animation.py')], cwd=root, check=True)
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--windowed', '--onedir',
           '--name', name, '--distpath', str(args.dist_dir),
           '--workpath', str(root/'build'),
           '--hidden-import', 'battle', '--hidden-import', 'battle_ui',
           '--hidden-import', 'pet_factory', '--hidden-import', 'daily_tasks']
for library in ['ffi.dll', 'tcl86t.dll', 'tk86t.dll', 'yaml.dll', 'zlib.dll',
                'libexpat.dll', 'libssl-3-x64.dll', 'libcrypto-3-x64.dll']:
    candidate = Path(sys.base_prefix)/'Library/bin'/library
    if candidate.exists():
        command += ['--add-binary', str(candidate)+';.']
command.append(str(root/'src/pc_game.py'))
subprocess.run(command, cwd=root, check=True)
output = args.dist_dir/name
data = output/'data'
if data.exists() and data.resolve() != (root/'original-1.20.4').resolve():
    if data.is_symlink() or data.resolve().parent != output.resolve():
        raise ValueError('Refusing to replace a data directory outside the build package')
    shutil.rmtree(data)
shutil.copytree(root/'original-1.20.4', data, dirs_exist_ok=True)
shutil.copytree(root/'generated-assets/lottery', data/'cache/lottery', dirs_exist_ok=True)
for filename in ['README.md', 'docs/DEEPSEEK_HANDOVER.md', 'docs/MECHANICS_EVIDENCE.md',
                 'docs/RESTORATION_REMAINING.md', 'docs/RELEASE_WORKFLOW.md', 'docs/VERIFICATION_0.2.61.md', 'docs/VERIFICATION_0.2.62.md', 'docs/VERIFICATION_0.2.63.md', 'docs/VERIFICATION_0.2.66.md', 'docs/VERIFICATION_0.2.67.md', 'docs/VERIFICATION_0.2.68.md', 'docs/VERIFICATION_0.2.69.md', 'docs/VERIFICATION_0.2.70.md', 'docs/VERIFICATION_0.2.71.md', 'docs/VERIFICATION_0.2.72.md', 'docs/VERIFICATION_0.2.73.md', 'docs/VERIFICATION_0.2.74.md', 'docs/VERIFICATION_0.2.75.md', 'docs/VERIFICATION_0.2.76.md', 'docs/VERIFICATION_0.2.77.md', 'docs/VERIFICATION_0.2.78.md', 'docs/VERIFICATION_0.2.79.md', 'docs/VERIFICATION_0.2.80.md']:
    source = root/filename
    if source.exists():
        shutil.copy2(source, output/('使用说明.md' if filename == 'README.md' else source.name))
research = root/'research/资源搜索与版本核验.md'
if research.exists():
    shutil.copy2(research, output/research.name)
print(output)
print(install_launcher(args.dist_dir, output))
