using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

internal static class Launcher {
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr handle);
    [STAThread] private static int Main(string[] args) {
        try {
            string home = AppDomain.CurrentDomain.BaseDirectory;
            string root = Path.GetFullPath(Path.Combine(home, "..")).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string relative = File.ReadAllText(Path.Combine(home, "current-release.txt"), Encoding.UTF8).Trim();
            string target = Path.GetFullPath(Path.Combine(home, relative));
            if (!target.StartsWith(root, StringComparison.OrdinalIgnoreCase) || !File.Exists(target)
                || !File.Exists(Path.Combine(Path.GetDirectoryName(target), "data", "tables.json")))
                throw new IOException("未找到完整的游戏版本，请重新完成更新。");
            if (args.Length == 2 && args[0] == "--resolve") {
                File.WriteAllText(args[1], target, new UTF8Encoding(false));
                return 0;
            }
            foreach (Process process in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(target))) {
                try {
                    if (String.Equals(process.MainModule.FileName, target, StringComparison.OrdinalIgnoreCase)) {
                        SetForegroundWindow(process.MainWindowHandle);
                        return 0;
                    }
                } catch { }
            }
            Process.Start(new ProcessStartInfo(target) {
                WorkingDirectory = Path.GetDirectoryName(target), UseShellExecute = false
            });
            return 0;
        } catch (Exception error) {
            if (args.Length == 2 && args[0] == "--resolve") return 1;
            MessageBox.Show(error.Message, "口袋妖怪", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return 1;
        }
    }
}
