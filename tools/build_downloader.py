"""Build the standalone Windows friend downloader; no desktop changes."""
import os
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parent.parent

def build(output=None):
    output=Path(output or ROOT/'outputs/口袋妖怪下载器.exe').resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    framework=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319'
    compiler=framework/'csc.exe'
    if not compiler.exists():compiler=framework.parent.parent/'Framework/v4.0.30319/csc.exe'
    references=['System.Windows.Forms','System.Drawing','System.Web.Extensions','System.IO.Compression','System.IO.Compression.FileSystem','Microsoft.CSharp']
    subprocess.run([str(compiler),'/nologo','/target:winexe','/codepage:65001',
                    *['/reference:'+r+'.dll' for r in references],'/out:'+str(output),str(ROOT/'native/Downloader.cs')],check=True)
    return output

if __name__=='__main__':print(build())
