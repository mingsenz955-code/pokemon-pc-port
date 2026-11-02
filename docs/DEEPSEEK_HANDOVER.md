## 2026-11-02 / 0.2.58 接续

分支 codex/restore-special-battle-effects，基于 0.2.57/7bb529c，需先合入 PR13。新增六类特效计划与多命中时间线、已见图鉴保存、可见区域寻宝与原雷达。优先跑 check_special_battle_effects.py、check_seen_encyclopedia.py、check_treasure_search.py，以及 battle/原页面/道具/存档回归。详见 VERIFICATION_0.2.58.md。

不要将 path2 当成敌方特效；目标读取 Skill.effectpos。寻找宝藏必须传入当前地图和世界坐标可见矩形；搜索失败仍会消耗道具。新 seen_species 存档字段的历史缺失只能从捕获记录恢复。完整剩余项仍在 RESTORATION_REMAINING.md 顶部。

## 2026-11-02 / 0.2.57 接续

基线 origin/main=c104ab8，分支 codex/fix-original-inventory-pages。新增 pet_pages.py（原宠物行/说明框）和 particles.py（原 plist 星光）。不要回退最近商店/地图/战斗改动。优先跑 check_inventory_interactions.py、check_original_page_flows.py、check_pet_list_ui.py、check_pet_property_ui.py、check_continuous_login.py、check_treasure.py、check_activities.py、check_regressions.py。

桌面 helper 超时，本次未完成屏幕试玩；连充无支付资格服务。全部剩余边界以 RESTORATION_REMAINING.md 顶部为准，不要宣称全部复刻完成。玩家存档和旧包保留。

## 2026-11-02 / 0.2.56 接续基线

主目录 main 后续变更在 codex/restore-original-pages-effects 分支交付。不要回退到 0.2.55 的 mainUp_Button 地点菜单；用户已确认点击指引必须自动走向当前任务点。

本版把原卡片组合、点击/裁剪/悬停放到 src/original_pages.py，地区图在 src/area_map.py，普通技能特效在 src/battle_effects.py。原代码依据见 docs/MECHANICS_EVIDENCE.md 顶部，未完成项见 docs/RESTORATION_REMAINING.md。不要把原 ARM 推断或局部测试写成全部复刻完成。

优先回归：tools/check_original_page_flows.py、check_home_guidance.py、check_shop_goods_ui.py、check_continuous_login.py、check_battle_clicks.py、check_spine_animation.py。测试必须用临时 POCKET_NATIVE_SAVE_DIR，禁止改写玩家真实 slot1.json。部分 Canvas 点击测试需要映射窗口，现有脚本用 alpha=0 隐藏；不要随意 withdraw 该脚本窗口导致 event_generate 不投递。

重要修正：登录奖励按原 checkLoginInRewardCanReceived / loginRewardReceived 累计，断登不清零；普通技能以原 Armature fi/evt 命中与音效帧推进，不再按26个宿主tick一刀切。特殊弹道、粒子、全部多段、全部图鉴状态、地图云雾/传送规则和后期剧情继续待做。

桌面只用固定“口袋妖怪”入口，build_windows.py 全部完成后才切换版本。当前运行中的旧游戏应由玩家保存后自行关闭重开，禁止强杀或替换玩家存档。

---

# 给 DeepSeek 的接续提示词（可整段复制）

你要接续一个已开始的游戏移植项目，请先读取本文件以及项目源码，不要重新从零画一个类似的宝可梦游戏。

## 最后交接检查点（本轮继续开发后的状态，优先于后文早期描述）

- 源码入口仍是 `src\pc_game.py`：`.\.venv\Scripts\python.exe src\pc_game.py`。原生 0.2 EXE/ZIP 已生成：`outputs\口袋妖怪-PC移植开发版0.2\口袋妖怪-PC移植开发版0.2.exe`、`outputs\口袋妖怪-PC移植开发版0.2.zip`；0.1 验证包仍保留，未覆盖。打包脚本已改为 `pc_game.py`，并补入 `libexpat.dll`、`libssl-3-x64.dll`、`libcrypto-3-x64.dll`，否则原 `plistlib`/`xml` 导入会缺 DLL。
- **本轮已实际接入**：真实序章 7401→7228→5807→101、研究所初始宠物三选一（`openui 7`，InitPet 1/2/3）、主线 1–5 的任务状态推进、原版战斗核心与战斗 UI、野外遇敌、战斗内道具/捕捉。
  - 战斗核心 `src\battle.py`：原伤害/克制/暴击/状态/掉落/经验/升级/捕捉率/敌方 AI/换宠/逃跑；仍有个别状态特殊目标与携带物未完整核定。
  - 战斗界面 `src\battle_ui.py`：原 `BattleMainUI`、`BattleButtonMenuNode`、`BattleSkillMenuNode`、`BattleItemMenuNode`，宠物 Spine 立绘、HP/能量条、状态、队伍点、战斗日志、技能/道具/精灵球分页、确认和结算面板。
  - 敌方/野外战斗：`VillageEnemy` 加权选取；`VillageMap.enemyAppearInterval` 决定 30–40 步遇敌，`enemyProbability` 为权重。反汇编依据：`VillageMapControler::setEnemyAppearStepNum`、`VillageMapControler::checkEnemy`、`DataManager::fightWithVillageMapEnemy`。
  - 任务状态修正：`submit_task` 的下一主线状态改为 **4**（上一轮曾误设 3），这样原触发器 `pEvent5801001`(2,4)、`pEvent5801006`(3,4)、`pEvent101002`(4,4) 才能按原顺序触发。`advance_main_condition` 仍按 `MainTask.conditionType` 处理 1/2/3/4/5/6/7。
  - 出口语义修正：原 `tomap`/出口编号是 `<地图ID><落点后缀>`（如 722801→map7228、10105→map101、580101→map5801），`request_map` 现按此解析，不再错误地扫描同号出口。
  - 已接入 `mainuivisible`、`addteachnode`，不再把它们当未实现错误；教程 `button`/`tapscreen` 在战斗中作为提示继续。
  - 战斗/道具修复：新增 `Battle._use_item`（按原 `Item.des` 的“生命/能量/全回复”解析），确认使用道具时由宿主扣 1 个；`choose_skill(0)` 普通攻击不再误走 `_use_item`。野外捕捉会扣球并把宠物加入队伍/仓库。
- 已通过测试：
  - `tools\check_original_formulas.py`：15 函数 × 200 组，3,000 组一致。
  - `tools\check_game_runtime.py`：触发、任务、存读、原子扣费、奖励不可重复、缺结果停止均通过；`native_host_full_gameplay` 现为“partial: prologue→starter→main task 4 verified”。
  - `tools\check_battle_runtime.py`：NPC 战 48 回合胜利、野外战捕捉成功；报告 `outputs\verification\battle-runtime-checks.json`。
  - `build\_host_debug.py`：Tk 宿主实跑 序章→冠军战→初始宠物→主线 4→商店任务 6，状态/事件/宠物均保留。
  - 截图：`outputs\verification\battle-ui-main.png`、`battle-ui-skills.png`、`battle-ui-items.png`、`battle-ui-balls.png`、`host-fight-result.png`、`wild-encounter.png`、`exe-prologue.png`。
- **背包/宠物界面**：不再只是文本列表。背包可对受伤宠物使用原版回复道具并扣数量；宠物界面显示等级/生命/能量/五维/品质/突破/亲密度/技能/天赋，并可尝试原版数据驱动的进化。
- **仍明确未完成，不能称完整还原**：57 种状态的完整语义、天赋/携带物全结算、全部技能动画/招式表现、战斗内存档、宠物图鉴/训练/进化/突破/融合/品质、完整背包与道具使用、支线任务全流程、商店按原 shopType 过滤与购买交互、道馆/竞技场/无限竞技场/轮盘/卡牌/赛宠/圣兽使者、原 Spine 时间线动画、音乐音效全接入、结局与全流程回归。
- 开发原则不变：区分“已由二进制/数据验证”“推断”“未实现”；缺机制抛 `PendingMechanic` 或明确提示，不自动通过、不伪造奖励、不覆盖 0.1 包与原始 APK。
- 源码与文档均未提交 Git；不要因 git log 空而丢弃。

## 用户真正要什么

用户用四张旧游戏截图要求：尽可能 1∶1 还原其童年《口袋妖怪单机版》的**所有内容**，制作**原生 Windows PC 单机版**。用户已明确表示“我想要pc版”“我要求你还原所有”。安卓模拟器封装不能当成原生 PC 移植完成。用户没有接受把地图浏览器、演示版当作游戏成品。

不要把未完成内容声称完成；不要靠跳过剧情、自动获胜、伪造奖励、占位界面、任意编造伤害或更换成另一款宝可梦游戏来“还原所有”。能独立推进就继续做，不要反复请求确认。不要覆盖已有原 APK、原资源和历史验证版；不要破坏已有存档。

## 项目位置与素材

项目根目录：`C:\Users\Mingsen\Documents\ChatGPT\口袋妖怪`

1. 候选旧版 APK：`resources\口袋妖怪_1.20.4_候选旧版.apk`。
   - 66,479,496 字节，包名 `com.zzlt.pet.oppo`，内部版本 `1.20.4`，代码 `70`。
   - MD5 `11423b7795ff53819f8f42d65b76455d`。
   - SHA256 `df9a3d1a9832c3a13dc8981013ef252621a62b8852d5422e1b6c1d0425280508`。
   - MD5 与多个旧下载页公开记录一致，但这不等于独立验证官方签名、安全性或精确童年构建。
2. 玩家改版 APK：`resources\口袋妖怪_1.33.0_玩家修改包.apk`，包名 `com.zzlt.pet.zmkz`，MD5 `aa5d446ae2f06bc87a909c4cad1c6d2b`。不要把它当成旧版。它的宠物上限 300，而 1.20.4 配置上限 170；用户第 3 张截图却有 230 级，所以截图的精确版本仍不确定。
3. 已恢复的旧版素材：`original-1.20.4\assets\`。
   - 地图 `assets\Map\`：447 个 TMX（含区域地图等），431 条场景配置。
   - 人物骨骼 `assets\Sprite\CcsAni\`：Cocos Studio `ExportJson` + plist + PNG。
   - 宠物骨骼 `assets\Sprite\Spine\`：Spine JSON + atlas + PNG。
   - UI `assets\res\UI\`：原 PNG、字体、Cocos Studio `.csb` 布局；不是所有屏幕都已移植。
   - 音乐和音效 `assets\Audio\`。
   - 1,687 张 PNG 已通过结构验证；其中 603 张已恢复原游戏自定义文件头。原 APK 不改动。
4. 已解码数据：`original-1.20.4\tables.json`，83 张表，315 条宠物配置、105 条技能、57 条技能状态、155 条主线、170 条支线等。
5. 已解码剧情：`original-1.20.4\events\`。注意 `pEventContents.json` **不是剧情步骤文件**，而是 461 条触发规则；其余文件才是剧情步骤。上一次把所有 JSON 统称 1,686 份脚本，后续应区分元数据与可执行脚本。
6. 原始核心二进制：`research\original-core.so`，从 1.20.4 原 APK 取出的 ARM `libcocos2dcpp.so`，仅用于分析，不是 Windows DLL 或源码。
7. 原程序符号：`research\original-symbols.json`、`research\demangled-symbols.json`。
8. 参数实例：`research\event-command-examples.json`（旧文件包含触发元数据里的 type，统计时需排除 pEventContents）。
9. 搜索与版本记录：`research\资源搜索与版本核验.md`。
10. 用户截图原路径位于 `C:\Users\Mingsen\xwechat_files\wxid_tsn7em6j9tqc22_ea0b\temp\RWTemp\2026-11\9e20f478899dc29eb19741386f9343c8\`，四个文件名分别为 `c13e5b2fd74fdd9a0c3fbcd103481bba.jpg`、`cfd5cb47e06e213e2ce101649139ba5f.jpg`、`f3983d6a531cfdc14fbf4771b8da46e2.jpg`、`b309baa28c47f63f4899edae08b5480d.jpg`。如临时文件已失效，应保留已恢复游戏素材继续推进。

## 已有代码与真实完成程度

- `src\original_data.py`：读取原版数据、TMX、PNG、Cocos Studio 骨骼静态姿态；渲染地图与静态人物。
- `src\pc_preview.py`：Tk + Pillow 的原生 Windows **验证程序**；地图移动、部分出口、少量开场脚本、原配置浏览、独立位置存档。它不是完整游戏。
- 当前打包 EXE：`outputs\口袋妖怪-PC移植验证版\口袋妖怪-PC移植验证版.exe`。
- 历史完整打包 ZIP：`outputs\口袋妖怪-PC移植验证版.zip`，约 82 MB。EXE 同目录 `data`、`_internal` 必须一起保留。该包是此前 0.1 阶段成果，不包含本轮新加入但未重新打包的模块。
- `src\game_formulas.py`：本轮新增，15 个原程序数值函数已翻译为原生 Python，严格逐步 binary32 舍入。
- `tools\check_original_formulas.py`：用 Unicorn **仅在开发测试中**执行原二进制的纯数值函数，与原生实现比较。15 个函数各 200 组输入、共 3,000 组结果全部一致。报告 `outputs\verification\original-formula-comparison.json`。这个测试的 CPU 模拟器不能混进游戏包，也不代表游戏整体逻辑已验证。
- `tools\inspect_binary.py`：只读 ARM/Thumb 反汇编，识别函数符号、浮点常量和 Thumb→ARM veneer。
- `tools\recover_assets.py`：从校验匹配的 APK 可重复恢复 PNG 头、剧情和表格。
- `tools\check_native.py`：此前验证地图解析、开场文本、未支持战斗指令必须停止、位置往返、画面生成。
- `tools\build_windows.py`：打包工具，补齐 Anaconda 环境下 PyInstaller 容易漏掉的 ffi/tcl/tk/yaml/zlib DLL。运行时请用项目 `.venv\Scripts\python.exe`。

尚未完成的重点：完整战斗状态机、完整技能和天赋效果、捕捉与随机生成、养成的所有属性修正、完整任务条件统计、道馆、商店/背包的全部交互、骨骼动画、原 UI 动态交互、原安卓存档兼容与全流程回归。触发器、存档、原布局等已继续推进，精确状态见文首最新检查点。**不要把目前状态当作已经实现全部游戏。**

## 本轮关键新发现

### 剧情触发规则

`events\pEventContents.json` 共 461 条：`toarea` 196、`tomap` 127、`toexit` 70、`talk` 63、`fightover` 4、`fight` 1。

字段：`id`、`type`、`conditions_add`（map/area/npcid/exit 等）、`conditions_event`（事件编号与状态）、`conditions_mtask`、`conditions_btask`（任务编号与状态）、`repeat`、`ending`。

开场不是斯塔镇短对话。真正故事前奏从地图 **7401** 的 `pEvent7401001.json` 开始，涉及十年前冠军赛，随后 7228、5807，再回到 101。此前验证版直接从 101 开始，不能称作完整序章。

任务状态语义尚须核对。脚本/触发数据显示：主线 2 状态 4 时可向朗基罗博士领取徽章；任务 3 状态 3/4 用于选择/取得初始宠物；已提交后的条件常用状态 5。请结合原二进制确认，而不是随便定义全部通过。

原有剧情指令包括 topplace、face、toface、spritevisible、tempnpc、talk、airtalk、aside、fight、fightover、goto、tomap、submittask、accepttask、costtaskitem、eventstate、taskstate、openui、closeui、screen、screenclose、screenflash、screenmove、areamapmove、wait、function、button、tapscreen、mainuivisible、addteachnode、trialride、save、init、iarenastate、end。`goto` 参数分支含 mtask/btask/npcfight/npcid/initid/ride/event/iarenaid 和 state/id，不能一律跳第一分支。

### 已经由原机器码验证的数值函数

`src\game_formulas.py` 中的 15 个函数已经通过原二进制独立比较，保持测试。核心地址例如：

- 升级经验 `0x2b5954`。
- HP 属性 `0x2b598c`；其他属性 `0x2b59d8`。
- 力量/防御/速度/能量伤害 `0x2b5a4c` / `0x2b5aa8` / `0x2b5b2c` / `0x2b5b98`。
- 技能附加伤害 `0x2b5c08`；逃跑 `0x2b5c3c`；经验分配 `0x2b5c54` / `0x2b5cdc`。

属性参数顺序是 `(base, variation, growth, level)`，不是把 base 与 growth 先相乘。原始公式 `int(base + ((base + variation) * growth / 100) * level)`，HP 的增长项额外乘 1.8。函数调用时仍需追查各参数的原本来源，不能因为单个公式一致就宣称完整战斗一致。

`D:\MinGW\bin\c++filt.exe` 必须加 `-n`，否则 Windows 默认去下划线导致符号不解码。

已保存反汇编：`research\formula-disassembly.txt`、`research\battle-stat-disassembly.txt`。后者是在 veneer 注释补充之前生成的，必要时重新用 inspect_binary 生成。

### 原 UI 可继续解析

游戏保留了原 `.csb` UI 布局。已经通过 GitHub 连接器发现 Cocos2d-x 官方 schema：

`https://raw.githubusercontent.com/cocos2d/cocos2d-x/v3/cocos/editor-support/cocostudio/fbs-files/CSParseBinary.fbs`

该 schema 已下载，CSB 解析器和 175 份布局导出已完成，见文首最新检查点。不要使用整屏截图当作可交互界面；界面交互行为仍需根据原游戏代码逐项恢复。

## 建议继续顺序

1. 先读源码和上述报告，确认文件确实存在、测试还能跑通。
2. 将 pEventContents 的全触发、条件状态、分支、跨地图连续执行和持久化独立成数据驱动模块，按真实序章接入。
3. 实现完整宠物/背包/任务存档数据模型，继承已验证的公式，保存随机种子和所有状态；不要只保存位置。
4. 继续反向核对技能效果、状态、捕捉率、经验、敌方 AI 等实际逻辑；区分已验证、推断和待实现。
5. 恢复原 Spine 动画、Cocos UI 布局与所有可操作界面，再接完整战斗、养成、道馆、经济与支线。
6. 对每个系统做实质测试，推进真实流程，从原始序章到结局及支线，不能通过直接跳地图来冒充流程通过。
7. 每次只在验证范围内报告进度，直到确实完成再称完整；保留原版资源和 0.1 验证包。

用户希望持续推进到所有内容，不要只给计划就停下；不要因为这份交接文件存在就认为用户取消了任务。
