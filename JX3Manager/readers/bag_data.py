
"""
BagDataReader - 背包物品数据
来源: my#data/!all-users@zhcn_hd/userdata/role_statistics/bag_stat.v4.db
"""
import os, sqlite3, re

class BagDataReader:
    def __init__(self, data_path):
        self.data_path = data_path
    
    def read_all(self):
        db = os.path.join(self.data_path, "!all-users@zhcn_hd", "userdata", "role_statistics", "bag_stat.v4.db")
        if not os.path.exists(db): return {}
        
        conn = sqlite3.connect(db)
        c = conn.cursor()
        
        # Get owner mapping
        c.execute("SELECT ownerkey, ownername, servername FROM OwnerInfo")
        owners = {r[0]: {"name": r[1], "server": r[2]} for r in c.fetchall()}
        
        # Get item info mapping
        c.execute("SELECT tabtype, tabindex, tabsubindex, name, quality FROM ItemInfo")
        item_info = {}
        for r in c.fetchall():
            key = f"{r[0]}_{r[1]}_{r[2]}"
            item_info[key] = {"name": r[3], "quality": r[4]}
        
        # Get bag items grouped by owner
        c.execute("SELECT ownerkey, boxtype, boxindex, tabtype, tabindex, tabsubindex, bagcount FROM BagItems")
        bag_data = {}
        for ownerkey, boxtype, boxindex, tabtype, tabindex, tabsubindex, bagcount in c.fetchall():
            if ownerkey not in bag_data:
                bag_data[ownerkey] = {"items": [], "total_count": 0}
            
            info_key = f"{tabtype}_{tabindex}_{tabsubindex}"
            item = item_info.get(info_key, {"name": f"item_{tabindex}", "quality": 0})
            
            bag_data[ownerkey]["items"].append({
                "name": item["name"],
                "quality": item["quality"],
                "count": bagcount,
                "box_type": boxtype
            })
            bag_data[ownerkey]["total_count"] += bagcount
        
        conn.close()
        
        # Map ownerkey to character names
        result = {}
        for okey, data in bag_data.items():
            owner = owners.get(okey, {"name": okey, "server": "?"})
            result[owner["name"]] = data
        
        return result
    
    def get_baizhan_items(self):
        """Get only Baizhan-related items"""
        all_data = self.read_all()
        bz_items = {}
        for name, data in all_data.items():
            bz = [item for item in data["items"] if "百战" in item["name"] or "殊影" in item["name"] or "修罗" in item["name"]]
            if bz:
                bz_items[name] = {"items": bz, "total": sum(i["count"] for i in bz)}
        return bz_items
