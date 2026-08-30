-- Config.lua - 常量定义与门派映射
-- 路径约定: "Interface/" 映射到 bin/{version}/interface/
-- 插件结构: interface/RoleManager/Main/ (匹配 JH/MY 的 sub-plugin 模式)

RoleManager = RoleManager or {}

RoleManager.VERSION    = "0.1.0"
RoleManager.PLUGIN_NAME = "JX3多角色管理"
RoleManager.ROOT_PATH   = "Interface/RoleManager/"
RoleManager.PLUGIN_PATH = "Interface/RoleManager/Main/"
RoleManager.DATA_PATH   = "Interface/RoleManager/Main/Data/"
RoleManager.DATA_FILE   = "RoleData.jx3dat"
RoleManager.UI_INI      = "Interface/RoleManager/Main/ui/MainPanel.ini"

-- 门派ID映射
RoleManager.ForceNames = {
    [0]  = "未知",
    [1]  = "少林", [2]  = "万花", [3]  = "天策",
    [4]  = "纯阳", [5]  = "七秀", [6]  = "藏剑",
    [7]  = "五毒", [8]  = "唐门", [9]  = "五毒",
    [10] = "唐门", [11] = "明教", [12] = "丐帮",
    [13] = "苍云", [14] = "长歌", [15] = "霸刀",
    [16] = "蓬莱", [17] = "凌雪阁", [18] = "衍天宗",
    [19] = "药宗", [20] = "刀宗", [21] = "万灵",
    [22] = "段氏",
}

function RoleManager.GetForceName(dwForceID)
    return RoleManager.ForceNames[dwForceID] or ("门派#" .. tostring(dwForceID))
end

function RoleManager.Log(szMsg)
    OutputMessage("MSG_SYS", "[RoleManager] " .. szMsg .. "\n")
end

function RoleManager.Tip(szMsg)
    OutputMessage("MSG_ANNOUNCE_YELLOW", "[RoleManager] " .. szMsg .. "\n")
end

-- 首次加载完成回调
function RoleManager.OnFirstLoadingEnd()
    RoleManager.Log("插件已加载 v" .. RoleManager.VERSION)
end
