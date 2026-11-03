"""Exercise compiled downloader against local HTTP, real ZIPs and failure paths."""
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from build_downloader import build,ROOT

class DownloaderChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary=build()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
        cls.server.files={};cls.server.requests=[]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.home=self.path/'friends';self.home.mkdir()
        self.server.files.clear();self.server.requests.clear()
    def tearDown(self):self.temp.cleanup()
    def archive(self,extras=None):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as f:
            for key,value in {'PocketGame.exe':b'test binary, never executed','data/tables.json':b'{}',**(extras or {})}.items():f.writestr(key,value)
        return stream.getvalue()
    def manifest(self,content,version='0.0.1',**changes):
        self.server.files['/game.zip']=content
        m={'version':version,'asset_url':self.url+'/game.zip','sha256':hashlib.sha256(content).hexdigest(),'size':len(content),'executable':'PocketGame.exe',**changes}
        self.server.files['/manifest.json']=json.dumps(m).encode()
        return m
    def install(self,code=0,binary=None):
        result=self.path/'result.json'
        p=subprocess.run([str(binary or self.binary),'--install-only','--manifest',self.url+'/manifest.json','--root',str(self.home),'--result',str(result)],timeout=25)
        self.assertEqual(code,p.returncode,result.read_text('utf-8-sig') if result.exists() else 'no output')
        return result.read_text('utf-8-sig')
    def test_install_resolve_and_repeated_install_does_not_download_again(self):
        self.manifest(self.archive());self.install()
        pointer=json.loads((self.home/'installed.json').read_text())
        installed=self.home/pointer['directory'];self.assertTrue((installed/'PocketGame.exe').exists())
        count=self.server.requests.count('/game.zip');self.install();self.assertEqual(count,self.server.requests.count('/game.zip'))
        target=self.path/'resolved.txt'
        p=subprocess.run([str(self.binary),'--root',str(self.home),'--resolve',str(target)],timeout=10)
        self.assertEqual(0,p.returncode);self.assertEqual(installed/'PocketGame.exe',Path(target.read_text('utf-8-sig')))
    def test_update_preserves_prior_version_and_existing_local_save(self):
        self.manifest(self.archive());self.install()
        old=(self.home/'installed.json').read_text()
        # Installer does not own or delete any save directory.
        save=self.home/'存档'/'slot1.json';save.parent.mkdir();save.write_text('{"player":"friend-A","progress":42}')
        self.manifest(self.archive({'changed.txt':b'new'}),'0.0.2');self.install()
        self.assertEqual('{"player":"friend-A","progress":42}',save.read_text())
        self.assertTrue((self.home/json.loads(old)['directory']/'PocketGame.exe').exists())
        self.assertEqual('0.0.2',json.loads((self.home/'installed.json').read_text())['version'])
    def test_checksum_failure_keeps_current_pointer_and_save(self):
        self.manifest(self.archive());self.install();old=(self.home/'installed.json').read_bytes()
        self.manifest(self.archive(),'0.0.2',sha256='0'*64)
        self.assertIn('SHA256',self.install(1));self.assertEqual(old,(self.home/'installed.json').read_bytes())
    def test_incomplete_download_never_publishes(self):
        content=self.archive();self.manifest(content,size=len(content)+7)
        self.install(1);self.assertFalse((self.home/'installed.json').exists())
    def test_zip_traversal_and_personal_save_packages_are_rejected(self):
        for path in ('../escape.txt','data/../../escape.txt','data/slot1.json'):
            self.manifest(self.archive({path:b'forbidden'}));self.install(1)
            self.assertFalse((self.home/'installed.json').exists())
            self.assertFalse((self.path/'escape.txt').exists())
    def test_missing_game_data_never_publishes(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as f:f.writestr('PocketGame.exe',b'test')
        self.manifest(stream.getvalue());self.install(1)
        self.assertFalse((self.home/'installed.json').exists())
    def test_fallback_moves_from_failed_mirror_to_next_verified_source(self):
        # Compile a harness against production code, replacing only mirror hosts.
        source=self.path/'Harness.cs';binary=self.path/'Harness.exe'
        source.write_text('''using System; class Harness { static int Main(string[] a) { try { PocketClient.Mirrors[0]=a[0]+"/fail/";PocketClient.Mirrors[1]=a[0]+"/ok/"; var c=new PocketClient(a[1]);c.Install(c.Latest(a[0]+"/manifest.json"));return 0;} catch {return 1;} } }''')
        framework=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        refs=['System.Windows.Forms','System.Drawing','System.Web.Extensions','System.IO.Compression','System.IO.Compression.FileSystem','Microsoft.CSharp']
        subprocess.run([str(framework),'/nologo','/codepage:65001','/main:Harness','/out:'+str(binary),*['/reference:'+r+'.dll' for r in refs],str(ROOT/'native/Downloader.cs'),str(source)],check=True)
        content=self.archive();self.manifest(content,asset_url='https://github.com/example/project/releases/download/0/game.zip')
        self.server.files['/ok/https://github.com/example/project/releases/download/0/game.zip']=content
        p=subprocess.run([str(binary),self.url,str(self.home)],timeout=15)
        self.assertEqual(0,p.returncode)
        self.assertTrue(any(p.startswith('/fail/') for p in self.server.requests))
        self.assertTrue(any(p.startswith('/ok/') for p in self.server.requests))
        self.assertTrue((self.home/'installed.json').exists())

    def test_folder_selection_remembers_install_target_and_preserves_old_files(self):
        source=self.path/'FolderHarness.cs';binary=self.path/'FolderHarness.exe'
        source.write_text('''using System;using System.IO;using System.Reflection;using System.Windows.Forms;
class FolderHarness {
 static void Check(bool value,string message){if(!value)throw new Exception(message);}
 [STAThread] static int Main(string[] a) {try {
  string old=Path.Combine(a[0],"old"),selected=Path.Combine(a[0],"selected-game"),settings=Path.Combine(a[0],"settings.json");
  Directory.CreateDirectory(old);File.WriteAllText(Path.Combine(old,"keep.txt"),"old version");
  using(var form=new DownloaderForm(old,settings)) {
   form.SelectInstallRoot(selected);
   Check(PocketInstallLocation.Read(settings,old)==selected,"selection was not remembered");
   var client=(PocketClient)typeof(DownloaderForm).GetField("client",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(form);
   Check(client.Root==selected,"form retained old client");
   var hiddenHandle=form.Handle;
   client.Install(client.Latest(a[1]));
   Check(File.Exists(Path.Combine(selected,"installed.json")),"installed outside selection");
   Check(!File.Exists(Path.Combine(old,"installed.json")),"old install changed");
   Check(File.ReadAllText(Path.Combine(old,"keep.txt"))=="old version","old files lost");
   typeof(DownloaderForm).GetField("busy",BindingFlags.NonPublic|BindingFlags.Instance).SetValue(form,true);
   bool refused=false;try{form.SelectInstallRoot(old);}catch(InvalidOperationException){refused=true;}
   Check(refused,"folder changed during active installation");
  }
  string root=PocketInstallLocation.Read(settings,old);
  using(var reopened=new DownloaderForm(root,settings)) {
   var client=(PocketClient)typeof(DownloaderForm).GetField("client",BindingFlags.NonPublic|BindingFlags.Instance).GetValue(reopened);
   Check(client.Installed()!=null,"reopened installer lost selected game");
  }
  File.WriteAllText(settings,"invalid");Check(PocketInstallLocation.Read(settings,old)==old,"invalid settings did not fall back");
  return 0;
 }catch(Exception e){Console.Error.WriteLine(e);return 1;} }
}''',encoding='utf-8')
        framework=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        refs=['System.Windows.Forms','System.Drawing','System.Web.Extensions','System.IO.Compression','System.IO.Compression.FileSystem','Microsoft.CSharp']
        subprocess.run([str(framework),'/nologo','/codepage:65001','/main:FolderHarness','/out:'+str(binary),*['/reference:'+r+'.dll' for r in refs],str(ROOT/'native/Downloader.cs'),str(source)],check=True)
        self.manifest(self.archive())
        completed=subprocess.run([str(binary),str(self.path/'custom-folder-test'),self.url+'/manifest.json'],capture_output=True,text=True,timeout=25)
        self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests.append(self.path)
        if self.path not in self.server.files:self.send_error(503);return
        content=self.server.files[self.path]
        self.send_response(200);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
    def log_message(self,*a):pass

if __name__=='__main__':unittest.main(verbosity=2)
