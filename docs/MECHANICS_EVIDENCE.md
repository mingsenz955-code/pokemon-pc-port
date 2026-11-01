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
| 普通地图宝箱 | `VillageChestControler::open` 0x2d65dc、VillageChest | 原表整批奖励、永久开启状态与 opened 图像；藏宝图生成宝箱仍待接入 |
| 任务 | `MainTaskItemTalk::acceptTask` 0x300264、`PlotEventItemSubmitTask::begin` 0x2f5a04 | 主线对话任务接受即就绪；mtask 为提交当前主线的标志，不是任务编号；收集、捕捉、战斗、多条件计数。支线类型 8/9 待接入 |
| 任务指引 | MainTask/BranchTask 条件字段、VillageMap.exitIds、TMX 出口对象、eventLayer 区域对象 | conditionType 1 按区域 ID 拆地图并进入区域；3 的第三字段是捕捉地图；4 查 NPC 对象；5 直达地图。跨图路线从 TMX `toExit` 与目标地图 `exitIds` 建图，逐格 BFS，移动调用宿主 `move_to` 以保留坐骑地形限制。已修正出口 `face` 落点算反导致负坐标/墙内落点的问题。`tools/check_guide.py` 核对 8 个主线目标、真实区域移动、NPC 接近和一次出口切换 |
| 坐骑地形通行 | `compareRideCollidesAble` 0x32ad48、`compareRideMapTypeAble` 0x32ad88、`compareRidesCollidesAble` 0x32ae44、`onRideWithCollideTile` 0x32adc8、`VillagePlayerControler::rideProcess` 0x2e1108、`setMoveSpeed` 0x2e0b5c | 读取 Ride.collidesAble 白名单及 mapTypeDisable 黑名单；步行仅 0；当前坐骑优先，其次已获得的 kind=2/3 自动换乘；飞行需手动骑乘。陆行鸟/护城龙 0、乘龙 2、芭叶虫 0/3、飞龙 0/1/2/3；所有坐骑禁地图类型 1，飞龙额外禁类型 3。已获得宠物按 Ride.petId 关联解锁，旧移植存档从获得图鉴补回。试乘不写入永久所有权。基础速度 320，乘以 speed/100。原骨骼静态站立图接入显示；完整骑乘动画、破障事件尚未复刻 |
| 宠物合体 | `DataManager::getHeTiData` 0x31dd50、`createHeTiPet` 0x31dd88 | 配方键为 `petA*1000000+petB`，顺序敏感；结果等级 1，五项 variation/growth 取两亲整数平均，再按结果宠物表生成天赋/技能并重算品质；材料与双亲原子移除。`tools/check_fusion.py` 覆盖正常、反向拒绝、材料不足 |
| 宠物融合 | `PlayerDataManager::petMerge` 0x3306d2、`PetDataManager::petMerge` 0x327218 | 按基础宠物品质选择 PetMerge 配方，材料须同品质且达到等级；`attAddition` 加到五项 variation 和五项 growth，重算品质/属性；扣货币并移除材料。`tools/check_merge.py` 覆盖成功与原子失败 |
| 战斗点击与菜单 | `mineMenuPanelRespond` 0x355878、`enemyMenuPanelRespond` 0x3558e4、`energyButtonRespond` 0x355950、`hpButtonRespond` 0x3559a0、`showButtonMenu` 0x3544d0、`showSkillMenu` 0x354a7c；BattleMainUI 的 mine/enemyMenuPos_Panel | 我方区域打开补给菜单，敌方区域打开技能菜单；补蓝筛能量、补血筛生命。菜单使用原 panel 中心；修复命中完整节点路径导致短名动作无法分发，优先命中小的说明按钮，原 SkillInfoNode 展示原表说明。原版发招/特效/结果页、强制引导与菜单显示状态仍未完整对照 |

## 测试和审计

- `tools/check_regressions.py`：战斗切换、NPC 道具、奖励防重复、原子回滚等。
- `tools/check_activities.py`：真实表数据的经济、小游戏和养成规则。
- `tools/check_task_progress.py`：原剧情捕捉后提交任务 6 并进入任务 7。
- `tools/check_attribute_intervals.py`：受控随机输入下执行原 ARM 区间函数。
- `tools/check_activity_ui.py`：真实 Tk 窗口启动与卡牌按钮检查、截图。控件仍有临时移植布局。
- `tools/check_ui_buttons.py`：32 个原版 UI 布局、74 个可见 Button 的真实命中区、pressed 纹理、27 个原版关闭按钮、
  全部按钮均有动作或通用关闭分发、closeui no/yes 分支；不代表每个按钮背后的玩法都已完整。
- `tools/check_fusion.py` / `tools/check_merge.py`：合体（PetHeTi）与融合（PetMerge）的属性/材料/货币/
  原子回滚及真实 Tk 按钮。
- `tools/check_native.py`：地图读取和预览；不代表全地图剧情可通关。
- `tools/check_mounts.py`：5 种坐骑 × 4 种地图 × 6 种地形/越界的 120 项判断，以及自动换乘、手动飞行、试乘、存档和真实移动入口回归；遍历 431 张地图检查 collideTile 保真。不是完整原版步行通关对照。
- `tools/check_battle_clicks.py`：真实 Tk Canvas 的 Button-1 事件，检查两侧宠物菜单、补血/补蓝/背包/换宠、普通攻击/技能推进真实战斗回合、说明按钮不误发招以及关闭、静态帧复用。尚不是全部按钮/全部分辨率覆盖。
- `tools/check_guide.py`：8 个主线目标解析、7401→101 地图路线、区域 BFS、真实 NPC 接近、出口切换和 11 条路线边落点边界检查；不是 431 张地图的完整步行回归。
- `build/_host_debug.py`：有直接触发和传送的序章集成测试；不是玩家全程步行测试。

## 仍未完成

融合/合体已接入核心逻辑，但完整原版动画、坐骑商店/破障交互、竞技场/无限竞技场/试炼塔、地图障碍与藏宝图宝箱、
赛跑、成就与每日任务、连续登录和礼包发货等交互；
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
