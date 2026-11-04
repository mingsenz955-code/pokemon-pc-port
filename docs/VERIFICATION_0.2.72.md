# 0.2.72 抽宠原动画与刷新优化

基于 fb4b1ea 并合入最新主分支 93ec3ed（银行、技能和柜员页面生命周期修复），保留 0.2.67–0.2.69 的柜员、孵化、六格、永久购买和合体修复。价格仍为 1 元＝1000 金币，本轮没有支付服务或音乐商品。

## 抽宠原生依据和实现

核对 research/original-core.so 的 LuckyDrawUILayer::drawPet（0x375940）、movement 回调（0x375324）、frame 回调（0x375630）、showAttribute（0x374e00）和确认回调（0x374074），结合原 niudanji.ExportJson、ndchongwubeijingguang.ExportJson、LuckyDrawEffectUI 和 LuckyDrawPetInfoUI。

- 原顺序为 Animation1 → Animation2 → Animation3_抽宠类型 → Animation4_1/2。按原 60Hz 帧时间推进，不用每次刷新加一帧，掉帧不会拖长动画。
- Animation4 第 87 帧 chouchong 出宠；保留原光效、dead 动作和 0.2 初始缩放，发光褪去 1.5 秒、停留 1.2 秒、放大 1 秒后出现属性与确认键。
- 属性页本身透明，必须叠在原 LuckyDrawEffectUI 不透明背景和演出上；已取消直接打开透明属性页的旧流程。
- 三连抽逐只确认，后两只只重播 Animation4_2；抽取仍由 Activities 一次完成，演出不重新扣费、发宠或消耗 RNG。最后确认返回原抽宠页，提前确认无效。
- 按原事件播放 SE_UI_32、SE_UI_33，演出暂停背景音乐，结束恢复。

构建时从原资源生成 1279 个无损动画帧，运行时仅保留最近 32 个解码帧。机器按可见舞台裁切，源文件哈希或渲染版本变化即重建，缺失帧回退实时渲染。生成目录被 Git 忽略，不把数百 MB 衍生图片提交仓库；构建脚本自动生成并复制到 data/cache/lottery。源码运行前执行：

```powershell
.venv\Scripts\python.exe tools/bake_lottery_animation.py
.venv\Scripts\python.exe src/pc_game.py
```

## 刷新与性能

刷新预算覆盖整个 NativeGame.tick；Windows 运行期间申请并在退出时释放 1ms 定时精度。繁忙帧至少留 3ms 给窗口消息处理，避免全屏情况下 update 饥饿。复用 Tk 图像对象、对不透明最终画面使用 RGB 缩放、缓存村民翻转姿态和页面宠物缩放姿态，仅变换骨骼的局部区域；不改变移动速度、战斗数值或奖励概率。

同机、同脚本、隔离存档，基线 fb4b1ea 对比本轮。隐藏 Tk 测量渲染及图像上传，**不是显示器实测 FPS**：

| 指标 | 基线 | 本轮 |
| --- | ---: | ---: |
| 城镇热帧中位数 | 12.455ms | 10.164ms |
| 城镇移动热帧中位数 | 12.296ms | 9.965ms |
| 宠物页热帧中位数 | 5.889ms | 3.957ms |
| 主循环平均刷新 | 43.59Hz | 59.96Hz |
| 主循环间隔 P95 | 24.827ms | 17.531ms |

抽宠前六秒的 180 帧渲染加上传中位数 11.34ms、P95 14.13ms；冷帧最大 50.96ms，不能宣称所有帧都稳定 60fps。战斗首次资源准备仍有约 242ms 冷帧，后续还需异步准备；本轮未掩盖该限制。

## 验证与边界

新增 check_frame_pacing_lottery.py 六项：实际按钮触发三种抽宠、三连逐只确认、背景不透明、音效与 BGM 次数、交易/RNG 不变、缓冲复用不冻结和缩放后坐标、宠物局部裁切与旧算法像素一致。五个代表动画姿态的缓存与实时原资源渲染可见像素一致。全屏真实 Tk 缩放点击十项回归通过。

继续执行柜员孵化、单窗口、页面流程、捕捉/布局、战斗动作/运行/技能特效、点击寻路、剧情动作、永久购买容量、合体、教程、任务进度检查。结果和截图位于本机 outputs/verification。check_story_motion 的轻量宿主补齐 ui_info=None 和音效回调，业务实现未因夹具报错改变。

未完成原 Android 与 Windows 双端逐帧录像对比。原 ShaderArmature 的亮化目前用原贴图白色淡出近似，全部叠加混合仍待核对；缓存像素一致只证明没有改变当前渲染器输出，不代表已证明与原机像素完全一致。全游戏和全部后期剧情仍未完成，不能称完美复刻。
