# 1.20.4 规则核对记录

当前不是完整复刻。原布局可读不等于对应玩法完成；Python 测试通过也不等于原版逐帧一致。

## 核对基准

恢复的 APK：MD5 `11423b7795ff53819f8f42d65b76455d`，SHA256
`df9a3d1a9832c3a13dc8981013ef252621a62b8852d5422e1b6c1d0425280508`。
恢复审计见本地 `original-1.20.4/recovery-audit.json`。83 张表、431 张地图配置、
315 种宠物、1685 个剧情脚本、175 个 UI 布局、1687 张 PNG 已恢复。
下列地址为同一 APK 的 ARM 库虚拟地址，运行时不加载该库。

| 系统 | 原始证据 | 本次实现与验证边界 |
| --- | --- | --- |
| 数值公式 | 独立 ARM 公式，`tools/check_original_formulas.py` | 16 个公式各 200 组对照通过；不能推广为整套战斗一致 |
| 随机属性区间 | `getFloatValueWithIntervalList` 0x2ba826 | 取消一位小数取整，使用 binary32 运算；受控 RNG 输入下 520 组原指令对照一致。全局 RNG 序列尚未复刻 |
| 抽宠 | `LuckyDrawEvent::handle` 0x2ec124、LuckyDraw、Store 70601–70603 | 徽章 10/25/50，单/单/三抽，三抽第一只稀有池；免费冷却持久化。原随机数序列与联网时间未复刻 |
| 轮盘 | `refreshItems` 0x32356c、LuckyRoulette | 六组共 12 格，100 次成对换位；抽奖扣券 220009，刷新扣徽章。跨日按本地 UTC+8，整数权重解析还需进一步对照 |
| 卡牌 | `mathScore` 0x35b9dc、`checkGameEnd` 0x35d11c、`getNewCard` 0x35d240、`otherPlayCard` 0x35cd88、奖励事件 0x2eaa3c/0x2eabf4 | 五张牌、五轮比星、平局不计分、不可逆领先提前结束；对手随机选未用牌；券 220008；胜利按表随机一份奖励。牌局及待领奖状态持久化。领取按钮为移植版操作，未复刻原发牌动画 |
| 训练 | `PetDataManager` 训练处理，`research/cost-and-training.txt` | 参数指向五项训练；单项 1000、总计 2000，增量截断；无效果不扣道具 |
| 突破 | `research/breakthrough.txt`、PetTuPo | 按下一阶材料及货币扣费，提升后恢复；材料不足整笔回滚 |
| 回复 | `addAttributePercent` 0x3260e0、PetItem | 固定/百分比/复活分开处理；整数百分比向零截断；NPC 消耗自己的有限道具 |
| 技能师 | `SkillLearnEvent::handle` 0x2ede90、`confirmLearn` 0x3b6868、`skillListViewInit` 0x3b832c、`isSkillFull` 0x3255fc、`isTalentLearnedFull` 0x325612 | 本物种主动技能付费学习、四槽替换；卷轴主动技能与两槽后天被动技能。被动效果仍受战斗实现范围限制，升级选技弹窗待接入 |
| 孵化 | `HatchPetEvent` 0x2eb90c、`isConditionIsReached` 0x322654、`createPetWithHatchId` 0x31bf44、列表循环 0x36c410 | 10 个孵化位，经验加材料或金币直接孵化；固定/随机属性、取回蛋与领取宠物、满仓保留待领奖。经验转换公式已对照，但战斗经验总额算法仍需继续核对，活动特殊免费渠道未接入 |
| 护士治疗 | `confirmButtonRespond` 0x365238、`cureAllPets` 0x329fe4 | 医疗卡 70201 免费，否则优先扣免费医疗 700006 一次，再否则金币 100；只治疗携带宠物 |
| 普通地图宝箱 | `VillageChestControler::open` 0x2d65dc、VillageChest | 原表整批奖励、永久开启状态与 opened 图像 |
| 藏宝图 | `PlayerDataManager::addTreasure` 0x32fb38、`TreasureDataManager::initData` 0x33360c、`TreasureMapUILayer::useButtonRespond` 0x3c12b8 | 购买按 `Treasure.price/moneyType` 扣货币并给予 `itemId/itemCount`；从 `chestPoss` 随机 `TChestPos` 生成隐藏宝箱；UI 24 的 `use_Button` 只在已有藏宝图时扣 1 枚 220007 并显现，不会把购买混进使用按钮；宝箱作为 `TChest.spriteId` 地图对象，靠近交互按 `TChest` 概率/数量抽奖并移除。UI 37/38 为原版 `TreasureBuyConfirmUI`/`TreasureGetTipUI` 的内部页面。`tools/check_treasure.py` 覆盖原子扣费、库存、随机坐标、重复开启、UI 24/37/38、真实 `pEventTalk50319` 的 `closeui yes` 分支、真实地图 actor 和交互 |
| 任务 | `MainTaskItemTalk::acceptTask` 0x300264、`PlotEventItemSubmitTask::begin` 0x2f5a04 | 主线对话任务接受即就绪；mtask 为提交当前主线的标志，不是任务编号；收集、捕捉、战斗、多条件计数。支线类型 8/9 待接入 |
| 任务指引 | MainTask/BranchTask 条件字段、VillageMap.exitIds、TMX 出口对象、eventLayer 区域对象 | conditionType 1 按区域 ID 拆地图并进入区域；3 的第三字段是捕捉地图；4 查 NPC 对象；5 直达地图。跨图路线从 TMX `toExit` 与目标地图 `exitIds` 建图，逐格 BFS，移动调用宿主 `move_to` 以保留坐骑地形限制。已修正出口 `face` 落点算反导致负坐标/墙内落点的问题。`tools/check_guide.py` 核对 8 个主线目标、真实区域移动、NPC 接近和一次出口切换 |
| 坐骑地形通行 | `compareRideCollidesAble` 0x32ad48、`compareRideMapTypeAble` 0x32ad88、`compareRidesCollidesAble` 0x32ae44、`onRideWithCollideTile` 0x32adc8、`VillagePlayerControler::rideProcess` 0x2e1108、`setMoveSpeed` 0x2e0b5c | 读取 Ride.collidesAble 白名单及 mapTypeDisable 黑名单；步行仅 0；当前坐骑优先，其次已获得的 kind=2/3 自动换乘；飞行需手动骑乘。陆行鸟/护城龙 0、乘龙 2、芭叶虫 0/3、飞龙 0/1/2/3；所有坐骑禁地图类型 1，飞龙额外禁类型 3。已获得宠物按 Ride.petId 关联解锁，旧移植存档从获得图鉴补回。试乘不写入永久所有权。基础速度 320，乘以 speed/100。原骨骼静态站立图接入显示；完整骑乘动画尚未复刻 |
| 树/岩障碍 | TMX `spriteTileLayer` 的 `obsType` 属性、`Ride.obstacleAble`、`wait type=3`、MainTask 129/132、BranchTask 301/4101/6501/9301/14701 等 conditionType=6 | 护城龙 `obstacleAble=2` 破坏岩石，陆行鸟 `obstacleAble=1` 砍伐树木；障碍在步行时真实阻挡，使用对应坐骑进入时移除该 `spriteTileLayer` 对象、刷新背景并写入 `GameState.removed_obstacles`；原 `conditionType=6` 任务按 obsType 1/2 计数。月桂叶 `collidesAble` 含 3 穿越荆棘，炼狱龙 0/1/2/3 跨越全部障碍，乘龙 2 渡水。坐骑商人试乘脚本的 `wait type=3` 在破坏对应障碍后继续。全量地图解析到 143 张含障碍地图、10,937 个障碍对象（树 9,562、岩 1,375）。`tools/check_obstacles.py` 覆盖真实地图解析、阻挡、能力匹配、对象移除、渲染变化、任务计数、试乘 wait 和存读档。破坏时按 obsType 播放 22 tick 木屑/石屑与尘土表现；这是移植版表现层，原版粒子/点击动作仍未复刻 |
| 竞技场 | `DataManager::fightWithArenaNpc` 0x31eabd、`ArenaDataManager` 0x319679、`ArenaInfoUILayer` 0x349409；事件 740299/740399 | 事件固定为 `openui 10 par1=<arenaId> par2=<1/2>` → `closeui yes` → `fight type=3 npcid=<arenaId>`；yes 分支不是直接发奖。已按原 `ArenaNpc.rankInterval` 选择当前排名上一位对手，按 `ArenaNpcPet` + `petLevel` 生成 6 只真实战斗宠物；首次/离开后收 1 枚 700002，连胜免费；胜利排名 -1、Boss 授予 `ArenaTitle`、发放 `dropItemIds/dropItemCounts`；失败重置连胜。`tools/check_arena.py` 覆盖纯逻辑、旧存档补字段、真实 UI 与完整事件往返 |
| 无限竞技场 | `Formula_InfiniteArenaHonorReward` 0x2b5a46（4 字节 ARM `movs r0,#1; bx lr`）、`IArenaNpc`/`IArenaNpcPet`、`InfiniteArenaUI`；事件 790101/7901501/30523 | 原版事件：`openui 20 par1=1` → `closeui yes` → `fight {type:5,npcid:1}`；`npcid` 是 IArena 编号而非层数。按 `InfiniteArena` 扣 1 枚 700002；`infinite_level` 选择 Lv.30/60/90/120/121 的 IArenaNpc，生成 6 只 IArenaNpcPet；胜利荣誉 +1（公式恒返回 1）并入账 700007，层数递增封顶；失败把 `arenas['1']` 复位而保留层数/荣誉。UI 19/20/21 与商店已接入；`tools/check_infinite_arena.py` 覆盖工厂、真实 UI、事件往返和旧存档 |
| 战斗动画反馈 | `BattleUI` 事件队列、`battle.py` 的 `attack/skill/damage` 事件 | `BattleUI._capture_events` 读取真实战斗事件，不修改伤害/HP；按攻击方突进、受击方抖动/闪红、伤害值上浮、HP 条八分之一缓动，26 tick 后结束。`tools/check_battle_animation.py` 验证像素变化、HP 实际变化和时间线结束。仍不是原版 Spine 骨骼时间轴/粒子/音效的完整复刻 |
| 宠物合体 | `DataManager::getHeTiData` 0x31dd50、`createHeTiPet` 0x31dd88 | 配方键为 `petA*1000000+petB`，顺序敏感；结果等级 1，五项 variation/growth 取两亲整数平均，再按结果宠物表生成天赋/技能并重算品质；材料与双亲原子移除。`tools/check_fusion.py` 覆盖正常、反向拒绝、材料不足 |
| 宠物融合 | `PlayerDataManager::petMerge` 0x3306d2、`PetDataManager::petMerge` 0x327218 | 按基础宠物品质选择 PetMerge 配方，材料须同品质且达到等级；`attAddition` 加到五项 variation 和五项 growth，重算品质/属性；扣货币并移除材料。`tools/check_merge.py` 覆盖成功与原子失败 |
| 战斗点击与菜单 | `mineMenuPanelRespond` 0x355878、`enemyMenuPanelRespond` 0x3558e4、`energyButtonRespond` 0x355950、`hpButtonRespond` 0x3559a0、`showButtonMenu` 0x3544d0、`showSkillMenu` 0x354a7c；BattleMainUI 的 mine/enemyMenuPos_Panel | 我方区域打开补给菜单，敌方区域打开技能菜单；补蓝筛能量、补血筛生命。菜单使用原 panel 中心；修复命中完整节点路径导致短名动作无法分发，优先命中小的说明按钮，原 SkillInfoNode 展示原表说明。原版发招/特效/结果页、强制引导与菜单显示状态仍未完整对照 |
| 赛宠嘉年华 | `Formula_GetRunningPetWinProbability` 0x2b5db4、`RunningPetReadyUILayer::getWinnerIndex` 0x3abf78、`handleResult` 0x3abfd0、`getBetMaxMedalCount` 0x3ab664、`RunningPetUILayer::getWinnerRunTime` 0x3ad1e0、`getRandomRunningPetRunTime` 0x3add04、`gameDone` 0x3ad9a8；RunningPet/MedalShop 801 | 胜率 `1/(1.2+倍率/3)`；先掷 1–100，命中则所选宠物夺冠，否则随机一只其他宠物；中奖结算 `int(押注*(倍率-1))`，失败扣押注，货币 700008；默认 10、上限 `min(持有,9999)`，左右按 10/上限循环；冠军时间 8.0 秒，其他选手按 `101–105%` 与 `110–130%` 双界随机；UI 39–42 用四只 `zq1–7` 原始骨架。MedalShop 801 = 1 徽章换 100 奖牌。`tools/check_running_pet.py` 覆盖公式、输赢原子结算、左右循环、存档、UI 39–43、8 秒时间轴转结果页 |
| 连续登录 | `ContinuousLogin` 7 行、`PlayerDataManager::getContinuousLoginDays` 0x3291c5、`setContinuousLoginDays` 0x3291d9、`ContinuousLoginUILayer::getButtonRespond` 0x36161f | 第 1–7 天原奖励依次为大师球×1、徽章×5、神秘蛋×1、220009×10、220008×10、240012×1、280002×20；同一天不可重复领取；超过一天未登录回到第 1 天；领取与库存写入同一事务。`tools/check_continuous_login.py` 覆盖 7 天表、断签、重复领取、原子失败、真实 UI 12 |
| 道馆试练 | 事件 `pEvent590199`/`pEvent5901012`、`Budokan` 5 行、`BudokanNpc` 100 行、`BudokanNpcPet` 335 行；`fight type=4 npcid=<budokanId>` | `openui 15 par1=<道馆>` 后 `closeui yes` 才进入战斗，`type=4` 的 `npcid` 是道馆编号而非 `NpcFight` 编号。每个道馆按 `Budokan.npcIds` 顺序挑战二十位 `BudokanNpc`，队伍逐只读取 `BudokanNpcPet` 的等级/技能/天赋/属性；胜利推进 `GameState.budokans`，失败不推进；第二十位按原表 `dropItemIds/dropItemCounts` 发放高级进化材料。UI 15 目前用原布局标题和动态列表，尚未逐帧复刻原版动态 item 动画。`tools/check_budokan.py` 覆盖 20 场顺序、越序拒绝、失败不推进、最终材料只发一次、存档和真实 `openui 15 → closeui yes → fight type=4` 往返 |
| 每日任务 | `DailyTask` 8 行、`DailyTaskRefreshEvent::handle` 0x2f08f9、`DailyTaskItem::process` 0x2fd727、`addReachCount` 0x2fd743、`TaskUI` 的 `tag_1/2/3` 与 `receive_Button` | 七项日常条件为捕捉 1、NPC 战斗 3、聊天 10、购买 3、轮盘 1、卡牌获胜 1、赛宠获胜 3；第八行“全能训练”需七项全部完成。完成与领取分离，同日不可重复领取，奖励按 `rewardIds/rewardCounts` 原表原子发放；本地日期变化清空计数与领取记录。TaskUI 的 `tag_1=main/tag_2=branch/tag_3=daily` 三页已分别显示 MainTask、BranchTask、DailyTask 的原表名称/描述/进度/奖励；主线和支线奖励只在目标 NPC 的 `submittask` 事件发放，界面按钮不会远程伪造领取。服务器时间校准和原版逐帧 item 动画仍未复刻。`tools/check_daily_tasks.py` 覆盖八行表、七类计数、上限、重置、奖励精确值、存档、购买/轮盘钩子、三页 tab、主线不伪造领取与 TaskUI 每日领取；`tools/check_task_ui.py` 用真实 MainTask 129 / BranchTask 4101 检查三页名称、进度、奖励、可提交状态及主支线不远程发奖 |

| 支线接受 | `AcceptBTaskUI`、`accept_Button`/`close_Button`、`accepttask` 脚本请求 | 原版 `accepttask` 不再使用系统 messagebox，而是读取 AcceptBTaskUI 布局，写入任务名与描述，保留原 `accept_Button`/`close_Button` 命中区；接受/关闭分别恢复脚本一次，窗口关闭按拒绝处理。接受后的任务状态、计数、奖励仍由原事件 `taskstate`/`submittask` 驱动。`tools/check_accept_task.py` 覆盖原按钮命中区存在、接受/拒绝只恢复一次、窗口清理 |

| 成就 | `Achievement` 142 行、`AchievementUI`、`AchievementItemUI`、`conditionType` 1–24 | `AchievementUI` 的 142 行全部列出；当前对 16 类本地可验证条件给出进度：1 品质/星级宠物数量、2 指定 `Item.type` 的持有种类、3 野外捕获、4 孵化、5 进化、7 骑乘、8 银行宠物数、11 总战斗胜利、12 破障、13 NPC 谈话、14 村庄宝箱、15 到达地图、17 支线完成、22 游戏时间、23 存档次数、24 图鉴中指定 `Pet.kind` 的收集数。可领取时按原 `rewardIds/rewardCounts` 原子发奖并累计 `score`；其余条件类型显示“未接入”，拒绝领取，不伪造进度。原版 `AchievementItemUI` 逐行动画和其余 7 类条件尚未接入。`tools/check_achievements.py` 覆盖 142 行、16 类进度、重复领取拒绝、未接入拒绝、UI 打开/关闭 |

| 战斗商店 | `BattleMainUI.battleShop_Button`、`BattleShopUI`、`BattleShop` 12 行 | 战斗 HUD 左上角原版 `battleShop_Button` 现在真实可点，打开 `BattleShopUI`；商品按原表价格/货币购买，进入背包，购买和关闭按钮均有实际命令。`tools/check_battle_shop.py` 覆盖原按钮命中、打开、购买扣款/入库、关闭；原版商品列表逐行动画仍未复刻 |

| 剧情/地图覆盖 | 1,685 个 `pEvent*.json`、461 个触发器、431 张 `VillageMap` | `tools/check_event_coverage.py` 逐脚本解析原加密事件数据：36 种实际命令全部在 `EventRuntime` 的 PRESENTATION/STATE/INTERACTIVE 分派内，未知命令为 0；461 个触发器类型（tomap/toarea/toexit/talk/fightover/fight）均有宿主通知入口；431 张地图均能由 `OriginalData.load_map` 读取。该测试只证明“可解析/可加载”，不代表每条剧情分支、每个事件 UI 选择和每张地图的完整玩法都已逐帧复刻 |

| 背包 | `BagUI`、`item_ListView`、`tag_1..5_Button`、`use_Button`、`heCheng_Button`、`DebrisItem` | 背包现在打开原版 `BagUI`，五个分类页签分别过滤原 `Item.type`；列表叠加在原 `item_ListView` 区域；`use_Button` 调用 `GameState.use_item` 对选中宠物使用道具；`heCheng_Button` 对 `DebrisItem` 检查 `needCount`、原子消耗碎片并 `grant` 对应 `petId`，失败不消耗。`tools/check_bag_ui.py` 覆盖原布局/页签/动作绑定、70 个埃拉芬碎片合成和关闭；原版逐格物品图标、拖动和合成特效尚未复刻 |

## 测试和审计

- `tools/check_regressions.py`：战斗切换、NPC 道具、奖励防重复、原子回滚等。
- `tools/check_activities.py`：真实表数据的经济、小游戏和养成规则。
- `tools/check_task_progress.py`：原剧情捕捉后提交任务 6 并进入任务 7。
- `tools/check_attribute_intervals.py`：受控随机输入下执行原 ARM 区间函数。
- `tools/check_activity_ui.py`：真实 Tk 窗口启动与卡牌按钮检查、截图。控件仍有临时移植布局。
- `tools/check_ui_buttons.py`：42 个原版 UI 布局、112 个可见 Button 的真实命中区、pressed 纹理、35 个原版关闭按钮、
  全部按钮均有动作或通用关闭分发、closeui no/yes 分支；不代表每个按钮背后的玩法都已完整。
- `tools/check_fusion.py` / `tools/check_merge.py`：合体（PetHeTi）与融合（PetMerge）的属性/材料/货币/
  原子回滚及真实 Tk 按钮。
- `tools/check_arena.py`：竞技场排名区间、ArenaNpcPet 真实队伍、徽章/连胜、Boss 称号与掉落、旧存档补字段，
  以及 openui 10 → closeui yes → fight type=3 → fightover → 再次 openui 的完整事件往返。
- `tools/check_infinite_arena.py`：无限竞技场五层 IArenaNpc、IArenaNpcPet 队伍、徽章、荣誉/层数、
  UI 19/20 确认按钮和 `fight type=5` 事件往返，以及旧存档补字段。
- `tools/check_battle_animation.py`：真实战斗事件 → 突进/受击/伤害飘字像素变化 → 时间线结束。
- `tools/check_treasure.py`：藏宝图购买/附赠放大镜、随机 TChestPos、显现、真实地图 actor 与 TChest 开箱，
  UI 24/37/38，以及重复开启和货币不足的原子拒绝。
- `tools/check_running_pet.py`：赛宠原概率/倍率结算、押注左右循环、8 秒冠军时间轴、四只 zq 骨架合成、
  UI 39–43 与 MedalShop 801 的 1 徽章 → 100 奖牌兑换。
- `tools/check_continuous_login.py`：原版 7 天奖励、同日重复拒绝、断签重置、原子失败和真实 UI 12。
- `tools/check_budokan.py`：五座道馆的二十场顺序、`BudokanNpcPet` 真实队伍、胜利/失败进度、
  最终进化材料唯一发放、存档和 `openui 15 → closeui yes → fight type=4` 事件往返。
- `tools/check_daily_tasks.py`：DailyTask 八行、七类计数与上限、跨日重置、同日重复拒绝、
  原表奖励精确发放、购买/轮盘钩子、存档与 TaskUI 真实领取。
- `tools/check_native.py`：地图读取和预览；不代表全地图剧情可通关。
- `tools/check_mounts.py`：5 种坐骑 × 4 种地图 × 6 种地形/越界的 120 项判断，以及自动换乘、手动飞行、试乘、存档和真实移动入口回归；遍历 431 张地图检查 collideTile 保真。不是完整原版步行通关对照。
- `tools/check_battle_clicks.py`：真实 Tk Canvas 的 Button-1 事件，检查两侧宠物菜单、补血/补蓝/背包/换宠、普通攻击/技能推进真实战斗回合、说明按钮不误发招以及关闭、静态帧复用。尚不是全部按钮/全部分辨率覆盖。
- `tools/check_guide.py`：8 个主线目标解析、7401→101 地图路线、区域 BFS、真实 NPC 接近、出口切换和 11 条路线边落点边界检查；不是 431 张地图的完整步行回归。
- `build/_host_debug.py`：有直接触发和传送的序章集成测试；不是玩家全程步行测试。

## 仍未完成

融合/合体已接入核心逻辑，但完整原版动画、坐骑商店/破障交互、宠物使者付费试用/发货、
地图障碍、成就、排行榜领奖和礼包发货等交互仍未完成；
道馆试练、每日任务、赛宠与连续登录已接入核心表与界面，但原版动态 item/粒子/音频、服务器时间校准仍待核对。
全部技能状态和 AI 的原版对照、全部主支线通关测试、动态 Spine 动画和音频、
原 Android 存档兼容、全 UI 的原交互与布局。已有实现也仍需要针对原版逐项比较。
不以占位窗口、自动判胜或手工发奖励视为完成。

## 剧情转场核对（待实现，不能标为完成）

`PlotEventItemToPlace::begin` 0x2f51d4 调用 `spriteMoveToPosition` 0x2dc03e，
后者进入 `VillageSpriteControler::moveToPosition` 0x2e6c04：speedscale=0 直接定位，否则寻路移动；
当前移植仍将这两种都当成直接定位，缺少寻路、移动动画与完成回调。
`PlotEventItemScreenMove::begin` 0x2f5df8 调用 `setViewpoint` 0x2d9eb0，
原版按 speedscale 创建 MoveTo/DelayTime/完成回调，移植目前仍直接切换焦点。
只缓存静态画面不会修好这些语义；下一步应恢复这些动作和脚本等待关系，再对照序章录像。
全部页面恢复、原音频与过场动画仍需要独立核对，不能把这次按钮修复写成“完全一样”。
