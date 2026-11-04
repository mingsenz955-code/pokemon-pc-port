# 0.2.96 验证记录：X 2.10.9 默认数据

本记录对应独立工作区 `D:\口袋妖怪-X2109-独立开发`。原工作区已恢复到 APK 导入前的 `e575b3d`，本工作区从该版本重新开始。

## 数据来源

- APK：`C:\Users\Mingsen\Downloads\口袋妖怪X_2.10.9.apk.1`
- SHA-256：`054F4EEEC42919C35D4527999B7A56AF7755A0259B7A6FE110CC81868F1588E9`
- 解包数据：工作区 `research/apk-x-2.10.9`
- 生成数据：`x-data`，由 `tools/stage_x_full.py` 从解包数据生成；开发模式可链接 400 MB 资源，发布构建会复制实际文件。

## 已验证项目

运行：

```powershell
& .\.venv\Scripts\python.exe -u tools\check_x_full.py -v
```

结果：**10 个测试全部通过**。

- 数据规模：575 张 `VillageMap`、606 种 `Pet`、296 个 `Item`、162 个 `Skill`、500 条 `NpcFight`、668 条 `VillageEnemy`、2,320 个事件文件。
- 全部 575 张地图成功解析；29 张使用外置 TSX 图块的地图不再因路径或 gzip 数据失败。
- 全部 176 个 `res/UI/*.csb` 成功解码并渲染。
- 全部 2,318 个可执行事件文件成功载入 `EventRuntime`，含 X 的重复/零步骤 id。
- 全部 500 场 NPC 战斗和 668 个野外配置成功实例化，含 X 101025 的异常天赋概率行。
- 从 `pEvent119007` 开始受控播放 X 对话，自动点击到第一场战斗；战斗敌方均来自 X `NpcPet`。
- 旧 1.20.4 存档可载入 X 数据并恢复到相同地图。
- 启动 `OpeningUI` 可渲染，跳过序章后进入 7401。
- `gzip` TMX、外置 TSX、`pcWalkThrough` 和特殊路线修正均已加入。

另运行了回归：

```powershell
& .\.venv\Scripts\python.exe -u tools\check_event_coverage.py
& .\.venv\Scripts\python.exe -u tools\check_battle_clicks.py
& .\.venv\Scripts\python.exe -u tools\check_battle_runtime.py
```

均通过（1.20.4 数据）。

## 兼容性修复

- `OriginalMap` 支持 base64 + gzip 压缩层。
- `OriginalMap` 解析外置 `.tsx` 图块并跟踪缺失引用。
- `OriginalMap` 支持 X 的 `pcWalkThrough`。
- 光之城 2101 补回 `210102` 出口；巴特姆希 1101 把返回传送门归入出口层；奈特美尔洞 7502 的装饰石不再阻塞唯一触发格。
- `Pet` 101025 的 `talentNum`/`talentNumPro` 长度不一致时按已有权重回退，避免战斗生成崩溃。
- 事件奖励、`StoryToken`、主线续接、战斗捕捉信物、战斗入场动画与 X 序章已接入。

## 尚未完成

- 没有对 `libcocos2dcpp.so` 做逐函数还原，不能声称二进制级 1∶1；部分新逻辑仍可能依赖尚未解码的原版行为。
- APK 本身缺失 4 个触发脚本：`313901`、`315901`、`421502`、`507902`；已从 `pEventContents` 中剔除，未伪造内容。
- 未进行从序章到结局的全程步行通关；当前结论限于自动化加载、受控剧情/战斗和代表性 UI。
- X 的少数附属动画、特效组合、战斗镜头和支线边界仍需逐项核对。
- 1.20.4 回退可用 `POCKET_NATIVE_DATA=original-1.20.4`；默认源码数据为 `x-data`（存在时）。