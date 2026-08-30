-- Main.lua - 插件主入口
-- 初始化插件、管理数据缓存、协调各模块

RoleManager = RoleManager or {}

-- 当前角色数据缓存
RoleManager.CurrentData = nil

-- 面板是否已创建
RoleManager.PanelCreated = false

-- 采集重试计数（用于延迟采集机制）
RoleManager._collectRetry = nil

-- 插件首次加载时执行
function RoleManager.OnFirstLoadingEnd()
    RoleManager.Log("插件已加载 v" .. RoleManager.VERSION)
    RoleManager.Log("数据目录: " .. RoleManager.DATA_PATH)

    -- 注册所有事件
    RoleManager.RegisterAllEvents()

    -- 初始化界面入口
    RoleManager.InitUIMenu()
end

-- 角色进入世界时执行（登录/切角色后）
function RoleManager.OnPlayerEnterWorld()
    local me = GetClientPlayer()
    if not me or me.szName == "" then
        return
    end

    RoleManager.Log("检测到角色进入: " .. me.szName)

    -- 启动延迟采集
    RoleManager._collectRetry = 0
end

-- 呼吸帧回调（每秒约16帧，用于延迟采集）
function RoleManager.OnFrameBreathe()
    -- 延迟采集逻辑
    if RoleManager._collectRetry then
        RoleManager._collectRetry = RoleManager._collectRetry + 1
        local me = GetClientPlayer()
        if me and me.szName ~= "" and me.nLevel and me.nLevel > 0 then
            RoleManager.CollectAndSave()
            RoleManager._collectRetry = nil
        elseif RoleManager._collectRetry > 180 then
            -- 约3秒（180帧/60fps）超时
            RoleManager.Log("采集超时，请确认角色已完全登录")
            RoleManager._collectRetry = nil
        end
    end
end

-- 采集并保存（核心流程）
function RoleManager.CollectAndSave()
    local data = RoleManager.CollectRoleData()
    if data then
        RoleManager.CurrentData = data
        RoleManager.SaveRoleData()
        RoleManager.UpdatePanelDisplay()
        RoleManager.Log("数据已采集并保存: " .. data.Role .. " Lv." .. data.Level)
    end
end

-- 手动刷新
function RoleManager.Refresh()
    local me = GetClientPlayer()
    if not me or me.szName == "" then
        RoleManager.Log("未检测到在线角色，请先登录角色")
        return
    end
    RoleManager.Log("手动刷新...")
    RoleManager.CollectAndSave()
end

-- 手动保存
function RoleManager.ManualSave()
    if not RoleManager.CurrentData then
        RoleManager.Log("无数据可保存，请先刷新")
        return
    end
    RoleManager.SaveRoleData()
end

-- 手动导出JSON
function RoleManager.ManualExport()
    if not RoleManager.CurrentData then
        RoleManager.Log("无数据可导出，请先刷新")
        return
    end
    RoleManager.ExportJSON()
end
