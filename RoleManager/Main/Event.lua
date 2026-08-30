-- Event.lua - 事件监听系统
-- 注册所有游戏事件，在关键时机自动触发数据采集与保存

RoleManager = RoleManager or {}

-- 注册所有事件
function RoleManager.RegisterAllEvents()
    -- 首次加载完成（游戏启动）
    RegisterEvent("FIRST_LOADING_END", RoleManager.OnFirstLoadingEnd)

    -- 加载界面结束（每次过图/登录角色）
    RegisterEvent("LOADING_END", RoleManager.OnLoadingEnd)

    -- 玩家进入世界
    RegisterEvent("PLAYER_ENTER_WORLD", RoleManager.OnPlayerEnterWorld)

    -- 玩家退出游戏
    RegisterEvent("PLAYER_EXIT_GAME", RoleManager.OnPlayerExit)

    -- 游戏进程退出
    RegisterEvent("GAME_EXIT", RoleManager.OnPlayerExit)

    -- 插件即将重载
    RegisterEvent("RELOAD_UI_ADDON_BEGIN", RoleManager.OnPlayerExit)

    RoleManager.Log("事件注册完成")
end

-- 加载结束回调
function RoleManager.OnLoadingEnd()
    local me = GetClientPlayer()
    if me and me.szName ~= "" then
        -- 触发采集延迟
        RoleManager._collectRetry = 0
    end
end

-- 退出回调
function RoleManager.OnPlayerExit()
    local me = GetClientPlayer()
    if me and me.szName ~= "" and RoleManager.CurrentData then
        -- 退出前最后一次采集保存
        local data = RoleManager.CollectRoleData()
        if data then
            RoleManager.CurrentData = data
        end
    end
    if RoleManager.CurrentData then
        RoleManager.SaveRoleData()
        RoleManager.Log("退出前数据已保存: " .. RoleManager.CurrentData.Role)
    end
end
