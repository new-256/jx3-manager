"""
Combat Log Configuration Module
Enables combat log recording in dungeon/secret realm maps for all characters
"""
import os, sqlite3
from logger import get_logger

# Correct boolean encoding (19 bytes) - matches plugin_settings.py
BOOL_TRUE = bytes.fromhex("74 02 00 73 01 00 76 73 00 00 73 01 00 64 62 01 00 00 00")

logger = get_logger(__name__)

# Combat log settings that should be enabled
COMBAT_LOG_SETTINGS = {
    "MY_CombatLogs.bEnable": 1,
    "MY_CombatLogs.bEnableInDungeon": 1,      # 关键：秘境/副本中记录
    "MY_CombatLogs.bEnableInBattleField": 1,  # 战场中记录
    "MY_CombatLogs.bEnableInOtherMaps": 1,    # 其他地图记录
    "MY_CombatLogs.bTargetInformation": 1,    # 目标信息
}

def get_character_settings_path(data_path, uid_dir):
    """获取角色的 settings.db 路径"""
    return os.path.join(data_path, uid_dir, "config", "settings.db")

def get_all_characters(data_path):
    """获取所有角色的 uid_dir 和名称"""
    import re
    chars = []
    for uid_dir in os.listdir(data_path):
        if not uid_dir.endswith("@zhcn_hd"):
            continue
        info_path = os.path.join(data_path, uid_dir, "info.jx3dat")
        if os.path.exists(info_path):
            with open(info_path, "rb") as f:
                txt = f.read().decode("gbk", errors="replace")
            m = re.search(r'name="([^"]+)"', txt)
            name = m.group(1) if m else uid_dir.split("@")[0]
            chars.append({"uid_dir": uid_dir, "name": name, "info_path": info_path})
    return chars

def read_combat_log_settings(settings_path):
    """读取当前战斗日志设置"""
    if not os.path.exists(settings_path):
        return {}
    conn = sqlite3.connect(settings_path)
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM data WHERE key LIKE "%CombatLog%"')
    rows = cursor.fetchall()
    conn.close()
    return {k: v for k, v in rows}

def enable_combat_logs_for_character(settings_path, dry_run=False):
    """为单个角色启用战斗日志设置"""
    if not os.path.exists(settings_path):
        return {"success": False, "error": "settings.db not found", "updated": []}
    
    conn = sqlite3.connect(settings_path)
    cursor = conn.cursor()
    updated = []
    
    try:
        for key, value in COMBAT_LOG_SETTINGS.items():
            # Check current value
            cursor.execute('SELECT value FROM data WHERE key = ?', (key,))
            row = cursor.fetchone()
            
            # Encode value as the game expects: b't\x02\x00s\x01\x00vs\x00\x00s\x01\x00db\x01\x00\x00\x00'
            # This is a serialized boolean true value
            encoded_value = b't\x02\x00s\x01\x00vs\x00\x00s\x01\x00db\x01\x00\x00\x00'
            
            if row:
                current = row[0]
                if current != encoded_value:
                    if not dry_run:
                        cursor.execute('UPDATE data SET value = ? WHERE key = ?', (encoded_value, key))
                    updated.append(key)
            else:
                # Insert new setting
                if not dry_run:
                    cursor.execute('INSERT INTO data (key, value) VALUES (?, ?)', (key, encoded_value))
                updated.append(key + " (new)")
        
        if not dry_run:
            conn.commit()
        
        conn.close()
        return {"success": True, "updated": updated}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e), "updated": []}

def enable_combat_logs_for_all(data_path, dry_run=False):
    """为所有角色启用战斗日志设置"""
    chars = get_all_characters(data_path)
    results = []
    
    for char in chars:
        settings_path = get_character_settings_path(data_path, char["uid_dir"])
        result = enable_combat_logs_for_character(settings_path, dry_run)
        result["name"] = char["name"]
        result["uid_dir"] = char["uid_dir"]
        results.append(result)
        
        if result["success"]:
            logger.info(f"[{char['name']}] Combat log settings updated: {result['updated']}")
        else:
            logger.error(f"[{char['name']}] Failed: {result['error']}")
    
    return results

if __name__ == "__main__":
    import sys
    data_path = r"D:\游戏\JX3\bin\zhcn_hd\interface\my#data"
    
    if len(sys.argv) > 1 and sys.argv[1] == "--apply":
        print("Applying combat log settings to all characters...")
        results = enable_combat_logs_for_all(data_path, dry_run=False)
    else:
        print("DRY RUN - Preview of changes (use --apply to apply):")
        results = enable_combat_logs_for_all(data_path, dry_run=True)
    
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f'{status} {r["name"]}: {r["updated"] or "No changes needed"}')
        if not r["success"]:
            print(f'   Error: {r["error"]}')
