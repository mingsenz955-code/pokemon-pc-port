# 0.2.78 取消教学、商人卡点与后期稳定性检查

用户最终要求：取消全部教学。此前尝试恢复岩石教学的实现已撤回，最终行为如下。

- EventRuntime 统一过滤全部 button、addteachnode、trialride、wait type3 和教学主界面显隐命令；原始事件文件保留。恢复旧 pending 时也会跳过，清除旧试骑与教学节点，恢复 HUD。
- 商人剧情保留普通对话与购买页，不再等待试骑破岩、飞行或穿荆棘。三段原事件 202001/315002/403002 均运行到购买页并可关闭退出。
- 原 uiid16 的 par1 是 Ride 编号，不是 PetShop 编号。修复此前打开后 KeyError，使用原 BuyPetUI、Ride.petId、Ride.storeId 和 Store 价格；关闭不扣费，购买仅解锁该坐骑。
- 普通孵化页面不强制点击，可自行放蛋、查看、加速与关闭；原首次免费孵化保留。普通孵化仍扣原表费用。
- 出口使用原 VillageSprite40001/jiantou 动画，根据 TMX face 朝向和出口宽度排布。依据原 VillageExitControler::initSprite/setAnimation/initWithMapValue；不添加虚构目的地文字。未进行原安卓运行录像逐帧位置对照。
- 拉斯雷加100162及NPC21065骨骼实际在 Sprite 根目录，统一资源搜索兼容该目录，避免 pet_clip_duration 文件不存在导致刷新回调中断。
- 有破坏能力的坐骑点击寻路允许到达可破坏障碍，实际移步才破坏；动态场景破岩不再重复重绘整张地图底图。

## 已执行的检查

隔离临时存档，未读写用户实际存档，未关闭用户游戏。

- 431张地图：加载、全部角色解码、13帧绘制和Tk图像上传、40次NPC巡逻步进，最终0失败。
- 315只宠物：setup及stand/attack/dead两帧与时长读取，最终0失败。
- 1685份事件脚本：指令、跳转与地图目的地静态扫描，0项问题；另检查325条任务条件和21张头像。静态扫描不能证明所有剧情分支可通关。
- check_mount_tutorial：全事件教学命令过滤、三位商人完整流程、旧护城龙wait存档恢复、手动免费孵化、四向出口素材、拉斯雷加资源。
- check_hatch_tutorial 改为取消教学后的手动孵化/关闭/普通收费验证，旧版强制教学断言不再适用。
- check_click_navigation 12项，check_mounts 10项，check_sunshine_quests 10项，check_teleport_exit 3项，check_frame_pacing_lottery 6项，check_story_motion 15项，check_purchase_mount_render 7项通过。
- 多个隐藏Tk窗口测试退出时有ttk ThemeChanged销毁告警，无测试断言失败，区别于游戏剧情异常。

## 帧耗时与未解决内容

串行隐藏Tk基准包含渲染与图像上传，不是显示器实测FPS。代表复杂双宠战斗热缓存帧中位9.259ms、P95 10.141ms；首次帧480.477ms、全段P95 173.871ms，首次资源准备仍明显卡顿，本轮未解决。并发全地图扫描的耗时受资源竞争影响，不用来宣传帧率。

没有从开局逐任务步行通关全部后期剧情；没有宣称所有卡死已排除。抽宠着色器、原机逐帧动画对照、尚未移植的卡牌玩法等沿用剩余工作文档。

check_hatch_tutorial 最终8项通过；check_obstacles 破岩、禁行、存档恢复和底图不重复重绘检查通过。0.2.78 Windows 包启动测试退出码0，临时存档目录没有生成异常日志。

合并复核：check_removed_tutorials 的旧断言仍要求保留孵化强制教学，已按本版行为更新为取消教学，同时确认该脚本普通对话、奖励、提交及孵化屋打开指令仍保留。4项通过。
