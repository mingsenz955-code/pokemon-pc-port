# 0.2.59 验证记录

基线：origin/main 5be35b5，包含 PR13 与9f11787复审修复。传送落点、免费抽宠资格重查/计时、奖励返回滚轮恢复均保留。

14组脚本通过：check_special_battle_effects、check_seen_encyclopedia、check_treasure_search、check_pr13_review、check_battle_runtime、check_battle_damage、check_battle_animation、check_battle_clicks、check_battle_result_ui、check_battle_achievement_events、check_original_page_flows、check_inventory_interactions、check_treasure、check_regressions。所有脚本在临时 POCKET_NATIVE_SAVE_DIR 下运行。

新增8项战斗特效检查覆盖六类原特效计划、狂风前后层、龙卷六个命中帧、跳过命中的序号保持、治愈水add回调、慢帧结束状态、音效精确帧/一次触发、渲染不消耗战斗随机数。104个有特效配置的技能对应102条原效果记录；发呆原effectId=0，没有人为补造特效。

新增4项已见图鉴检查覆盖看到不授予所有权/骑宠、状态不倒退、旧存档迁移与新存档往返、非法species不修改状态。16项道具宿主检查额外验证已见未捕获卡片可打开、战斗只登记当前出场对手、实际摄像机寻宝与原雷达渲染。

新增5项寻宝检查覆盖错图和画面外搜索失败仍扣道具、包围盒边缘进入画面即可发现、道具不足和无效区域的原子性。寻宝完整购买/搜索/宝箱打开/放弃确认/剧情事件及保存往返检查继续通过。

源码 compileall 与 git diff --check 通过。页面图来自真实宿主离屏渲染，另有 Canvas 事件验证；没有完成原版/移植版双窗口逐帧验收或全流程通关。本记录不能当成全部技能结算、全部动作、全部玩法已经完美复刻的证明。

仍未完成：soundEnv附属特效及原Armature全部混合/粒子、多段技能所有重复动作、完整倒下/换宠/捕捉/结算转场与状态/天赋；图鉴其他发现来源/历史记录；寻宝多张地图购买替换与全部动作；抽宠整套演出、充值资格服务、后期剧情。详见 RESTORATION_REMAINING.md。

Windows 0.2.59 构建成功，固定启动器已切换到完整包，旧版本和玩家存档保留。
