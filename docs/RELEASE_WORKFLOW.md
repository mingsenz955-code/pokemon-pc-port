# 固定启动入口（用户明确要求）

桌面只保留“口袋妖怪”快捷方式，不再为每次发布新增带版本号的快捷方式。
不要删除旧游戏包或存档。旧版本快捷方式已移到 outputs/桌面快捷方式备份。

从仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe tools\build_windows.py
```

构建、资源与文档复制完成后，脚本才会更新
outputs/口袋妖怪启动器/current-release.txt。稳定启动器为同目录的口袋妖怪.exe。
只指向最近一次完整构建，不按文件名或修改时间猜测，不启动正在构建的目录。
本启动器选择本机最新完整版本，不冒充已实现联网下载更新。

首次安装或恢复桌面入口：

```powershell
.\.venv\Scripts\python.exe tools\install_launcher.py outputs\口袋妖怪-PC移植开发版0.2.45 --desktop
```

后续只需正常构建，无需重复创建桌面快捷方式。修改启动器时会重新编译 native/Launcher.cs，
未改变启动器源码时只原子切换版本指针。启动器不依赖项目 Python，不读写存档。

旧口袋妖怪-pr1-review 工作树的未提交源码另存于 GitHub 的
codex/archive-pre-deepseek 分支；基线较旧，不能整体覆盖当前 main。主线仍是继续复原的依据。
