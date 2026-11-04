# 0.2.67 柜员交互与孵化验证

## 修复与原版依据

基于 origin/main 52e7eec，保留最新战斗商店、序章、死亡恢复及当前金币价格规则。

- 原 VillageSpriteControler::areaProcess（0x2e4934）通过区域关联 NPC 调用 pushTalkEvent。原 TMX eventLayer.npcId 明确配置柜台前的服务区域，例如银行 580502 在 (832,768,64,192)，孵化师 580501 在 (192,448,256,64)。原有移植只处理 toarea 通知，漏掉 NPC 对话；点击寻路又只接受 NPC 相邻格。现在点击指定 NPC 会走到其原交互区域；进入区域可触发原剧情，区内允许跨柜台对话，区外不扩大普通 NPC 的对话距离，也不穿越柜台。
- 六个实际柜员入口通过：斯塔镇商店 580201、卷轴店 580302、技能指导员 580301、材料店 580401、孵化师 580501、银行职员 580502；依照原 pEventTalk 脚本打开对应页面并继续结束对话。孵化师的 events[5905001] 未开放条件保留，不修改玩家解锁。
- HatchRoomUILayer::itemListViewInit（0x36bfd4，循环终点 0x36c410 cmp #10）原为十张 153×233 的 HatchItemUI 横向卡。已替换临时绘制的两列黑格子/宿主按钮。原房间、NPC 立绘、蛋、四种按钮、条件卡和领取后的宠物待机使用原资源；鼠标滚轮查看后续槽位。
- 材料孵化检查 HatchItem.exp 与全部 itemIds/itemCounts；金币孵化按 moneyId/moneyCount 直接孵化。按原表生成随机或固定 variation/growth，保留孵化后等待领取状态。取回蛋需确认，领取宠物实际入携带栏或可用银行；全容量不足不丢失宠物或蛋。旧存档 activities.eggs 兼容。
- 既有 battle.apply_rewards 的孵化经验路径保留，本轮用真实捕获结算验证 hatch_exp 和重复结算幂等。没有将“打开孵化 UI”当作孵化成功。
- 解析原 PetHatchEffectUI.csb 的 FrameEvent：第 60 帧 showPet、第 200 帧 showPetInfo。按 60 帧/秒的实际秒数播放已支持的原 CSB 位置、缩放、透明度和显隐轨道，原事件前不显示宠物/属性和不可见确认按钮。结果确认返回孵化房；孵化检查页返回不提前恢复柜员 openui 脚本。
- 回归另发现最新主分支的捕获结束后还等待已经销毁的 BattleMainUI 教学按钮。仅对已经有真实战斗结果的 pEvent102001 跳过失效战斗点击，继续原捕获后续脚本；不伪造胜负或手动设置事件完成。

## 验证

新增 tools/check_counter_hatching.py 八项通过：实际地图 NPC 像素点击和完整寻路/剧情/页面；区域自动触发、未开放和远程禁止；真实背包选择、金币孵化、原结果页和领取；材料/金币不足与回滚；取回确认；全部十种蛋和十个槽位、滚动、存读档、满容量回滚；嵌套页不推进剧情；真实战斗结算只增加一次孵化经验。

另外十组通过：check_hatch_check_ui、check_click_navigation、check_guide、check_guide_conditions、check_tutorial_story、check_single_window_flows、check_original_page_flows、check_task_progress、check_fullscreen_gold_audio、check_story_recovery。旧孵化测试已从被替换的临时按钮别名改为原卡片点击，保留了选择第二个蛋的断言。

图片核对：hatch-egg、hatch-check、hatch-effect-final、hatch-ready。没有新增独立 OS 游戏窗口。全部使用隔离存档和真实宿主回调/命中路径，未修改玩家正在使用的存档；未完成原机与 PC 的逐帧同屏对照。

## 剩余边界

全部 UI 旋转/纹理切换、原生 Spine 混合、孵化音效及所有后期地图逐个柜员的屏幕试玩仍待继续核对。本轮已使用所有地图的同一 npcId 区域规则，但不把六个柜员代表入口等同于全地图全剧情通关。全游戏原机逐帧一致仍未达到。

## 打包

Windows 0.2.67 已打包，独立临时存档隐藏启动 --smoke-test 正常退出（0）。固定启动器已指向新版本，未关闭玩家旧窗口、未修改玩家实际存档。
