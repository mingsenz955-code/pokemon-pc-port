"""Package only built program + recovered data. Never include local player progress."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile
from build_downloader import build
ROOT=Path(__file__).resolve().parent.parent

def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def package(release,version):
    release=Path(release).resolve()
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Invalid version')
    executable=release/(release.name+'.exe')
    assert executable.is_file() and (release/'data/tables.json').is_file(),'Incomplete build'
    output=ROOT/'outputs/friends-release'/version
    output.mkdir(parents=True,exist_ok=True)
    archive=output/f'PocketPC-{version}-win64.zip'
    blocked={'slot1.json','save.json','preview-position.json'}
    entries=[]
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for file in sorted(release.rglob('*')):
            if not file.is_file():continue
            relative=file.relative_to(release)
            # Ship runtime files only, not development handovers or local notes.
            if relative.parts[0] not in ('data','_internal',executable.name):continue
            if file.name.lower() in blocked or any(p.lower() in ('saves','存档','__pycache__') for p in relative.parts):
                raise ValueError(f'Personal save/cache in release: {relative}')
            bundle.write(file,relative.as_posix());entries.append(relative.as_posix())
        bundle.writestr('使用说明.txt',
            '口袋妖怪 PC 单机开发版 '+version+'\n\n'
            '推荐通过口袋妖怪下载器安装，安装后点击“开始游戏”。\n'
            '首次运行是你自己的新游戏，已有本机进度会继续保留。\n'
            '存档：%LOCALAPPDATA%\\PocketNativePC\\slot1.json\n'
            '更新不会复制别人的存档，也不会删除你的存档。\n'
            'F11 / Alt+Enter 全屏，方向键/WASD移动，空格/E对话，G指引，F5保存。\n'
            '这是开发中的复刻版本，尚未完整还原全部内容。\n')
    digest=sha256(archive)
    manifest={'version':version,'asset_url':f'https://github.com/mingsenz955-code/pokemon-pc-port/releases/download/v{version}/{archive.name}',
              'sha256':digest,'size':archive.stat().st_size,'executable':executable.name}
    (output/'pocket-release.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    downloader=build(output/'PocketPC-Setup.exe')
    shutil.copy2(downloader,ROOT/'outputs/口袋妖怪下载器.exe')
    (output/'SHA256SUMS.txt').write_text('\n'.join(sha256(f)+'  '+f.name for f in (archive,downloader))+'\n',encoding='utf8')
    (output/'package-audit.json').write_text(json.dumps({'files':len(entries),'contains_save':False,'entries':entries},ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(manifest,ensure_ascii=False));return output

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('release',type=Path);parser.add_argument('--version',default='0.2.84');args=parser.parse_args()
    package(args.release,args.version)
