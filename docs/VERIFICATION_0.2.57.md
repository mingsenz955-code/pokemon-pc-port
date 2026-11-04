# 0.2.57 验证记录

基线：origin/main c104ab8。新分支：codex/fix-original-inventory-pages。

通过 13 组脚本：check_inventory_interactions、check_original_page_flows、check_original_pages、check_main_bag_shop、check_bag_ui、check_continuous_login、check_pet_property_ui、check_pet_list_ui、check_get_item_ui、check_treasure、check_activities、check_mounts、check_regressions。
新增 inventory_interactions 内含13项：原页面点击、全部16条PetItem效果/无效回滚、24条技能卷轴、201条Item的图标/描述与文字裁剪、已知图鉴卡详情、登录领取/防重、原奖励粒子、宠物技能/天赋页、抽宠与连充布局、三种战斗捕捉球、背包卷轴确认返回、香水状态替换。

道具按原使用场景处理：传送/香水在背包，精灵球在野外战斗，放大镜在藏宝图页，蛋在孵化页、碎片在合成页。Item.useType=0 的装备、任务道具、蛋等不能一概改成背包直接消费。201条资源与文本检查不等于201种玩法都已全流程试玩。捕捉与升级所需状态在临时存档内验证，未改写玩家存档。

源码 compileall 和 git diff --check 通过。0.2.57 Windows onedir 构建成功，包含恢复的原版数据，固定启动器已切换，旧包保留。

本轮桌面控制 helper 持续超时，停止了桌面输入；页面图来自实际宿主离屏渲染，不是截图试玩证明。未完成事项见 RESTORATION_REMAINING.md 顶部，尤其连充支付资格、全部演出/音效、全流程通关与原版逐帧验收。
