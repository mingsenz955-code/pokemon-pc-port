新版下载器可点击“选择目录”指定游戏安装位置，并记住选择。更新沿用所选位置；存档仍在当前用户 %LOCALAPPDATA%\PocketNativePC。已有旧版下载器也能更新游戏；路径选择入口由新版 PocketPC-Setup.exe 提供。

# 朋友下载、安装与自己的存档

把 `PocketPC-Setup.exe` 发给朋友即可；不需要发送源码、Python 或你的游戏目录。

1. 双击下载器，点击“下载 / 更新”。默认先使用国内访问加速线路，失败自动换线并回退 GitHub 官方源。
2. 下载器校验完整安装包后安装，点击“开始游戏”。首次安装后会创建固定“口袋妖怪”快捷方式。
3. 游戏安装在当前用户 `%LOCALAPPDATA%\PocketPCClient`；存档在当前用户 `%LOCALAPPDATA%\PocketNativePC\slot1.json`。每位朋友在自己的电脑/Windows 账户下使用自己的进度。已有本机存档直接保留；不会附带作者或其他玩家的进度。
4. 已安装后可以离线开始游戏。更新需联网，下载/校验失败保留旧版本，旧版运行中不会被强制关闭。

下载器使用 `https://gh-proxy.com/`、`https://gh-proxy.org/` 访问公开 GitHub Release；这些是第三方加速线路，并非本项目持有的国内服务器。可用性取决于各地网络，不能保证每个地区始终可达。安装包同时提供官方源。线路说明参考 [GH-Proxy 官方文档](https://gh-proxy.com/docs/github-accelerator)。

游戏是全系统复刻进行中的开发版，不是完整成品。死亡宠物只可使用复活石；普通回复药不会复活也不会误扣。背包“重要”页的老爸的信可查看原剧情全文。

## 发布新版本

先运行 `tools/build_windows.py` 构建并验证 Windows 游戏，再运行：

```powershell
.\.venv\Scripts\python.exe tools/package_friends.py 'outputs/口袋妖怪-PC移植开发版0.2.65' --version 0.2.65
```

发布 GitHub Release `v0.2.65`，附件为该目录下 `PocketPC-0.2.65-win64.zip`、`PocketPC-Setup.exe`、`pocket-release.json` 和 `SHA256SUMS.txt`。全部上传完成后再公开。下载器读取最新正式 Release 的 `pocket-release.json`，不依赖 GitHub API 查询额度。未来每次发布都要同步上传新的安装包和清单。

打包采用可执行程序、`_internal` 和原始 `data` 目录白名单，不分发开发交接记录；发现存档文件则拒绝打包。下载器校验 SHA256、大小和数据文件，拦截越界 ZIP 路径和个人存档包；先完整安装再原子切换版本指针。不会递归清理用户存档。
