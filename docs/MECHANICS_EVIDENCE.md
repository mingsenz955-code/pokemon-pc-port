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
| 坐骑地形通行 | `compareRideCollidesAble` 0x32ad48、`compareRideMapTypeAble` 0x32ad88、`compareRidesCollidesAble` 0x32ae44、`onRideWithCollideTile` 0x32adc8、`VillagePlayerControler::rideProcess` 0x2e1108、`setMoveSpeed` 0x2e0b5c | 读取 Ride.collidesAble 白名单及 mapTypeDisable 黑名单；步行仅 0；当前坐骑优先，其次已获得的 kind=2/3 自动换乘；飞行需手动骑乘。陆行鸟/护城龙 0、乘龙 2、芭叶虫 0/3、飞龙 0/1/2/3；所有坐骑禁地图类型 1，飞龙额外禁类型 3。已获得宠物按 Ride.petId 关联解锁，旧移植存档从获得图鉴补回。试乘不写入永久所有权。基础速度 320，乘以 speed/100。原骨骼静态站立图接入显示；完整骑乘动画、破障事件尚未复刻 |
| 战斗点击与菜单 | `mineMenuPanelRespond` 0x355878、`enemyMenuPanelRespond` 0x3558e4、`energyButtonRespond` 0x355950、`hpButtonRespond` 0x3559a0、`showButtonMenu` 0x3544d0、`showSkillMenu` 0x354a7c；BattleMainUI 的 mine/enemyMenuPos_Panel | 我方区域打开补给菜单，敌方区域打开技能菜单；补蓝筛能量、补血筛生命。菜单使用原 panel 中心；修复命中完整节点路径导致短名动作无法分发，优先命中小的说明按钮，原 SkillInfoNode 展示原表说明。原版发招/特效/结果页、强制引导与菜单显示状态仍未完整对照 |

## 测试和审计

- `tools/check_regressions.py`：战斗切换、NPC 道具、奖励防重复、原子回滚等。
- `tools/check_activities.py`：真实表数据的经济、小游戏和养成规则。
- `tools/check_task_progress.py`：原剧情捕捉后提交任务 6 并进入任务 7。
- `tools/check_attribute_intervals.py`：受控随机输入下执行原 ARM 区间函数。
- `tools/check_activity_ui.py`：8 个真实 Tk 窗口启动与卡牌按钮检查、截图。控件仍有临时移植布局。
- `tools/check_native.py`：地图读取和预览；不代表全地图剧情可通关。
- `tools/check_mounts.py`：5 种坐骑 × 4 种地图 × 6 种地形/越界的 120 项判断，以及自动换乘、手动飞行、试乘、存档和真实移动入口回归；遍历 431 张地图检查 collideTile 保真。不是完整原版步行通关对照。
- `tools/check_battle_clicks.py`：真实 Tk Canvas 的 Button-1 事件，检查两侧宠物菜单、补血/补蓝/背包/换宠、普通攻击/技能推进真实战斗回合、说明按钮不误发招以及关闭、静态帧复用。尚不是全部按钮/全部分辨率覆盖。
- `build/_host_debug.py`：有直接触发和传送的序章集成测试；不是玩家全程步行测试。

## 仍未完成

融合/合体、坐骑商店/完整动画与破障交互、竞技场/无限竞技场/试炼塔、地图障碍与藏宝图宝箱、
藏宝图、赛跑、成就与每日任务、连续登录和礼包等交互；
全部技能状态和 AI 的原版对照、全部主支线通关测试、完整 Spine/IK/特效时序和音频、
原 Android 存档兼容、全 UI 的原交互与布局。已有实现也仍需要针对原版逐项比较。
不以占位窗口、自动判胜或手工发奖励视为完成。

## 0.2.3：显示、存档与动画恢复

- 读取 Cocos TextOptions 的 custom size、h/vAlignment，按原 auto-size 行为调整动态标签；
  修正 Pillow 字形边界的顶部偏移导致下半字裁切。旁白改用原 `AsideUI` 的居中文字，
  不再套 `DialogUI`。解析字段参考 [Cocos 3.3 TextOptions](https://cocos2d-x.org/reference/native-cpp/V3.3/da/dea/structflatbuffers_1_1_text_options.html)。
- 移除自制顶部工具栏和底部调试栏；恢复 MainUI 场景图标及左右/上方菜单。
  `leftButtonsDisperse` 0x376eb4、`rightButtonsDisperse` 0x377224、`upButtonsDisperse` 0x377504
  使用按钮尺寸乘序号和 0.2 秒 MoveTo。已接背包、宠物、抽宠、任务、保存、骑乘与已有商店等入口；
  未完成的页面会明确提示，不能把显示原图标当成页面完整复刻。
- 人物消失：旧 request_map 额外加了一格，580101 出口会把 x 推到 1376，超出 1344 宽地图。
  `setPlayerPositionByExit` 0x2dbefc 实际复制出口位置并反转面向，已移除虚构偏移。
  对旧存档越界坐标在载入内存时修回边界内，原文件先保持；地图/人物及文本截图已经检查。
- 自动续档、20 秒定时自动保存、对话/切图/战前/战后/退出存档；写前保存上一个文件到
  `slot1.json.bak` 与 `backups/slot1-时间戳.json`。启动可回退到备份；损坏主文件另行归档，
  不覆盖已知正常的上一份备份。战斗中仍用战前检查点恢复，不声称支持战斗内快照。
- 原包 Spine 的 stand/attack/underattack/dead 接入战斗播放；骨骼 rotate/translate/scale、
  slot 附件/颜色、FFD、drawOrder 已采样。动作期间不接重复输入，动作结束才继续剧情回调。
  162 个宠物骨架的 1941 个采样姿态可读，不等于原版全部动作视觉一致；IK 等仍待实现。
  Spine 的曲线是十段查表而非解析贝塞尔求根：`spCurveTimeline_setCurve` 0x40b008 与
  `getCurvePercent` 0x40b190 的 600 组 ARM 对照 binary32 精确一致。
  历史官方参考：[Spine 2.1 Animation.c](https://github.com/EsotericSoftware/spine-runtimes/blob/1fa410bb533edd4a327c1590ba166419d8f534af/spine-c/src/spine/Animation.c)。
  运行时不加载该 C 文件或 ARM 库，仍为原生 Python 实现。

新增验证：`check_presentation.py` 7 项（开场三段旁白后开屏、正确出口落点、旧坐标恢复、
自动续档/历史备份/损坏回退、镜头插值及完成延迟、中途存档恢复）；
`check_spine_animation.py` 姿态覆盖与四种动作的差异图；`check_spine_curves_arm.py` 600 组原指令对照。

## 剧情转场核对（仍有未完成部分）

`PlotEventItemToPlace::begin` 0x2f51d4 调用 `spriteMoveToPosition` 0x2dc03e，
后者进入 `VillageSpriteControler::moveToPosition` 0x2e6c04：speedscale=0 直接定位，否则寻路移动；
当前移植仍将这两种都当成直接定位，缺少寻路、移动动画与完成回调。
`PlotEventItemScreenMove::begin` 0x2f5df8 调用 `setViewpoint` 0x2d9eb0，
原版按 speedscale 创建 MoveTo/DelayTime/完成回调，现已接镜头插值、按距离/格高×0.1/speedscale
计算移动时长、0.5 秒 DelayTime、完成后推进脚本；镜头进行中可存档并恢复剩余动作。
人物移动仍缺完整寻路及步行回调，镜头完整像素/时序对照尚未完成，需要继续对照序章录像。
全部页面恢复、原音频与过场动画仍需要独立核对，不能把这次按钮修复写成“完全一样”。
