-- Save.lua - 数据持久化模块
-- 使用 JX3 原生 SaveLUAData / LoadLUAData 进行二进制存储

RoleManager = RoleManager or {}

-- 保存当前角色数据到本地
function RoleManager.SaveRoleData()
    local data = RoleManager.CurrentData
    if not data then
        RoleManager.Log("保存失败: 无数据")
        return false
    end

    local ok, err = pcall(SaveLUAData, RoleManager.DATA_FILE, data)
    if ok then
        RoleManager.Log("数据已保存: " .. data.Role .. " (" .. data.Server .. ")")
        return true
    else
        RoleManager.Log("保存失败: " .. tostring(err))
        return false
    end
end

-- 从本地加载上次保存的角色数据
function RoleManager.LoadRoleData()
    local data = LoadLUAData(RoleManager.DATA_FILE)
    if data then
        RoleManager.CurrentData = data
        RoleManager.Log("数据已加载: " .. (data.Role or "未知") .. " Lv." .. (data.Level or "?"))
        return data
    else
        RoleManager.Log("未找到历史数据文件")
        return nil
    end
end

-- 按服务器和角色名保存（多角色支持预留）
-- 格式: Data/服务器_角色名.jx3dat
function RoleManager.SaveRoleDataByServerRole()
    local data = RoleManager.CurrentData
    if not data then return false end

    local server = (data.Server or "Unknown"):gsub("%s+", "_")
    local role   = (data.Role or "Unknown"):gsub("%s+", "_")
    local path   = server .. "_" .. role .. ".jx3dat"

    local ok, err = pcall(SaveLUAData, path, data)
    if ok then
        RoleManager.Log("多角色保存: " .. path)
        return true
    else
        RoleManager.Log("多角色保存失败: " .. tostring(err))
        return false
    end
end
