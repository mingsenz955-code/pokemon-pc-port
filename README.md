# 鍙ｈ濡栨€崟鏈虹増 路 鍘熺敓 Windows PC 绉绘

[![鐘舵€乚(https://img.shields.io/badge/status-0.2%20development-orange)](#褰撳墠瀹屾垚搴?
[![骞冲彴](https://img.shields.io/badge/platform-Windows%2010%2F11-blue)](#浠庢簮鐮佽繍琛?
[![Python](https://img.shields.io/badge/python-3.12-3776AB)](https://www.python.org/)

浣跨敤銆婂彛琚嬪鎬崟鏈虹増銆?.20.4 鍘熺増鏁版嵁銆佸湴鍥俱€丆ocos UI 涓?Spine 璧勬簮鍒朵綔鐨?*鍘熺敓 Windows 妗岄潰绉绘**銆備笉鏄畨鍗撴ā鎷熷櫒灏佽锛屼笉渚濊禆缃戦〉鎴栫綉缁滄湇鍔°€?
> **褰撳墠鏄?0.2 寮€鍙戠増锛屼笉鏄畬鏁?1鈭? 鎴愬搧銆?* 宸插畬鎴愬彲瀹為檯娓哥帺鐨勫簭绔犮€佸垵濮嬪疇鐗┿€佹垬鏂椾笌鎹曟崏銆佷富绾?1鈥? 绛夋牳蹇冮摼璺紱澶ч噺鍏绘垚銆佹敮绾裤€佸皬娓告垙鍜屽悗鏈熺郴缁熶粛鍦ㄧЩ妞嶃€傞亣鍒版湭瀹炵幇鐨勬満鍒朵細鏄庣‘鍋滀笅锛屼笉浼€犻€氳繃銆?
## 鐢婚潰

| 鍘熺増涓栫晫鍦板浘 | 鍘熺増鎴樻枟鐣岄潰 |
| --- | --- |
| ![涓栫晫鍦板浘](docs/screenshots/world-map.png) | ![鎴樻枟涓荤晫闈(docs/screenshots/battle-main.png) |

| 鎶€鑳借彍鍗?| 閲庡閬亣 |
| --- | --- |
| ![鎶€鑳借彍鍗昡(docs/screenshots/battle-skills.png) | ![閲庡閬亣](docs/screenshots/wild-encounter.png) |

| 搴忕珷 路 鍗佸勾鍓嶈开灏兼柉鍩?|
| --- |
| ![搴忕珷](docs/screenshots/prologue.png) |

## 褰撳墠瀹屾垚搴?
### 宸插疄闄呮帴鍏?
- **鐪熷疄搴忕珷**锛氫粠 7401 鍐犲啗璧涘紑濮嬶紝鎸夊師 `pEvent` 鑴氭湰鎺ㄨ繘 7401 鈫?7228 鈫?5807 鈫?101锛屽寘鎷璇濄€佹梺鐧姐€侀粦灞忋€佸満鏅垏鎹€佹垬鏂椼€佹寜閽?鐐瑰嚮绛夊緟銆?- **鍒濆瀹犵墿涓夐€変竴**锛氱爺绌舵墍 `openui 7`锛岃鍙栧師 `InitPet`锛氱毊鍗′笜銆佹澃灏奸緹銆佸铔欑瀛愩€?- **涓荤嚎浠诲姟 1鈥?**锛氫换鍔℃潯浠躲€佹彁浜ゃ€佸鍔便€佷笅涓€浠诲姟鐘舵€侊紱鏀寔 `conditionType` 1/2/3/4/5/6/7銆?- **鍘熺増鎴樻枟鏍稿績**锛?  - 鍘?`Pet` / `Skill` / `SkillState` / `Talent` 鏁版嵁锛?  - 浼ゅ銆佸睘鎬у厠鍒躲€佹毚鍑汇€侀槻寰?閫熷害/鑳介噺鍑忎激銆佺粡楠屻€佸崌绾с€佹帀钀斤紱
  - 鏁屾柟 AI銆佹崲瀹犮€侀€冭窇銆佹崟鎹夌巼銆佹崟鎹夊悗鍏ラ槦/浠撳簱锛?  - 鎴樻枟鍐呭洖澶嶉亾鍏枫€佺簿鐏电悆鍒嗛〉銆?- **鍘熺増鎴樻枟 UI**锛歚BattleMainUI`銆乣BattleButtonMenuNode`銆乣BattleSkillMenuNode`銆乣BattleItemMenuNode`锛屽惈鍘熺増鑳屾櫙銆佸疇鐗?Spine 绔嬬粯銆丠P/鑳介噺鏉°€佺姸鎬併€侀槦浼嶇偣銆佹棩蹇椼€佺‘璁や笌缁撶畻闈㈡澘銆?- **鍦板浘闅忔満閬囨晫**锛氭寜鍘?`VillageMap.enemyAppearInterval`锛?0鈥?0 姝ワ級鍜?`enemyProbability` 鏉冮噸閫夋嫨 `VillageEnemy`锛涜閫昏緫鐢?`VillageMapControler::checkEnemy` / `DataManager::fightWithVillageMapEnemy` 鍙嶆眹缂栨牳瀵广€?- **鑳屽寘/瀹犵墿鐣岄潰**锛氳儗鍖呭彲浣跨敤鍘熺増鍥炲閬撳叿骞舵墸闄ゆ暟閲忥紱瀹犵墿鐣岄潰鏄剧ず绛夌骇銆佺敓鍛?鑳介噺銆佷簲缁淬€佸搧璐ㄣ€佺獊鐮淬€佷翰瀵嗗害銆佹妧鑳姐€佸ぉ璧嬶紝骞舵敮鎸佹暟鎹┍鍔ㄧ殑杩涘寲灏濊瘯銆?- **鐙珛瀛樻。**锛氫繚瀛樺墽鎯呬綅缃€佸湴鍥俱€佽儗鍖呫€佷换鍔°€佷簨浠剁姸鎬併€佸疇鐗┿€侀殢鏈烘暟鐘舵€侊紱鍘熷瓙鍐欏叆骞朵繚鐣?`.bak`銆傛垬鏂椾腑瀛樻。浼氭槑纭嫆缁濓紝閬垮厤鍐欏叆涓嶄竴鑷寸姸鎬併€?
### 閮ㄥ垎瀹屾垚

- **鍟嗗簵**锛氬彲璇诲彇鍘?`Shop` 琛ㄥ苟璐拱锛屼絾灏氭湭鎸夊師 `VillageMap.shopType` 鍋氬畬鏁磋揣鏋惰繃婊ゃ€?- **鎴樻枟鐘舵€?*锛氬凡瑕嗙洊涓昏鐘舵€佷笌鎸佺画浼ゅ/鍥炲/鍏嶇柅/椹辨暎锛?7 绉嶇姸鎬佷腑浠嶆湁灏戞暟鐩爣閫夋嫨涓庡彔鍔犺鍒欏緟閫愭潯鏍稿銆?- **瀹犵墿鍏绘垚**锛氬凡鎺ュ叆杩涘寲涓庡熀纭€灞炴€э紱璁粌銆佺獊鐮淬€佽瀺鍚堛€佸搧璐ㄣ€佹惡甯︾墿灏氭湭瀹屾暣銆?- **鍦板浘浜や簰**锛氬嚭鍙ｃ€佷紶閫併€佸尯鍩熻Е鍙戝凡鎺ュ叆锛涢儴鍒嗗満鏅殰纰?楠戜箻/閲囬泦浠嶄細鍋滄骞舵彁绀恒€?
### 鏄庣‘鏈畬鎴?
- 鎴樻枟鍐呭瓨妗ｄ笌鎴樻枟涓柇鎭㈠锛?- 鍏ㄩ儴 57 绉?`SkillState` 鐨勫畬鏁磋涔夈€佸ぉ璧?鎼哄甫鐗╁叏缁撶畻锛?- 瀹犵墿鍥鹃壌銆佽缁冦€佺獊鐮淬€佽瀺鍚堛€佸搧璐ㄣ€佹斁鐢熴€佷粨搴撴暣鐞嗭紱
- 瀹屾暣鑳屽寘銆佷换鍔″垪琛?杩借釜銆佸晢搴楄揣鏋躲€侀亾棣嗐€佺珵鎶€鍦恒€佹棤闄愮珵鎶€鍦恒€佽疆鐩樸€佸崱鐗屼紶璇淬€佽禌瀹犮€佸湥鍏戒娇鑰咃紱
- 鍏ㄦ敮绾裤€佸叏鍦板浘銆佺粨灞€涓庡叏娴佺▼鍥炲綊锛?- Spine 鏃堕棿绾垮姩鐢汇€丗FD/IK銆佸叏閮ㄦ妧鑳借〃鐜帮紱
- 闊充箰/闊虫晥鍏ㄦ帴鍏ャ€佸師瀛椾綋涓€鑷存€э紱
- 鍘熷畨鍗撳瓨妗ｅ吋瀹广€?
## 浠庢簮鐮佽繍琛?
### 鐜

- Windows 10/11
- Python 3.12
- 鍘熺増 1.20.4 璧勬簮鐩綍锛歚original-1.20.4/`锛?*涓嶅寘鍚湪鏈粨搴?*锛岃涓嬫柟鈥滆祫婧愪笌鐗堟潈鈥濓級

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\pc_game.py
```

棣栨杩愯闇€瑕佹湰鍦板瓨鍦?`original-1.20.4/tables.json`銆乣assets/`銆乣events/`銆乣ui-layouts/`銆傝嫢鍙湁 APK锛屽彲鍏堟仮澶嶈祫婧愶細

```powershell
.\.venv\Scripts\python.exe tools\recover_assets.py <1.20.4 APK 璺緞> original-1.20.4
```

### 鎿嶄綔

| 鎸夐敭/鎿嶄綔 | 鍔熻兘 |
| --- | --- |
| WASD / 鏂瑰悜閿?| 绉诲姩 |
| 绌烘牸 / E / 榧犳爣鍗曞嚮 | 瀵硅瘽銆佷氦浜掋€佺‘璁?|
| F5 / F9 | 淇濆瓨 / 璇诲彇鐙珛瀛樻。 |
| 椤堕儴鎸夐挳 | 瀹犵墿銆佽儗鍖呫€佷换鍔°€佷繚瀛樸€佽鍙栥€佸叧浜?|
| 鎴樻枟鐣岄潰 | 鐐瑰嚮鍙充晶鎸囦护锛氭敾鍑汇€佹妧鑳姐€侀亾鍏枫€佹崲瀹犮€侀€冭窇銆佹崟鎹?|

## 鏋勫缓 Windows 鍖?
```powershell
.\.venv\Scripts\python.exe tools\build_windows.py
```

杈撳嚭锛歚outputs/鍙ｈ濡栨€?PC绉绘寮€鍙戠増0.2/`銆傚繀椤讳繚鐣欏悓鐩綍鐨?`_internal/` 涓?`data/`銆傛瀯寤鸿剼鏈細澶嶅埗 `original-1.20.4/` 涓?`data/`锛屾墍浠ュ彂甯冨寘鍐呭惈鍘熺増璧勬簮锛?*鏈粨搴撲笉鎻愪氦杩欎簺璧勬簮**銆?
## 娴嬭瘯涓庢牳瀵?
```powershell
# 15 涓叕寮?脳 200 缁勶紝涓?ARM 鍘熶簩杩涘埗姣旇緝
.\.venv\Scripts\python.exe tools\check_original_formulas.py

# 瑙﹀彂銆佷换鍔°€佸瓨璇汇€佸師瀛愭墸璐广€佹湭瀹炵幇鏈哄埗鍋滄
.\.venv\Scripts\python.exe tools\check_game_runtime.py

# 鎴樻枟鏍稿績涓庢崟鎹?.\.venv\Scripts\python.exe tools\check_battle_runtime.py

# Tk 瀹夸富瀹炶窇锛氬簭绔?鈫?鍒濆瀹犵墿 鈫?涓荤嚎 1鈥?
.\.venv\Scripts\python.exe build\_host_debug.py
```

娴嬭瘯鎶ュ憡鍐欏埌 `outputs/verification/`锛堜笉鎻愪氦锛夈€傚凡鏍稿鐨勫叧閿粨璁猴細

- 鍘熶换鍔＄姸鎬侊細褰撳墠浠诲姟绮剧‘姣旇緝锛涚紪鍙锋棭浜庡綋鍓?5锛屾櫄浜庡綋鍓?2锛涜Е鍙戝櫒涓?鏀潯浠舵暟缁勪负 OR锛屼簨浠舵潯浠舵暟缁勪负 AND銆?- 鍘?`end state=1` 鎵嶈褰曚簨浠跺畬鎴愶紱鑷劧 EOF 涔熻褰曘€?- 鍘?`wait` 鏄瓑寰呭尮閰嶆搷浣?浜嬩欢锛屼笉鏄浐瀹氬欢鏃躲€?- 鍑哄彛缂栧彿缂栫爜涓?`<鍦板浘 ID><钀界偣鍚庣紑>`锛屼緥濡?`722801 鈫?map 7228`銆乣10105 鈫?map 101`銆乣580101 鈫?map 5801`銆?
## 椤圭洰缁撴瀯

```text
src/
  pc_game.py          鍘熺敓 Tk 瀹夸富锛氬湴鍥俱€佷簨浠躲€佷换鍔°€乁I銆侀亣鏁屻€佸瓨妗?  event_runtime.py    461 鏉¤Е鍙戣鍒欎笌璇锋眰寮忎簨浠惰В閲婂櫒
  game_state.py       瀹犵墿/鑳屽寘/浠诲姟/浜嬩欢/闅忔満鏁扮姸鎬?  battle.py           鍥炲悎鍒舵垬鏂楁牳蹇?  battle_ui.py        鍘熺増 Cocos 鎴樻枟 UI 娓叉煋涓庣偣鍑?  original_data.py    鍘熺増琛ㄣ€乀MX銆丼pine銆丆ocos 璧勬簮璁块棶
  csb_reader.py       Cocos Studio .csb 瑙ｆ瀽
  csb_render.py       .csb 杞欢娓叉煋涓庣偣鍑诲尯鍩?  spine_renderer.py   Spine 2.1 闈欐€佺綉鏍兼覆鏌?  game_formulas.py    涓庡師浜岃繘鍒舵瘮瀵硅繃鐨勬暟鍊煎叕寮?tools/
  recover_assets.py   浠?APK 鎭㈠璧勬簮
  extract_ui_layouts.py
  check_*.py          鑷姩鏍稿
  build_windows.py    PyInstaller 鏋勫缓
build/
  _host_debug.py      Tk 瀹夸富绔埌绔皟璇?  _host_fight.py      鎴樻枟/鎹曟崏瀹夸富娴嬭瘯
  _battle_ui_shot.py  鎴樻枟 UI 鎴浘
docs/screenshots/     README 鎴浘
```

`original-1.20.4/`銆乣resources/`銆乣outputs/`銆乣research/`銆乣.venv/` 鍧囪 `.gitignore` 鎺掗櫎銆?
## 璧勬簮涓庣増鏉?
- 鏈粨搴撳彧鍖呭惈**绉绘浠ｇ爜銆佹祴璇曡剼鏈拰璇存槑鏂囨。**銆?- 鍘熺増 APK銆佸湴鍥俱€佸浘鐗囥€丼pine銆丆ocos 甯冨眬銆侀煶棰戙€佸墽鎯呮暟鎹瓑鐗堟潈褰掑師鏉冨埄浜烘墍鏈夛紝**鏈笂浼犲埌鏈粨搴?*銆?- 鏈」鐩敤浜庝釜浜哄涔犮€?Preservation 涓庝簰鎿嶄綔鎬х爺绌讹紱璇疯嚜琛屽悎娉曞彇寰楀師鐗堣祫婧愶紝涓嶈灏嗘墦鍖呭悗鐨勮祫婧愮敤浜庡晢涓氬垎鍙戙€?- 鏈」鐩笉鏄畼鏂圭増鏈紝涓庡師寮€鍙?鍙戣鏂规棤鍏宠仈銆?
## 浠撳簱

<https://github.com/mingsenz955-code/pokemon-pc-port>

褰撳墠涓虹鏈変粨搴擄紱濡傞渶鍏紑锛屽彲鍦?GitHub 浠撳簱 Settings 鈫?General 鈫?Danger Zone 涓慨鏀瑰彲瑙佹€с€
