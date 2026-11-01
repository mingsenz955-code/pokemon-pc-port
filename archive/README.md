# 完整内容归档

本目录保存公开仓库中的大文件分卷。所有 `.partNN` 必须按名称顺序拼接，不能单独解压。

## 分卷清单

| 仓库路径 | 字节 | 分卷 |
| --- | ---: | --- |
| `release/pokemon-pc-0.1.zip.part01` | 36700160 | 1 / 3 |
| `release/pokemon-pc-0.1.zip.part02` | 36700160 | 2 / 3 |
| `release/pokemon-pc-0.1.zip.part03` | 8591846 | 3 / 3 |
| `release/pokemon-pc-0.2.zip.part01` | 36700160 | 1 / 3 |
| `release/pokemon-pc-0.2.zip.part02` | 36700160 | 2 / 3 |
| `release/pokemon-pc-0.2.zip.part03` | 7945410 | 3 / 3 |
| `resources/pokemon-1.20.4-original.apk.part01` | 36700160 | 1 / 2 |
| `resources/pokemon-1.20.4-original.apk.part02` | 29779336 | 2 / 2 |
| `resources/pokemon-1.33.0-mod.apk.part01` | 36700160 | 1 / 2 |
| `resources/pokemon-1.33.0-mod.apk.part02` | 15697712 | 2 / 2 |
| `research/early_mod_1.1.0.apk.part01` | 36700160 | 1 / 2 |
| `research/early_mod_1.1.0.apk.part02` | 1356084 | 2 / 2 |
| `archive/original-1.20.4.zip.part01` | 36700160 | 1 / 2 |
| `archive/original-1.20.4.zip.part02` | 9175436 | 2 / 2 |
| `archive/research-extracted.zip.part01` | 36700160 | 1 / 2 |
| `archive/research-extracted.zip.part02` | 11922521 | 2 / 2 |
| `archive/outputs-verification.zip` | 19243279 | - |
| `archive/research-root.zip` | 3039844 | - |
| `research/original-core.so` | 8226468 | - |
| `research/demangled-symbols.json` | 5447220 | - |
| `research/original-symbols.json` | 2839745 | - |
| `research/evidence/face1_10.png` | 4782 | - |
| `research/evidence/face1_11.png` | 5159 | - |
| `research/evidence/face1_2.png` | 4325 | - |
| `research/evidence/face1_3.png` | 4230 | - |
| `research/evidence/face1_4.png` | 4402 | - |
| `research/evidence/face1_5.png` | 4203 | - |
| `research/evidence/face1_6.png` | 4230 | - |
| `research/evidence/face1_7.png` | 2995 | - |
| `research/evidence/face1_8.png` | 4530 | - |
| `research/evidence/face1_9.png` | 3779 | - |
| `research/evidence/faces.jpg` | 44654 | - |
| `research/evidence/icon.png` | 12804 | - |
| `release/pokemon-pc-0.2.2.zip` | 81457707 | - |

## 拼接示例（PowerShell）

```powershell
$parts = Get-ChildItem "release\pokemon-pc-0.2.zip.part*" | Sort-Object Name
$out = [IO.File]::Create((Join-Path $PWD "pokemon-pc-0.2.zip"))
foreach ($p in $parts) { $in = [IO.File]::OpenRead($p.FullName); $in.CopyTo($out); $in.Dispose() }
$out.Dispose()
Get-FileHash "pokemon-pc-0.2.zip" -Algorithm SHA256
```

## 内容说明

- `release/`: 0.1 验证包与 0.2 开发包，保留原始发布包。
- `resources/`: 1.20.4 候选旧版 APK 与 1.33.0 玩家修改包，按 35 MiB 分卷。
- `archive/original-1.20.4.zip`: 原版地图、图片、Spine、Cocos 布局、音频、剧情数据等完整资源。
- `archive/research-extracted.zip`: 从 APK 提取的研究材料。
- `archive/research-root.zip`: 研究笔记、网页记录和版本核验文本。
- `research/original-core.so`: 原 ARM 核心，用于反汇编核对。
- `research/*symbols*.json`: 符号与反汇编对照数据。
- `archive/outputs-verification.zip`: 截图、测试报告和核验输出。

`research/kf_package.apk` 与 `research/mod_package.bin` 分别和 `resources/` 中两个 APK 字节相同，归档时只保留一份，未丢失内容。

## 版权

原版游戏资源版权归原权利人所有。本归档只用于个人保存、学习与互操作性研究，不得商业分发。
