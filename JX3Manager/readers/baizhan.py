"""
BaizhanReader - 百战异闻录Boss击杀数据
来源: 战斗日志文件名 (my#data/{uid}/userdata/combat_logs/*百战*.jcl)
"""
import os, re
from logger import get_logger

logger = get_logger(__name__)

class BaizhanReader:
    def __init__(self, data_path):
        self.data_path = data_path
    
    def read_all(self):
        results = {}
        for uid_dir in os.listdir(self.data_path):
            if not uid_dir.endswith("@zhcn_hd"): continue
            
            cl_dir = os.path.join(self.data_path, uid_dir, "userdata", "combat_logs")
            if not os.path.exists(cl_dir): continue
            
            # Get character name
            info_path = os.path.join(self.data_path, uid_dir, "info.jx3dat")
            char_name = uid_dir.split("@")[0]
            if os.path.exists(info_path):
                with open(info_path, "rb") as f:
                    txt = f.read().decode("gbk", errors="replace")
                m = re.search(r'name="([^"]+)"', txt)
                if m: char_name = m.group(1)
            
            bosses = set()
            fights = []
            latest_time = ""
            for f in os.listdir(cl_dir):
                if "百战" not in f or not f.endswith(".jcl"): continue
                m = re.search(r'百战异闻录\(\d+\)-([^(]+)\((\d+)\)\.jcl$', f)
                if m:
                    boss = m.group(1)
                    bosses.add(boss)
                    tm = re.match(r'(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})', f)
                    t = tm.group(1) if tm else None
                    fights.append({"time": t, "boss": boss})
                    if t: latest_time = t
            
            if bosses:
                results[char_name] = {
                    "boss_count": len(fights),
                    "bosses": sorted(bosses),
                    "fights": fights,
                    "last_fight": latest_time
                }
        
        logger.debug(f"Read baizhan data for {len(results)} characters")
        return results
