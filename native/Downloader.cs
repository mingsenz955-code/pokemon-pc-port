using System;
using System.IO;
using System.Net;
using System.Text;
using System.Diagnostics;
using System.Drawing;
using System.Security.Cryptography;
using System.IO.Compression;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using System.Runtime.InteropServices;

public sealed class PocketManifest {
    public string version { get; set; }
    public string asset_url { get; set; }
    public string sha256 { get; set; }
    public long size { get; set; }
    public string executable { get; set; }
    public string directory { get; set; }
}

public sealed class PocketClient {
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr handle);
    public const string ManifestUrl = "https://github.com/mingsenz955-code/pokemon-pc-port/releases/latest/download/pocket-release.json";
    public static readonly string[] Mirrors = { "https://gh-proxy.com/", "https://gh-proxy.org/", "" };
    public readonly string Root;
    public Action<string,int> Report = delegate {};
    readonly JavaScriptSerializer json = new JavaScriptSerializer();
    public PocketClient(string root) { Root = Path.GetFullPath(root); Directory.CreateDirectory(Root); }
    public static string SaveDirectory { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PocketNativePC"); } }
    static bool Loopback(string url) { Uri u; return Uri.TryCreate(url, UriKind.Absolute, out u) && u.IsLoopback && u.Scheme == "http"; }
    static void ValidUrl(string url) { Uri u; if (!Uri.TryCreate(url,UriKind.Absolute,out u) || (u.Scheme!="https" && !Loopback(url))) throw new IOException("下载源地址无效。"); }
    static string Within(string parent, string relative) {
        string prefix=Path.GetFullPath(parent).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
        string result=Path.GetFullPath(Path.Combine(parent,relative));
        if (!result.StartsWith(prefix,StringComparison.OrdinalIgnoreCase)) throw new IOException("安装包路径超出了游戏目录。");
        return result;
    }
    IEnumerable<string> Sources(string url) {
        ValidUrl(url);
        if (Loopback(url) || !url.StartsWith("https://github.com/",StringComparison.Ordinal)) { yield return url; yield break; }
        foreach(string mirror in Mirrors) yield return mirror+url;
    }
    static HttpWebRequest Request(string url) {
        var request=(HttpWebRequest)WebRequest.Create(url);
        request.UserAgent="PocketPC-Downloader/0.2.65";
        request.Timeout=12000;request.ReadWriteTimeout=30000;request.AllowAutoRedirect=true;
        return request;
    }
    public PocketManifest Latest(string source) {
        if(source!=null && File.Exists(source)) return Validate(json.Deserialize<PocketManifest>(File.ReadAllText(source,Encoding.UTF8)));
        var failures=new List<string>();
        foreach(string url in Sources(source??ManifestUrl)) {
            try {
                Report("正在检查最新版本…",0);
                using(var response=Request(url).GetResponse()) using(var reader=new StreamReader(response.GetResponseStream(),Encoding.UTF8)) {
                    string text=reader.ReadToEnd();if(text.Length>65536)throw new IOException("版本信息过大。");
                    return Validate(json.Deserialize<PocketManifest>(text));
                }
            } catch(Exception e) { failures.Add(new Uri(url).Host+": "+e.Message); }
        }
        throw new IOException("暂时无法获取版本信息。已安装的版本仍可直接开始游戏。\r\n"+String.Join("\r\n",failures.ToArray()));
    }
    PocketManifest Validate(PocketManifest m) {
        if(m==null || String.IsNullOrEmpty(m.version) || !System.Text.RegularExpressions.Regex.IsMatch(m.version,@"^\d+\.\d+\.\d+$")
            || m.size<=0 || m.size>2000000000 || String.IsNullOrEmpty(m.sha256) || !System.Text.RegularExpressions.Regex.IsMatch(m.sha256,@"^[0-9a-fA-F]{64}$")
            || String.IsNullOrEmpty(m.executable) || !m.executable.EndsWith(".exe",StringComparison.OrdinalIgnoreCase)) throw new IOException("版本信息不完整。");
        ValidUrl(m.asset_url);Within(Root,m.executable);return m;
    }
    public PocketManifest Installed() {
        try {
            var m=json.Deserialize<PocketManifest>(File.ReadAllText(Path.Combine(Root,"installed.json"),Encoding.UTF8));
            string folder=Within(Root,m.directory);
            if(File.Exists(Within(folder,m.executable)) && File.Exists(Path.Combine(folder,"data","tables.json")))return m;
        } catch {} return null;
    }
    static string Hash(string path) {
        using(var hash=SHA256.Create()) using(var input=File.OpenRead(path))return BitConverter.ToString(hash.ComputeHash(input)).Replace("-","").ToLowerInvariant();
    }
    public PocketManifest Install(PocketManifest latest) {
        FileStream guard;
        try { guard=new FileStream(Path.Combine(Root,"install.lock"),FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None); }
        catch(IOException) { throw new IOException("另一个下载器正在安装，请稍后再试。"); }
        using(guard) return InstallCore(latest);
    }
    PocketManifest InstallCore(PocketManifest latest) {
        Validate(latest);
        var current=Installed();
        if(current!=null && current.version==latest.version && current.sha256==latest.sha256) { Report("已安装最新版 "+current.version,100);return current; }
        string cache=Path.Combine(Root,"cache");Directory.CreateDirectory(cache);
        string zip=Path.Combine(cache,"download-"+Guid.NewGuid().ToString("N")+".zip");
        string staging=Path.Combine(Root,"staging-"+Guid.NewGuid().ToString("N"));
        try {
            bool downloaded=false;var failures=new List<string>();
            foreach(string url in Sources(latest.asset_url)) {
                try {
                    Report("正在连接下载线路："+new Uri(url).Host,2);
                    using(var response=Request(url).GetResponse()) using(var input=response.GetResponseStream()) using(var output=File.Create(zip)) {
                        byte[] buffer=new byte[1024*256];long total=0;int read;
                        while((read=input.Read(buffer,0,buffer.Length))>0) {
                            total+=read;if(total>latest.size)throw new IOException("文件大小与版本信息不一致。");
                            output.Write(buffer,0,read);
                            Report("下载 "+(total/1048576.0).ToString("F1")+" / "+(latest.size/1048576.0).ToString("F1")+" MB",5+(int)(total*75/latest.size));
                        }
                        if(total!=latest.size)throw new IOException("下载未完成。");
                    }
                    Report("正在校验安装包…",82);
                    if(!String.Equals(Hash(zip),latest.sha256,StringComparison.OrdinalIgnoreCase))throw new IOException("SHA256 校验失败，已拒绝安装。");
                    downloaded=true;break;
                } catch(Exception e) { failures.Add(new Uri(url).Host+": "+e.Message); }
            }
            if(!downloaded)throw new IOException("下载失败，原版本和存档已保留。\r\n"+String.Join("\r\n",failures.ToArray()));
            Directory.CreateDirectory(staging);Report("校验通过，正在安装…",88);
            using(var archive=ZipFile.OpenRead(zip)) {
                long unpacked=0;
                if(archive.Entries.Count>30000)throw new IOException("安装包文件数量异常。");
                foreach(var entry in archive.Entries) {
                    string name=entry.FullName.Replace('\\','/');
                    if(name.StartsWith("/") || name.Contains(":") || name.Split('/').Length>30)throw new IOException("安装包路径无效。");
                    foreach(string part in name.Split('/'))if(part=="..")throw new IOException("安装包路径无效。");
                    string destination=Within(staging,name);
                    unpacked+=entry.Length;if(unpacked>1000000000)throw new IOException("安装包解压大小异常。");
                    if(name.EndsWith("/")){Directory.CreateDirectory(destination);continue;}
                    string filename=Path.GetFileName(destination).ToLowerInvariant();
                    if(filename=="slot1.json" || filename=="preview-position.json" || filename=="save.json")throw new IOException("安装包包含个人存档，已拒绝安装。");
                    Directory.CreateDirectory(Path.GetDirectoryName(destination));entry.ExtractToFile(destination,false);
                }
            }
            if(!File.Exists(Within(staging,latest.executable)) || !File.Exists(Path.Combine(staging,"data","tables.json")))throw new IOException("安装包缺少游戏程序或原版数据。");
            string versions=Path.Combine(Root,"versions");Directory.CreateDirectory(versions);
            string relative=Path.Combine("versions",latest.version+"-"+Guid.NewGuid().ToString("N").Substring(0,8));
            Directory.Move(staging,Within(Root,relative));latest.directory=relative;
            string pointer=Path.Combine(Root,"installed.json"),temp=pointer+".tmp";
            File.WriteAllText(temp,json.Serialize(latest),new UTF8Encoding(false));
            if(File.Exists(pointer)) File.Replace(temp,pointer,null);else File.Move(temp,pointer);
            Report("安装完成 "+latest.version+"，可以开始游戏。",100);return latest;
        } finally {
            if(File.Exists(zip))File.Delete(zip);
            if(Directory.Exists(staging) && staging.StartsWith(Root.TrimEnd('\\')+"\\",StringComparison.OrdinalIgnoreCase))Directory.Delete(staging,true);
        }
    }
    public string Resolve() {
        var current=Installed();if(current==null)throw new IOException("请先下载游戏。");
        return Within(Within(Root,current.directory),current.executable);
    }
    public void Play() {
        string executable=Resolve();
        string versions=Path.Combine(Root,"versions")+Path.DirectorySeparatorChar;
        foreach(var process in Process.GetProcesses()) {
            try {
                if(process.MainModule.FileName.StartsWith(versions,StringComparison.OrdinalIgnoreCase)) {
                    SetForegroundWindow(process.MainWindowHandle);return;
                }
            } catch {} finally { process.Dispose(); }
        }
        var info=new ProcessStartInfo(executable){WorkingDirectory=Path.GetDirectoryName(executable),UseShellExecute=false};
        // Normal releases use the current Windows user's own persistent save.
        info.EnvironmentVariables.Remove("POCKET_NATIVE_SAVE_DIR");
        Process.Start(info);
    }
    public void Shortcut() {
        string destination=Path.Combine(Root,"口袋妖怪下载器.exe");
        if(!String.Equals(Path.GetFullPath(Application.ExecutablePath),destination,StringComparison.OrdinalIgnoreCase))File.Copy(Application.ExecutablePath,destination,true);
        Type type=Type.GetTypeFromProgID("WScript.Shell");dynamic shell=Activator.CreateInstance(type);
        dynamic link=shell.CreateShortcut(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),"口袋妖怪.lnk"));
        link.TargetPath=destination;link.WorkingDirectory=Root;link.Description="口袋妖怪：下载、更新和开始游戏";link.Save();
    }
}

public sealed class DownloaderForm : Form {
    readonly PocketClient client;
    readonly Label status=new Label(), hint=new Label();
    readonly ProgressBar progress=new ProgressBar();
    readonly Button install=new Button(),play=new Button(),saves=new Button();
    bool busy;
    public DownloaderForm(string root) {
        client=new PocketClient(root);Text="口袋妖怪 · 下载与启动";ClientSize=new Size(610,270);
        FormBorderStyle=FormBorderStyle.FixedSingle;MaximizeBox=false;StartPosition=FormStartPosition.CenterScreen;
        Font=new Font("Microsoft YaHei UI",10);
        hint.Text="首次下载后可离线游玩。更新保留本机存档。\r\n默认使用国内加速线路，失败会自动换线。";hint.SetBounds(24,20,560,56);
        status.Text=client.Installed()==null?"尚未安装，点击下载。":"已安装 "+client.Installed().version;status.SetBounds(24,88,560,42);
        progress.SetBounds(24,139,560,22);
        install.Text="下载 / 更新";install.SetBounds(24,181,174,42);
        play.Text="开始游戏";play.SetBounds(216,181,174,42);play.Enabled=client.Installed()!=null;
        saves.Text="打开我的存档";saves.SetBounds(408,181,174,42);
        Controls.AddRange(new Control[]{hint,status,progress,install,play,saves});
        client.Report=(text,value)=> { if(IsDisposed)return;BeginInvoke(new Action(()=>{status.Text=text;progress.Value=Math.Max(0,Math.Min(100,value));})); };
        install.Click+=async delegate {
            busy=true;install.Enabled=play.Enabled=false;
            try { await Task.Run(()=>client.Install(client.Latest(null)));client.Shortcut(); }
            catch(Exception e){MessageBox.Show(this,e.Message,"下载提示",MessageBoxButtons.OK,MessageBoxIcon.Information);}
            finally {busy=false;install.Enabled=true;play.Enabled=client.Installed()!=null;}
        };
        play.Click+=delegate{try{client.Play();}catch(Exception e){MessageBox.Show(this,e.Message);}};
        saves.Click+=delegate{Directory.CreateDirectory(PocketClient.SaveDirectory);Process.Start("explorer.exe",PocketClient.SaveDirectory);};
        FormClosing+=delegate(object sender,FormClosingEventArgs e){if(busy){e.Cancel=true;status.Text="正在下载或安装，请等待完成后再关闭。";}};
    }
}

internal static class Downloader {
    static string Option(string[] args,string key) {int i=Array.IndexOf(args,key);return i>=0 && i+1<args.Length?args[i+1]:null;}
    [STAThread] static int Main(string[] args) {
        ServicePointManager.SecurityProtocol=(SecurityProtocolType)3072;
        string root=Option(args,"--root")??Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"PocketPCClient");
        string result=Option(args,"--result");
        try {
            var client=new PocketClient(root);
            if(Array.IndexOf(args,"--install-only")>=0) {
                var manifest=client.Install(client.Latest(Option(args,"--manifest")));
                if(result!=null)File.WriteAllText(result,new JavaScriptSerializer().Serialize(manifest),Encoding.UTF8);
                return 0;
            }
            if(Array.IndexOf(args,"--resolve")>=0) {File.WriteAllText(Option(args,"--resolve"),client.Resolve(),Encoding.UTF8);return 0;}
            Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new DownloaderForm(root));return 0;
        } catch(Exception e) {
            if(result!=null)File.WriteAllText(result,e.Message,Encoding.UTF8);
            else if(args.Length==0)MessageBox.Show(e.Message,"口袋妖怪下载器");
            return 1;
        }
    }
}
