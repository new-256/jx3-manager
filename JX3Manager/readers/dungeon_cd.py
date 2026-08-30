"""
DungeonCDReader - 副本CD数据
来源: my#data/!all-users@zhcn_hd/userdata/role_statistics/dungeon_stat.v3.db

ID说明 (茗伊内部分类, 非游戏地图ID):
  299 = 武林通鉴·秘境 (每周3个难度)
  482 = 武林通鉴·团队秘境 (每周6个Boss)  
  562 = 百战异闻录 (Boss击杀CD)
  793 = 阆风悬城
  794/795 = 当前赛季25人本
"""
import os, sqlite3, re, json
from logger import get_logger
from readers.baizhan_api import get_week_reset_time, get_this_monday_reset_time

logger = get_logger(__name__)

FORCE_NAMES = {
    0: "大侠", 1: "少林", 2: "万花", 3: "天策", 4: "纯阳", 5: "七秀",
    6: "藏剑", 7: "五毒", 8: "唐门", 9: "明教", 10: "丐帮",
    11: "苍云", 12: "长歌", 13: "霸刀", 14: "蓬莱", 15: "凌雪阁",
    16: "衍天宗", 17: "药宗", 18: "刀宗", 19: "万灵", 20: "段氏",
}

FORCE_CORRECTIONS = {
    0: 0,      # 实测校正: 大侠(0)
    6: 7,      # 实测校正: 五毒(7)
    7: 8,      # 实测校正: 唐门(8)
    9: 10,     # 实测校正: 丐帮(10)
    10: 9,     # 实测校正: 明教(9)
    21: 11,    # 实测校正: 苍云(11)
    22: 12,    # 实测校正: 长歌(12)
    23: 13,    # 实测校正: 霸刀(13)
    24: 14,    # 实测校正: 蓬莱(14)
    25: 15,    # 实测校正: 凌雪阁(15)
    211: 16,   # 实测校正: 衍天宗(16), 子ID+100
    212: 17,   # 实测校正: 药宗(17), 子ID+100
    213: 18,   # 实测校正: 刀宗(18), 子ID+100
    214: 19,   # 实测校正: 万灵(19), 子ID+100
    215: 20,   # 实测校正: 段氏(20), 子ID+100
}

def resolve_force(fid):
    fid = int(fid)
    if fid in FORCE_CORRECTIONS:
        target = FORCE_CORRECTIONS[fid]
        return FORCE_NAMES.get(target, "门派" + str(target))
    if fid > 100:
        base = fid // 10
        return FORCE_NAMES.get(base, "门派" + str(base))
    return FORCE_NAMES.get(fid, "门派" + str(fid))

from readers.dungeon_map import (
    DEFAULT_DUNGEON_NAMES,
    DUNGEON_NAMES_FILE,
    DUNGEON_NAMES,
    load_dungeon_names,
    write_dungeon_names,
    get_dungeon_names,
    learn_dungeon_names,
)

class DungeonCDReader:
    def __init__(self, data_path):
        self.data_path = data_path
    
    def read_all(self):
        # 自动学习战斗日志中的场景名并获取合并映射
        learn_dungeon_names(self.data_path)
        dungeon_names = get_dungeon_names()

        db = os.path.join(self.data_path, "!all-users@zhcn_hd", "userdata", "role_statistics", "dungeon_stat.v3.db")
        if not os.path.exists(db):
            logger.warning(f"Dungeon DB not found: {db}")
            return []
        
        conn = sqlite3.connect(db)
        c = conn.cursor()
        c.execute("SELECT name, server, region, force, level, equip_score, progress_info, copy_info, time FROM DungeonInfo")
        results = []
        reset_time = get_week_reset_time()

        for row in c.fetchall():
            name, server, region, force, level, equip, progress, copy_info = row[0:8]
            rec_time = row[8] if len(row) > 8 and row[8] else 0
            is_stale = rec_time < reset_time if rec_time > 0 else False

            dungeons = {}
            baizhan_boss = None
            unknown_ids = set()
            
            s = progress[1:-1]
            for part in re.split(r',\s*(?=\[)', s):
                m = re.match(r'\[(\d+)\]=\{(.*)\}', part)
                if m:
                    did = int(m.group(1))
                    bosses = [b.strip() for b in m.group(2).split(",")]
                    # 若记录时间早于本周一 12:00，说明该角色本周尚未上线刷新，副本 CD 已被服务端重置，进度清零
                    done = sum(1 for b in bosses if b == "true") if not is_stale else 0
                    total = len(bosses)
                    is_unknown = did not in dungeon_names
                    dname = dungeon_names.get(did, f"副本{did}")
                    if is_unknown:
                        unknown_ids.add(did)
                    
                    if did == 562:
                        baizhan_boss = {"name": dname, "done": done, "total": total, "is_stale": is_stale, "is_unknown": is_unknown}
                    else:
                        dungeons[did] = {"name": dname, "done": done, "total": total, "is_stale": is_stale, "is_unknown": is_unknown}
            
            results.append({
                "name": name, "server": server, "region": region,
                "force": force,
                "force_name": resolve_force(force),
                "level": level, "equip_score": equip,
                "dungeons": dungeons,
                "baizhan_boss": baizhan_boss,
                "unknown_ids": sorted(list(unknown_ids)),
                "record_time": rec_time,
                "is_stale": is_stale
            })
        conn.close()
        logger.debug(f"Read {len(results)} characters' dungeon data")
        return results
