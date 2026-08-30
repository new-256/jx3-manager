# JX3 多角色管理 (RoleManager) v0.1 — 安装与故障排查

## 方案A：正式插件（JH/MY 模式）

### 安装

将整个 `RoleManager` 文件夹复制到游戏 `interface` 目录下：

```
{游戏目录}\bin\zhcn_hd\interface\RoleManager\
├── package.ini
├── Main\
│   ├── info.ini
│   ├── Config.lua
│   ├── Main.lua
│   ├── Event.lua
│   ├── Collect.lua
│   ├── Save.lua
│   ├── Export.lua
│   ├── UI.lua
│   ├── ui\
│   │   └── MainPanel.ini
│   └── Data\
```

> 如果你的游戏安装在 `C:\Games\JX3\`，完整路径为：
> `C:\Games\JX3\bin\zhcn_hd\interface\RoleManager\`

> 如果你使用的是标准画质（非HD），路径为：
> `C:\Games\JX3\bin\zhcn\interface\RoleManager\`

### 验证

进入游戏后，系统聊天频道应显示：
```
[RoleManager] 插件已加载 v0.1.0
```

然后输入以下命令打开面板：
```
/script RoleManager.OpenPanel()
```

---

## 方案B：极简测试（先试这个！）

### 安装

将 `RoleManager_Test` 文件夹复制到 `interface` 目录下：

```
{游戏目录}\bin\zhcn_hd\interface\RoleManager_Test\
├── info.ini
└── Hello.lua
```

### 验证

进入游戏后，如果系统频道出现以下消息，说明**插件加载机制正常**：
```
[RoleManager_Test] 插件加载成功！
```

---

## 故障排查

### 如果方案B也没有消息：

1. **检查路径** — 打开游戏安装目录，确认 `interface` 文件夹的确切位置：
   - 常见位置：`bin\zhcn_hd\interface\` 或 `bin\zhcn\interface\`
   - 检查游戏快捷方式的"起始位置"
   - 不同画质版本路径不同

2. **在游戏内输入 `/reloadui`** 重载所有插件

3. **检查游戏日志：**
   打开 `{游戏目录}\bin\zhcn_hd\logs\` 查看最近的 `.log` 文件，
   搜索 "RoleManager" 或 "error" 关键词

4. **尝试其他路径：**
   - `bin\zhcn\interface\`
   - `bin\zhcn_exp\interface\`（开发版）
   - 游戏根目录的 `interface\`（如果存在）

5. **Key验证问题：**
   JH 插件 README 提到 "zhcn版本需要key验证，否则会被判为非法插件"
   - 如果这是原因，插件会被静默忽略
   - 可能需要将插件注册为JH或MY的子模块

### 如果方案B成功但方案A不行：

- 说明插件加载正常，问题出在方案A的代码或结构
- 请把游戏日志中的错误信息发给我

### 如果两个方案都没有消息：

- 最可能是路径不对或key验证拦截
- 请告诉我：
  1. 游戏安装的完整路径
  2. `interface` 文件夹下有哪些文件夹
  3. 是否安装了JH/茗伊等插件
