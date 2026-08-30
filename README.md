# 剑3小助手 (JX3 Manager)

多账号 / 多角色周常管理工具，面向《剑网3》多角色玩家：一眼看清每个角色本周**副本 CD、百战进度、修罗击杀、换将点数**与角色统计。

> **当前路线（2026-08-05 调整）：** 不再开发游戏内 Lua 插件。数据统一来自**现有插件（茗伊 MY）的本地数据库**与 **jx3api 公共接口**，由 Windows 管理工具完成汇总、展示与导出。`RoleManager/` 目录中的游戏内插件代码已搁置，仅保留作参考。

## 功能亮点

- **多前端支持**：PyQt6 桌面版（推荐，多线程防卡死）/ Tk 桌面版 / Eel Web 版，数据层共用
- **副本 CD 总览**：动态列展示各角色 5 人本与团队本周 CD（`0/5`、`5/7`），周一边界为**周一 12:00**
- **副本名称自动识别**：自动扫描茗伊战斗日志（`combat_logs/*.jcl`）文件名学习 副本ID→名称 映射，新赛季新副本打过一次本即自动识别，零维护；三层合并（静态兜底 ← 自动学习 ← `data/dungeon_names.json` 人工覆盖）
- **副本列智能过滤**：默认仅显示本周武林通鉴周常团队本 + 通鉴本，过气前尘本自动隐藏（可勾选"显示过气副本"找回，隐藏副本进度保留在角色名悬停提示中）
- **百战异闻录进度**：从战斗日志统计本周（周一 12:00 起）真实击杀首领数（去重、排除练习目标）；**击杀 ≥12 即记为全清**；修罗/镇守击杀单独标记；汇总条一键查看未全清名单
- **跨周自动归零**：未在周一 12:00 后上线的角色，百战进度与周常备注显示层自动归零并灰蓝置色 + 悬停说明
- **换将点数管理**：双击修改（二次确认防误触），悬停显示数据填入时间，自动持久化
- **百战排班页**：本周 100 层轮换表（列表/图谱双视图）、按首领/技能/层数筛选、修罗 Boss 手动校正
- **周常备注**：常驻备注 + 每周一 12:00 自动重置的每周备注，双表同步编辑
- **数据导出**：JSON / CSV 一键导出
- **界面细节**：单元格状态着色（全清绿/进行中橙/未打红）、汇总统计条、服务器/装分/搜索过滤、窗口状态记忆、刷新防抖

## 数据来源

| 数据 | 来源 |
|---|---|
| 角色信息 / 金币 / 贡献 / 装备分 | `my#data/{uid}@zhcn_hd/userdata/userdata.db` + `info.jx3dat` |
| 副本 CD | `my#data/!all-users@zhcn_hd/userdata/role_statistics/dungeon_stat.v3.db` |
| 背包 / 百战招式要诀 | `.../role_statistics/bag_stat.v4.db` |
| 装备详情 | `.../role_statistics/equip_stat.v4.db` |
| 百战击杀记录 + 副本名称 | `my#data/{uid}@zhcn_hd/userdata/combat_logs/*.jcl` |
| 每周首领轮换 / 角色百战精耐与技能 / 周常日历 | [jx3api](https://www.jx3api.com) |

> 以上茗伊数据需要先在游戏内开启对应统计功能（工具内提供 `⚙ 一键开启全角色统计与战斗日志` 按钮，或手动在茗伊设置中开启）。

## 运行

依赖（Python 3.10+，在 Windows + 游戏客户端环境下使用）：

```
pip install -r requirements.txt
```

三套前端任选其一（数据层共用）：

- **PyQt6 极速桌面版（推荐，支持多线程防卡死）**：`python JX3Manager/gui_qt.py`
- Tk 桌面版：`python JX3Manager/gui.py`
- Web 版（Eel）：`python JX3Manager/app.py`

### 配置注意事项

- 游戏路径 `GAME_PATH` 和 jx3api 的 token 统一保存在 `JX3Manager/config.json` 中（该文件含私人 token，已在 `.gitignore` 排除）。
- 首次运行桌面版 (`gui_qt.py` / `gui.py`) 时，会自动弹出配置窗口引导你完成设置。
- **请勿**将包含你私人 Token 的 `config.json` 外传。

### 周重置口径

所有周界（副本 CD、百战进度、每周备注、排班缓存）统一按 **周一 12:00**（服务器维护结束）为一周起点；jx3api 自身的周起点（周一 01:00）在读取时自动钳位对齐。

## 数据契约

各角色对象中 `baizhan_progress` 的字段（Tk / Web / 导出统一使用）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `killed` | int | 本周（周一12:00起）真实击杀的首领数（去重，不含剑圣幻影等练习目标） |
| `killed_in_roster` | int | 其中命中本周轮换表名单的数量 |
| `total` | int | 本周轮换表首领总数（去重；0-100 层同名首领只算一次） |
| `xiuluo` | bool | 镇守（修罗）首领是否已击杀 |
| `killed_bosses` | list[str] | 本周已击杀首领名（去重，按时间顺序） |
| `unmatched` | list[str] | 本周击杀但不在轮换表名单内的首领（排查用） |

计算逻辑集中在 `JX3Manager/main.py` 的 `compute_baizhan_progress()`：按 API 返回的本周 `start/end` 过滤战斗日志，并排除练习目标，不要在其他模块里重算。百战"全清"判定阈值为 `gui_qt.py` 顶部 `BAIZHAN_CLEARED_THRESHOLD = 12`（击杀 ≥12 即视为全清）。

## 测试

```
python -m pytest JX3Manager/tests/ -v
```

覆盖：百战进度计算（跨周过滤、周一 12:00 边界、练习目标排除）、副本名称自动学习（正则、三层合并优先级、mtime 缓存）、副本列过滤与换将点数存取格式。

## 目录结构

```
JX3Manager/
├── main.py                # 核心聚合：读茗伊 DB + jx3api，产出统一角色数据；副本列过滤、换将点数存取
├── gui_qt.py              # PyQt6 桌面前端（推荐）
├── gui.py                 # Tk 桌面前端
├── app.py + web/          # Eel Web 前端
├── readers/               # 各数据源读取器（role/dungeon_cd/dungeon_map/bag/equip/baizhan_api...）
│   └── dungeon_map.py     # 副本 ID→名称：combat_logs 自动学习 + 三层合并 + mtime 缓存
├── tests/                 # pytest 单元测试
├── decrypt/               # jx3dat 解密探索（未完成，暂不使用）
└── data/                  # 技能元数据、图标映射、API 缓存（运行时个人数据不入库）
RoleManager/               # 已搁置的游戏内 Lua 插件（参考用）
RoleManager_Test/          # 已搁置的 Lua 插件加载测试
```

## 已知遗留问题

- 茗伊私有数据库格式依赖逆向解析，游戏或插件升级后可能失效。
- jx3api 角色收录需要角色在游戏内世界频道发言过；未收录角色自动回退本地缓存（状态栏有提示，非错误）。
- 部分过气副本 ID 的名称无战斗日志佐证时由周轮换推断，可在 `data/dungeon_names.json` 人工修正。

## License

MIT
