# 0.2.60 试玩问题验证记录

本轮只针对用户五张截图反馈，基于 PR14/fca759e；未改写玩家存档，旧包保留。

新增 check_playtest_blockers.py 九项检查通过：选宠悬停/按下保留立绘属性、去掉支付样本并只选择一次；三种球点击后的成功结果绘制/宿主tick/返回；捕捉失败后敌方反击且接受下一次点击；敌方首回合普通攻击与双方动作队列；普通结算不使用世界Boss卡；无效/过时教程跳过且保留正常剧情；有效教程只接受真实目标；有界缓存与帧耗时记录；提高姿态采样后0.5秒对应的像素不变。

14组回归通过：check_playtest_blockers、check_battle_clicks、check_battle_result_ui、check_battle_animation、check_battle_runtime、check_battle_damage、check_special_battle_effects、check_spine_animation、check_battle_achievement_events、check_inventory_interactions、check_original_page_flows、check_original_pages、check_pr13_review、check_regressions。后续结算位置/目标可见性修正另复查专项、结算及技能特效。

compileall和git diff --check通过。页面图来自真实宿主离屏渲染，不能当作原版双窗口逐帧试玩的证明。

性能：缓存背景/HUD/缩放姿态，姿态从12Hz提升为30Hz，采用实际显示尺寸光栅化并保持锚点和秒数；帧调度按60Hz目标扣除绘制耗时，至少让出8ms。测量有改善，但复杂冷帧仍可能超时，不承诺稳定60fps。

结算边界：当前资源缺BattleResultInfoUI.csb，以现有ChallengeResultUI/BattleCalculationUI原资源展示胜负与经验/掉落、PetCatchedEffectUI展示捕捉结果；完整原经验/升级/掉落自动串联尚未恢复。其他未完成工作见RESTORATION_REMAINING.md。

Windows 0.2.60 构建及 EXE --smoke-test 启动通过；冒烟测试使用临时存档并自动退出。固定启动器已切换至0.2.60。
