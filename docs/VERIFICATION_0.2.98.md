# 0.2.98：品质颜色和闪光宠物

日期：2026-11-05。本版包含 0.2.97 的战斗、药水与性能修复。

## 原版证据

- 品质由每只宠物的 variation/growth 计算，PetQuality 为白、绿、蓝、紫、橙五档；不等同于物种星级或闪光标记。
- 重新读取 APK 的 DataManager 静态初始化器 0x2aa0b4，得到白 `(255,255,255)`、绿 `(1,127,13)`、蓝 `(0,123,180)`、紫 `(146,0,177)`、橙 `(255,229,8)`。保留原程序数值，不按颜色名称另选近似色。BattleUiLayer::refreshMinePetInfo 0x3507f0 使用 quality+1 调用 getFontColor 0x31a3f0。
- Pet 表有 149 条 `flash=1` 的物种形态，通过物种 ID 和 flashPetId 区分。正常/闪光形态可能共用同一套 Spine 文件，不能仅凭文件路径判定显示相同。
- PetSprite::init 0x346248 和 PetController 使用 getFlashAction 0x2b93ac。该动作是 15 段、每段 0.4 秒的 TintTo + RepeatForever：黄→白→橙→白→红→白→粉→白→紫→白→蓝→白→浅蓝→白→绿，再循环。它调制原贴图 RGB，保留透明度，没有擅自添加光环或替换立绘。
- `tools/extract_native_pet_colors.py`、`tools/inspect_x_binary.py` 可重现提取；证据在 outputs/verification/0.2.97/native-font-colors.json、native-pet-appearance.txt、native-quality-ui.txt。

## 显示修改

- 品质名称颜色接入宠物列表/详情、银行与选宠、技能页、孵化/进化/抽宠结果、融合选宠、战斗 HUD/换宠、捕捉及升级结果。
- 闪光形态接入共用 Page 的动态宠物绘制、战斗/出场、抽宠、捕捉和升级结果，所有普通物种继续使用原贴图颜色。
- 变色时间使用独立的显示时钟，不跟着待机动画取模重置；缓存保存未染色姿态，每次显示在副本上应用颜色，普通宠物和其他页面不会被污染。
- 品质颜色跟随每只宠物实际 quality。HUD 缓存纳入 quality，避免品质变化后名称仍显示旧色。物种 ID 和品质沿用现有存档，无需转换或覆盖存档。

## 验证

- check_pet_appearance_098.py：7 项通过，包含全部 149 条闪光记录的识别规则、15 段原色/时序、透明度及原缓存不变、真实 CSB 文本着色、页面循环和战斗缓存。
- check_restoration_097.py：13 项通过。
- X battle 筛选回归：23 项通过，70.419 秒。
- check_frame_pacing_lottery.py：6 项通过。
- check_service_page_lifecycle.py：4 项通过。
- check_pet_property_ui.py、check_pet_list_ui.py：均通过。PetList 旧测试曾错误要求禁止放生任何参战宠物，已按现有原版“只保护最后一只存活宠物”规则修正验证；未更改游戏放生规则。
- 前一轮 X 全量 98 项回归通过，详见 VERIFICATION_0.2.97.md。本版针对渲染/宠物页改动运行上述检查，没有把前一轮运行冒充本版重新完成的全量运行。
- 可视样张：outputs/verification/0.2.98/pet-colors-and-flash.jpg。

- check_special_battle_effects.py：8 项通过。
- 0.2.98 Windows 包构建完成；临时存档启动退出码 0，已核对 pet_appearance 等六个关键模块进入可执行文件，复杂技能缓存进入 data/cache/battle。固定启动器已切换到 0.2.98，旧包和玩家存档保留。
- 实际临时战斗窗口已观察到紫色品质名称、绿色对手名称及闪光炼狱龙的持续变色。测试没有覆盖用户真实存档。

## 边界

已恢复有直接原包依据的品质名称颜色和闪光循环变色。尚未进行 Android/PC 同时录像的逐帧验收；不代表全部战斗附属效果、FFD/IK/混合和全程剧情差异已清零。原包缺少 133_tuxi 的问题继续明确保留。
