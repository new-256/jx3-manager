-- UI.lua - 界面模块
-- 创建插件主面板，提供刷新/保存/导出按钮和信息显示
-- 重要: 面板 frame 名称为 "RoleManager"，与全局表同名，这样游戏引擎
--       会自动将 OnFrameCreate / OnLButtonClick / OnEvent 等回调绑定到 RoleManager 表

RoleManager = RoleManager or {}

-- 面板窗口名称（必须与 .ini section 名一致）
local PANEL_NAME = "RoleManager"

-- 初始化界面入口
function RoleManager.InitUIMenu()
    -- 检测 JH 插件
    local frame = Station.Lookup("Normal/JH")
    if frame then
        RoleManager.Log("检测到 JH 插件，可通过 JH 面板使用本插件")
    end
end

-- 面板创建回调（游戏引擎在窗口创建后自动调用）
function RoleManager.OnFrameCreate()
    RoleManager.PanelCreated = true
    RoleManager.UpdatePanelDisplay()
end

-- 面板事件回调
function RoleManager.OnEvent(szEvent)
    if szEvent == "UI_SCALED" then
        -- UI缩放时自动调整
    end
end

-- 打开插件面板
function RoleManager.OpenPanel()
    local frame = Station.Lookup("Normal/" .. PANEL_NAME)
    if frame then
        if not frame:IsVisible() then
            frame:Show()
        end
        frame:BringToTop()
        RoleManager.UpdatePanelDisplay()
        return frame
    end

    -- 创建新面板
    local ok, err = pcall(Wnd.OpenWindow, RoleManager.UI_INI, PANEL_NAME)
    if not ok then
        RoleManager.Log("面板创建失败: " .. tostring(err))
        return nil
    end

    RoleManager.UpdatePanelDisplay()
    return Station.Lookup("Normal/" .. PANEL_NAME)
end

-- 关闭面板
function RoleManager.ClosePanel()
    local frame = Station.Lookup("Normal/" .. PANEL_NAME)
    if frame and frame:IsVisible() then
        frame:Hide()
    end
end

-- 切换面板显隐
function RoleManager.TogglePanel()
    local frame = Station.Lookup("Normal/" .. PANEL_NAME)
    if frame and frame:IsVisible() then
        RoleManager.ClosePanel()
    else
        RoleManager.OpenPanel()
    end
end

-- 更新面板上的数据显示
function RoleManager.UpdatePanelDisplay()
    local frame = Station.Lookup("Normal/" .. PANEL_NAME)
    if not frame or not frame:IsVisible() then
        return
    end

    local data = RoleManager.CurrentData

    local function setText(cname, txt)
        local ctrl = frame:Lookup("", cname)
        if ctrl then
            ctrl:SetText(txt or "--")
        end
    end

    if data then
        setText("Text_Role",    data.Role    or "--")
        setText("Text_Server",  "服务器: " .. (data.Server or "--"))
        setText("Text_School",  "门派: " .. (data.School or "--"))
        setText("Text_Level",   "等级: " .. tostring(data.Level or "--"))
        setText("Text_Time",    "更新: " .. (data.UpdateTime or "--"))
    else
        setText("Text_Role",    "未采集")
        setText("Text_Server",  "请点击【立即刷新】")
        setText("Text_School",  "")
        setText("Text_Level",   "")
        setText("Text_Time",    "")
    end
end

-- 按钮点击事件处理（游戏引擎自动将子控件点击路由到此函数）
function RoleManager.OnLButtonClick()
    local szName = this:GetName()

    if szName == "Btn_Refresh" then
        RoleManager.Refresh()
    elseif szName == "Btn_Save" then
        RoleManager.ManualSave()
    elseif szName == "Btn_Export" then
        RoleManager.ManualExport()
    elseif szName == "Btn_Close" then
        RoleManager.ClosePanel()
    end
end
