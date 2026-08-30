# JX3 插件开发技术方案 — 完整开发指南

> 基于菊花插件集（JH）源码逆向分析 + 社区资料整理 | 2026-07-25

> **状态 (2026-08-05):** 本文档对应的游戏内插件开发已暂时搁置，项目改为从现有插件（茗伊）本地数据与 jx3api 获取数据。本文保留供未来参考。

---

## 零、前置知识：插件运行环境

《剑网3》客户端内置了一套 **Lua 5.x 脚本引擎**，通过 `interface/` 目录下的 `.lua` 文件加载插件。官方对外挂（全自动脚本）打击严厉，但**对基于官方接口的 UI 辅助插件是开放态度**——菊花插件集就是最大规模的第三方插件项目，拥有数百万用户。

**核心约束：**
- 插件仅能调用官方暴露的 C++ 绑定 Lua API，不能直接操作系统或网络
- 插件必须放在 `{游戏目录}/bin/zhcn_hd/interface/` 下（不同画质路径略有差异）
- 需要 key 验证（`zhcn` 版本），否则会被判为非法插件
- `info.ini` 是插件注册的唯一入口

---

## 一、插件目录结构与注册机制

### 1.1 标准目录结构

```
interface/
└── RoleManager/                  ← 插件根目录
    ├── info.ini                  ← 【必须】插件注册信息
    ├── Main.lua                  ← 插件入口
    ├── Event.lua                 ← 事件监听
    ├── Collect.lua               ← 数据采集
    ├── Save.lua                  ← 数据保存
    ├── Export.lua                ← 导出
    ├── UI.lua                    ← 界面
    ├── Config.lua                ← 配置
    ├── Data/                     ← 运行时数据
    │   └── RoleData.jx3dat       ← 序列化存储
    ├── ui/                       ← UI 布局文件
    │   └── MainPanel.ini         ← 面板布局
    └── lang/                     ← 多语言
        └── zhcn.jx3dat           ← 中文语言包
```

### 1.2 info.ini 规范

```ini
[RoleManager]
name=JX3多角色管理          ; 插件显示名称
desc=多角色周常数据管理      ; 描述
package=                    ; 所属包名（独立插件留空）
version=1.0                 ; 版本号
default=1                   ; 1=默认启用, 0=默认禁用
dependence=                 ; 依赖的其他插件名（逗号分隔）
lua_0=Main.lua              ; 第1个加载的 Lua 文件
lua_1=Event.lua             ; 第2个加载的 Lua 文件
lua_2=Collect.lua           ; 按顺序加载
lua_3=Save.lua
lua_4=Export.lua
lua_5=UI.lua
lua_6=Config.lua
```

**关键规则：**
- `lua_0` 是第一个执行的脚本，通常放核心入口
- 文件名按数字顺序加载，`lua_0` → `lua_1` → ...
- `default=1` 表示玩家安装后默认启用
- 如果没有 `package` 字段，表示独立插件

### 1.3 数据存储格式

JX3 插件使用 `SaveLUAData` / `LoadLUAData` 进行二进制序列化存储（`.jx3dat`），**不是 JSON 文本**。这意味着：

- 数据存储是 Lua table 的二进制序列化，读写高效
- 导出 JSON/CSV 需要额外的序列化转换
- 插件数据存储路径约定：`interface/{插件名}/@DATA/`
- 角色独立数据需要配合 `RegisterCustomData` 注册

---

## 二、核心 API 清单

### 2.1 角色与玩家 API

```lua
-- 获取当前登录角色对象
local me = GetClientPlayer()

-- 角色属性
me.szName        -- string: 角色名称
me.dwID          -- number: 角色唯一ID
me.dwForceID     -- number: 门派ID（如：唐门 = ？需查表）
me.nLevel        -- number: 当前等级
me.nCurrentLife  -- number: 当前血量
me.nMaxLife      -- number: 最大血量
me.nCurrentMana  -- number: 当前内力
me.nMaxMana      -- number: 最大内力
me.GetMapID()    -- number: 当前地图ID
me.GetScene()    -- KScene: 场景对象
me.GetTarget()   -- dwType, dwID: 当前目标
me.IsInParty()   -- bool: 是否在队伍中

-- 获取指定ID玩家
local player = GetPlayer(dwID)

-- 判断是否为真实玩家（非NPC）
IsPlayer(dwID)   -- bool

-- 当前登录角色名（UI层）
GetUserRoleName()

-- 客户端玩家ID（UI层）
UI_GetClientPlayerID()
```

### 2.2 门派ID映射（dForceID）

| dwForceID | 门派 | dwForceID | 门派 |
|---|---|---|---|
| 1 | 少林 | 9 | 五毒 |
| 2 | 万花 | 10 | 唐门 |
| 3 | 天策 | 11 | 明教 |
| 4 | 纯阳 | 12 | 丐帮 |
| 5 | 七秀 | 13 | 苍云 |
| 6 | 藏剑 | 14 | 长歌 |
| 7 | 五毒(旧) | 15 | 霸刀 |
| 8 | 唐门(旧) | 16+ | 蓬莱/凌雪/衍天/药宗/刀宗/万灵等 |

> **注意：** `dwForceID` 是门派基础ID，**心法**（如惊羽诀/天罗诡道）是另一个字段，暂未在JH源码中找到直接的"当前心法"API，可能需要通过 `GetClientPlayer()` 的其他属性获取。

### 2.3 服务器信息 API

```lua
-- 获取版本/服务器信息
GetVersion()
-- 返回值: version_number, version_string, server_area, server_tag
-- 示例: 120, "1.0.0.xxxx", "电信一区", "zhcn"

-- 从返回值中提取
local _, _, serverName, serverTag = GetVersion()
-- serverName: "电信一区" / "双线一区" 等
-- serverTag: "zhcn"（国服）
```

### 2.4 副本/地图 API

```lua
-- 获取所有地图列表
GetMapList()  -- 返回 {dwMapID, ...}

-- 获取地图参数
GetMapParams(dwMapID)
-- 返回: dwMapID, nMapType, szMapName
-- nMapType: MAP_TYPE.DUNGEON = 2（副本）

-- 获取地图名称
Table_GetMapName(dwMapID)  -- string

-- 判断是否为副本
-- 通过 g_tTable.DungeonInfo 表查询
local a = g_tTable.DungeonInfo:Search(dwMapID)
if a and a.dwClassID == 3 then
    -- 是5人/10人/25人副本
end

-- 副本信息表字段
-- dwMapID, dwClassID, szName, ...
```

### 2.5 装备与物品 API

```lua
-- 装备栏查询（通过 UI station）
local frame = Station.Lookup("Normal/Player")
-- 装备栏是 UI 层的固定 station 结构

-- 物品图标/名称
Table_GetItemName(nUiId)    -- string
Table_GetItemIconID(nUiId)  -- number

-- 角色身上装备可能需要遍历装备槽位
-- 具体槽位编号需要通过 Station 层级查找
```

### 2.6 技能与BUFF API

```lua
-- 获取技能信息
Table_GetSkill(dwSkillID, dwLevel)
GetSkill(dwSkillID, dwLevel)

-- 获取BUFF信息
Table_GetBuff(dwBuffID, dwLevel)
me.GetBuff(dwBuffID, dwLevel)   -- 返回 KBuff 对象
me.GetBuffCount()                -- BUFF数量
me.GetBuff(nIndex)               -- 获取第n个BUFF
-- 返回: dwID, nLevel, bCanCancel, nEndFrame, nIndex, nStackNum, dwSkillSrcID, bValid

-- BUFF列表遍历
local nCount = me.GetBuffCount()
for i = 1, nCount do
    local dwID, nLevel, bCanCancel, nEndFrame, nIndex, nStackNum, dwSkillSrcID, bValid = me.GetBuff(i - 1)
end
```

### 2.7 百战相关 API

**⚠ 关键发现：** 百战（BaiZhan）是较新的玩法系统，在JH插件（最后更新于2018年）中未发现直接的百战API。这意味着：

- 百战数据可能需要通过 **非标准途径** 采集
- 可能的采集路线：
  1. UI Station 层级抓取（百战界面是 UI 树的一部分）
  2. 战斗记录/系统消息解析
  3. 请求官方在后续版本开放接口
  4. V0.1 先预留字段，V0.4 根据接口情况再实现

```lua
-- 可能的UI层采集路径（待验证）
-- 百战次数可能在聊天记录或特定UI面板中
-- 精耐值可能在角色属性面板中

-- UI Station 查找示例
local frame = Station.Lookup("Normal/BaiZhanPanel")
if frame then
    -- 读取子控件文本
end
```

### 2.8 数据存储 API

```lua
-- 保存Lua数据（二进制序列化）
SaveLUAData(szPath, data)
-- szPath: 相对于插件Data目录的路径，如 "RoleData.jx3dat"
-- data: Lua table

-- 加载Lua数据
local data = LoadLUAData(szPath)

-- 注册持久化变量（切换角色时自动保存/加载）
RegisterCustomData(szVarPath, nVersion, szDomain)
-- 示例: RegisterCustomData("MyData.RoleInfo", 1, "Role")
-- szDomain: "Account" = 账号级, "Role" = 角色级

-- JH 封装的保存/加载（自动拼接路径前缀）
JH.SaveLUAData(szPath, data)
JH.LoadLUAData(szPath)
```

---

## 三、事件系统

### 3.1 核心游戏事件

```lua
-- 事件注册
RegisterEvent(szEvent, fnHandler)

-- 事件处理函数签名
function handler(szEvent)
    -- arg0 ~ arg9 为事件参数（全局变量）
end

-- V0.1 需要的事件清单
```

| 事件名 | 触发时机 | 参数 | V0.1使用 |
|---|---|---|---|
| `LOADING_END` | 加载界面结束 | 无 | ✅ 角色登录后触发采集 |
| `FIRST_LOADING_END` | 首次加载完成 | 无 | ✅ 游戏启动后初始化 |
| `PLAYER_ENTER_WORLD` | 玩家进入世界 | dwPlayerID | ✅ 进入游戏世界触发 |
| `PLAYER_EXIT_GAME` | 玩家退出游戏 | 无 | ✅ 退出前保存 |
| `GAME_EXIT` | 游戏进程退出 | 无 | ✅ 游戏关闭前保存 |
| `RELOAD_UI_ADDON_BEGIN` | 插件重载开始 | 无 | ✅ 插件重载前保存 |
| `UI_SCALED` | UI缩放改变 | 无 | ❌ UI适配用 |
| `PLAYER_LEVEL_UP` | 玩家升级 | 无 | 后续版本 |
| `ON_ENTER_DUNGEON` | 进入副本 | 无 | V0.3 |
| `ON_LEAVE_DUNGEON` | 离开副本 | 无 | V0.3 |
| `SKILL_EFFECT_TEXT` | 技能效果文本 | dwCaster, dwTarget... | 百战数据分析 |
| `FIGHT_HINT` | 进出战斗 | arg0(bool) | 战斗状态 |

### 3.2 JH 事件系统封装（推荐使用）

```lua
-- JH 风格的事件注册（支持 key 去重和批量注册）
JH.RegisterEvent("LOADING_END.RoleManager", function()
    -- 事件处理函数
end)

-- 批量注册
JH.RegisterEvent({
    "LOADING_END.RoleManager",
    "PLAYER_EXIT_GAME.RoleManager",
    "GAME_EXIT.RoleManager",
}, function(szEvent)
    -- 统一处理
end)

-- 取消注册
JH.UnRegisterEvent("LOADING_END.RoleManager")

-- 模块初始化（注册一组事件和呼吸回调）
JH.RegisterInit("RoleManager",
    { "LOADING_END",   OnLoadingEnd },
    { "PLAYER_EXIT_GAME", OnExit },
    { "GAME_EXIT",     OnExit },
    { "Breathe",       OnBreathe, 1000 }  -- 每秒执行一次
)

-- 注销模块
JH.UnRegisterInit("RoleManager")

-- 退出事件快捷注册
JH.RegisterExit(function()
    SaveRoleData()
end)
```

---

## 四、UI 系统

### 4.1 UI 布局文件（.ini）

```ini
[RoleManager_Panel]
w=400
h=500
; 子控件定义...

[WndButton_Refresh]
w=100
h=30
x=20
y=20
txt=立即刷新

[WndButton_Save]
w=100
h=30
x=130
y=20
txt=立即保存
```

### 4.2 面板创建与生命周期

```lua
-- 打开窗口
local frame = Wnd.OpenWindow("ui/MainPanel.ini", "RoleManager_Panel")

-- Station 层级查找
local frame = Station.Lookup("Normal/RoleManager_Panel")
local btn = frame:Lookup("", "WndButton_Refresh")

-- 控件事件绑定（在 OnFrameCreate 中）
function RoleManager.OnFrameCreate()
    this:RegisterEvent("UI_SCALED")
end

function RoleManager.OnEvent(szEvent)
    -- 处理事件
end

function RoleManager.OnLButtonClick()
    local szName = this:GetName()
    if szName == "Btn_Refresh" then
        -- 刷新逻辑
    end
end

-- 控件操作
btn:SetText("新文本")
btn:GetText()
btn:Show()
btn:Hide()
btn:IsVisible()
btn:SetFontColor(r, g, b)
btn:SetRelPos(x, y)
```

### 4.3 GUI 辅助构建（JH 风格，可选）

```lua
-- JH 的 GUI 链式调用（更推荐用于复杂面板）
local ui = GUI(frame)
ui:Append("Text", {
    x = 10, y = 10,
    txt = "角色信息",
    font = 18,
    color = {255, 255, 255}
})
ui:Append("WndButton2", {
    x = 10, y = 40,
    txt = "立即刷新"
}):Click(function()
    CollectRoleData()
end)
```

---

## 五、V0.1 可行方案

### 5.1 技术可行性评估

| 功能 | 官方API支持 | 可行性 | 说明 |
|---|---|---|---|
| 角色名称 | ✅ `GetClientPlayer().szName` | 确定 | 直接获取 |
| 服务器 | ✅ `select(3, GetVersion())` | 确定 | 直接获取 |
| 门派 | ✅ `GetClientPlayer().dwForceID` | 确定 | 需维护ID映射表 |
| 等级 | ✅ `GetClientPlayer().nLevel` | 确定 | 直接获取 |
| 心法 | ⚠️ 待验证 | 部分可行 | 可能需UI层抓取 |
| 更新时间 | ✅ `GetCurrentTime()` | 确定 | 本地生成 |
| 角色ID | ✅ `GetClientPlayer().dwID` | 确定 | 直接获取 |
| 副本CD | ⚠️ 待验证 | 后续可行 | V0.3实现，需DungeonInfo表 |
| 百战随机次数 | ❌ 无直接API | 待探索 | V0.4实现，可能需UI爬取 |
| 百战定向次数 | ❌ 无直接API | 待探索 | V0.4实现，可能需UI爬取 |
| 百战精耐 | ❌ 无直接API | 待探索 | V0.4实现，可能需UI爬取 |
| 百战技能 | ❌ 无直接API | 待探索 | V0.4实现，可能需UI爬取 |

### 5.2 V0.1 架构设计

```
RoleManager/
├── info.ini              ← 插件注册：[RoleManager], lua_0~6
├── Main.lua              ← 全局命名空间 + 入口函数
├── Event.lua             ← 事件绑定中心
├── Collect.lua           ← 数据采集核心
├── Save.lua              ← 本地持久化
├── Export.lua            ← JSON导出（自定义序列化）
├── UI.lua                ← 简单面板（3个按钮）
├── Config.lua            ← 门派映射表 + 常量
└── Data/                 ← 运行时生成
    └── RoleData.jx3dat   ← 二进制存储
```

### 5.3 Main.lua 入口设计

```lua
-- Main.lua - 插件主入口
RoleManager = {
    VERSION = "0.1.0",
    DATA_DIR = "interface/RoleManager/Data/",
}

-- 全局数据缓存
RoleManager.Cache = {}

-- 插件面板生命周期
function RoleManager.OnFrameCreate()
    -- 面板初始化
end

function RoleManager.OnFrameBreathe()
    -- 呼吸帧回调（每帧）
end

function RoleManager.OnEvent(szEvent)
    -- 面板事件
end

function RoleManager.OnLButtonClick()
    -- 按钮点击
end

-- 主菜单注册（在游戏主菜单添加入口图标）
-- 使用 RegisterAddonMenu 或 GUI.RegisterPanel
```

### 5.4 Event.lua 设计

```lua
-- Event.lua - 事件绑定
local EVENTS = {
    "LOADING_END.RoleManager",
    "FIRST_LOADING_END.RoleManager",
    "PLAYER_ENTER_WORLD.RoleManager",
    "PLAYER_EXIT_GAME.RoleManager",
    "GAME_EXIT.RoleManager",
    "RELOAD_UI_ADDON_BEGIN.RoleManager",
}

function RoleManager.RegisterEvents()
    for _, ev in ipairs(EVENTS) do
        JH.RegisterEvent(ev, RoleManager.OnGameEvent)
    end
end

function RoleManager.OnGameEvent(szEvent)
    -- 去掉后缀 key
    local baseEvent = szEvent:match("^(.-)%..*$") or szEvent

    if baseEvent == "FIRST_LOADING_END" then
        RoleManager.Initialize()
    elseif baseEvent == "LOADING_END"
        or baseEvent == "PLAYER_ENTER_WORLD" then
        RoleManager.OnEnterWorld()
    elseif baseEvent == "PLAYER_EXIT_GAME"
        or baseEvent == "GAME_EXIT"
        or baseEvent == "RELOAD_UI_ADDON_BEGIN" then
        RoleManager.OnExit()
    end
end

function RoleManager.Initialize()
    -- 首次加载：初始化配置
    RoleManager.Output("插件已加载 v" .. RoleManager.VERSION)
end

function RoleManager.OnEnterWorld()
    local me = GetClientPlayer()
    if me and me.szName ~= "" then
        RoleManager.Output("检测到角色: " .. me.szName)
        RoleManager.CollectRoleData()
        RoleManager.SaveRoleData()
    end
end

function RoleManager.OnExit()
    RoleManager.CollectRoleData()
    RoleManager.SaveRoleData()
    RoleManager.Output("数据已保存")
end
```

### 5.5 Collect.lua 设计

```lua
-- Collect.lua - 数据采集
function RoleManager.CollectRoleData()
    local me = GetClientPlayer()
    if not me then return end

    local _, _, serverName = GetVersion()

    local data = {
        Server     = serverName or "未知",
        Role       = me.szName,
        RoleID     = me.dwID,
        ForceID    = me.dwForceID,
        School     = RoleManager.GetSchoolName(me.dwForceID),
        Level      = me.nLevel,
        UpdateTime = os.date("%Y-%m-%d %H:%M:%S"),
    }

    RoleManager.Cache = data
    RoleManager.Output("数据采集完成: " .. data.Role)
    return data
end

-- 门派ID→名称映射
function RoleManager.GetSchoolName(dwForceID)
    return RoleManager.Config.ForceNames[dwForceID] or "未知门派"
end
```

### 5.6 Save.lua 设计

```lua
-- Save.lua - 数据持久化
local DATA_FILE = "RoleData.jx3dat"
local DATA_DIR  = "interface/RoleManager/Data/"

function RoleManager.SaveRoleData()
    if not RoleManager.Cache or not RoleManager.Cache.Role then
        RoleManager.Output("无数据可保存")
        return
    end

    local ok, err = pcall(SaveLUAData, DATA_FILE, RoleManager.Cache)
    if ok then
        RoleManager.Output("数据已保存: " .. RoleManager.Cache.Role)
    else
        RoleManager.Output("保存失败: " .. tostring(err))
    end
end

function RoleManager.LoadRoleData()
    local data = LoadLUAData(DATA_FILE)
    if data then
        RoleManager.Cache = data
        RoleManager.Output("数据已加载: " .. (data.Role or "未知"))
        return data
    end
end

-- 多角色数据结构（V0.5+）
function RoleManager.SaveRoleDataByServer()
    local data = RoleManager.Cache
    local serverDir = data.Server:gsub("%s+", "_")
    local roleFile = data.Role .. ".jx3dat"

    -- 按 服务器/角色名.jx3dat 保存
    local path = serverDir .. "/" .. roleFile
    SaveLUAData(path, data)
end
```

### 5.7 Export.lua 设计

```lua
-- Export.lua - JSON导出
-- ⚠ JX3 Lua环境没有原生JSON库，需内嵌简单序列化

function RoleManager.ExportJSON()
    local data = RoleManager.Cache
    if not data then
        RoleManager.Output("无数据可导出")
        return
    end

    local json = RoleManager.TableToJSON(data)

    -- 保存为 .json 文件（.jx3dat 也可以存字符串）
    SaveLUAData("Export/" .. data.Role .. ".json", json)
    RoleManager.Output("JSON已导出: " .. data.Role)
end

-- 简易 JSON 序列化（Lua实现）
function RoleManager.TableToJSON(tbl, indent)
    -- 递归序列化实现
    -- 处理 string/number/boolean/table
end
```

### 5.8 UI.lua 设计

```lua
-- UI.lua - 简单面板
local PANEL_INI = "interface/RoleManager/ui/MainPanel.ini"

function RoleManager.OpenPanel()
    local frame = Station.Lookup("Normal/RoleManager_Panel")
    if frame then
        frame:Show()
        frame:BringToTop()
        return
    end

    frame = Wnd.OpenWindow(PANEL_INI, "RoleManager_Panel")
    -- 绑定按钮事件
    local btnRefresh = frame:Lookup("", "Btn_Refresh")
    local btnSave    = frame:Lookup("", "Btn_Save")
    local btnExport  = frame:Lookup("", "Btn_Export")
end

-- 注册主菜单入口
GUI.RegisterPanel("多角色管理", 100, g_tStrings.CHANNEL_CHANNEL, {
    OnPanelActive = function(frame)
        -- 面板打开时刷新数据显示
        local ui = GUI(frame)
        local d = RoleManager.Cache
        if d then
            ui:Append("Text", {x=10, y=10, txt=d.Role})
            ui:Append("Text", {x=10, y=30, txt=d.Server})
        end
    end
})
```

---

## 六、版本更新与分发

### 6.1 版本管理

```
info.ini 中的 version 字段控制版本号
- 格式: "major.minor" 如 "1.0"
- 更新插件时只需替换 interface/RoleManager/ 下文件
- 客户端启动时自动检测并加载新版本
```

### 6.2 更新机制

- **手动更新：** 用户下载新文件覆盖
- **打包分发：** 将整个 RoleManager 文件夹打包为 .zip
- **开发者调试：** 使用 `/reloadui` 命令重载插件或 `EnableDebugEnv` 开启调试环境
- **调试日志：** 在 `@DATA/EnableDebug` 文件存在时启用 JH 调试输出

### 6.3 分发注意事项

- 需要 key 验证（zhcn版本），合法插件才能加载
- 避免调用未公开的API，防止被封禁
- 推荐签名/打包机制（具体需咨询官方）

---

## 七、风险与限制

| 风险 | 等级 | 应对 |
|---|---|---|
| 百战API缺失 | 🔴 高 | V0.1-V0.3先跳过，V0.4探索UI层抓取 |
| 心法API缺失 | 🟡 中 | 预留字段，或通过技能配置反推 |
| 副本CD API不确定 | 🟡 中 | JH有DungeonInfo表查询，V0.3可尝试 |
| 插件Key验证 | 🟡 中 | 需确认当前版本的验证机制 |
| 跨版本兼容 | 🟢 低 | 使用稳定的基础API，加版本判断 |
| 存储路径变化 | 🟢 低 | 统一使用 `interface/插件名/Data/` 约定 |

---

## 八、建议的新版本路线（基于实际API能力）

鉴于百战和部分副本CD API的缺失，建议调整版本规划：

```
V0.1 ✅ 基础框架 + 角色信息采集 + 本地存储
      └── 使用 100% 已确认可用的API

V0.2 ✅ 装备面板
      └── 通过 Station.Lookup("Normal/Player") 遍历装备槽

V0.3 ✅ 副本CD（可采集部分）
      └── 用 g_tTable.DungeonInfo + GetMapList 获取有API支持的副本CD

V0.4 ⚠️ 百战数据（探索性开发）
      └── 优先尝试 UI Station 抓取
      └── 如不可行，保持预留字段等待官方接口

V0.5 ✅ 多角色汇总UI
      └── 基于已采集到的数据展示

V1.0 ✅ Windows管理工具
      └── 读取 .jx3dat 或导出的 .json 文件
      └── 提供统计、搜索、Excel导出
```

---

## 九、参考资源

| 资源 | 说明 |
|---|---|
| [菊花插件集 GitHub](https://github.com/luckyyyyy/JH) | 最大规模JX3插件，源码参考 |
| [JX3Box API](https://node.jx3box.com/documentation) | 社区提供的JX3数据API |
| [CSDN: 剑三插件教程](https://blog.csdn.net/wdykanq/article/details/11741677) | 调试环境搭建 |
| [GitHub: jx3-plugin](https://github.com/jx3-plugin) | 社区插件组织 |
| [百度文库: 剑三插件编写入门](https://wenku.baidu.com/view/7a56bb6cab956bec0975f46527d3240c8447a18f.html) | 入门教程 |

---

**文档版本:** 1.0 | **最后更新:** 2026-07-25
