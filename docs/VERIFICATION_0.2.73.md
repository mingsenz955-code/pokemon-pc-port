# 0.2.73 购买提示、坐骑绘制与安装目录

原版证据：BuyItemEvent::handle 0x2e9b50 经 sendAddDropItemsEvent 0x2e9a28 发放物品；RewardTipsUiLayer::showRewardItemTip 0x3a9040 获取 DropItemDataManager::getDescription。createUiLayer 0x3a8dac 加载 TipsUiNode.csb；showRewardItemTip 0x3a91cc / 0x3a91d6 分别 DelayTime(.5) / FadeOut(.5)，Text.json 的 dropitemTips3 为“获得道具：”。本次普通商店、卷轴、材料及战斗商店确认成功后显示名称和实际数量的短暂原资源提示，不增加确认按钮，不在取消/失败时提示成功，不推进柜员对话。

坐骑根因：NativeGame.player_image 在文件中定义两次，后定义只绘制步行人物，覆盖了原骑乘分支。合并为一处，保留剧情朝向和步行逻辑，骑乘使用 Ride.filePath 原资源及 stand/walk 四方向动画，镜像同步翻转脚点。骑乘权限、地图、地形和自动切换沿用原 Mounts 规则，不给玩家额外解锁。

下载器增加“游戏安装目录”与“选择目录”按钮；用 FolderBrowserDialog 选择目标并保存到当前用户 PocketPCClient/download-location.json。再次启动读取选择。下载中禁用改目录；切换时不移动/删除旧文件，选择已有安装可继续启动。CLI --root 继续优先，不写测试目录到真实用户设置。玩家存档仍在当前用户 PocketNativePC。

验证：check_purchase_mount_render 覆盖实际 HUD 点击后的坐骑画面（修复前会失败）、移动不掉坐骑、五种坐骑四方向和走路原图，以及真实三种柜员脚本的数量/扣款/提示/失败/取消。check_downloader 包含原7项安装/更新/校验/安全回滚及新路径选择后安装、重开记忆、旧目录保留、下载中禁止切换的生产代码检查。

本轮通过：购买与真实坐骑/页面7项，下载器8项（含生产 WinForms 选目录后实际安装），原骑乘菜单、战斗商店、柜员孵化、抽宠/帧缓存回归。Windows 打包启动和固定启动器解析均确认0.2.73。测试使用隔离存档。
