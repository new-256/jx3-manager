"""
RoleDataReader - 读取角色基本信息和统计数据
来源: my#data/{uid}@zhcn_hd/userdata/userdata.db (SQLite)
      my#data/{uid}@zhcn_hd/info.jx3dat (明文Lua)
"""
import os, sqlite3, struct, re
from logger import get_logger

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

# Known parent keys for parse boundary detection
PARENT_KEYS = {
    "mentor_score","guid","account_stamina","level","equip_score",
    "role_stamina_remain","prestige","time","role_stamina","justice_remain",
    "force","architecture_remain","server","monster","camp_level",
    "coin","owner","region","money","name","achievement_score",
    "camp_point","contribution_remain","prestige_remain","architecture",
    "starve","pet_score","contribution","justice","account"
}

class RoleDataReader:
    def __init__(self, data_path):
        self.data_path = data_path
    
    def _parse_binary(self, data):
        """Parse MY binary format (t/s/n markers)"""
        def skip_null(p):
            while p < len(data) and data[p] == 0: p += 1
            return p
        
        def read_val(p):
            p = skip_null(p)
            if p >= len(data): return None, p
            b = data[p]; p += 1
            if b == 0x6E:  # number
                v = struct.unpack("<d", data[p:p+8])[0]; p += 8
                return v, p
            elif b == 0x73:  # string
                l = struct.unpack("<H", data[p:p+2])[0]; p += 2
                s = data[p:p+l]; p += l
                try: return s.decode("gbk"), p
                except: return s.hex(), p
            elif b == 0x74:  # table
                tt = data[p]; p += 1; p = skip_null(p)
                if tt in (2, 30):
                    r = {}
                    for _ in range(100 if tt == 2 else 30):
                        p = skip_null(p)
                        if p >= len(data): break
                        nxt = data[p]
                        if nxt == 0x6E:
                            p += 1; v = struct.unpack("<d", data[p:p+8])[0]; p += 8
                            r[len(r)+1] = v
                        elif nxt == 0x73:
                            if tt != 30:  # boundary check for nested
                                pp = p + 1
                                kl = struct.unpack("<H", data[pp:pp+2])[0]; pp += 2
                                pk = data[pp:pp+kl]
                                try: pks = pk.decode("gbk")
                                except: pks = pk.hex()
                                if pks in PARENT_KEYS: break
                            p += 1; kl = struct.unpack("<H", data[p:p+2])[0]; p += 2
                            k = data[p:p+kl].decode("gbk", errors="replace"); p += kl
                            v, p = read_val(p)
                            if k: r[k] = v
                        else:
                            break
                    return r, p
                elif tt == 3:
                    r = {}
                    for _ in range(3):
                        p = skip_null(p)
                        if p >= len(data) or data[p] != 0x73: break
                        k, p = read_val(p); v, p = read_val(p)
                        if k: r[k] = v
                    return r, p
                return {}, p
            return None, p
        
        root, _ = read_val(0)
        return root.get("d", {}) if isinstance(root, dict) else {}
    
    def read_all(self):
        """Read all characters"""
        equip_db = os.path.join(self.data_path, "!all-users@zhcn_hd", "userdata", "role_statistics", "equip_stat.v4.db")
        equip_level_map = {}
        if os.path.exists(equip_db):
            try:
                conn = sqlite3.connect(equip_db)
                c = conn.cursor()
                c.execute("SELECT ownername, servername, ownerlevel FROM OwnerInfo")
                for r in c.fetchall():
                    if r[0] and r[2]:
                        equip_level_map[(r[0], r[1])] = int(r[2])
                conn.close()
            except Exception as e:
                logger.warning(f"Failed to read equip_stat.v4.db: {e}")

        characters = []
        for uid_dir in os.listdir(self.data_path):
            if not uid_dir.endswith("@zhcn_hd"): continue
            uid = uid_dir.split("@")[0]
            if not uid.isdigit(): continue
            
            char_dir = os.path.join(self.data_path, uid_dir)
            
            # Read basic info from info.jx3dat
            info_path = os.path.join(char_dir, "info.jx3dat")
            info = {}
            if os.path.exists(info_path):
                with open(info_path, "rb") as f:
                    txt = f.read().decode("gbk", errors="replace")
                m = re.search(r'name="([^"]+)"', txt)
                if m: info["name"] = m.group(1)
                m = re.search(r'server="([^"]+)"', txt)
                if m: info["server"] = m.group(1)
                m = re.search(r'region="([^"]+)"', txt)
                if m: info["region"] = m.group(1)
            
            # Read stats from userdata.db
            udb = os.path.join(char_dir, "userdata", "userdata.db")
            if os.path.exists(udb):
                conn = sqlite3.connect(udb)
                c = conn.cursor()
                c.execute("SELECT value FROM data WHERE key='MY_RoleStatistics_RoleStat.tAlertTodayVal'")
                row = c.fetchone()
                conn.close()
                
                if row:
                    stats = self._parse_binary(row[0])
                    if stats:
                        force_id = int(stats.get("force", 0))
                        info["force"] = force_id
                        info["force_name"] = resolve_force(force_id)
                        raw_level = int(stats.get("level", 0))
                        equip_score = int(stats.get("equip_score", 0))

                        if raw_level > 10:
                            info["level"] = raw_level
                        elif equip_level_map.get((info.get("name"), info.get("server"))):
                            info["level"] = equip_level_map.get((info.get("name"), info.get("server")))
                        elif equip_score >= 500000:
                            info["level"] = 130
                        elif equip_score >= 100000:
                            info["level"] = 120
                        elif raw_level > 0:
                            info["level"] = raw_level
                        else:
                            info["level"] = 0
                        info["equip_score"] = int(stats.get("equip_score", 0))
                        info["pet_score"] = int(stats.get("pet_score", 0))
                        info["achievement_score"] = int(stats.get("achievement_score", 0))
                        info["contribution"] = int(stats.get("contribution", 0))
                        info["justice"] = int(stats.get("justice", 0))
                        money = stats.get("money", {})
                        info["gold"] = int(money.get("nGold", 0))
            
            # Calculate character local data modification time
            mtimes = []
            if os.path.exists(udb):
                mtimes.append(os.path.getmtime(udb))
            if os.path.exists(info_path):
                mtimes.append(os.path.getmtime(info_path))
            
            if mtimes:
                from datetime import datetime
                info["last_update"] = datetime.fromtimestamp(max(mtimes)).strftime("%Y-%m-%d %H:%M:%S")
            else:
                info["last_update"] = "未知"

            if info.get("name"):
                characters.append(info)
        
        logger.debug(f"Read {len(characters)} characters from {self.data_path}")
        return sorted(characters, key=lambda c: (c.get("region",""), c.get("server",""), c.get("name","")))
