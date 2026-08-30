
"""
EquipDataReader - 装备详情
来源: my#data/!all-users@zhcn_hd/userdata/role_statistics/equip_stat.v4.db
"""
import os, sqlite3, re

class EquipDataReader:
    def __init__(self, data_path):
        self.data_path = data_path
    
    def read_all(self):
        db = os.path.join(self.data_path, "!all-users@zhcn_hd", "userdata", "role_statistics", "equip_stat.v4.db")
        if not os.path.exists(db): return {}
        
        conn = sqlite3.connect(db)
        c = conn.cursor()
        
        # Owner info
        c.execute("SELECT ownerkey, ownername, servername FROM OwnerInfo")
        owners = {r[0]: {"name": r[1], "server": r[2]} for r in c.fetchall()}
        
        # Equip items
        c.execute("SELECT ownerkey, boxtype, boxindex, itemid, desc FROM EquipItems")
        
        result = {}
        for ownerkey, boxtype, boxindex, itemid, desc in c.fetchall():
            owner = owners.get(ownerkey, {"name": ownerkey, "server": "?"})
            name = owner["name"]
            if name not in result:
                result[name] = {"items": [], "total_score": 0}
            
            # Extract item name from desc (HTML-like format)
            item_name = f"item_{itemid}"
            if desc:
                m = re.search(r'text="([^"]+)"', desc)
                if m:
                    item_name = m.group(1)
            
            # Extract equipment score
            score = 0
            if desc:
                m = re.search(r'装备分数(\d+)', desc)
                if m:
                    score = int(m.group(1))
                    result[name]["total_score"] += score
            
            slot_names = {0: "武器", 1: "暗器", 2: "帽子", 3: "衣服", 4: "腰带", 5: "护腕", 6: "裤子", 7: "鞋子", 8: "项链", 9: "戒指", 10: "腰坠"}
            slot = slot_names.get(boxindex, f"槽位{boxindex}")
            
            result[name]["items"].append({
                "name": item_name,
                "slot": slot,
                "score": score,
                "item_id": itemid
            })
        
        conn.close()
        return result
