# 0.2.71 柜员页面与嵌套弹窗生命周期

原因：旧银行和技能列表仅手工更新 ui_base_layer，而 hover 使用 open_ui 留下的空 ui_render_args 重画整张资源模板，覆盖真实内容。购买确认的 _back_to_shop 与技能确认 back 调用了 close_ui，提前 resume 柜员的 openui，出现告别对话后又重开商店，背景因此残留对话与立绘。

修复：
- 增加 ServicePages。银行使用原 PetBankUI/PetBankItemUI 153×234 横向卡、真实容量/余额、待机宠物、取回按钮；寄存打开原 PetSelectUI。技能学习使用原 SkillLearnUI/SkillLearnItemUI、真实能量与费用、左右滚动列表，全部携带宠物可选。
- 由 Page.publish 原子发布完整图层和命中数据，反馈始终从当前完整页面生成。旧自定义页 hover 也仅更新按钮区域，不重画整张未填充模板。
- 商品购买/取消、技能确认返回只替换页面，保留柜员 openui 的 pending/index；真正关闭服务页面才继续原告别剧情。返回商品页不重复计商店访问次数。

专项 check_service_page_lifecycle 4 项通过：银行悬停/寄存/取回，技能原卡片/两列滚动，实际三种柜员脚本中购买与取消不推进剧情，技能确认返回保留剧情。验证使用隔离存档；不改写玩家存档。

其余回归通过：战斗商店8项、柜员/孵化8项、技能确认脚本、原版页面流程9项、战斗点击10项。Windows 隔离存档启动与固定启动器解析检查通过，指向0.2.71。
