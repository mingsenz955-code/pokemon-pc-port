# 0.2.79 两类通用问题：坐骑障碍与跨地图 NPC 状态

## 碰撞类别分离

旧 terrain_at 将 obsType 返回为 collideTile；两种枚举的 2 分别表示岩石和水。故持有乘龙会将岩石当水自动骑乘，骑乘乘龙也可进入岩石。已用原地图 202 复现，修复前两项移动断言均失败。

terrain_at 现在只读原 collideLayer；blocked 独立检查 obsType、SpriteTile、地图边界及地形。真正移动时护城龙破岩、陆行鸟砍树，然后重新检查底层地形；乘龙不能放行岩石，合法飞行可越过但不破坏。点击和 NPC/任务寻路统一使用 route_blocked，只为当前拥有正确破坏能力的坐骑规划破障路线。渡水自动骑乘及地图禁用规则保留。

旧存档若在自由行动时处于未清除障碍内，读取时移到最近合法格，不删障碍，不扣道具，不改任务；剧情运行中不强行搬动。五坐骑按原 Ride 表验证：陆行鸟砍树并加速、乘龙渡水、炼狱龙飞越、月桂叶穿荆棘、护城龙破岩。

## 跨地图 NPC 显隐

原 VillageMapControler::setSpriteVisible @ 0x2dc252 对 spritetype=2 调用 PlayerDataManager::setNpcState(npcId,state)，不使用执行脚本的地图作为状态键。

旧宿主写 currentMap:2:npcId。pEvent6201001 第17步在浅橙道馆要求深蓝道馆莎莉 590103 显示，却写成6201:2:590103，导致后续5901中的角色仍隐藏。现在所有 NPC 的显隐写入 global:2:npcId，绘制和巡逻读取同一规则；宝箱等其他类别保留原隔离，不因重号被误隐藏。原剧本未改，未按名字或任务24硬编码显示。

旧存档读取时将同一 NPC 无冲突的地图局部写入迁为全局，保留旧字段与审计记录，重复读取不重复迁移。旧值若彼此冲突且无时间戳，不猜测最后一次写入，保留局部回退并记入 ambiguous，后续真实剧情显隐命令会给出明确全局状态。这类历史歧义没有伪造剧情完成来覆盖。

## 检查

- check_ride_obstacle_collision：8项通过。真实岩石进入拒绝、持有乘龙不自动骑石、真正渡水保留、正确坐骑破坏一次、飞行不破坏、五坐骑×两种障碍、点击绕路、旧重叠存档恢复，以及所有原地图10000多个障碍均不能由乘龙放行。
- check_cross_map_npc_visibility：4项通过。原浅橙道馆对话→莎莉转移→深蓝道馆剧情→主线24选择具体鲤鱼王→下一主线；旧错误地图键恢复及再次存读档；后续隐藏/重显和宝箱重号隔离；全脚本1072条NPC显隐指令均按全局状态执行。
- 全431图建立NPC目录；1072条指令中18个引用在现有地图资源没有匹配实体（包括旧圣兽使者支线和7401021），输出审计清单，不虚构角色位置。这个静态资源缺口不等于所有后期剧情已完整通关。
- check_mounts 10、check_click_navigation 12、check_story_motion 15、check_sunshine_quests 10、check_teleport_exit 3、check_purchase_mount_render 7项通过；check_obstacles通过。所有游戏操作在隔离存档中执行，不修改玩家真实进度。

原版ARM依据保存在本地 outputs/verification/mount-obstacle-native.txt、mount-is-collide-native.txt、cross-map-visibility-native.txt。新增检查与回归日志位于 outputs/verification。此版本修复上述通用逻辑，不宣称全游戏全部分支已逐一通关。
