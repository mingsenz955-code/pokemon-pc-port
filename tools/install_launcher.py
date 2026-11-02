"""Publish a stable Windows launcher only after a complete package exists."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def install_launcher(dist, release, desktop=False):
    dist, release = Path(dist).resolve(), Path(release).resolve()
    executable = release/(release.name+'.exe')
    if release.parent != dist or not executable.is_file() or not (release/'data/tables.json').is_file():
        raise ValueError('Only a complete release under the output directory can be published')
    home = dist/'口袋妖怪启动器'
    home.mkdir(parents=True, exist_ok=True)
    launcher = home/'口袋妖怪.exe'
    source = ROOT/'native/Launcher.cs'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    digest_path = home/'launcher-source.sha256'
    if not launcher.exists() or not digest_path.exists() or digest_path.read_text().strip() != digest:
        windows = Path(os.environ.get('WINDIR', r'C:\Windows'))
        compiler = windows/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.exists():
            compiler = windows/'Microsoft.NET/Framework/v4.0.30319/csc.exe'
        temporary = home/'launcher-next.exe'
        subprocess.run([str(compiler), '/nologo', '/target:winexe', '/codepage:65001',
                        '/reference:System.Windows.Forms.dll', '/out:'+str(temporary), str(source)], check=True)
        os.replace(temporary, launcher)
        digest_path.write_text(digest, encoding='utf-8')
    pointer = home/'current-release.txt'
    temporary = pointer.with_suffix('.tmp')
    temporary.write_text(os.path.relpath(executable, home), encoding='utf-8')
    os.replace(temporary, pointer)
    if desktop:
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                        str(ROOT/'tools/install_desktop_launcher.ps1'), '-LauncherPath', str(launcher),
                        '-DistRoot', str(dist)], check=True)
    return launcher


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('release', type=Path)
    parser.add_argument('--dist-dir', type=Path, default=ROOT/'outputs')
    parser.add_argument('--desktop', action='store_true')
    options = parser.parse_args()
    print(install_launcher(options.dist_dir, options.release, options.desktop))
