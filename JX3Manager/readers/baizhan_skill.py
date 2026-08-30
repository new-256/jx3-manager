"""
BaizhanSkillReader - 百战技能数据 (从背包物品提取)
来源: my#data/!all-users@zhcn_hd/userdata/role_statistics/bag_stat.v4.db
百战技能在背包中以"招式要诀"物品形式存在
"""
import os, sqlite3, re
from logger import get_logger

logger = get_logger(__name__)

class BaizhanSkillReader:
    def __init__(self, data_path):
        self.data_path = data_path
    
    def read_all(self):
        db = os.path.join(self.data_path, "!all-users@zhcn_hd", "userdata", "role_statistics", "bag_stat.v4.db")
        if not os.path.exists(db):
            logger.warning(f"Bag stat DB not found: {db}")
            return {}
        
        conn = sqlite3.connect(db)
        c = conn.cursor()
        
        c.execute("""
            SELECT o.ownername, i.name, i.quality, b.bagcount
            FROM BagItems b
            JOIN OwnerInfo o ON b.ownerkey = o.ownerkey
            JOIN ItemInfo i ON b.tabtype = i.tabtype AND b.tabindex = i.tabindex
            WHERE i.name LIKE '%招式要诀%'
        """)
        
        skills = {}
        for name, item_name, quality, count in c.fetchall():
            if name not in skills:
                skills[name] = []
            
            m = re.search(r'《(.+?)》.*?·(.+)重', item_name)
            if m:
                skills[name].append({
                    "name": m.group(1),
                    "level": m.group(2),
                    "quality": quality,
                    "count": count
                })
        
        conn.close()
        logger.debug(f"Read baizhan skills for {len(skills)} characters")
        return skills
