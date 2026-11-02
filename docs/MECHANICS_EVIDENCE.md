# 1.20.4 规则核对记录

## 0.2.55：社区入口移除与功能菜单遮挡修复

- `community_Button` 永久隐藏并移除回调，社区/公告页不再从主界面进入。
- `uiDisappear_Button` 是原版四箭头 HUD 显隐按钮，正常位置在底部中间；
  右侧“功能”菜单展开后，它与图鉴图标重叠。现在 `visible` 条件绑定为
  `right == 0`：展开“功能”时隐藏，收回后恢复；`self.hidden` 分支也
  保持同一条件，避免 HUD 已隐藏时又被菜单重新画出来。
- `check_main_bag_shop.py` 新增断言：展开后 `uiDisappear_Button`、
  `community_Button` 均不在 `scene_ui.hits`；收起后四箭头重新出现。
- 截图：`outputs/verification/main-menu-open-0255.png`（图鉴无遮挡）、
  `main-menu-closed-0255.png`（四箭头恢复）。

## 0.2.54：单机化删减、原始初始宠物页与获得物品页

按“单机游戏不需要排行榜/礼包兑换/蓝牙对战”的要求，主界面功能菜单
只保留背包、宠物、图鉴、成就；`right_left_5/6/7` 三个非单机入口从
命中表中隐藏并移除回调，避免玩家点到空按钮。旧布局和旧代码未删除，
只是不再从主界面进入。

- `UI_LAYOUTS[7]` 原来写的是不存在的 `ChoiceFirstPetUI`，实际改为
  `ChooseFirstPetUI`。初始宠物确认现在走原版 800×480 卡面：名字、等级、
  属性系、地形、克制系、进化次数、星级和心形都来自 `Pet`/`InitPet`；
  星级按 `starLevel` 点亮，进化次数按 `evolutionCount`，不再固定五颗星。
  `confirm_Button` 调用原有 `choose_starter`，真实写档并推进剧情。
- 获得物品从宿主 `tk.Listbox` 改为 `GetItemUI` + `GetItemUIItemUI`：
  两列奖励卡、真实 `ItemIcon`/宠物头像/货币图标、名称和数量；超过两件
  支持滚轮翻页，确认按钮关闭。测试 `tools/check_get_item_ui.py` 断言
  窗口内不存在 `tk.Listbox`，且 4 件奖励显示第一页 2 张卡。
- 新增主界面回归断言：展开“功能”后 `right_left_5/6/7` 不得出现在
  `scene_ui.hits` 中。

仍不是完整 1∶1：初始宠物候选分支、道具目标选择、商店限购/刷新、
深层活动规则、动画与音频仍待继续核对。

## 0.2.53：主菜单点击、五类商店、购买确认与排行榜

这版修的是“页面能画出来但点不到/点开是错的”问题：

- 主界面右侧子菜单在收起时 `alpha=0`，但渲染器仍把它们的按钮区域算进
  命中表，导致点“功能”先被看不见的背包按钮吃掉。`SceneUI` 现在只把
  `visible` 且 `alpha>0` 的按钮放进命中表；`mainRight_Button`、
  `mainUp_Button` 点击后能展开原版动画菜单，背包红图标真实可点。
- 键盘 `B` 作为 PC 快捷入口打开 `BagUI`，不改变原版菜单。
- 商店按原版拆页：`ShopUI`（联盟商店）、`EvolutionShopUI`（进化材料屋）、
  `SkillShopUI`（技能屋）、`InfiniteArenaShopUI`（竞技场商店）、
  `MedalShopUI`（奖牌兑换）；不再用一张 `ShopUI` 冒充所有商店。
- 金币/奖牌读取 `GameState.count('700001')` 与 `700002`，并替换
  `badge_ProjectNode` / `gold_ProjectNode` 内嵌的 `8888888`；金币图标与
  奖牌图标也按节点名改回 `money_little_icon_gold.png` /
  `money_little_icon_badge.png`。
- 商品列表按每页 8 格分页，滚轮翻页；点击商品用原版 `GoodsItemNode`
  打开 `ShopGoodsUI` 卡片，显示真实图标、名称、价格和货币图标。
- 购买从错误的 `GoodsBuyConfirmUI`（复活礼包模板）改成原版
  `BuyConfirmUI`：左右按钮调数量（1–99）、`共需` 总价、取消/购买；
  确认调用 `GameState.buy(table,key,quantity)` 扣真实货币并回到原商店。
- 排行榜 `RankUI` 读取 `FightRank`、`PetCollectCountRank`、`RankNpcPet`
  实际行，替换编辑器占位“一个大鸭子 5000”；分页展示前 10 名，点击行
  显示名次/名称/数值，三个页签切换。
- 仍不是完整 1∶1：商店的限购/刷新/排序、排行榜挑战与奖励表、深层
  活动规则尚未全部接入；`RankReward` 在原表中为空，页面明确说明，不伪造。

测试：`tools/check_main_bag_shop.py`、`check_shop_goods_ui.py`、
`check_rank_ui.py`、`check_ui_buttons.py`、`check_bag_ui.py` 已通过。
截图：`outputs/verification/main-right-expanded.png`、`shop-current.png`、
`shop-detail-current.png`、`buy-confirm-current.png`、`bag-ui-current.png`、
`rank-current.png`、`rank-taofa.png`。

## 0.2.52：宠物、图鉴、成就与活动页改为原版布局

继续用手机版 APK 内的原始资源，而不是宿主 Tk 控件：

- 宠物页：`PetListUI` 整页 + `PetListItemUI` 三行，行内填充等级、生命、
  能量和亲密度；选中宠物用 `pet_image` 合成到原版 `petPos_Node`。技能/天赋
  页签切换原版 `skillInfo_Panel`，不再用黑色 `Listbox` 盖住左半页。
- 图鉴页：`item_ScrollView` 内按 3×5 合成 `IllustratedItemUI`，显示
  `PetHead` 头像、编号、名称、星级；点击卡片打开
  `IllustratedPetInfoUI`，合成宠物立绘和原版信息栏。
- 成就页：`item_ScrollView` 内合成 `AchievementItemUI`，保留原版积分栏、
  星星/旗帜/进度条；点击行查看，领取按钮只在 `ready` 行生效。仍未支持的
  条件类型继续显示“未接入”，不伪造进度。
- 连续登录、宠物银行、孵化屋、技能学习、突破、合体、融合、轮盘、坐骑/
  宠物商店：全部限制在 800×480 原版页内；隐藏宿主列表/文字区，按原版 `ContinuousLoginItemUI`、`PetBankItemUI` 等资源绘制内容，并接回原版
  按钮动作。孵化、技能学习等深层规则仍以原表/原状态为准，不伪造。
- 工作区只有手机版 APK、ARM `libcocos2dcpp.so` 和符号表，没有可直接编译的
  Java/Kotlin/Lua 工程源码；因此这里能用的是 APK 内的 `assets/Data`、
  `res/UI/*.csb`、`PlotEvent` 和原版布局/符号，而不是把安卓 `.so` 直接
  当 Windows 代码运行。0.2.52 仍不是完整 1∶1 成品。

`tools/check_pet_list_ui.py`、`check_illustrated_ui.py`、
`check_achievements.py`、`check_ui_buttons.py`、`check_activity_ui.py`
已重跑；截图在 `outputs/verification/pet-ui-current.png`、
`illustrated-current.png`、`achievement-current.png`、`login-current.png`、
`bank-current.png`、`hatch-current.png`、`skill-current.png`。

## 0.2.51：背包、商店与主界面入口

用户反馈“商店不够还原、背包也并没有”。实际截取旧实现的 Tk 页面后确认：
背包把 `tk.Listbox` 和下拉框直接覆盖在 `BagUI` 的 800×480 原图上，窗口被
撑到 804×613，列表与说明互相遮挡；商店同样用 `tk.Listbox` 盖住
`goods_ListView`。因此不是“原版页面”，而是宿主控件叠图。

现在：

- 背包只保留原版 `BagUI` 整页。`item_ListView` 的 300×319 区域内逐行合成
  `BagListItemUI`（300×89），行内使用原版 `icon_Image`、`itemName_Text`、
  `itemCount_BitmapFontLabel`，选中行显示 `selected_Image`；右侧
  `info_Text` 显示名称、数量和原版 `des`。滚动条区域支持鼠标滚轮翻行。
- 五页签按原物品分类：道具 `type 1/2/3`（含精灵球、香水、卷轴、食物和药品）、
  蛋 `5`、卷轴 `6`、重要 `4/7`、碎片 `8`。0.2.50 把 `type 2` 放进“卷轴”，
  导致精灵球不在道具页；已纠正。
- 商店只保留原版 `ShopUI`。`goods_ListView` 内按 `GoodsItemNode` 4 列×2 行
  合成商品格；格内使用原版图标底、物品图标、`name_Text` 和 `count_BitmapFontLabel`。
  点击商品格打开原版 `ShopGoodsUI`，再走 `GoodsBuyConfirmUI` 的真实购买路径。
- 主界面 `community_Button`、`right_up_1_Button`、`right_left_6/7_Button`、
  `ad_Button` 不再弹“功能未完成”，分别打开原版
  `PublicNoticeUI`、`SystemUI`、`GiftBagSaleUI`、`BluetoothListUI`
  和 `RechargeFreeUI`。这些页面中未接入的联网/音频/计费功能仍会明确说明，
  不伪造奖励。

`tools/check_bag_ui.py`、`tools/check_shop_goods_ui.py`、
`tools/check_main_entries.py` 和 `tools/check_ui_buttons.py` 已重跑；
`check_ui_buttons.py` 覆盖 63 个原版布局、162 个原版按钮、47 个关闭按钮，
未绑定按钮为 0。视觉截图保存在 `outputs/verification/bag-ui-current.png`
和 `shop-ui-current.png`。这仍不是背包/商店全部深层规则（排序、分页、
宠物选择、限购刷新等）的完成证明。

## 0.2.50：野外遇敌、原版胜利页与教程按钮

用户反馈三点，分别核对到三个独立缺陷：

1. **野外遇不到精灵**
   `load_map()` 每次切图都把 `encounter_distance` 和 `encounter_threshold` 清成 0，
   之后只在开局/战斗结束时调用 `reset_encounter()`。因此进入 201/202/601 等有
   `enemyIds` 的地图后阈值一直为 0，`check_encounter()` 永远提前返回。
   现在每次 map load 后重新读取 `enemyAppearInterval`，按原表在 30–40 格内随机阈值；
   距离按实际位移累计，达到阈值才按 `enemyProbability` 抽取 `VillageEnemy`。
   `tools/check_wild_encounter.py` 验证 201 地图阈值非 0、达到后真实建立 wild battle。

2. **战斗胜利不是原版**
   `BattleUI` 原先自绘深色框、标题和“继续”按钮。现改为合成原版
   `WorldMonsterBattleResultUI`：胜利/失败牌、宠物名、伤害值、经验提示、
   掉落/经验列表和原版 `confirm_Button` 命中区。`exp_gained`、`drops`、
   `caught_pet` 仍来自真实战斗结果，不自造奖励。
   `tools/check_battle_result_ui.py` 验证原布局、命中区和真实结果字段。
   原版的标题弹入/粒子/音效时间轴仍未逐帧恢复。

3. **教程“隐藏界面”提示点了没反应**
   `pEvent101002` 的两个 `button nodekey=uiDisappear_Button` 被当成普通对白：
   任意点击都会 `resume`，不会点实际按钮，因此既不会隐藏也不会还原。
   现在 `button` 请求只接受高亮节点的命中，点击空地不推进；点
   `uiDisappear_Button` 后执行真实隐藏/还原并恢复事件。
   `tools/check_button_tip.py` 覆盖空地不推进、按钮命中推进、隐藏状态变化。

4. **保存入口**
   左上角 `save_Button` 原先直接写盘，没有原版确认页；现改为打开
   `SaveConfirmUI`（原 `info_Text`：是否保存），`confirm_Button` 只在
   `save()` 成功后关闭并写入，`cancel_Button` 不写盘。写入路径固定为
   `%LOCALAPPDATA%\PocketNativePC\slot1.json`，属于当前 Windows 用户，
   发布包不包含开发机存档；`POCKET_NATIVE_SAVE_DIR` 仅供测试隔离。
   保存内容仍为当前地图/坐标、剧情运行时、背包、任务、宠物、镜头和
   随机数状态；战斗中明确拒绝，不写半截战斗。`tools/check_save_ui.py`
   验证原布局、确认/取消分支、原子文件和用户目录隔离。
   商店按钮接 `ShopUI`，充值奖励按钮接原 `RechargeFreeUI`；“单机版没有
   计费点”会在页内说明，不伪造充值或奖励。

## 0.2.48：修正指引触发和真实回家路线

用户明确确认原版点击“指引”后人物自动走向任务点。0.2.47 把另一个早期剧情提示
createMainTaskGuideIcon 的静态方向图标当作此功能，并错误恢复成常驻箭头。现撤回该替代：
mainUp_Button 接实际任务导航，启动前更新任务进度，默认不显示标记；再次点击或手动行走停止。
只有显式启动且有实际路径才绘制标记，方向取当前可走直线段的末端/下一拐点，
不取远端 NPC 的直线方位。G 与界面按钮共用同一个导航状态，不存在两套互相矛盾的目标。
此按钮语义以用户本次确认纠正为准，不把先前静态提示函数的局部反解当成全调用链证明。

发现并修复两个能复现“回不了家”的实际缺陷：

1. createSpriteTile 0x2df41e..0x2df43a 在 Cocos 底原点中对 x、y 均加半格，
   再调用 setSpriteTileCollide 0x2df458。旧实现只给 x 加半格，y 直接取 TMX raw y，
   导致静态碰撞多落一行。50083 妮妮家门口 (1,19) 被房体覆盖。
   现在场景 Sprite 根坐标为 (rawX+32, rawY-32)，按这个根坐标登记碰撞与可破障物；
   门口 (96,1248) 可进，相邻墙格仍阻挡，未通过清空整栋碰撞来绕过。
   旧已破障记录按对应原 TMX 对象转换坐标一次；在内存迁移并记 audit，
   手动保存才写盘，保护已有破障成果。碰撞/障碍坐标版本为 2。
2. 修正门口后，研究所出门后的最短步行路径会穿过刚出来的出口 10104，
   从 101 再进入 5801，反复往返。现在跨图路径只允许经过本次选中的出口，
   普通同图人物/区域任务路线避开全部无关出口；手动点击出口仍可主动进出。

验证：check_home_guidance.py 6 项，隔离生成与本次真实存档相同的主线4/研究所位置；
检查界面按钮启动/停止、默认无箭头、拐点方向、家门/墙体碰撞、旧障碍坐标一次迁移。
原事件未完成夹具按真实触发停在 pEvent101002 对手剧情，未跳过战斗或伪造胜利。
另一个明确标记“对手剧情已完成”的导航夹具检查地图序列严格为
5801→101→5807，并触发 pEvent5807003 原妮妮对话，不来回弹门。
这两个夹具不能拼成一次已经完成的真实全程战斗通关验收。
真实用户存档只读检查/复制，没有覆盖。

资源清点：431 张 VillageMap 全部可解析，events 目录 1686 份 JSON 文件存在。
这不证明全部剧情指令、地图出口、后期分支、UI 或结局已完整实现；完整复原目标仍未完成。

## 0.2.47：按原机制重建任务页、场景指引和换宠页

用户最新要求以原版机制和页面为准，取代 0.2.42–0.2.46 中把任务页“领取”改为自动寻路的做法。

- TaskUILayer::receiveButtonRespond 0x3bda74 只处理每日任务提交；refreshSubmitButtonState
  0x3be5c8 在主/支线隐藏按钮，daily 状态 4 可用，状态 5 隐藏。已按此恢复。
- 使用原 TaskUI 的 800×480 坐标及 286×319 列表视窗、286×44 TaskItemUI 行、
  RewardItemUI 图标/数量/背景。任务页改为原游戏 Canvas 内的覆盖层；删除原 _daily_body
  的 Tk Listbox、详情栏、额外按钮和附加高度。主/支/每日页签、选择、列表与奖励区
  独立滚动/拖动、关闭、实际每日领取接到原节点命中区。描述采用 RichTextEx 风格的动态文本高度；
  完整彩色文字标签、原 ListView 惯性和全部富文本语义尚未逐项核定。
- 直接从原 CSB 读取 TextOptions 的 h/vAlignment，字段依据官方 cocos2d-x 3.3
  CSParseBinary_generated.h；此前 JSON 丢失这些字段。字体从 ink 顶端排入原字框，减少基线裁字。
  透明 Panel/ListView 的 background_alpha=0 现在不擦除后面的原版底图；半透明底色按 RGBA 合成。
  这项修复作用于共用渲染器，不等于其他页面的自制控件已全部替换。
  来源：https://github.com/cocos2d/cocos2d-x/blob/cocos2d-x-3.3/cocos/editor-support/cocostudio/CSParseBinary_generated.h
- MainUILayer::upButtonRespond 0x3775d4 展开/收起上方菜单，bank/shop 等回调 0x377f24..
  从按钮 tag 读取本地图出口并折叠菜单；getShopList 0x2dae24 只列本地图连接的设施。
  现恢复为商店/银行/材料/卷轴/道馆，shopType 依次 1/4/3/2/5；未配置的设施不显示。
  不再把按钮序号当 shopType，也不再跨图猜最近的同类设施。
- VillageMapControler::createMainTaskGuideIcon 0x2dfecc 明确限制 main key <=17；
  getTargetSprite 虚函数给出原地图对象/目标地图，跨图选择下一出口。
  mainTaskGuideIconUpdate 0x2e1274 以最大坐标差选四向，使用原 guideIcon.png，
  距玩家 2 格、0.5 秒向外移 17 再 0.5 秒返回。已移除自制黄色屏边线/“目标”圈。
  原收集任务进行中没有空间箭头；完成后指向提交 NPC。不向后期任务添加原版不存在的箭头。
  G 自动前往仍是保留的 PC 便捷键，不能冒充原版任务页的按钮功能。
- BattleScene::showPetUILayer 0x341980 调用 PetSelectUILayer，现使用 PetSelectUI /
  PetSelectItemUI 的原行、生命/能量/等级/种类/亲密度、选中框和关闭按钮；
  六只宠物列表可滚动，强制换宠不提供关闭入口。种类图标直接取 PetKindEnum.iconTexture。
- BattleUiLayer::itemMenuItemRespond 0x353734 的已有道具分支发 sendUseItemEvent；
  现点击已有道具/球直接执行，删除额外自制确认步骤以及预测概率提示的常规入口。
  去掉自制技能/道具菜单底部说明。缺货购买、更多道具目标、完整结算/捕捉/倒下演出仍待移植。

验证：18 份相关检查脚本通过，其中 tools/check_original_pages.py 10 项；
175 份原布局经新版渲染器生成均无异常/资源诊断。这只证明可读取和绘制，
不能证明 175 页交互或运行时数据已复原。原任务/战斗 Canvas 点击检查及已有回归通过；
不操作或观察用户的真实游戏窗口，测试存档隔离。页面资产与指令对照属于局部依据，
仍需完整原版逐场景/逐页对照，不能把此记录当作所有页面已相同的证明。

## 0.2.46：PR #9 复审补修

检查 PR #9 / a88bd5b 后补修以下可复现缺陷：

- Battle._perform_round / _attempt_catch 每回合替换 events，BattleUI 却把旧列表长度当作全局读取位置。
  第二回合与第一回合事件数相同时会整回合漏播。现在跟踪列表对象与读取位置，
  新回合从头消费，同一批再次捕获不会重播。
- 我方血条在 _draw_bars 使用 mine 键，但动画快照存入 player 键，导致数字缓动而条立即跳变。
  现双方的数字和条读取相同的 side/uid 快照。
- NativeGame.start_battle 原先忽略 GameState.active_pet。现在战斗开始前选定对应队列索引；
  选中宠物倒下时使用第一只存活宠物，不重排或复制存档宠物，不消耗一次换宠回合。
  这是当前宠物页的选中语义修正；原版排序细节尚待完整核定。
- 战斗演出按宿主实际 elapsed 推进，保留小数帧并跨动作边界消费时间，避免绘制慢就变慢。
  **26 tick / 中点受击仍是 PR #9 的临时动作节奏，不等同于已恢复原技能回调。**
- 普通任务指引和点击寻路都避开可见 NPC/宝箱；下一路径格被移动 NPC 占据时重算，
  同一 tick 跨多个路径点也重新检查占用，防止越过人物。
- 支线状态和子任务计数变化会重新解析当前选中的主/支线；不会把支线重定向到另一条主线。
  原表 submitNpcs 的逗号列表（主线 33/85 等）逐项解析为真实 NPC，优先当前地图/近处目标，
  不再把整串 ID 当成一个 NPC 导致无法指引。

新增 tools/check_pr9_review.py 的 10 项无窗口回归，覆盖连续三回合、多次捕获不重播、
血条取值、真实宿主开场选宠/倒下回退、时间跨动作、动态避让、支线刷新、多提交 NPC 和重名 NPC/宝箱的确切交互对象。
测试使用新建状态/临时目录，未写入真实用户存档，也未观察用户正在玩的窗口。
原 ARM 新核读：initPlayerPet 0x2cc32c 从原 bag list 首位建立角色；attackAction 0x2d11bc
选动画并发事件；attackedAction 0x2d0218 还有 Fade/Tint 组合，说明单一中点受击仍不足以复原。
本次不声称所有战斗规则、Spine 演出、粒子/音频或全地图任务均一致。

## 0.2.45：指引入口、基础伤害和战斗动画复核

用户反馈指引无效且战斗整体不还原。本次确认并修复以下独立问题：

- 主界面任务按钮此前打开纯文本旧页；现接原 TaskUI 主/支/每日三页。
  主/支线目标按钮现在关闭任务页后启动实际寻路，到达 NPC 触发确切对象对话。
  原先只停止并把“按空格”写入已隐藏的状态栏，用户看不到这一步。
  check_scene_presentation 在研究所存档 fixture 上点击实际 MainUI 按钮，再调用 TaskUI
  目标动作，经过 Guide 移动后验证触发原 pEvent5801006，而不是远程发奖励。
- `checkPetUseSkill` 0x2c83f0 的 mainAttribute 0/1/2/3 对应力量/速度/防御/能量。
  原实现把 1/2 映射颠倒，四个已恢复公式也未被战斗调用。现在按 0x2c84d2..0x2c85d0
  的参数接 `Formula_PetAttackDamage`、`PetSpeedDamage`、`PetDefenceDamage`、`PetEnergyDamage`。
  vtable 确认偏移 0x9c 是 getMaxEnergy，0x134/0x13c 是伤害修正 getter；本次默认修正值为 0。
  移除另写的防御减半/三分之一近似，以及没有依据的 ±5% 随机浮动。
  damageAddition 0x2c91bc 在克制百分比上加 50 表示暴击，再交给技能系数公式，
  不再先对最终伤害乘 1.5。普通攻击使用 300056 表项，移除凭空恢复 10 点能量。
  check_battle_damage 新增运行时 4×100 组 ARM 对照及系数顺序、映射、能量回归。
- 画布由 1024×576 改为宿主和原 800×480 设计的等比 960×576；
  BattleMainUI 的 minePetPos_Panel / enemyPetPos_Panel 提供角色原点，
  与 `BattleUiLayer::getFightPetPos` 0x351318 读取节点的方式一致。
  原图默认朝左，左侧我方翻转朝向右侧；原点元数据随缩放/翻转保留。
- Spine 2.1 原动画接入骨骼旋转/位移/缩放、线性/stepped/Bezier、slot attachment/color、drawOrder。
  使用 stand/attack/underattack 原时间轴，移除通用突进/抖动/漂浮代替骨架动画的做法。
  动作组按事件顺序排队，演出中禁止再次点击跳过动作，HP 数字和条使用显示进度。
  161 份不同骨架的三类动画采样审计无报错；check_spine_animation 验证插值、层级、
  原点、画布尺寸和双方动作顺序；仍有 FFD/IK、原版命中时点、特效/音效等未完成。

未解决的具体范围见 RESTORATION_REMAINING.md 的 0.2.45 清单；本轮不宣称完整复刻。

## 0.2.44：研究所旧存档无法点击行走

用户实际体验报告点击地面不走。只读复制当前存档复现：地图 5801 是 21×20 格，
存档位置 (1376,1024) 的 x 格号是 21，已越界；同时 player_visible=false。
原 A* 正确拒绝越界起点，之前的空白地图单元测试未覆盖该实际宿主状态。

新增定向读档修复：仅在已选初始宠物、主线 3/状态 4、地图 5801、对应三选一脚本
或空脚本的阶段恢复可见性；越界坐标恢复到最近可通行、无人物占据的格中心。
不改变正常坐标，不跳过对话、不增加宠物，不对序章越界动画及明确隐藏指令套用修复。
在载入的内存状态记录 audit；原存档通过原有保存/备份流程处理。

check_scene_presentation 新增真实地图、MainUI 点击命中、NativeGame.tick 的联合回归，
模拟这份存档结构并完成两句原始对话后验证移动，源 fixture 哈希不变。
Windows computer-use 的 list_windows 连续超时，重置重连仍超时，尚未完成屏幕点击验收。
宠物使者未完成草稿保存在 Git stash，未混入此修复版。

## 0.2.43：NPC 提示、点击行走与支线分发

本次同步基线 `ae68f07` / 0.2.42，旧本地坐骑草稿保留在独立归档分支，未覆盖新实现。

原 `addMainTaskIcon` 0x2e71f4 使用 10+任务状态，`addBranchTaskIcon` 0x2e72a4
使用 20+状态；目标标记为 19/29。直接使用 TaskIcon 的 8 张原图：橙黄色主线、蓝绿色支线，
感叹号为可接任务、灰色问号为进行中、彩色问号为可提交；没有为普通闲聊创造未读标记。
`showTaskIcon` 0x2e70e8 的上下 4 像素/0.4 秒循环已接入。主线目标优先于主线交接，
再显示支线目标和交接；状态更改与读档换状态对象都会刷新。与 NPC 按脚底深度一起绘制，
避免悬浮在前景建筑上；逐 NPC 原节点高度和全场景缩放仍需原机对照。

`playerMoveToPosition` 0x2d92a2 选取点击格和目标 NPC，调用寻路（搜索上限 300）。
本次用已有原规则 A* 接入地面点击、原 `dianji_path.png` 路径点和 `dianji/Animation1` 终点；
HUD/剧情点击优先，方向键中断，新点击替换目标。到 NPC 相邻格中心后转向，按确切对象触发
一次对话；移动 NPC 重规划、消失 NPC 取消、封闭 NPC 不伪造对话。地图内普通路径会经过原
碰撞/坐骑/出口逻辑，同 ID 的宝箱与 NPC 用 sprite ID 区分。原版全场景目标碰撞和路径层级仍需验收。

`PlotEventManager::process` 0x2f7958 在匹配剧情后运行 NPC 支线，再回退普通对话；
`compareTriggerNpcId` 0x2f7282 对比本次发起对话的 NPC，并非战胜状态。接通 170 个 BranchTask
表行的原支线脚本选择，其中 33 个脚本含 NPC 分支；上下文随剧情存档恢复。目标图标优先，
同组按状态降序、任务 ID 升序（原比较器 0x2e35fc / 0x2e3672）。前置主线/支线条件要求全部匹配。

任务类型 8 根据真实支线提交事件计数，重复提交不计数；类型 9 按图鉴历史获得种类计数，
重复宠物和放生不改变种类数。依据 `BranchTaskItemBTaskSubmit::process` 0x2fc11c、
`BranchTaskItemIllustratedCollect::setReachCountByStateData` 0x2fbac2 及 `getPetCountByThisStatus`
0x329d9c。补充这两类任务的子任务/收录指引；不凭空指定宠物出现坐标。

另据 `PlayerDataManager::initPlayer` 0x331538..0x3315ae，角色初始化先移除队伍/银行宠物，
清空坐骑表和 IllustratedStatus 后才发放新预设。本次修正序章临时宠物的图鉴/坐骑残留，
同时重置银行及队伍选择；只影响剧情再次执行初始化，不改写已有用户存档。

新增无窗口测试：`check_branch_dispatch.py` 13 项、`check_task_icons.py` 5 项、
`check_click_navigation.py` 12 项。场景可见性回归改用用户报告的旧斯塔镇存档结构作为确定性
fixture，不再假定任意真实存档都必须显示玩家（序章可以合法隐藏）；不写入用户存档。

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

| 成就 | `Achievement` 142 行、`AchievementUI`、`AchievementItemUI`、`conditionType` 1–24 | `AchievementUI` 的 142 行全部列出；当前对 22 类本地可验证条件给出进度：1 品质/星级宠物数量、2 指定 `Item.type` 的持有种类、3 野外捕获、4 孵化、5 进化、6 指定回复/飞越道具使用次数、7 骑乘、8 银行宠物数、9 一次攻击击败、10 石化/睡眠施加次数、11 总战斗胜利、12 破障、13 NPC 谈话、14 村庄宝箱、15 到达地图、17 支线完成、18 全商店累计消费指定货币、19 指定商店店员对话次数、20 银行格子上限、22 游戏时间、23 存档次数、24 图鉴中指定 `Pet.kind` 的收集数。可领取时按原 `rewardIds/rewardCounts` 原子发奖并累计 `score`；第 21 类攻略时限和 `7201-7203` 神秘商店次数仍显示“未接入”，拒绝领取，不伪造进度。原版 `AchievementItemUI` 逐行动画尚未接入。`tools/check_achievements.py` 和 `tools/check_battle_achievement_events.py` 覆盖 142 行、22 类进度、战斗事件标记、重复领取拒绝、未接入拒绝、UI 打开/关闭 |

| 战斗商店 | `BattleMainUI.battleShop_Button`、`BattleShopUI`、`BattleShop` 12 行 | 战斗 HUD 左上角原版 `battleShop_Button` 现在真实可点，打开 `BattleShopUI`；商品按原表价格/货币购买，进入背包，购买和关闭按钮均有实际命令。`tools/check_battle_shop.py` 覆盖原按钮命中、打开、购买扣款/入库、关闭；原版商品列表逐行动画仍未复刻 |

| 剧情/地图覆盖 | 1,685 个 `pEvent*.json`、461 个触发器、431 张 `VillageMap` | `tools/check_event_coverage.py` 逐脚本解析原加密事件数据：36 种实际命令全部在 `EventRuntime` 的 PRESENTATION/STATE/INTERACTIVE 分派内，未知命令为 0；461 个触发器类型（tomap/toarea/toexit/talk/fightover/fight）均有宿主通知入口；431 张地图均能由 `OriginalData.load_map` 读取。该测试只证明“可解析/可加载”，不代表每条剧情分支、每个事件 UI 选择和每张地图的完整玩法都已逐帧复刻 |

| 背包 | `BagUI`、`item_ListView`、`tag_1..5_Button`、`use_Button`、`heCheng_Button`、`DebrisItem` | 背包现在打开原版 `BagUI`，五个分类页签分别过滤原 `Item.type`；列表叠加在原 `item_ListView` 区域；`use_Button` 调用 `GameState.use_item` 对选中宠物使用道具；`heCheng_Button` 对 `DebrisItem` 检查 `needCount`、原子消耗碎片并 `grant` 对应 `petId`，失败不消耗。`tools/check_bag_ui.py` 覆盖原布局/页签/动作绑定、70 个埃拉芬碎片合成和关闭；原版逐格物品图标、拖动和合成特效尚未复刻 |

| 宠物列表 | `PetListUI`、`itemListView_Panel`、`baseInfo_Panel`、`joinBattle_Button`、`evolution_Button`、`useItem_Button`、`free_Button` | 顶栏“宠物”打开原版 `PetListUI`；列表叠加在 `itemListView_Panel`，详情/技能/天赋切换覆盖 `baseInfo_Panel`；`joinBattle_Button` 设置真实出战索引，`evolution_Button` 调用 `GameState.evolve`，`useItem_Button` 带选中宠物进入原版背包，`free_Button` 两段确认后才放生且禁止放生出战宠物。`tools/check_pet_list_ui.py` 覆盖原布局、动作绑定、页签、出战和放生保护；原版逐行 `PetListItemUI` 卡牌、点击展开动画尚未复刻 |

| 图鉴 | `IllustratedUI`、五个 `tag_*_Button`、`item_ScrollView`、`PetKindEnum`、`encyclopedia` | 顶栏“图鉴”打开原版 `IllustratedUI`；五个页签对应原 `PetKindEnum` 1–5，列出全部 `Pet` 并按 `kind` 过滤；`✓/·` 标记是否已收录，点击显示名称、种族、星级、最大等级和技能；`findedCount_BitmapFontLabel` 与 `progress_BitmapFontLabel` 已用真实图鉴数量重绘，不再显示布局占位 100。`tools/check_illustrated_ui.py` 覆盖五页签、植物/飞行系过滤、收录标记和关闭；原版 `IllustratedItemUI` 卡片和宠物立绘动画尚未复刻 |

| 获得物品 | `GetItemUI`、`title_Text`、`item_ListView`、`confirm_Button` | 地图宝藏和村庄宝箱不再只写一行提示，而是打开原版 `GetItemUI`：标题按真实来源重绘，奖励按 `Item/Pet/Money` 表列出名称和数量，`confirm_Button` 关闭。`tools/check_get_item_ui.py` 覆盖打开、标题、奖励列表和确认关闭；`check_treasure.py` 的真实地图宝箱流程也改为验证该界面。原版逐个物品飞入/翻牌动画尚未复刻 |

| 确认/提示 | `SecondConfirmUI`、`TipConfirmUI`、`confirm_Button`、`cancel_Button` | 战斗前确认改为原版 `SecondConfirmUI`：确认才 `start_battle` 并 `runtime.resume('start')`，取消 `resume('no')`；顶栏“当前进度”改为原版 `TipConfirmUI`，不再弹 Tk messagebox。`tools/check_confirm_ui.py` 覆盖两个原版布局、按钮绑定、取消/确认关闭；原版弹窗缩放动画尚未复刻 |

| 商店详情/购买确认 | `ShopGoodsUI`、`GoodsBuyConfirmUI`、`buy_Button` | `ShopUI` 的 `goods_ListView` 改为原版位置列表，双击/“详情”打开 `ShopGoodsUI` 卡片：名称、价格、数量按商品行重绘；卡片按钮打开 `GoodsBuyConfirmUI`，确认后才调用真实 `GameState.buy`，取消不扣款。`tools/check_shop_goods_ui.py` 覆盖 商品详情 → 购买确认 → 库存/扣款 → 返回商店，并验证缩放后的 `buy_Button` 命中区 |

| 技能替换 | `SkillReplaceUI`、`skill_ListView`、`confirm_Button` | 技能学习页新增“打开原版替换界面”：按主动/被动列出当前技能槽，选择后确认才调用 `GameState.learn_skill(replace=...)`，卷轴/货币按原逻辑扣除；`tools/check_skill_replace_ui.py` 覆盖 4 槽已满、替换第 1 槽、货币扣除和关闭 |

| 宝箱开启 | `OpenChestConfirmUI`、`ChestItem` 210001、`240001` 钥匙 | 背包使用 210001 时打开原版 `OpenChestConfirmUI`，显示钥匙持有数；确认后按原 `ChestItem` 权重抽取、原子消耗宝箱和 1 把钥匙，再用 `GetItemUI` 展示真实奖励。`tools/check_open_chest_ui.py` 覆盖 确认 → 扣箱扣钥匙 → 奖励界面 |

| 放生宠物 | `FreePetConfirmUI`、`confirm_Button`、`cancel_Button` | PetList 的放生改为打开原版 `FreePetConfirmUI`，显示宠物名和等级；取消回宠物列表，确认才真正移除宠物并修正出战序号；出战中宠物拒绝放生。`tools/check_free_pet_ui.py` 覆盖取消、确认、出战保护 |

| 宠物属性 | `PetPropertyUI`、`skillTag_Button`、`talentTag_Button`、`free_Button`、`evolution_Button` | PetList 双击宠物打开原版 `PetPropertyUI`；显示名字、等级、编号和五项属性，技能/天赋标签切换真实列表和原版描述；放生走 `FreePetConfirmUI` 并在取消后回到属性页，确认放生后回宠物列表；进化调用原 `Pet.evolve`。`tools/check_pet_property_ui.py` 覆盖标签切换、按钮绑定和关闭 |

| 抽宠结果 | `LuckyDrawPetInfoUI`、`arrt*_BitmapFontLabel`、`confirm_Button` | 真实抽宠成功后打开原版结果页，显示宠物名、等级和五项属性；确认/微信按钮关闭并返回原 `LuckyDrawUI`，保留继续抽宠。`tools/check_lucky_pet_info_ui.py` 覆盖属性、按钮和返回 |

| 关于 | `GameAboutUI`、`about_Text_*` | “关于”改为原版 `GameAboutUI`，填充版本/数据来源/未完成声明，显示同一份真实说明文本，关闭按钮和 ESC 退出。`tools/check_about_ui.py` 覆盖布局、文本和关闭 |

| 技能学习确认 | `SkillLearnConfirmUI`、`petName_Text`、`skillName_Text`、`confirm_Button` | 技能学习不再直接扣费，先打开原版确认页，显示宠物、技能、消耗卷轴/货币和替换槽；确认后才调用真实 `learn_skill` 并回技能页，取消/Esc 回技能页。`tools/check_skill_learn_confirm_ui.py` 覆盖扣费前状态、确认学习和返回 |

| 进化条件 | `EvolutionConditionUI`、`condition_ListView`、`evolution_Button` | PetList/属性页的进化先打开原版条件页，列出目标宠物、等级和每种材料持有/需求；确认才调用真实 `Pet.evolve`，取消/Esc 返回来源页。`tools/check_evolution_ui.py` 覆盖真实数据和进化结果 |

| 孵化检查 | `HatchCheckUI`、`condition_ListView`、`hatch_Button`、`moneyHatch_Button` | 孵化位“检查”和双击改为原版 `HatchCheckUI`，显示经验/材料/金币；真实的取回蛋、材料孵化、金币孵化都只在该页执行，完成回孵化室。`tools/check_hatch_check_ui.py` 覆盖三种真实动作 |

## 测试和审计

- `tools/check_regressions.py`：战斗切换、NPC 道具、奖励防重复、原子回滚等。
- `tools/check_activities.py`：真实表数据的经济、小游戏和养成规则。
- `tools/check_task_progress.py`：原剧情捕捉后提交任务 6 并进入任务 7。
- `tools/check_attribute_intervals.py`：受控随机输入下执行原 ARM 区间函数。
- `tools/check_activity_ui.py`：真实 Tk 窗口启动与卡牌按钮检查、截图。控件仍有临时移植布局。
- `tools/check_ui_buttons.py`：59 个原版 UI 布局、150 个可见 Button 的真实命中区、pressed 纹理、44 个原版关闭按钮、
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

## 0.2.37：任务与指引纠错

基于 DeepSeek 更新后的 main / 86baa38 继续，没有覆盖旧审查工作树中的未提交改动。
`GuideResolver` 的类型 5/6/7 原先错误映射为到地图/等级/道具；现按 `TaskProgress` 与原
`MainTaskItemFight::getTargetSprite` 0x300eac、`MainTaskItemToMap::getTargetSprite`
0x2ffda4 恢复为战斗 NPC / 破障 / 到地图。破障没有配置固定目标地图时不猜测坐标。
剧情可显现的 state=0 人物也建立位置索引，修复任务 16 的 11522 无法定位。
`VillageMap.enemyIds` 先查 `VillageEnemy.petId` 再查 Pet；宠物 ID 与种类必须匹配同一遭遇。

`DailyTaskItem::submitTask` 0x2ff91c 在提交时发出条件类型 14；
`DailyTaskItemDTaskSubmit::process` 0x2fe1c8 对该事件累加 1。因此全能训练统计其他七项
已领取任务，而非已达成条件任务。日期回拨保留较新日期的记录，避免再次领取。

验证：`tools/check_guide_conditions.py` 7 项数据检查；
`tools/check_daily_tasks.py --logic-only` 覆盖八项计数、提交、奖励、防重复、次日重置、
日期回拨、存档往返和奖励发放失败回滚。本轮未打开窗口观察；未验证原版逐帧视觉一致。
完整范围继续由 [未完成清单](RESTORATION_REMAINING.md) 约束。

## 0.2.38：原版镜头时序与存读档

重新核对原 ARM：`setViewpointCenter` 0x2d8f50 跟随玩家位置加一个格高（Cocos 底部原点），
在 PC 顶部原点坐标中为玩家 y 减一个格高。`PlotEventItemScreenMove::begin` 0x2f5df8
检查 speedscale 是否存在，缺省值为 1；`setViewpoint` 0x2d9eb0 将目标夹在可视地图范围内，
按距离/格高×0.1/speedscale 创建 MoveTo，接 DelayTime(0.5) 和 moveScreenOver 完成回调。
speedscale=0 即刻完成；stop=1 固定镜头，其他情况完成后恢复跟随。

本次将此过程接入 NativeGame：动作未完成不 resume 剧情，完成后只回调一次；
presentation 增加 camera_action，手动存读档可恢复剩余动作而非重新执行；
渲染地图、藏宝箱光效、破障碎片及任务指引共用 camera_origin。
另补正捕捉条件字段顺序为 `(petId, petKind, mapId)`，与 TaskProgress 的事件参数一致。

`tools/check_story_camera.py` 7 项不启动窗口的检查覆盖插值、默认/零速度、停留、
恢复跟随、小地图边界、事件快照与 NativeGame 实际存读档路径；
指引 8 项、每日任务逻辑、26 项回归和事件/存档运行时检查通过。
这些检查不代表视觉逐帧一致，也不证明剧情人物寻路、相对移动、全部转场或自动备份已经恢复。
本轮按用户要求没有窗口观察，旧审查工作树中的自动备份和 Spine 等改动仍需分别整合。

## 0.2.39：剧情人物逐格移动

原 ARM `spriteMoveToPosition` 0x2dc03e：pspace=0 使用原格坐标；1 以玩家当前格为基准，
2 以玩家格和朝向为基准。朝向查表原字节 `[13,2,5,7]` 指向
0x2dc146/0x2dc130/0x2dc136/0x2dc13a，对应 `(x,y),(-x,-y),(y,-x),(y,x)`。
face=0 使用玩家朝向；这里并非以被移动 NPC 自己为坐标原点。
原数据共 1,231 条 toplace 人物参数，类型 1/2/7，pspace=0/1/2 分别 1192/30/9 条。

`moveToPosition` 0x2e6c04 区分 speedscale=0 定位与非零寻路。
`searchShortestPath` 0x2e6944、`walkableAdjacentTilesCoordForTileCoord` 0x2da6a2：
四邻接顺序上/左/右/下；直走成本 10，H 为未乘 10 的曼哈顿距离；
`insertInOpenSteps` 0x2e6630 将新节点放在相等 F 节点前。
`walkAction` 0x2e6210 按距离/格宽×0.2/speedscale 创建每段 MoveTo；
玩家基础速度受坐骑 speed/100 调整。类型 2 的 NPC 寻路对其他 NPC 有豁免（0x2d8dd2）。

新 StoryMotion 接入玩家、地图人物和临时 NPC；多个参数同时行走，全部到达才 resume
这一条 toplace，零速度仍立即定位。坐标改为顶部原点格中心，与 TMX 一致。
presentation 保存各人物路径、当前段及已用时间、朝向，读档后接着走剩余距离。
场景播放原 Cocos walk 关键帧、循环和左右镜像，导出文件和帧结果缓存避免每圈重复解析。

验证：`check_story_motion.py` 10 项，无窗口，覆盖上述坐标、速度、绕墙、并行回调、
阻塞时停止、实际地图路线、实际 NativeGame 存读档及原 walk 帧差异/循环/镜像；
镜头 7 项、26 项回归、事件运行时和每日逻辑检查通过。
仍未证明与原版逐帧一致：原寻路到不可达目标的候选终点回退、多格动态碰撞、出口上的自动
对话/换图、每个途经格的 areaProcess、原骨骼帧间插值和渲染锚点均需继续核对。
无法找到路径时当前明确停止，不直接传送到目标，也不把这次受控检查写成全剧情通关。

## 0.2.40：人物隐藏存档与原版场景菜单

用户报告的实际 slot1：map=101、x=928、y=1056、sprite=10001、main_task=1/state=4，
presentation.player_visible=false，原剧情停在 pEvent101001 第 6 条对话。
原 NPC1 图片可读，坐标位于地图内，当前原脚本前缀没有隐藏玩家的命令。
本次对旧格式（没有 player_visibility_map）的斯塔镇前六项主线存档恢复玩家可见，
当前脚本明确隐藏玩家时不修复；新保存带地图标记，后续合法隐藏状态保持。
正常换图创建的玩家显示状态也恢复初始可见。初始化时自动读取已有独立存档，不再总是重播序章。

删除 Tk 顶部工具栏与底部调试状态栏，原版 800×480 布局等比例放大到 960×576。
接回 MainUI 原图标、点击命中区和 0.2 秒菜单展开（原 0x376eb4/0x377224/0x377504）。
背包、宠物、图鉴、任务、成就、排行、抽宠、签到、地图、保存及骑乘接现有真实入口；
上方五个地点指引沿已有出口图实际行走；隐藏界面按钮保留恢复入口。
尚未接入真实数据的通知角标不显示编辑器默认数字；未完成页面仍明确提示。

`check_scene_presentation.py` 3 项：真实 MainUI 资源点击/回调，合法隐藏不误修复，
当前存档只读克隆的完整 NativeGame 初始化及离屏渲染；比较主角开/关时对应区域像素，
确认主角确实可见、根窗口只有 Canvas 被布局、原存档哈希不变。本轮未观察或操作游戏窗口。

同时恢复原寻路最近候选：insertInOpenSteps 0x2e6630 保存有父节点且 H 最小的节点，
相同 H 保留首次候选；searchShortestPath 0x2e6bd2 在不可达时采用该候选。
完全封闭则保持原位并完成动作回调，目标在地图外则只走到有效候选格，均不直接传送。
areaProcess 0x2e4934 在开始及逐格回调发送区域任务；PlotEventManager::process 0x2f7958
在 running 标志为真时忽略新剧情触发，任务计数仍处理。getAreaSpriteAtTileCoord 0x2d8eca
使用首个匹配区域。15 项移动检查覆盖回退、沿途任务和同格不按渲染帧重复计数。
原始任意事件队列、动态多格碰撞、自动交互、完整 HUD 状态和全部菜单页面仍需进一步核对。

## 0.2.41：转向、待机、行走和原地图 NPC 巡逻

用户报告普通移动始终面向一侧：StoryMotion.animation 在没有剧情动作时仍优先返回
保存的 `faces['map:1:0']`，覆盖了键盘设置的 face。现无剧情动作时由实际输入/位移决定
玩家朝向；实际移动选 walk，停止选 stand。此前 scene_sprite 对 stand 固定采第 0 帧，
普通移动也没有 walk 状态，现统一推进场景动画时间。

CCS ExportJson 的 tweenFrame=true / twE=0 轨道按原帧位置插值变换和颜色，附件切换离散；
应用原透明度。返回图片附原骨架 origin，场景按该原点定位，不再按每帧边界框的底部重新对齐。
非线性 easing、额外旋转圈数、全部混色/约束并未完整复原。图集和姿态缓存、紧凑绘制范围及
未变 MainUI 图层缓存减少逐帧重复解析；斯塔镇 9 类可见人物的 31 组站姿本机生成约 0.39 秒，
此为离屏姿态生成用时，不等于实际游戏帧率。

原 `setMoveArea` 0x2e09a8 从 TMX move 绑定区域，调度间隔 1 秒；
`setMoveState` 0x2e0954 的等待为随机整数 3–7；moveUpdate 0x2e09e4 仅对可见 NPC 扣等待，
moveByArea 0x2e0a16 随机选择区域目标，speedscale=1、face=0、寻路搜索上限=30；
moveOver 0x2e0adc 重新进入等待。getRandomPosition 0x2d5df4 用
truncate(min + randomFloat × (max-min-1)) 选格。
斯塔镇原配置为 10103/10111/10112/10115，隐藏的 10115 不执行巡逻，其余无 move 配置的人物
不添加虚构的随机行走。巡逻独立于剧情动作回调，剧情/战斗时暂停；保存等待、路径及独立随机
状态以恢复继续巡逻。随机分布及状态机已接，原 C++ RNG 的逐位序列尚未对齐。

验证：`check_scene_animation.py` 6 项无窗口检查，覆盖旧剧情朝向不覆盖四向输入、实际位移
转向、待机帧及插值变化、镜像原点、仅原配置且可见 NPC 巡逻、不会误推进剧情指令，以及
巡逻状态/随机数保存恢复。15 项剧情移动、7 项镜头、3 项当前存档副本场景检查、26 项回归通过。
未对用户正在玩的窗口进行观察或操作；不以这些检查声称全部原动画逐帧一致。

## 0.2.42：建筑碰撞、遮挡、任务指引与稳定启动器

此前只加载 collideLayer 和 obsType，完全漏掉原加密 Sprite/spriteTile.json 的 348 个
SpriteTileData 定义。现按原替换字母表解码，读取 collideInfo 的多格偏移，
setSpriteTileCollide 0x2e4e8c 以 `(tx+dx,ty-dy)` 写入占用格。塔楼 50168 的四格与
商店 50166 的门口空格保留原形状，不使用整张图片的矩形作为碰撞。
compareSpriteTilesAble 0x2e0bfc / getIsFlying 0x2e0b1c：普通及地面坐骑受阻，合法飞行
可忽略静态 SpriteTile 碰撞；地图禁用仍生效。可破障物继续使用原可移除 obsType 层。

建筑图片按原 positionOffset 定位；场景不再将建筑全部烘焙到人物背后，而是与人物按脚底 y
一起排序，人在塔楼后面时由塔楼遮挡。旧存档若在自由行动时卡进新恢复的建筑碰撞格，会移到
最近有效地面格并记录旧/新坐标，保留任务、背包、宠物；剧情动作中的合法放置不自动改动。
多种动态碰撞和层级仍需继续全场景对照。

指引旧代码固定 movement_speed/60 且每格清点后 return，实际 25Hz 左右使速度偏低且每格停顿。
现由 NativeGame 传入实际 elapsed，消费整段距离，跨格不加停顿。NPC 目标到相邻格中心才停止，
不再以 150 像素提前结束；同图优先取实际移动 NPC 的坐标，主线状态变更后刷新任务目标。
按用户明确要求，场景“指引”按钮改为当前任务目标入口；不把此用户指定行为冒充全版本原 UI 一致。

新增固定 Windows 启动器。tools/build_windows.py 全部成功后才原子发布 current-release.txt，
桌面唯一快捷方式保持不变。旧快捷方式归档，旧游戏包与存档保留。启动器不会读写玩家数据。
check_launcher.py 编译并执行 resolver 模式，验证完整版本切换、拒绝未完成包、相对路径及入口不变；
check_traversal_update.py 4 项验证原塔楼碰撞、飞行例外、门口空格、真实绘制遮挡和按时间连续指引。
坐骑 10 项（含 431 图分类）、场景/移动/镜头回归仍单独检查，未据此声称全部按钮或全剧情完成。

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
