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

## 测试和审计

- `tools/check_regressions.py`：战斗切换、NPC 道具、奖励防重复、原子回滚等。
- `tools/check_activities.py`：真实表数据的经济、小游戏和养成规则。
- `tools/check_task_progress.py`：原剧情捕捉后提交任务 6 并进入任务 7。
- `tools/check_attribute_intervals.py`：受控随机输入下执行原 ARM 区间函数。
- `tools/check_activity_ui.py`：8 个真实 Tk 窗口启动与卡牌按钮检查、截图。控件仍有临时移植布局。
- `tools/check_native.py`：地图读取和预览；不代表全地图剧情可通关。
- `build/_host_debug.py`：有直接触发和传送的序章集成测试；不是玩家全程步行测试。

## 仍未完成

融合/合体、坐骑、竞技场/无限竞技场/试炼塔、地图障碍与藏宝图宝箱、
藏宝图、赛跑、成就与每日任务、连续登录和礼包等交互；
全部技能状态和 AI 的原版对照、全部主支线通关测试、动态 Spine 动画和音频、
原 Android 存档兼容、全 UI 的原交互与布局。已有实现也仍需要针对原版逐项比较。
不以占位窗口、自动判胜或手工发奖励视为完成。
