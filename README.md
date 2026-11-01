# 口袋妖怪单机版 · 原生 Windows PC 移植

[![状态](https://img.shields.io/badge/status-0.2.2%20development-orange)](#当前完成度)
[![平台](https://img.shields.io/badge/platform-Windows%2010%2F11-blue)](#从源码运行)
[![Python](https://img.shields.io/badge/python-3.12-3776AB)](https://www.python.org/)

使用《口袋妖怪单机版》1.20.4 原版数据、地图、Cocos UI 与 Spine 资源制作的**原生 Windows 桌面移植**。不是安卓模拟器封装，不依赖网页或网络服务。

> **当前是 0.2.2 开发版，不是完整 1∶1 成品。** 序章、初始宠物、战斗与捕捉、主线 1–6 有受控测试；不代表全程步行通关。大量系统和页面、原版动画及转场仍未完成。遇到未实现的机制会明确停下，不伪造通过。

### 当前开发改动

新增抽宠、幸运轮盘、卡牌、孵化、银行存取、宠物商店、技能学习及卷轴、训练和突破的交互；
修复战斗换宠与 NPC 用药、奖励重复领取、扣费失败留下部分修改、主线任务 6 捕捉后卡住等问题。
护士治疗与普通地图宝箱也已接入。0.2.2 修复战斗按钮完整节点名未分发的故障；
按原 ARM 回调恢复“点我方打开补给/换宠，点敌方打开技能”的入口，补蓝/补血各筛选对应道具，
保留原图标与菜单坐标，技能/道具说明可点击。取消遮挡敌方血条的自制日志框；静态战斗帧复用以减少无效重绘。
坐骑现在按原表区分地形通行、地图禁用、自动换乘和手动飞行；基础移动速度 320，坐骑按 speed/100 缩放。
**这些改动仍不代表完整复刻**：竞技场、合体、完整坐骑交互、
地图障碍、后期主支线、技能状态细节和原版动态 UI 等仍有大量工作。

核对地址、测试及差异见 [规则核对记录](docs/MECHANICS_EVIDENCE.md)。
原交接文档保存在 [DeepSeek 交接](docs/DEEPSEEK_HANDOVER.md) 和
[原始接续要求](docs/DEEPSEEK_REQUEST.txt)，其中历史完成度及旧电脑路径不作为当前验证结论。

开发对照测试使用 `pip install -r requirements-dev.txt`，原生游戏仍只需 `requirements.txt`。

### 启动及战斗操作

本地打包产物为 `outputs/口袋妖怪-PC移植开发版0.2.2/口袋妖怪-PC移植开发版0.2.2.exe`。
双击 EXE；保留旁边的 `_internal` 和 `data` 文件夹。WASD/方向键移动，空格/E 对话，F5 保存、F9 读取。
战斗时点击我方宠物打开补给/背包/换宠，点击对方宠物打开技能/普通攻击/捕捉。
说明按钮打开技能或道具原表说明，单击关闭。训练师战斗不显示逃跑和捕捉。
游戏存档独立存放在 `%LOCALAPPDATA%/PocketNativePC/slot1.json`，新包沿用原移植存档。
恢复 APK 时可用 `python tools/recover_assets.py 游戏.apk original-1.20.4 --research-output research`；
恢复工具会拒绝覆盖非空资源目录。原资源与 ARM 分析文件不随源码提交。

## 画面

| 原版世界地图 | 原版战斗界面 |
| --- | --- |
| ![世界地图](docs/screenshots/world-map.png) | ![战斗主界面](docs/screenshots/battle-main.png) |

| 技能菜单 | 野外遭遇 |
| --- | --- |
| ![技能菜单](docs/screenshots/battle-skills.png) | ![野外遭遇](docs/screenshots/wild-encounter.png) |

| 序章 · 十年前迪尼斯城 |
| --- |
| ![序章](docs/screenshots/prologue.png) |

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
- **原版战斗 UI**：`BattleMainUI`、`BattleButtonMenuNode`、`BattleSkillMenuNode`、`BattleItemMenuNode`，含原版背景、宠物 Spine 立绘、HP/能量条、状态、队伍点、日志、确认与结算面板。
- **地图随机遇敌**：按原 `VillageMap.enemyAppearInterval`（30–40 步）和 `enemyProbability` 权重选择 `VillageEnemy`；该逻辑由 `VillageMapControler::checkEnemy` / `DataManager::fightWithVillageMapEnemy` 反汇编核对。
- **背包/宠物界面**：背包可使用原版回复道具并扣除数量；宠物界面显示等级、生命/能量、五维、品质、突破、亲密度、技能、天赋，并支持数据驱动的进化尝试。
- **独立存档**：保存剧情位置、地图、背包、任务、事件状态、宠物、随机数状态；原子写入并保留 `.bak`。战斗中存档会明确拒绝，避免写入不一致状态。

### 部分完成

- **商店**：可读取原 `Shop` 表并购买，但尚未按原 `VillageMap.shopType` 做完整货架过滤。
- **战斗状态**：已覆盖主要状态与持续伤害/回复/免疫/驱散；57 种状态中仍有少数目标选择与叠加规则待逐条核对。
- **宠物养成**：已接入进化与基础属性；训练、突破、融合、品质、携带物尚未完整。
- **地图交互**：出口、传送、区域触发已接入；部分场景障碍/骑乘/采集仍会停止并提示。

### 明确未完成

- 战斗内存档与战斗中断恢复；
- 全部 57 种 `SkillState` 的完整语义、天赋/携带物全结算；
- 宠物图鉴、训练、突破、融合、品质、放生、仓库整理；
- 完整背包、任务列表/追踪、商店货架、道馆、竞技场、无限竞技场、轮盘、卡牌传说、赛宠、圣兽使者；
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
| 顶部按钮 | 宠物、背包、任务、保存、读取、关于 |
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

# Tk 宿主实跑：序章 → 初始宠物 → 主线 1–6
.\.venv\Scripts\python.exe build\_host_debug.py
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

`original-1.20.4/`、`resources/`、`outputs/`、`research/`、`.venv/` 均被 `.gitignore` 排除。

## 资源与版权

- 本仓库只包含**移植代码、测试脚本和说明文档**。
- 原版 APK、地图、图片、Spine、Cocos 布局、音频、剧情数据等版权归原权利人所有，**未上传到本仓库**。
- 本项目用于个人学习、保存研究与互操作性研究；请自行合法取得原版资源，不要将打包后的资源用于商业分发。
- 本项目不是官方版本，与原开发/发行方无关联。

## 仓库

<https://github.com/mingsenz955-code/pokemon-pc-port>

当前为私有仓库；如需公开，可在 GitHub 仓库 Settings → General → Danger Zone 中修改可见性。
