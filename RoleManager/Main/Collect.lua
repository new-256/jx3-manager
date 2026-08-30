-- Collect.lua - 数据采集模块
-- 从游戏客户端获取角色基础信息

RoleManager = RoleManager or {}

-- 采集当前角色数据
-- 返回 table 或 nil
function RoleManager.CollectRoleData()
    local me = GetClientPlayer()
    if not me then
        RoleManager.Log("采集失败: 无法获取角色对象")
        return nil
    end

    if me.szName == "" then
        RoleManager.Log("采集失败: 角色名称为空（可能尚未完全登录）")
        return nil
    end

    -- 获取服务器信息
    local _, _, serverName = GetVersion()
    if not serverName or serverName == "" then
        serverName = "未知服务器"
    end

    -- 获取当前时间
    local updateTime = os.date("%Y-%m-%d %H:%M:%S")

    local data = {
        Server     = serverName,
        Role       = me.szName,
        RoleID     = me.dwID,
        ForceID    = me.dwForceID,
        School     = RoleManager.GetForceName(me.dwForceID),
        Level      = me.nLevel,
        UpdateTime = updateTime,
    }

    return data
end

-- 检查角色是否已切换（与缓存数据比较）
function RoleManager.HasRoleChanged()
    if not RoleManager.CurrentData then
        return true
    end
    local me = GetClientPlayer()
    if not me then
        return false
    end
    return me.szName ~= RoleManager.CurrentData.Role
        or me.dwID ~= RoleManager.CurrentData.RoleID
end
