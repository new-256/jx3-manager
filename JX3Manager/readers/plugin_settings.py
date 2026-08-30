"""
PluginSettings - 直接修改茗伊插件设置
"""
import sqlite3, os
from logger import get_logger

logger = get_logger(__name__)

# 茗伊(MY)自己写入的布尔开关序列化格式（19 字节）。
# 注意: 之前误写成 20 字节（多一个 0x00），会让茗伊在登录加载插件时
#       GetUserSettings 解析崩溃（attempt to index a function value），
#       表现为游戏内无法打开茗伊插件。请勿改动此值。
BOOL_TRUE = bytes.fromhex("74 02 00 73 01 00 76 73 00 00 73 01 00 64 62 01 00 00 00")

# 需要开启的所有统计功能
REQUIRED_SETTINGS = {
    # 战斗日志
    "MY_CombatLogs.bEnable": BOOL_TRUE,
    "MY_CombatLogs.bEnableInDungeon": BOOL_TRUE,
    # 聊天记录
    "MY_ChatLog.bAutoConnectDB": BOOL_TRUE,
    # 角色统计
    "MY_RoleStatistics_RoleStat.bFloatEntry": BOOL_TRUE,
    "MY_RoleStatistics_RoleStat.bSaveDB": BOOL_TRUE,
    # 背包统计
    "MY_RoleStatistics_BagStat.bFloatEntry": BOOL_TRUE,
    "MY_RoleStatistics_BagStat.bSaveDB": BOOL_TRUE,
    # 副本统计
    "MY_RoleStatistics_DungeonStat.bFloatEntry": BOOL_TRUE,
    "MY_RoleStatistics_DungeonStat.bSaveDB": BOOL_TRUE,
    # 装备统计
    "MY_RoleStatistics_EquipStat.bFloatEntry": BOOL_TRUE,
    "MY_RoleStatistics_EquipStat.bSaveDB": BOOL_TRUE,
    # 任务统计
    "MY_RoleStatistics_TaskStat.bFloatEntry": BOOL_TRUE,
    "MY_RoleStatistics_TaskStat.bSaveDB": BOOL_TRUE,
    # 门派染色
    "MY_Farbnamen.bSaveDB": BOOL_TRUE,
    # 金团记录
    "MY_GKP.bMoneySystem": BOOL_TRUE,
    # 伤害统计
    "MY_Recount.bEnable": BOOL_TRUE,
}

def enable_all_stats(my_data_path, uid):
    """为指定角色开启所有统计功能"""
    config_dir = os.path.join(my_data_path, f"{uid}@zhcn_hd", "config")
    os.makedirs(config_dir, exist_ok=True)
    settings_db = os.path.join(config_dir, "settings.db")
    
    try:
        conn = sqlite3.connect(settings_db)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS data (key TEXT PRIMARY KEY, value BLOB)")
        count = 0
        for key, value in REQUIRED_SETTINGS.items():
            c.execute("INSERT OR REPLACE INTO data (key, value) VALUES (?, ?)", (key, value))
            count += 1
        conn.commit()
        conn.close()
        logger.info(f"Enabled {count} stats settings for uid {uid}")
        return True, f"已开启 {count} 项功能 (战斗日志/背包/副本/装备/任务统计等，需重登生效)"
    except Exception as e:
        logger.error(f"Failed to enable stats for uid {uid}: {e}")
        return False, str(e)

def enable_all_stats_for_all(my_data_path):
    """为 my#data 下的所有角色开启所有统计功能"""
    results = []
    if not os.path.exists(my_data_path):
        return results

    for d in os.listdir(my_data_path):
        if not d.endswith("@zhcn_hd"):
            continue
        uid = d.split("@")[0]
        if not uid.isdigit():
            continue

        ok, msg = enable_all_stats(my_data_path, uid)
        results.append({"uid": uid, "success": ok, "msg": msg})

    return results

def check_stats_enabled(my_data_path, uid):
    """检查统计功能是否已开启（同时校验值格式，损坏/格式错误的配置不计入）"""
    settings_db = os.path.join(my_data_path, f"{uid}@zhcn_hd", "config", "settings.db")
    if not os.path.exists(settings_db):
        logger.warning(f"settings.db not found for uid {uid}")
        return {"enabled": 0, "total": len(REQUIRED_SETTINGS)}
    try:
        conn = sqlite3.connect(settings_db)
        c = conn.cursor()
        c.execute("SELECT key, value FROM data WHERE key IN (" + ",".join("?" * len(REQUIRED_SETTINGS)) + ")",
                  list(REQUIRED_SETTINGS.keys()))
        rows = dict(c.fetchall())
        conn.close()
        count = sum(1 for k in REQUIRED_SETTINGS if rows.get(k) == BOOL_TRUE)
        logger.debug(f"Stats check for uid {uid}: {count}/{len(REQUIRED_SETTINGS)} enabled")
        return {"enabled": count, "total": len(REQUIRED_SETTINGS)}
    except Exception as e:
        logger.error(f"Failed to check stats for uid {uid}: {e}")
        return {"enabled": 0, "total": len(REQUIRED_SETTINGS)}
