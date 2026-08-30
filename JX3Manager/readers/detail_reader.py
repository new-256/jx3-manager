"""
RoleDetailReader - 提取角色的背包物品、成就、宠物及奇遇等深入数据
"""
import os, sqlite3, re, logger
from datetime import datetime

logger = logger.get_logger(__name__)

class RoleDetailReader:
    def __init__(self, data_path):
        self.data_path = data_path
        self.bag_db = os.path.join(data_path, "!all-users@zhcn_hd", "userdata", "role_statistics", "bag_stat.v4.db")
        self.equip_db = os.path.join(data_path, "!all-users@zhcn_hd", "userdata", "role_statistics", "equip_stat.v4.db")

    def get_bag_items(self, name, server=""):
        """获取角色的背包与仓库物品列表"""
        items = []
        if not os.path.exists(self.bag_db):
            return items
        
        try:
            conn = sqlite3.connect(self.bag_db)
            c = conn.cursor()
            sql = """
                SELECT 
                    item.name,
                    bag.bagcount + bag.bankcount as cnt,
                    item.quality,
                    item.desc
                FROM BagItems bag
                JOIN OwnerInfo owner ON bag.ownerkey = owner.ownerkey
                LEFT JOIN ItemInfo item ON bag.tabtype = item.tabtype AND bag.tabindex = item.tabindex AND bag.tabsubindex = item.tabsubindex
                WHERE owner.ownername = ?
            """
            params = [name]
            if server:
                sql += " AND owner.servername = ?"
                params.append(server)
            
            c.execute(sql, tuple(params))
            for row in c.fetchall():
                iname = row[0]
                if not iname:
                    continue
                cnt = int(row[1]) if row[1] else 1
                quality = int(row[2]) if row[2] else 1
                desc = row[3] if row[3] else ""
                # Clean up tabbed formatting in desc
                desc_clean = re.sub(r'[\r\n\t]+', ' ', desc).strip()
                items.append({
                    "name": iname,
                    "count": cnt,
                    "quality": quality,
                    "desc": desc_clean
                })
            conn.close()
        except Exception as e:
            logger.warning(f"Error querying bag items for {name}: {e}")
        
        return sorted(items, key=lambda x: (-x["quality"], -x["count"], x["name"]))

    def get_achievements(self, uid):
        """获取已解锁成就 ID 数组"""
        ach_file = os.path.join(self.data_path, f"{uid}@zhcn_hd", "userdata", "achievement_acquire_shot.jx3dat")
        ach_ids = []
        if os.path.exists(ach_file):
            try:
                with open(ach_file, "rb") as f:
                    txt = f.read().decode("gbk", errors="replace")
                m = re.search(r'\{([0-9,\s]+)\}', txt)
                if m:
                    ach_ids = [int(x.strip()) for x in m.group(1).split(",") if x.strip().isdigit()]
            except Exception as e:
                logger.warning(f"Error reading achievements for {uid}: {e}")
        return ach_ids

    def get_equipped_items(self, name, server=""):
        """获取角色的已穿戴装备列表与面板总结属性"""
        gear_list = []
        summary_attrs = {
            "attack": 0,
            "crit": 0,
            "overcome": 0,
            "haste": 0,
            "strain": 0,
            "total_score": 0
        }
        if not os.path.exists(self.equip_db):
            return gear_list, summary_attrs

        slot_map = {
            0: "武器",
            1: "武器",
            2: "暗器",
            3: "上衣",
            4: "帽子",
            5: "项链",
            6: "戒指 1",
            7: "戒指 2",
            8: "腰带",
            9: "腰坠",
            10: "裤子",
            11: "鞋子",
            12: "护手"
        }

        try:
            conn = sqlite3.connect(self.equip_db)
            c = conn.cursor()
            sql = """
                SELECT 
                    eq.boxindex,
                    eq.strength,
                    eq.desc,
                    eq.suitindex
                FROM EquipItems eq
                JOIN OwnerInfo ow ON eq.ownerkey = ow.ownerkey
                WHERE ow.ownername = ? AND (eq.suitindex = 1 OR eq.suitindex = ow.ownersuitindex)
            """
            params = [name]
            if server:
                sql += " AND ow.servername = ?"
                params.append(server)
            
            c.execute(sql, tuple(params))
            rows = c.fetchall()
            conn.close()

            seen_slots = set()
            for row in rows:
                b_idx = int(row[0]) if row[0] is not None else 0
                if b_idx in seen_slots:
                    continue
                
                strength = int(row[1]) if row[1] is not None else 0
                desc = row[2] if row[2] else ""

                # Extract Name
                m_name = re.search(r'<[Tt]ext>text="([^"]+)"', desc)
                item_name = m_name.group(1) if m_name else ""
                if not item_name or item_name == "未知装备":
                    continue
                
                seen_slots.add(b_idx)

                # Quality & Equip Score
                m_q = re.search(r'品质等级\s*([0-9]+)', desc)
                quality_lvl = int(m_q.group(1)) if m_q else 0

                m_es = re.search(r'装备分数\s*([0-9]+)', desc)
                score_val = int(m_es.group(1)) if m_es else 0
                summary_attrs["total_score"] += score_val

                # Accumulate Combat Attributes
                for atk in re.findall(r'攻击提高\s*([0-9]+)', desc): summary_attrs["attack"] += int(atk)
                for crt in re.findall(r'会心等级提高\s*([0-9]+)', desc): summary_attrs["crit"] += int(crt)
                for ovc in re.findall(r'破防等级提高\s*([0-9]+)', desc): summary_attrs["overcome"] += int(ovc)
                for hst in re.findall(r'加速等级提高\s*([0-9]+)', desc): summary_attrs["haste"] += int(hst)
                for strn in re.findall(r'无双等级提高\s*([0-9]+)', desc): summary_attrs["strain"] += int(strn)

                gear_list.append({
                    "slot_id": b_idx,
                    "slot_name": slot_map.get(b_idx, f"部位 {b_idx}"),
                    "name": item_name,
                    "strength": strength,
                    "quality_level": quality_lvl,
                    "equip_score": score_val,
                    "raw_desc": desc
                })

        except Exception as e:
            logger.warning(f"Error reading equipped items for {name}: {e}")

        return sorted(gear_list, key=lambda x: x["slot_id"]), summary_attrs

    def get_serendipity_records(self, uid):
        """获取奇遇分享记录"""
        records = []
        seren_file = os.path.join(self.data_path, f"{uid}@zhcn_hd", "userdata", "serendipity_autoshare.jx3dat")
        if os.path.exists(seren_file):
            try:
                with open(seren_file, "rb") as f:
                    txt = f.read().decode("gbk", errors="replace")
                # Parse matches
                matches = re.findall(r'name\s*=\s*"([^"]+)".*?time\s*=\s*([0-9]+)', txt, re.DOTALL)
                for m in matches:
                    s_name = m[0]
                    t_stamp = int(m[1])
                    t_str = datetime.fromtimestamp(t_stamp).strftime("%Y-%m-%d %H:%M") if t_stamp > 0 else "未知"
                    records.append({"name": s_name, "time": t_str})
            except Exception as e:
                logger.warning(f"Error reading serendipity for {uid}: {e}")
        return records
