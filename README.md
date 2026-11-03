当前更新 0.2.72：恢复原抽宠扭蛋机、出球、宠物发光及属性展示顺序，结果页保留原背景，三连抽逐只确认；优化刷新调度、图像上传和动画缓存。详见 [验证记录](docs/VERIFICATION_0.2.72.md)。

当前更新 0.2.69：合体接入原 PetHeTiUI/PetSelectUI，显示真实宠物、材料和结果预览，确认后执行原 PetHeTi 配方并保存。包含 0.2.68 的永久购买、六格和战斗图标修复。

当前更新 0.2.68：使者宠物永久购买后禁止重复扣款，兼容旧存档购买识别；随身宠物固定 6 格；战斗药品和捕捉道具图标按实际道具替换。价格维持 1 元＝1000 金币。

# 口袋妖怪单机版 · 原生 Windows PC 移植

[![状态](https://img.shields.io/badge/status-0.2.72%20development-orange)](#当前完成度)
[![平台](https://img.shields.io/badge/platform-Windows%2010%2F11-blue)](#从源码运行)
[![Python](https://img.shields.io/badge/python-3.12-3776AB)](https://www.python.org/)

使用《口袋妖怪单机版》1.20.4 原版数据、地图、Cocos UI 与 Spine 资源制作的**原生 Windows 桌面移植**。不是安卓模拟器封装，不依赖网页或网络服务。

> **当前是 0.2.72 开发版，不是完整 1∶1 成品。** 序章、初始宠物、战斗与捕捉、主线 1–6 有受控测试；不代表全程步行通关。大量系统和页面、原版动画及转场仍未完成。遇到未实现的机制会明确停下，不伪造通过。

### 当前开发改动

0.2.67 修复隔柜台点击 NPC 不触发剧情：按原 TMX 的 npcId 交互区域寻路、进入触发、对话，不再要求走进柜台。孵化改用原 HatchRoomUI / HatchItemUI 横向十个孵化位、HatchCheckUI 条件卡与 PetHatchEffectUI，支持放蛋、经验/材料或金币孵化、取回、领取和存读档；保留原剧情开放条件。见 [0.2.67 验证记录](docs/VERIFICATION_0.2.67.md)。

当前价格标准：**1 元＝1000 金币**。原人民币商品、礼包、永久宠物及金币进化统一使用此倍率；已有金币余额保留。此前 0.2.64 的 1∶10000 标准已作废。

0.2.66 修复战斗商店：改为原 BattleShopUI 横向商品卡和 BuyConfirmUI 数量确认，购买/关闭均可点击。购物期间暂停战斗绘制/演出，关闭与确认不推进剧情战斗，不消耗回合；购买后的道具可立即回到战斗使用。

同版补齐序章 27–39 的原版免费经验石点击链、全灭挑战中止提示、任务零奖励说明，并把宠物突破和幸运转盘改为原 PetTuPoUI / RouletteUI 页面；真实扣除材料、轮盘券和徽章，结果只发放一次。参战宠物现在会在原 PetListUI 中标记并立即生效。

朋友下载器、国内加速线路与独立本机存档见 [朋友下载说明](docs/FRIENDS_DOWNLOAD.md)，本轮复审与验证见 [0.2.65 记录](docs/VERIFICATION_0.2.65.md)。

0.2.65 合并本轮 PR，纠正死亡用药规则，保留老爸的信正文回看，并提供朋友下载器。死亡宠物只能使用复活石，普通回复药失败时不扣除并明确提示。0.2.60 对普通药复活的误改已撤回。

0.2.64：F11 / Alt+Enter 切换全屏，Esc 退出全屏；支持等比缩放和同步点击坐标。地图/战斗自动播放原背景音乐，系统设置可开关音乐与音效，不设音乐商店。取消充值入口，原人民币价格按 **1 元＝10000 金币** 改为本地金币购买（该旧倍率已在 0.2.66 作废，现为 1 元＝1000 金币）；下架金币买金币的充值商品，保留其他游戏货币。另修日常奖励残留任务边框和单奖励居中。见 [验证记录](docs/VERIFICATION_0.2.64.md)。

0.2.63 修复捕获结果一次确认返回地图、全局奖励文字锚点与边界、背包分类标签遮挡、原试用宠物参数和页面，以及面板周围残留旧对话/战斗帧。独立存档覆盖三种球、五种分类、全部奖励名称与抽宠流程；见 [验证记录](docs/VERIFICATION_0.2.63.md)。

0.2.62 修复面板矩形黑影、进化临时列表/前后预览和结果、放大镜/宝箱爱心占位图、登录已领取与次日未开放状态、登录动画开销及皮卡丘成就条件。已合入主分支 PR17 的骑宠菜单修复。

藏宝图：没有进行中的藏宝图时，点击放大镜进入购买页；首张原表 ID1 花费 5 徽章，附赠 3 个放大镜，线索在镇东树林。到目标地图后搜索；找不到也会消耗放大镜。详见 [0.2.62 验证记录](docs/VERIFICATION_0.2.62.md)。


0.2.61 接续修复：所有原独立游戏页嵌入主窗口；宠物待机、道具点击/返回、错误框误报背包满、剧情奖励弹窗、抽宠费用与入库、接任务卡、任务文字留白和原尺寸奖励、原银行护士治疗、捕捉原动画。另修复任务 7 因 counts=0 被菜单刷新提前勾选、阻断原剧情的问题。

治疗地点按原版地图/脚本：斯塔镇日常护士位于银行；回镇时的临时护士属于新手教学，未新增医院。验收与未完成边界见 [0.2.61 记录](docs/VERIFICATION_0.2.61.md)。


0.2.60 修复用户五张试玩截图中的阻塞：

- 初始宠物页使用原页面组合和真实属性，悬停/按下不再退回空白编辑器模板；隐藏支付样本文字，领取只选择一次伙伴。
- 普通战斗不再套世界怪兽排行榜卡；改用原结算资源分步显示胜负、经验/掉落，去掉黑色描边叠字、虚假伤害榜和败方站立残留。
- 捕捉结果通过 species 查询名称，修复读取不存在的 Pet.name 导致 Tk 刷新链停止。三种球的成功、失败后反击、再次点击和返回场景均覆盖。
- 原版 newAi 按技能列表轮换：去掉宿主85%随机抽技能，低级对手首回合不再随机发呆；发呆本身仍保留为原技能，不播放假的攻击动作。
- 跳过已移除、不可见和功能已更改的按钮教程；有效引导指向实际按钮，只有点中该按钮才推进；保留正常剧情。去掉战斗里的永久黑色教程横条。
- 缓存战斗背景/HUD/缩放姿态，按实际显示大小渲染宠物；提高姿态采样至30Hz，按真实秒数保持动作时长，刷新按60Hz目标扣除绘制耗时。复杂冷帧仍可能掉帧，不保证稳定60fps。

0.2.59 继续补原版战斗和寻宝规则：

- 接入原 effectType=1..5：狂风前/后两层、定向效果、世界坐标效果、龙卷六次横移、治愈水。104个有配置技能可读取102条原特效，发呆的 effectId=0 不伪造动画；这不等于所有特效混合、附属效果和战斗动作均已完成。
- 特效对象读取 Skill.effectpos；path2 不再被误当成敌方版本。龙卷按原5/40/80/120/160/200帧逐段刷新血量，命中序号保留空过位置；治愈水按 add 帧显示回复，音效在原 sound 帧只触发一次。
- 图鉴加入实际出场对手的已见记录并保存；已见未捕获可查看详情，不解锁捕获数或骑宠。旧存档只能补回已有捕获记录，不能恢复从未保存的历史已见数据。
- 放大镜按原 spriteTile.box 与当前画面相交查找宝藏；不在同图或画面外时搜索失败并扣除一个放大镜，保留隐藏宝藏。接入原 leida 雷达和 Text.json 的成功/失败提示，提示框随文字扩宽。

0.2.58 复审 PR #13 后补充修复：

- 传送道具与地图传送统一按原 `<map>01` 出口选择可行走落点，排除同名 NPC 和出口触发区；没有安全点时拒绝传送且不扣道具，不再直接放到地图中心。
- 普通抽宠在点击时重新读取免费资格，计时显示每秒刷新；免费到期后不扣徽章，免费次数使用后下一次仍按原表付费。
- 奖励弹窗关闭时恢复进入前的滚轮回调；登录和成就页滚动不再反复打开旧奖励框。
- 新增 `check_pr13_review.py` 的 5 项隔离回归，保留 0.2.57 的页面及道具改动。固定启动入口指向 0.2.58，旧包和玩家存档保留。


0.2.57 同步 main/c104ab8 后修复背包、宠物与活动页：

- 修复装饰图标吞掉行/卡片点击；背包说明、宠物技能/天赋说明和图鉴地点/材料在原框内换行，长内容可滚动。
- 宠物详情采用原技能行、原属性行，修复编号、系别/地形/克制、稀有度、经验条与立绘遮挡；恢复真实训练值页。
- 补齐亲密度和升级道具、背包技能卷轴确认/返回、香水状态替换与有效期、传送目标滚动；三种精灵球按原使用类型在战斗中使用。
- 登录、成就、每日任务等奖励接入原 GetItemUIItemUI 与 lizi_2.plist 星光粒子。累计登录可领取，领取反馈可确认返回，重复领取不发奖。
- 抽宠改用原 LuckyDrawUI，保留原剧情解锁与真实费用；三连结果依次查看。连充恢复原 ContinuousTopUpUI 与七日原卡，不伪造充值资格。放大镜使用原字段与确认流程；未获得骑宠时显示原获取说明。

测试、原版函数依据和仍未完成的部分见 docs/MECHANICS_EVIDENCE.md 与 docs/RESTORATION_REMAINING.md。本版没有通过原版与移植版双窗口逐帧/全流程验收，不能称为完美复刻。

0.2.56 对照原 ARM 函数、原始 CSB 和技能 ExportJson 重做页面组合：

- 商店使用原 `ShopGoodsUI` 横向完整购买卡与原列表间距，选卡更新说明，价格按钮打开 `BuyConfirmUI`；确认保留真实商店背景，真实扣费/发物。
- 背包恢复原尺寸道具行、五类页签和说明；用药打开原 `PetSelectUI` 选择目标。孵化放蛋也改为实际选蛋，不再固定拿第一种。
- 图鉴恢复五列 `115×113` 卡片及未发现状态，详情“查看/介绍”切换原发现地点与进化材料；成就按 `MainAchievement` 分档，显示原星级、进度、奖励和领取状态；累计登录恢复横向奖励卡与标题时间轴终态。
- 登录规则按 `checkLoginInRewardCanReceived` / `loginRewardReceived` 修正：跨日可领、断登不重置、同日及日期回拨不可多领。以前错误重置的历史无法推断，不补造奖励。
- 世界地图使用原 `WorldMap1UI` / `WorldMap2UI`，滚轮或左右拖动切换；点地区名进入原 TMX 地区地图，可拖动查看地点、出口、当前位置和任务标记。
- 战斗接入 `effectType=0` 原技能 Armature、`Animation1` 时长、`attack` 命中帧和 `sound` 音效帧，并按原骨架 `p_center/p_shadow` 定位。特殊弹道、多段命中、完整粒子/混色和所有战斗转场仍未完成。
- 修复点击指引被改成商店菜单、读档消耗随机数、悬停重画静态模板使动态商品消失等回退。原用户存档保留，固定启动器指向本次完成的包。

本版不是全部页面或全游戏 1∶1 验收。地图云雾解锁、传送完整规则、部分道具深层功能、全部技能表现和后期剧情仍待原版逐项对照。


0.2.55 修主界面遮挡并继续单机化：

- 去掉社区入口 `community_Button`，不再打开公告/社区页，也不保留可点区域。
- 打开右侧“功能”菜单时，暂时隐藏 `uiDisappear_Button`（四箭头 HUD 显隐按钮），
  它原本正好压在图鉴图标上；收回“功能”菜单后四箭头恢复。只影响显示和
  命中，不改变 HUD 显隐状态。
- 主界面回归测试新增断言：展开时四箭头和社区均不可点，收起时四箭头恢复。

0.2.54 按单机版方向做了删减和补页：

- 去掉主界面“功能”菜单里的排行榜、礼包兑换、蓝牙对战入口；这三个
  非单机功能不再出现在菜单命中区，也不再有回调。排行榜/礼包/蓝牙的
  旧代码和布局暂留，方便以后核对，但玩家不会从主界面点进去。
- 初始宠物确认页从宿主 Tk 小窗改为原版 `ChooseFirstPetUI`：显示原作
  立绘、名字、等级、属性系、地形、克制系、进化次数和星级；星级/心形
  按宠物表数据点亮，不再一律显示 5 星。确认按钮调用真实
  `choose_starter`，写入存档并继续剧情。
- 获得物品页从黑色 Tk `Listbox` 改为原版 `GetItemUI` +
  `GetItemUIItemUI` 奖励卡：两列卡面、真实道具图标/名称/数量，四件以上
  滚轮翻页；确认关闭。奖励仍由剧情/战斗真实发放，不新增假奖励。
- 修正 `UI_LAYOUTS[7]` 原本指向不存在的 `ChoiceFirstPetUI` 的问题。

这些改动仍不等于完整还原；背包道具目标选择、商店限购/刷新、深层活动
规则和大量原版动画仍待继续接入。

0.2.53 专门修主界面入口和商店流程：主界面右侧“功能”菜单的子按钮现在
按展开动画真实显示并可点；未展开时隐藏按钮不再抢点击，所以点“功能”能
打开菜单，红背包图标、宠物、图鉴、成就都能进入（排行/礼包/蓝牙入口
已在 0.2.54 移除）。键盘
`B` 也可直接打开背包。商店按原版拆成 `ShopUI`、`EvolutionShopUI`、
`SkillShopUI`、`InfiniteArenaShopUI`、`MedalShopUI` 五种页面，标题、NPC
和商品同步；右上金币/奖牌读取真实存档，不再显示编辑器占位 `8888888`；
商品支持滚轮翻页，点击商品打开 `ShopGoodsUI` 卡片，购买改用原版
`BuyConfirmUI`（数量左右按钮、总价、取消/购买），确认后真实扣货币并回店。
排行榜改为读取 `FightRank`、`PetCollectCountRank`、`RankNpcPet` 真实行，
替换编辑器占位“一个大鸭子 5000”。这些页面仍不是全部深层玩法；0.2.53
不是完整还原。

0.2.52 继续按手机版 APK 内原始 `assets/Data`、`res/UI/*.csb`、`PlotEvent`
和 UI 布局驱动页面，不再用宿主 Tk 列表框盖住原版画面。宠物页改为
`PetListUI` + 三张 `PetListItemUI`，显示原版立绘、属性/技能/天赋页签；
图鉴页改为 `IllustratedItemUI` 卡片网格并接入 `IllustratedPetInfoUI`；
成就页改为原版 `AchievementItemUI` 卡片和积分栏；连续登录、宠物银行、
孵化屋、技能学习、突破、合体、融合、轮盘、坐骑/宠物商店都限制在
800×480 原版页内，隐藏宿主列表并保留原版按钮动作。孵化屋、技能学习等
页仍有未接入的深层规则；0.2.52 不是完整还原。

0.2.51 把背包和商店从宿主 Tk 控件改为原版页面：背包在 `BagUI` 的
`item_ListView` 内逐行合成 `BagListItemUI`，显示原版页签、道具图标、名称、
数量和右侧说明，支持滚轮翻行；道具分类改为道具/蛋/卷轴/重要/碎片五页，
精灵球等捕捉道具回到“道具”页。商店在 `ShopUI` 的 `goods_ListView` 内按
原版 `GoodsItemNode` 排成 4×2 商品格，点击商品进入 `ShopGoodsUI` 详情。
主界面公告、设置、蓝牙、礼包、排行榜等入口也改为打开对应原版布局，不再
弹“功能未完成”。这些页面仍有未接入的深层玩法；0.2.51 不是完整还原。

0.2.50 修复野外遇敌：每次进入地图重新按 `enemyAppearInterval` 设置步数阈值，不再把阈值清成 0。
胜利结算改用原版 `WorldMonsterBattleResultUI` 的胜利牌/名称/伤害值/经验/掉落和确认按钮，
移除自制深色弹窗；教程 `button` 指令必须点击高亮的 `uiDisappear_Button` 才能继续，
不会点空地跳过隐藏/还原界面步骤。左上角保存入口改为打开原版 `SaveConfirmUI`，
确认后才原子写入本机用户存档；取消不写盘，战斗中拒绝保存。商店、充值奖励入口也接回原版页面，
单品不伪造计费。

0.2.48 按用户确认的操作恢复“点击指引 → 自动走向任务点”：默认无常驻箭头，
再次点击/方向键可停止；标记只跟随实际可走路径，不直指远处人物穿墙。
修正建筑半格定位漏算导致妮妮家门被碰撞覆盖，以及路线穿过无关出口导致研究所/城镇反复往返。
保留原对手剧情与战斗拦截；独立的对手剧情已完成夹具验证研究所→斯塔镇→妮妮家和真实对话触发，
不代表已经完成全剧情通关。431 张地图可以解析，1686 份剧情文件在本地，全部玩法/分支/结局仍未验收。

0.2.47 按原 ARM 行为重做任务页和指引：任务在游戏画面内打开，使用 TaskUI / TaskItemUI /
RewardItemUI，主/支线页不再伪装成远程导航按钮，领取只用于每日任务。恢复顶部地点菜单和
当前地图设施出口、原版早期主线方向箭头。战斗换宠改用 PetSelectUI / PetSelectItemUI；
普通道具和投球不再多弹自制确认框。修正影响各页的透明面板合成，读取原 CSB 文字对齐字段。
完整页面/粒子/音效和战斗回调仍在复原，不能将本次开发版视作全游戏 1∶1 验收。

0.2.46 复审 PR #9：修复连续回合漏播动画、我方血条快照错位、选中宠物未在战斗开场出战；
任务路径加入动态人物避让，支线/子任务变化后重新指引，多 NPC 提交目标正确解析。
战斗演出改按实际时间推进，技能命中回调、完整特效音频仍未全部恢复。

新增抽宠、幸运轮盘、卡牌、孵化、银行存取、宠物商店、技能学习及卷轴、训练、突破、原版宠物合体与融合的交互；
修复战斗换宠与 NPC 用药、奖励重复领取、扣费失败留下部分修改、主线任务 6 捕捉后卡住等问题。
护士治疗与普通地图宝箱也已接入。0.2.2 修复战斗按钮完整节点名未分发的故障；
按原 ARM 回调恢复“点我方打开补给/换宠，点敌方打开技能”的入口，补蓝/补血各筛选对应道具，
保留原图标与菜单坐标，技能/道具说明可点击。取消遮挡敌方血条的自制日志框；静态战斗帧复用以减少无效重绘。
坐骑现在按原表区分地形通行、地图禁用、自动换乘和手动飞行；基础移动速度 320，坐骑按 speed/100 缩放。
任务指引已接入原版任务条件解析、跨地图出口路线和逐格实际移动，修正出口落点在地图外或墙内的旧问题。
原版 Cocos 按钮现在全部建立真实点击区域，按下时优先切换原版 pressed 纹理；`closeui` 的 no/yes 分支
会按玩家的实际确认结果跳转。合体（PetHeTi）与融合（PetMerge）已按 ARM 反汇编接入材料、货币、
属性平均值/加成、品质重算和原子回滚；竞技场已接入原版事件 `openui 10 → closeui yes → fight type=3`
往返、真实 ArenaNpcPet 队伍、排名/称号/连胜/徽章与 Boss 掉落；无限竞技场已接入
`openui 19/20 → closeui yes → fight type=5`、五层 IArenaNpc 队伍、徽章消耗、荣誉/层数推进和商店。
0.2.6 接入原版藏宝图购买、放大镜显现、随机 `TChestPos` 地图宝箱、`TChest` 开箱与开箱光效，
并补齐内部 UI 37/38；战斗事件现在有突进、受击闪烁、伤害飘字和血条缓动。
0.2.7 接入原版赛宠嘉年华：`RunningPet` 数据随机四只赛宠、`Formula_GetRunningPetWinProbability`
原公式、`RunningPetReadyUILayer::handleResult` 原倍率结算、10–9999 奖牌押注与左右循环、
8 秒冠军时间轴、四只 `zq` 原始骨架、结果页与 `MedalShop` 801（1 徽章换 100 奖牌）。
同版本接入原版连续登录 7 天奖励表、同日防重复、断签重置和原奖励原子发放。
0.2.8 接入原版道馆试练：`openui 15 par1=<道馆>` → `closeui yes` → `fight type=4 npcid=<道馆>`
往返，按 `Budokan` / `BudokanNpc` / `BudokanNpcPet` 顺序生成二十场真实战斗；
胜利推进 `GameState.budokans`，失败不推进，第二十场按原表发放该道馆高级进化材料。
0.2.9 接入原版每日任务 `DailyTask` 八行（七项日常 + 全能训练），按原条件接入捕捉、NPC 战斗、
聊天、购买、轮盘、卡牌获胜、赛宠获胜计数；每天重置，完成与领取分离，奖励原子发放。
TaskUI 的每日页可用真实按钮领取；原版任务页的逐帧 item 动画和服务器时间校准仍未完成。
0.2.10 接入原版 `obsType` 树/岩障碍：护城龙破坏岩石、陆行鸟砍伐树木，月桂叶穿越荆棘、
炼狱龙越过全部障碍、乘龙渡水；障碍从 `spriteTileLayer` 真实移除、写入
`removed_obstacles` 并推进 `conditionType=6` 任务，试乘 `wait type=3` 在破障后继续。
当前 143 张地图共解析 10,937 个原版障碍对象。
0.2.11 接通 TaskUI 三页与 `tag_task_main/branch/daily` 原标签：主线和已接支线显示真实
`MainTask`/`BranchTask` 名称、描述、状态、条件进度与奖励；每日页保留八行领取。
主线/支线奖励仍由原目标 NPC 的 `submittask` 事件发放，界面不会伪造远程领奖。
破障时加入按障碍类型着色的碎片与尘土短动画；这是表现层，碰撞和任务写入已先完成。
0.2.12 接入原版 `AcceptBTaskUI`：支线接受不再弹系统 yes/no 框，而是显示原布局的
`accept_Button`/`close_Button` 命中区与任务名、描述、奖励；接受和关闭只恢复一次
`accepttask` 脚本，窗口关闭按拒绝处理。
0.2.13 接入原版 `AchievementUI`：142 行全部可浏览，已接入地图到达、支线完成、村庄宝箱、
NPC 谈话和 obsType 破障五类条件的真实进度；这些条件可以原子领取原表奖励并累计积分，
其余条件类型明确显示“未接入”，不会伪造完成或发奖。
0.2.14 接通战斗界面左上角原版 `battleShop_Button`：点击打开 `BattleShopUI`，列出 12 行
`BattleShop` 商品，购买直接使用原表货币并进入背包；购买/关闭都是真实按钮，不模拟付费。
0.2.17 成就进度扩展到星级/品质宠物收藏、战斗胜利、捕获、孵化、进化、骑乘、银行存量、
游戏时间、存档次数、道具种类收藏和图鉴种族收藏，共 16 类可验证条件；同时新增全量核对：
431 张 `VillageMap` 均可加载、1,685 个剧情脚本和 461 个触发器全部命中已实现的命令/触发分派，
没有未知事件命令。
0.2.18 背包改用原版 `BagUI`：五个原版分类页签、`item_ListView` 实际物品列表、
`use_Button` 对宠物使用道具、`heCheng_Button` 按 `DebrisItem.needCount` 消耗碎片并召唤宠物；
不再使用自制背包窗口。
0.2.19 宠物列表改用原版 `PetListUI`：真正列出携带宠物、基础/技能/天赋页签、出战切换、
进化、带宠物进背包、两段确认放生；接替原来的自制宠物窗口。
0.2.20 图鉴改用原版 `IllustratedUI`：五个 `PetKindEnum` 页签、全 `Pet` 列表、收录标记、
真实“发现数量/捕捉数量”重绘，点击查看种族、星级、等级和技能。
0.2.21 地图宝藏和村庄宝箱改用原版 `GetItemUI`：真实标题、奖励列表和确认关闭，
不再只写一行 event_issue 提示。
0.2.22 战斗前确认改用原版 `SecondConfirmUI`，顶栏“当前进度”改用原版 `TipConfirmUI`；
两个界面都有真实确认/取消分支。
0.2.23 成就增加第 17 类：按原 `heal_items` 统计指定回复/飞越道具的真实使用次数，
覆盖“健健康康”“爱心满满”“初次飞越”“空间穿越者”。
0.2.24 商店商品列表回到原版 `goods_ListView` 位置，双击商品打开 `ShopGoodsUI`
原版商品卡，再进入 `GoodsBuyConfirmUI` 确认购买；确认后才扣款发货。
0.2.25 成就增加第 18、19 类：全商店累计消费指定货币、三类商店店员对话次数；
购买和打开商店时写入真实计数。
0.2.26 技能学习增加原版 `SkillReplaceUI`：从当前技能槽选择替换位置，确认后
按原消耗扣卷轴/货币并写入技能。
0.2.27 成就再增加第 9、10、20 类：一次攻击击败、石化/睡眠施加次数、银行格子上限；
战斗事件和真实道具数量参与进度。
0.2.28 背包宝箱 210001 接入原版 `OpenChestConfirmUI`：显示钥匙数量，确认后
按原 `ChestItem` 权重抽奖并扣除宝箱和钥匙，奖励进入 `GetItemUI`。
0.2.29 宠物放生改为原版 `FreePetConfirmUI`：显示名字/等级，取消回列表，确认才
移除并修正出战序号，出战中宠物拒绝放生。
0.2.30 宠物列表双击接入原版 `PetPropertyUI`：名字/等级/编号/五项属性、技能与
天赋标签切换、原版描述、放生和进化按钮。
0.2.31 修正属性页放生返回路径：取消放生回到原 `PetPropertyUI`，确认放生回
`PetListUI`。
0.2.32 真实抽宠成功后打开原版 `LuckyDrawPetInfoUI`：宠物名、等级、五项属性，
确认后回到抽宠界面。
0.2.33 “关于”改为原版 `GameAboutUI`，显示真实版本/数据来源/未完成声明。
0.2.34 技能学习接入原版 `SkillLearnConfirmUI`：先确认宠物/技能/消耗/替换槽，
确认后才扣费学习。
0.2.35 宠物进化接入原版 `EvolutionConditionUI`：先显示目标、等级和材料条件，
确认后才真实进化。
0.2.36 孵化“检查”接入原版 `HatchCheckUI`：显示经验/材料/金币，取回、材料孵化、
金币孵化都在原版页执行。
0.2.37 修正指引的战斗/破障/到地图类型、被剧情隐藏人物的位置索引，以及捕捉目标的
VillageEnemy → Pet 关联；全能训练改为领取另外七项日常奖励后才完成，日期回拨不会清空领取记录。
本轮只运行逻辑检查，未做窗口观察；[未完成清单](docs/RESTORATION_REMAINING.md) 继续保留。
0.2.38 将原版 `screenmove` 的镜头插值、距离/速度时长、0.5 秒停留和完成回调接回剧情，
独立存档保存镜头剩余动作。场景、指引线和特效共用镜头坐标；人物寻路及步行回调仍未完成。
同时校正捕捉指引字段顺序为宠物 ID、种类、地图，避免特定种类任务选错地点。
0.2.39 接入剧情 `toplace` 的绝对/玩家相对/朝向相对坐标、非零速度逐格移动、并行人物
到达回调，以及移动途中存读档；角色和临时 NPC 不再用倒置的地图高度换算脚本 y 坐标。
播放原 Cocos 角色 walk 关键帧并循环，仍缺完整骨骼插值、动态碰撞和出口/沿路事件的完整对照。
0.2.40 移除顶部/底部开发栏，恢复原版 `MainUI` 场景按钮与菜单展开；启动读取现有存档，
修复旧版本在斯塔镇前期存入的错误主角隐藏标记（保留剧情中明确要求的隐藏）。
用当前存档只读副本验证主角确有可见像素，未覆盖用户存档；原版全部场景按钮页面仍未完成。
本版也补回寻路最近候选格回退和逐格区域任务计数，剧情中区域触发不排队补播。
0.2.41 修复剧情朝向覆盖键盘转向，普通移动播放原 walk 动画、站立和 NPC 播放原 stand
时间轴；线性骨骼关键帧与透明度插值，使用导出骨架原点定位，减少按帧裁剪造成的脚底漂移。
按 TMX `move` 字段恢复 NPC 区域巡逻，等待 3–7 秒后选择区域目标；无配置 NPC 不随意游走。
0.2.42 提供固定“口袋妖怪”启动器，后续构建成功才切换最新版本，桌面不再添加版本号快捷方式。
从原加密 spriteTile.json 恢复建筑多格碰撞与图片偏移，按脚底位置绘制遮挡；地面坐骑仍受建筑
碰撞限制，合法飞行按原规则豁免。任务指引按实际时间连续移动，到 NPC 相邻格中心停止并转向，
跟随当前任务状态与 NPC 实际位置；场景指引按钮直接前往任务目标。全部按钮页面仍未完成。
0.2.43 加入点击地面寻路、原版橙色路径点与终点动画；点击 NPC 或头顶任务标记，走到身旁后
自动转向并对话，移动 NPC 会重新寻路。新点击重定目标，方向键中断；封闭目标不穿墙、不伪造对话。
恢复主线橙黄色、支线蓝绿色的原 TaskIcon 感叹号/问号及目标箭头，按可接、进行中、可提交状态更新；
普通闲聊不会凭空添加未读任务标记。接通 NPC 支线分发和 `goto:npcid` 对话上下文、支线提交依赖
与图鉴收录条件，并为这两种任务补充指引。全部后期主支线仍未完成通关验收。

0.2.49 将主界面任务入口接到原 TaskUI，目标按钮启动寻路，到 NPC 后自动触发对话。
修正战斗速度/防御属性映射，实际调用四类原版基础伤害公式；战斗画布与宿主统一为 960×576，
从原布局读取宠物站位。接入原 Spine 骨骼/插槽/绘制顺序时间轴，按动作顺序播放攻击与受击。
**仍未解决**：特殊技能与全部状态/天赋/携带物、原版命中特效与音效、FFD/IK、各宠物原始比例、
完整换宠/捕捉/结算及全地图指引验收。具体差异见 [未完成清单](docs/RESTORATION_REMAINING.md)。

日常启动请使用桌面唯一的 **口袋妖怪**；构建与发布规则见 [固定启动入口](docs/RELEASE_WORKFLOW.md)。
**这些改动仍不代表完整复刻**：宠物使者付费试用/发货、试炼塔、礼包发货、成就剩余
攻略时限/神秘商店、排行榜领奖、后期主支线、技能状态细节和原版 Spine 特效/音频等仍有大量工作。

核对地址、测试及差异见 [规则核对记录](docs/MECHANICS_EVIDENCE.md)。
原交接文档保存在 [DeepSeek 交接](docs/DEEPSEEK_HANDOVER.md) 和
[原始接续要求](docs/DEEPSEEK_REQUEST.txt)，其中历史完成度及旧电脑路径不作为当前验证结论。

开发对照测试使用 `pip install -r requirements-dev.txt`，原生游戏仍只需 `requirements.txt`。

### 启动及战斗操作

本地打包产物为 `outputs/口袋妖怪-PC移植开发版0.2.36/口袋妖怪-PC移植开发版0.2.36.exe`，
完整 ZIP 已归档到 [`publish/release/pokemon-pc-0.2.36.zip`](publish/release/pokemon-pc-0.2.36.zip)。
双击 EXE；保留旁边的 `_internal` 和 `data` 文件夹。WASD/方向键移动，空格/E 对话，F5 保存、F9 读取。
战斗时点击我方宠物打开补给/背包/换宠，点击对方宠物打开技能/普通攻击/捕捉。
说明按钮打开技能或道具原表说明，单击关闭。训练师战斗不显示逃跑和捕捉。
游戏存档独立存放在当前 Windows 用户的 `%LOCALAPPDATA%\PocketNativePC\slot1.json`；
发布包不附带开发机存档，换用户/换电脑不会继承别人的进度。需要把进度交给另一台电脑时，
复制这个文件到相同位置即可。左上角保存按钮会先打开原版 `SaveConfirmUI`，确认后才写入。
恢复 APK 时可用 `python tools/recover_assets.py 游戏.apk original-1.20.4 --research-output research`；
恢复工具会拒绝覆盖非空资源目录。原 APK、恢复资源、研究材料和发布包已保存到本仓库的
[完整归档](archive/README.md)，按其中的分卷顺序拼接即可。

## 画面

| 原版世界地图 | 原版战斗界面 |
| --- | --- |
| ![世界地图](docs/screenshots/world-map.png) | ![战斗主界面](docs/screenshots/battle-main.png) |

| 技能菜单 | 野外遭遇 |
| --- | --- |
| ![技能菜单](docs/screenshots/battle-skills.png) | ![野外遭遇](docs/screenshots/wild-encounter.png) |

| 序章 · 十年前迪尼斯城 | 任务指引 · 原版区域目标 |
| --- | --- |
| ![序章](docs/screenshots/prologue.png) | ![任务指引](docs/screenshots/guide-marker.png) |

## 当前完成度

### 已实际接入

- **真实序章**：从 7401 冠军赛开始，按原 `pEvent` 脚本推进 7401 → 7228 → 5807 → 101，包括对话、旁白、黑屏、场景切换、战斗、按钮/点击等待。
- **初始宠物三选一**：研究所 `openui 7`，读取原 `InitPet`：皮卡丘、杰尼龟、妙蛙种子。
- **主线任务 1–6**：任务条件、提交、奖励、下一任务状态；支持 `conditionType` 1/2/3/4/5/6/7。
- **原版战斗核心**：
  - 原 `Pet` / `Skill` / `SkillState` / `Talent` 数据；
  - 伤害、属性克制、暴击、防御/速度/能量减伤、经验、升级、掉落；
  - 敌方 AI、换宠、逃跑、捕捉率、捕捉后入队/仓库；
  - 战斗内回复道具、精灵球分页。
- **原版战斗 UI**：`BattleMainUI`、`BattleButtonMenuNode`、`BattleSkillMenuNode`、`BattleItemMenuNode`，含原版背景、宠物 Spine 立绘、HP/能量条、状态、队伍点、日志、确认与结算面板。战斗事件会驱动突进、受击抖动/闪红、伤害飘字和血条缓动；这仍不是原版完整 Spine 时间轴。
- **地图随机遇敌**：按原 `VillageMap.enemyAppearInterval`（30–40 步）和 `enemyProbability` 权重选择 `VillageEnemy`；该逻辑由 `VillageMapControler::checkEnemy` / `DataManager::fightWithVillageMapEnemy` 反汇编核对。
- **藏宝图与宝藏**：按原 `Treasure` 行扣徽章、附赠放大镜，从 `chestPoss` 随机 `TChestPos` 生成隐藏宝箱；使用放大镜扣 1 个后在地图上显现 `TChest.spriteId` 宝箱，靠近按 `TChest` 概率/数量开箱。UI 24 线索、UI 37 购买确认、UI 38 线索确认均接入。
- **任务指引与寻路**：按原 `MainTask`/`BranchTask` 的 `conditionType` 解析目标：区域 ID、NPC ID、捕捉地图、目标地图、等级/道具；自动沿已核验出口逐图行走，地图切换后重新计算路线，并在 NPC 交互范围或区域触发处停下。找不到原版对象时明确报告，不编造坐标。
- **背包/宠物界面**：背包可使用原版回复道具并扣除数量；宠物界面显示等级、生命/能量、五维、品质、突破、亲密度、技能、天赋，并支持数据驱动的进化尝试。
- **独立存档**：保存剧情位置、地图、背包、任务、事件状态、宠物、随机数状态；原子写入并保留 `.bak`。战斗中存档会明确拒绝，避免写入不一致状态。

### 部分完成

- **商店**：可读取原 `Shop` 表并购买，但尚未按原 `VillageMap.shopType` 做完整货架过滤。
- **战斗状态**：已覆盖主要状态与持续伤害/回复/免疫/驱散；57 种状态中仍有少数目标选择与叠加规则待逐条核对。
- **宠物养成**：进化、训练、突破、原版合体（PetHeTi）与融合（PetMerge）已接入；品质重算、携带物和放生仍不完整。
- **竞技场**：按原版 `ArenaNpc.rankInterval` 选择当前排名上一位对手，按 `ArenaNpcPet`/`petLevel` 生成真实 6 只队伍；
  首次或离开后收 1 枚徽章，连胜免费；胜利提升排名、Boss 授予称号并发放原版掉落，失败重置连胜。界面与事件往返已实测，
  但原版竞技场专属发招动画/结算特效仍需继续对照。
- **无限竞技场**：`IArenaNpc` 五层（Lv.30/60/90/120/121），按当前层生成 6 只 `IArenaNpcPet`
  真实队伍；每次挑战消耗 1 枚徽章，胜利按原 `Formula_InfiniteArenaHonorReward` 获得 1 荣誉并升层，
  最高层封顶；UI 19/20/21 与事件 `fight type=5` 已接通。层间地图引导、原版层间转场/动画仍未完整复刻。
- **道馆试练**：`Budokan` 五座道馆，每馆二十位 `BudokanNpc` 按顺序挑战；队伍读取
  `BudokanNpcPet`，胜利推进 `GameState.budokans`，失败不推进；第二十场发放原表进化材料。
  UI 15 与 `openui 15 → closeui yes → fight type=4` 已实测，原版动态 item 动画仍待继续对照。
- **每日任务与任务页**：`DailyTask` 八行按原条件统计捕捉、NPC 战斗、聊天、购买、轮盘、卡牌获胜、
  赛宠获胜；七项日常全部完成后“全能训练”可领取。每天按本地日期重置，完成与领取分离，
  奖励走原表 `rewardIds/rewardCounts` 和事务发放。TaskUI 的 `tag_1/2/3` 已分别打开主线、
  支线、每日三页；主线/支线显示原表描述、进度、奖励，但奖励仍必须由目标 NPC 的
  `submittask` 事件发放，界面不做远程伪造领取。原版任务页逐帧 item 动画与服务器时间校准仍未完成。
- **地图交互**：出口、传送、区域触发、树/岩障碍和坐骑破障已接入；`obsType` 障碍会阻挡步行，
  护城龙/陆行鸟可破坏并移除，月桂叶/炼狱龙/乘龙按原表穿越对应地形。原版障碍点击/采集动作、
  部分场景机关和后期地图仍会停止并提示。

### 明确未完成

- 战斗内存档与战斗中断恢复；
- 全部 57 种 `SkillState` 的完整语义、天赋/携带物全结算；
- 宠物图鉴、训练、放生、仓库整理；
- 完整背包、任务列表/追踪、商店货架、道馆/赛宠/每日任务的原版逐帧界面；
- 圣兽使者（付费试用/发货）、成就、排行榜领奖、礼包发货；
- 全支线、全地图、结局与全流程回归；
- Spine 时间线动画、FFD/IK、全部技能表现；
- 音乐/音效全接入、原字体一致性；
- 原安卓存档兼容。

## 从源码运行

### 环境

- Windows 10/11
- Python 3.12
- 原版 1.20.4 资源目录：`original-1.20.4/`（**不包含在本仓库**，见下方“资源与版权”）

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\pc_game.py
```

首次运行需要本地存在 `original-1.20.4/tables.json`、`assets/`、`events/`、`ui-layouts/`。若只有 APK，可先恢复资源：

```powershell
.\.venv\Scripts\python.exe tools\recover_assets.py <1.20.4 APK 路径> original-1.20.4
```

### 操作

| 按键/操作 | 功能 |
| --- | --- |
| WASD / 方向键 | 移动 |
| 空格 / E / 鼠标单击 | 对话、交互、确认 |
| F5 / F9 | 保存 / 读取独立存档 |
| G | 开始/停止自动任务指引 |
| 顶部按钮 | 宠物、背包、任务、指引、抽宠、坐骑、保存、读取、关于 |
| 战斗界面 | 点击右侧指令：攻击、技能、道具、换宠、逃跑、捕捉 |

## 构建 Windows 包

```powershell
.\.venv\Scripts\python.exe tools\build_windows.py
```

输出：`outputs/口袋妖怪-PC移植开发版0.2/`。必须保留同目录的 `_internal/` 与 `data/`。构建脚本会复制 `original-1.20.4/` 为 `data/`，所以发布包内含原版资源；**本仓库不提交这些资源**。

## 测试与核对

```powershell
# 15 个公式 × 200 组，与 ARM 原二进制比较
.\.venv\Scripts\python.exe tools\check_original_formulas.py

# 触发、任务、存读、原子扣费、未实现机制停止
.\.venv\Scripts\python.exe tools\check_game_runtime.py

# 战斗核心与捕捉
.\.venv\Scripts\python.exe tools\check_battle_runtime.py

# 任务目标解析、路线和真实逐格移动
.\.venv\Scripts\python.exe tools\check_guide.py

# 原版全部 UI 布局的按钮点击区、pressed 纹理、closeui no/yes 分支
.\.venv\Scripts\python.exe tools\check_ui_buttons.py

# 宠物合体（PetHeTi）与融合（PetMerge）
.\.venv\Scripts\python.exe tools\check_fusion.py
.\.venv\Scripts\python.exe tools\check_merge.py

# 竞技场：排名、真实 ArenaNpcPet 队伍、徽章/连胜、完整事件往返
.\.venv\Scripts\python.exe tools\check_arena.py

# 无限竞技场：五层 IArenaNpc、荣誉、徽章、完整事件往返
.\.venv\Scripts\python.exe tools\check_infinite_arena.py

# 战斗事件 → 突进/受击/伤害飘字/血条缓动
.\.venv\Scripts\python.exe tools\check_battle_animation.py

# 原版战斗胜利结算页
.\.venv\Scripts\python.exe tools\check_battle_result_ui.py

# 野外地图步数遇敌
.\.venv\Scripts\python.exe tools\check_wild_encounter.py

# 教程高亮按钮才能继续（界面隐藏/还原）
.\.venv\Scripts\python.exe tools\check_button_tip.py

# 左上角保存 → 原版 SaveConfirmUI → 本机用户存档
.\.venv\Scripts\python.exe tools\check_save_ui.py

# 藏宝图购买、放大镜显现、地图宝箱、UI 24/37/38、真实事件 closeui yes
.\.venv\Scripts\python.exe tools\check_treasure.py

# 赛宠：原公式/原结算/押注循环、四骨架 8 秒比赛、结果页与 MedalShop 801
.\.venv\Scripts\python.exe tools\check_running_pet.py

# 连续登录：7 天原表、同日防重复、断签重置、原子发放
.\.venv\Scripts\python.exe tools\check_continuous_login.py

# 道馆试练：Budokan 20 场顺序、BudokanNpcPet 队伍、type=4 原事件与最终材料
.\.venv\Scripts\python.exe tools\check_budokan.py

# 每日任务与 TaskUI：八行、七类计数、三页 tab、每日重置、原子领取与主线/支线不伪造领奖
.\.venv\Scripts\python.exe tools\check_daily_tasks.py
.\.venv\Scripts\python.exe tools\check_task_ui.py

# 支线接受：原版 AcceptBTaskUI 布局、accept/close 命中、单次恢复
.\.venv\Scripts\python.exe tools\check_accept_task.py

# 成就：142 行、五类真实条件、原子领奖、未接入不伪造
.\.venv\Scripts\python.exe tools\check_achievements.py

# 战斗商店：BattleMainUI 原版 battleShop_Button、BattleShopUI 购买
.\.venv\Scripts\python.exe tools\check_battle_shop.py

# 全量剧情/触发器/地图覆盖：1,685 脚本、461 触发器、431 地图
.\.venv\Scripts\python.exe tools\check_event_coverage.py

# 原版背包：五页签、使用、碎片合成
.\.venv\Scripts\python.exe tools\check_bag_ui.py

# 原版宠物列表：出战/进化/放生保护
.\.venv\Scripts\python.exe tools\check_pet_list_ui.py

# 原版图鉴：五个种族页签与收录统计
.\.venv\Scripts\python.exe tools\check_illustrated_ui.py

# 原版获得物品界面
.\.venv\Scripts\python.exe tools\check_get_item_ui.py

# 原版二次确认/提示界面
.\.venv\Scripts\python.exe tools\check_confirm_ui.py

# 原版商店商品详情与购买确认
.\.venv\Scripts\python.exe tools\check_shop_goods_ui.py

# 原版技能替换界面
.\.venv\Scripts\python.exe tools\check_skill_replace_ui.py

# 成就使用的战斗事件标记
.\.venv\Scripts\python.exe tools\check_battle_achievement_events.py

# 原版宝箱开启确认
.\.venv\Scripts\python.exe tools\check_open_chest_ui.py

# 原版放生确认
.\.venv\Scripts\python.exe tools\check_free_pet_ui.py

# 原版宠物属性
.\.venv\Scripts\python.exe tools\check_pet_property_ui.py

# 原版抽宠结果
.\.venv\Scripts\python.exe tools\check_lucky_pet_info_ui.py

# 原版关于界面
.\.venv\Scripts\python.exe tools\check_about_ui.py

# 原版技能学习确认
.\.venv\Scripts\python.exe tools\check_skill_learn_confirm_ui.py

# 原版进化条件
.\.venv\Scripts\python.exe tools\check_evolution_ui.py

# 原版孵化检查
.\.venv\Scripts\python.exe tools\check_hatch_check_ui.py

# 树/岩障碍：obsType 解析、坐骑能力、真实移除、conditionType=6 任务、试乘 wait 继续
.\.venv\Scripts\python.exe tools\check_obstacles.py

# Tk 宿主实跑：序章 → 初始宠物 → 主线 1–6
.\.venv\Scripts\python.exe build\_host_debug.py

# 打包 EXE 独立启动、窗口标题与首帧截图
.\.venv\Scripts\python.exe tools\check_packaged_boot.py
```

测试报告写到 `outputs/verification/`（不提交）。已核对的关键结论：

- 原任务状态：当前任务精确比较；编号早于当前=5，晚于当前=2；触发器主/支条件数组为 OR，事件条件数组为 AND。
- 原 `end state=1` 才记录事件完成；自然 EOF 也记录。
- 原 `wait` 是等待匹配操作/事件，不是固定延时。
- 出口编号编码为 `<地图 ID><落点后缀>`，例如 `722801 → map 7228`、`10105 → map 101`、`580101 → map 5801`。

## 项目结构

```text
src/
  pc_game.py          原生 Tk 宿主：地图、事件、任务、UI、遇敌、存档
  event_runtime.py    461 条触发规则与请求式事件解释器
  task_progress.py    原版任务条件计数
  daily_tasks.py      原版 DailyTask 八行、每日重置与领取
  guide.py            任务目标解析、跨地图路线、逐格自动移动
  activity_ui.py      抽宠/轮盘/孵化/商店/训练等界面
  mounts.py           原版坐骑地形规则
  game_state.py       宠物/背包/任务/事件/随机数状态
  battle.py           回合制战斗核心
  battle_ui.py        原版 Cocos 战斗 UI 渲染与点击
  original_data.py    原版表、TMX、Spine、Cocos 资源访问
  csb_reader.py       Cocos Studio .csb 解析
  csb_render.py       .csb 软件渲染与点击区域
  spine_renderer.py   Spine 2.1 静态网格渲染
  game_formulas.py    与原二进制比对过的数值公式
tools/
  recover_assets.py   从 APK 恢复资源
  extract_ui_layouts.py
  check_*.py          自动核对
  build_windows.py    PyInstaller 构建
build/
  _host_debug.py      Tk 宿主端到端调试
  _host_fight.py      战斗/捕捉宿主测试
  _battle_ui_shot.py  战斗 UI 截图
docs/screenshots/     README 截图
```

`original-1.20.4/`、`resources/`、`outputs/`、`research/`、`.venv/` 不参与源码安装；
其完整内容以 35 MiB 分卷保存在 `publish/`，拼接与校验方法见 [完整归档](archive/README.md)。

## 资源与版权

- 本仓库同时保存**移植代码、测试脚本、说明文档和原始资源归档**。
- 原版 APK、地图、图片、Spine、Cocos 布局、音频、剧情数据等版权归原权利人所有；归档用于个人保存、学习与互操作性研究。
- 本项目不是官方版本，与原开发/发行方无关联；不得将打包后的资源用于商业分发。

## 仓库

<https://github.com/mingsenz955-code/pokemon-pc-port>

当前为私有仓库；如需公开，可在 GitHub 仓库 Settings → General → Danger Zone 中修改可见性。
