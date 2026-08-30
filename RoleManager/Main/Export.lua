-- Export.lua - 数据导出模块
-- 将采集的角色数据导出为 JSON 文本文件

RoleManager = RoleManager or {}

-- 简易 JSON 序列化器
-- JX3 Lua 环境没有原生 JSON 库，需自行实现
local function ToJSON(obj, indent)
    local indentStr = indent or ""
    local nextIndent = indentStr .. "  "

    local t = type(obj)
    if t == "nil" then
        return "null"
    elseif t == "boolean" then
        return obj and "true" or "false"
    elseif t == "number" then
        return tostring(obj)
    elseif t == "string" then
        -- 转义特殊字符
        local escaped = obj:gsub("\\", "\\\\")
                           :gsub('"', '\\"')
                           :gsub("\n", "\\n")
                           :gsub("\r", "\\r")
                           :gsub("\t", "\\t")
        return '"' .. escaped .. '"'
    elseif t == "table" then
        local parts = {}
        local isArray = true
        local maxIdx = 0

        for k in pairs(obj) do
            if type(k) ~= "number" then
                isArray = false
                break
            end
            if k > maxIdx then maxIdx = k end
        end

        if isArray and maxIdx == #obj and #obj > 0 then
            -- 数组格式
            for i, v in ipairs(obj) do
                parts[#parts + 1] = nextIndent .. ToJSON(v, nextIndent)
            end
            return "[\n" .. table.concat(parts, ",\n") .. "\n" .. indentStr .. "]"
        else
            -- 对象格式
            for k, v in pairs(obj) do
                local key
                if type(k) == "string" then
                    key = '"' .. k .. '"'
                else
                    key = '"' .. tostring(k) .. '"'
                end
                parts[#parts + 1] = nextIndent .. key .. ": " .. ToJSON(v, nextIndent)
            end
            return "{\n" .. table.concat(parts, ",\n") .. "\n" .. indentStr .. "}"
        end
    else
        return '"<' .. t .. '>"'
    end
end

-- 导出当前角色数据为 JSON
function RoleManager.ExportJSON()
    local data = RoleManager.CurrentData
    if not data then
        -- 尝试从文件加载
        data = RoleManager.LoadRoleData()
    end
    if not data then
        RoleManager.Log("导出失败: 无数据")
        return false
    end

    local json = ToJSON(data, "")

    -- 保存 JSON 文本文件
    local roleName = (data.Role or "unknown"):gsub("%s+", "_")
    local exportPath = roleName .. ".json"

    local ok, err = pcall(SaveLUAData, exportPath, json)
    if ok then
        RoleManager.Tip("JSON 已导出: " .. exportPath)
        RoleManager.Log("导出成功 -> " .. exportPath)
        return true
    else
        RoleManager.Log("导出失败: " .. tostring(err))
        return false
    end
end

-- 导出 CSV 格式（预留，后续版本实现）
function RoleManager.ExportCSV()
    -- TODO: V0.2+ 实现
    RoleManager.Log("CSV 导出将在后续版本支持")
end
