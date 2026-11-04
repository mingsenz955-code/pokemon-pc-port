# 0.2.65 复审、规则纠正与朋友版下载器

复审 PR20（原 head 1d9f93d）及其依赖 PR14、15、16、18、19；在最新 main/dada019 上整合。保留全屏和逻辑输入坐标同步、原背景音乐、金币替代真实付费、进化/捕捉/页面修复。纠正此前 0.2.60 的普通药复活误改，死亡宠物只能使用复活石，指定目标的错误提示直接保留具体原因；老爸的信正文回看保留。

复审补充修复：TreasureHunt.entries 的纯查询不再通过 setdefault 修改活动状态，仅购买时创建记录。覆盖实际背包正文回看前后完整状态一致。原充值页已按本轮方案改为金币商店，相应旧测试更新为 ShopUI/ShopGoodsUI 合约；无藏宝图入口按购买页验证。旧寻宝宿主检查补齐独立存档目录，避免从当前 Windows 用户的真实存档恢复。

游戏回归 136 项通过，另寻宝端到端脚本通过。日志在本机 outputs/verification/pr20-review：fullscreen_gold_audio 10、global_layout_lottery_capture 10、single_window_flows 13、restore_followups 7、special_battle_effects 8、seen_encyclopedia 4、treasure_search 5、playtest_blockers 9、pet_recovery 7、letter_reading 2、regressions 26、ride_menu 10、inventory_interactions 16、task_progress 9。

下载器新增 7 项编译后实际执行检查：完整安装/解析/再次检查免重复下载、更新保留旧版和测试存档、校验失败不改指针、不完整下载不发布、越界与存档 ZIP 拒绝、缺数据包拒绝，以及真实 HTTP 首线路失败后使用备用线路。测试使用本地 HTTP 服务和临时文件。

朋友包由编译后的下载器实际下载、校验并解压。解压后的 Windows 程序用 friendA / friendB 两个隔离存档启动，退出码均为0，两个已有金币进度与存档文件哈希均保持不变。包内不含 slot1.json。固定本机启动器解析到0.2.65；没有关闭正在运行的旧游戏。下载器安装后另设固定入口，重复启动已安装游戏会聚焦现有进程，不同时打开两个版本写同一进度。

国内线路与公开 Release 的最终连通结果另保存在本机 outputs/verification；第三方线路可用性不等于每个国内网络均可达。完整原版剧情/所有状态天赋/演出/音频混合和全程通关仍未完成，本次未做原机逐帧验收，不宣称全系统完全还原。
