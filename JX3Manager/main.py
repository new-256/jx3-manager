"""
JX3Manager - 剑网3多角色管理器 v0.2
"""
import os, sys, json, datetime
from logger import get_logger
from config_loader import get_cached_config

logger = get_logger(__name__)

# 百战练习场/训练目标，不算真实击杀（剑圣幻影是自由训练的"木桩"目标）
PRACTICE_BOSSES = {"剑圣幻影"}

BOSS_PAIRS = [
    {"钱宗龙", "杜姬欣"},
    {"胡哒", "酷哒"},
    {"阿依努尔", "牡丹"},
]

# 单向异象涵盖字典：ANOMALY_MAP[异象BOSS] = 普通BOSS
# 异象 BOSS (如肖红) 的书只能在肖红产出，不能在肖童产出；但肖童的书可以在肖红处产出。
ANOMALY_MAP = {
    "肖红": "肖童",
    "韦柔丝·困境": "韦柔丝",
}

def get_boss_aliases(bname):
    """返回首领名及其同组/别名集合，用于轮换表与名字的等价匹配。"""
    if not bname:
        return set()

    bname = str(bname).strip()
    if not bname:
        return set()

    aliases = {bname}

    if bname.startswith("恶战") or "恶战" in bname:
        aliases.add("恶战")
        return aliases

    import re
    parts = [p.strip() for p in re.split(r'[/／、·\s]+', bname) if p.strip()]
    for p in parts:
        aliases.add(p)

    for pair in BOSS_PAIRS:
        if any(p in pair for p in parts) or bname in pair:
            aliases.update(pair)
            pair_list = sorted(list(pair))
            aliases.add("/".join(pair_list))
            aliases.add("、".join(pair_list))

    return aliases

def get_floors_for_skill_boss(sboss, boss_floors_map):
    """
    根据招式来源首领 sboss，获取其可以掉落/产出的排班层数列表。

    规则：
    1. 同级双刷 BOSS（如钱宗龙与杜姬欣）：双向涵盖。
    2. 异象与普通 BOSS（如肖红与肖童）：
       - 肖红（异象 BOSS）招式：只能在肖红层数产出，【不能】涵盖肖童层数。
       - 肖童（普通 BOSS）招式：可在肖童层数产出，【亦可在肖红（异象）层数】产出。
    """
    if not sboss:
        return []

    sboss = str(sboss).strip()
    if not sboss:
        return []

    if sboss.startswith("恶战") or "恶战" in sboss:
        return sorted(boss_floors_map.get("恶战", []))

    floors = set(boss_floors_map.get(sboss, []))

    # 1. 检查同级双刷 BOSS
    for pair in BOSS_PAIRS:
        if sboss in pair:
            for p in pair:
                floors.update(boss_floors_map.get(p, []))

    # 2. 检查普通 BOSS 是否能从异象 BOSS 处获得涵盖
    for anomaly_b, base_b in ANOMALY_MAP.items():
        if sboss == base_b:
            floors.update(boss_floors_map.get(anomaly_b, []))

    return sorted(list(floors))

def get_weekly_roster_summary(weekly_bosses, custom_xiuluo_boss=None):
    """获取本周排班首领去重总数与修罗首领名"""
    total = 0
    xiuluo_boss = ""
    if weekly_bosses and isinstance(weekly_bosses, dict):
        seen = set()
        for boss in weekly_bosses.get("list", []):
            bname = boss.get("name", "") if isinstance(boss, dict) else ""
            if bname and bname not in seen:
                seen.add(bname)
        total = len(seen)
        xiuluo_boss = custom_xiuluo_boss.strip() if custom_xiuluo_boss and custom_xiuluo_boss.strip() else weekly_bosses.get("boss", "")
    return total, xiuluo_boss

def compute_baizhan_progress(fights, weekly_bosses, custom_xiuluo_boss=None):
    """计算百战周进度（统一数据契约）。

    fights: BaizhanReader 返回的战斗记录列表，元素为
            {"time": "YYYY-MM-DD-HH-MM-SS" 或 None, "boss": "首领名"}。

    baizhan_progress 契约字段:
      killed           int   本周（周一12:00~下周一12:00）真实击杀的首领数（去重，不含练习目标）
      killed_in_roster int   其中命中本周轮换表名单的数量
      total            int   本周轮换表首领总数（去重）
      xiuluo           bool  镇守（修罗）首领是否已在本周击杀
      killed_bosses    list  本周已击杀首领名（去重，按时间顺序）
      unmatched        list  本周击杀但不在轮换表名单内的首领（用于排查名单缺失）

    返回 dict；本周无击杀或无轮换表数据时返回 None。
    """
    if not weekly_bosses or "list" not in weekly_bosses:
        return None
    if not fights:
        return None

    # 本周时间窗：过滤窗起点 = max(api_start, 本周一12:00)，终点 = api_end 或 (start + 7天)
    from readers.baizhan_api import get_week_reset_time
    monday_reset_dt = datetime.datetime.fromtimestamp(get_week_reset_time())

    start_ts = weekly_bosses.get("start")
    end_ts = weekly_bosses.get("end")
    if start_ts:
        api_start = datetime.datetime.fromtimestamp(start_ts)
        start = max(api_start, monday_reset_dt)
    else:
        start = monday_reset_dt

    if end_ts:
        api_end = datetime.datetime.fromtimestamp(end_ts)
        end = max(api_end, start + datetime.timedelta(days=7))
    else:
        end = start + datetime.timedelta(days=7)

    roster = []  # 去重后的本周首领名单（保持轮换表顺序）
    roster_aliases = set()
    seen = set()
    for boss in weekly_bosses["list"]:
        bname = boss.get("name", "")
        if bname and bname not in seen:
            seen.add(bname)
            roster.append(bname)
            roster_aliases.update(get_boss_aliases(bname))

    killed_names = set()
    killed_order = []
    for fight in sorted(fights, key=lambda x: x.get("time") or ""):
        boss = fight.get("boss", "")
        if not boss or boss in PRACTICE_BOSSES:
            continue
        t_raw = fight.get("time")
        if not t_raw:
            continue  # 无时间信息的历史记录不计入本周
        try:
            t = datetime.datetime.strptime(t_raw[:19], "%Y-%m-%d-%H-%M-%S")
        except ValueError:
            logger.debug(f"Invalid time format skipped: {t_raw}")
            continue
        if t < start or t > end:
            continue
        if boss not in killed_names:
            killed_names.add(boss)
            killed_order.append(boss)

    if not killed_names:
        return None

    killed_in_roster = [b for b in killed_order if (b in roster or any(a in roster_aliases for a in get_boss_aliases(b)))]
    xiuluo_boss = custom_xiuluo_boss.strip() if custom_xiuluo_boss and custom_xiuluo_boss.strip() else weekly_bosses.get("boss", "")
    
    is_xiuluo_killed = False
    if xiuluo_boss:
        targets = [t.strip() for t in xiuluo_boss.replace("／", "/").split("/") if t.strip()]
        for target in targets:
            clean_target = target.split("·")[0].strip()
            for b in killed_names:
                clean_b = b.split("·")[0].strip()
                if clean_target == clean_b or target in b or b in target:
                    is_xiuluo_killed = True
                    break
            if is_xiuluo_killed:
                break

    return {
        "killed": len(killed_order),
        "killed_in_roster": len(killed_in_roster),
        "total": len(roster),
        "xiuluo": is_xiuluo_killed,
        "xiuluo_boss": xiuluo_boss,
        "killed_bosses": killed_order,
        "unmatched": [b for b in killed_order if b not in roster],
    }

def normalize_char_name(raw_name):
    """清理角色名中的服务器/称号后缀（如 角色名·服务器名 -> 角色名，角色名@服务器 -> 角色名）"""
    if not raw_name:
        return ""
    return raw_name.split("·")[0].split("@")[0].strip()

def find_char_key(char_dict, raw_name):
    if not raw_name or not isinstance(raw_name, str):
        return None
    if raw_name in char_dict:
        return raw_name
    clean = normalize_char_name(raw_name)
    if not clean:
        return None
    if clean in char_dict:
        return clean
    for k in char_dict.keys():
        if k and normalize_char_name(k) == clean:
            return k
    return None

XIULUO_OVERRIDE_PATH = os.path.join(os.path.dirname(__file__), "data", "xiuluo_override.json")

def load_xiuluo_override():
    if os.path.exists(XIULUO_OVERRIDE_PATH):
        try:
            with open(XIULUO_OVERRIDE_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d.get("custom_boss", "")
        except Exception as e:
            logger.error(f"Failed to load xiuluo_override.json: {e}")
    return ""

def save_xiuluo_override(boss_name):
    try:
        os.makedirs(os.path.dirname(XIULUO_OVERRIDE_PATH), exist_ok=True)
        with open(XIULUO_OVERRIDE_PATH, "w", encoding="utf-8") as f:
            json.dump({"custom_boss": boss_name}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save xiuluo_override.json: {e}")
        return False

def filter_cd_dungeon_ids(sorted_dids, dungeon_names=None, raid_names=None, show_legacy=False):
    """
    根据本周周常日历 raid 名单过滤副本列。
    
    参数:
      sorted_dids: list[int] 副本 ID 列表
      dungeon_names: dict[int, str] 副本 ID 到副本名称的映射（若为 None 则默认使用 DUNGEON_NAMES）
      raid_names: list[str] 本周武林通鉴/周常 raid 名单（如 ["阆风悬城", "冰火岛·荒血路", "白帝江关"]）
      show_legacy: bool 是否显示过气副本（若 True 则不作过滤全部返回）
      
    返回:
      (visible_dids, hidden_dids): tuple[list[int], list[int]]
    """
    if dungeon_names is None:
        try:
            from readers.dungeon_cd import DUNGEON_NAMES
            dungeon_names = DUNGEON_NAMES
        except Exception:
            dungeon_names = {}

    # 过滤掉 562（百战异闻录，不属于普通副本 CD 列）
    clean_dids = [did for did in sorted_dids if did != 562]

    if show_legacy:
        return list(clean_dids), []

    raid_names = raid_names or []
    PREFIXES = ["25人普通", "25人英雄", "10人普通", "10人英雄", "25人挑战", "10人挑战", "25人", "10人", "普通", "英雄", "挑战", "试炼"]

    def _clean_pfx(name_str):
        s = str(name_str).strip()
        for pfx in PREFIXES:
            if s.startswith(pfx):
                s = s[len(pfx):].strip()
                break
        return s.strip("·_ ")

    cleaned_raids = []
    for r in raid_names:
        if r and isinstance(r, str):
            cr = _clean_pfx(r)
            if cr:
                cleaned_raids.append((r.strip(), cr))

    visible_dids = []
    hidden_dids = []

    for did in clean_dids:
        dname = dungeon_names.get(did, f"副本{did}")
        
        # 1. 武林通鉴开头的副本列始终保留
        if dname.startswith("武林通鉴"):
            visible_dids.append(did)
            continue

        # 2. 与 raid_names 匹配
        clean_d = _clean_pfx(dname)
        is_matched = False
        for raw_r, cr in cleaned_raids:
            if (cr in dname or dname in cr or 
                cr in clean_d or clean_d in cr or
                dname.startswith(cr) or raw_r.startswith(dname) or
                clean_d.startswith(cr) or cr.startswith(clean_d) or
                raw_r in dname or dname in raw_r):
                is_matched = True
                break

        if is_matched:
            visible_dids.append(did)
        else:
            hidden_dids.append(did)

    return visible_dids, hidden_dids

HUANJIANG_PATH = os.path.join(os.path.dirname(__file__), "data", "huanjiang_points.json")

def load_huanjiang_points_full():
    """
    加载换将点数完整数据结构（含填入时间戳）。
    返回格式: {"角色名": {"points": int, "updated_at": str|None}}
    完全向后兼容旧格式（值为 int 时自动适配 points=该值, updated_at=None）。
    """
    if os.path.exists(HUANJIANG_PATH):
        try:
            with open(HUANJIANG_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    res = {}
                    for k, v in raw.items():
                        if isinstance(v, dict):
                            try:
                                pts = int(v.get("points", 0))
                            except (ValueError, TypeError):
                                pts = 0
                            up = v.get("updated_at")
                            res[k] = {"points": pts, "updated_at": str(up) if up else None}
                        elif isinstance(v, (int, float, str)):
                            try:
                                pts = int(v)
                            except (ValueError, TypeError):
                                pts = 0
                            res[k] = {"points": pts, "updated_at": None}
                        else:
                            res[k] = {"points": 0, "updated_at": None}
                    return res
        except Exception as e:
            logger.error(f"Failed to load huanjiang_points.json: {e}")
    return {}

def load_huanjiang_points():
    """
    加载换将点数兼容字典（旧形态调用）。
    返回格式: {"角色名": points_int}
    """
    full = load_huanjiang_points_full()
    return {k: v["points"] for k, v in full.items()}

def save_huanjiang_points(data_dict):
    """
    保存换将点数到 JSON 文件。
    接受旧形态 {name: points_int} 或新形态 {name: {"points": int, "updated_at": ...}}，
    旧形态自动补齐 updated_at=写入时刻 并规范化写入新格式。
    """
    try:
        os.makedirs(os.path.dirname(HUANJIANG_PATH), exist_ok=True)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        normalized = {}
        for k, v in (data_dict or {}).items():
            if isinstance(v, dict):
                try:
                    pts = int(v.get("points", 0))
                except (ValueError, TypeError):
                    pts = 0
                up = v.get("updated_at")
                normalized[k] = {"points": pts, "updated_at": str(up) if up else None}
            elif isinstance(v, (int, float, str)):
                try:
                    pts = int(v)
                except (ValueError, TypeError):
                    pts = 0
                normalized[k] = {"points": pts, "updated_at": now_str}
            else:
                normalized[k] = {"points": 0, "updated_at": None}
        with open(HUANJIANG_PATH, "w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save huanjiang_points.json: {e}")
        return False

class JX3Manager:
    def __init__(self, game_path=None):
        config = get_cached_config()
        self.game_path = game_path or config["game_path"]
        self.my_data = os.path.join(self.game_path, "my#data")
        self.characters = {}
        self.weekly_bosses = None
        self.custom_xiuluo_boss = None
        self.active_calendar = None

    def update_custom_xiuluo_boss(self, new_boss_name):
        self.custom_xiuluo_boss = new_boss_name
        save_xiuluo_override(new_boss_name)
        if self.weekly_bosses:
            roster_total, roster_xiuluo = get_weekly_roster_summary(self.weekly_bosses, self.custom_xiuluo_boss)
            for c in self.characters.values():
                bz = c.get("baizhan_boss")
                fights = bz.get("fights", []) if isinstance(bz, dict) else (bz if isinstance(bz, list) else [])
                progress = compute_baizhan_progress(fights, self.weekly_bosses, custom_xiuluo_boss=self.custom_xiuluo_boss)
                if progress:
                    c["baizhan_progress"] = progress
                elif bz:
                    c["baizhan_progress"] = {
                        "killed": 0,
                        "killed_in_roster": 0,
                        "total": roster_total,
                        "xiuluo": False,
                        "killed_bosses": [],
                        "unmatched": [],
                        "xiuluo_boss": roster_xiuluo,
                    }

    def update_huanjiang_points(self, char_name, points):
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hj_full = load_huanjiang_points_full()
        try:
            pts_int = int(points)
        except (ValueError, TypeError):
            pts_int = 0
        hj_full[char_name] = {"points": pts_int, "updated_at": now_str}
        save_huanjiang_points(hj_full)
        if char_name in self.characters:
            self.characters[char_name]["huanjiang_points"] = pts_int
            self.characters[char_name]["huanjiang_updated_at"] = now_str
    
    def load_all(self):
        old_chars = dict(self.characters)  # Save for preserving API data
        from readers.role_data import RoleDataReader
        from readers.dungeon_cd import DungeonCDReader
        from readers.baizhan import BaizhanReader
        from readers.baizhan_skill import BaizhanSkillReader
        from readers.baizhan_api import api as bz_api
        
        logger.info("Loading role data...")
        role_reader = RoleDataReader(self.my_data)
        chars = role_reader.read_all()
        for c in chars:
            clean_name = normalize_char_name(c["name"])
            c["name"] = clean_name
            self.characters[clean_name] = c
        
        logger.info("Loading dungeon CD...")
        cd_reader = DungeonCDReader(self.my_data)
        cd_data = cd_reader.read_all()
        for cd in cd_data:
            raw_name = cd["name"]
            target_key = find_char_key(self.characters, raw_name)
            if target_key:
                c = self.characters[target_key]
                c["dungeon_cd"] = cd.get("dungeons", {})
                c["is_stale"] = cd.get("is_stale", False)
                c["record_time"] = cd.get("record_time", 0)
                if cd.get("level", 0) > 0 and (c.get("level", 0) <= 10 or cd["level"] > c.get("level", 0)):
                    c["level"] = cd["level"]
                if cd.get("force_name") and not c.get("force_name"):
                    c["force_name"] = cd["force_name"]
                if cd.get("region") and not c.get("region"):
                    c["region"] = cd["region"]
                if cd.get("server") and not c.get("server"):
                    c["server"] = cd["server"]
            else:
                clean_name = normalize_char_name(raw_name)
                cd["name"] = clean_name
                self.characters[clean_name] = cd
        
        logger.info("Loading baizhan boss kills...")
        bz_reader = BaizhanReader(self.my_data)
        bz_data = bz_reader.read_all()
        for raw_name, bz_info in bz_data.items():
            target_key = find_char_key(self.characters, raw_name)
            if target_key:
                self.characters[target_key]["baizhan_boss"] = bz_info
        
        logger.info("Loading baizhan skills...")
        skill_reader = BaizhanSkillReader(self.my_data)
        skill_data = skill_reader.read_all()
        for raw_name, skills in skill_data.items():
            target_key = find_char_key(self.characters, raw_name)
            if target_key:
                self.characters[target_key]["baizhan_skills"] = skills

        logger.info("Loading huanjiang points...")
        hj_full = load_huanjiang_points_full()
        for name, c in self.characters.items():
            c_hj = hj_full.get(name)
            if c_hj:
                c["huanjiang_points"] = c_hj.get("points", 0)
                c["huanjiang_updated_at"] = c_hj.get("updated_at")
            else:
                c["huanjiang_points"] = 0
                c["huanjiang_updated_at"] = None
        
        logger.info("Loading weekly boss roster (local cache only)...")
        self.weekly_bosses = bz_api.get_weekly_bosses(force_refresh=False)
        if "error" not in self.weekly_bosses and self.weekly_bosses:
            w = self.weekly_bosses.get("week", "?")
            logger.info(f"  Weekly bosses loaded from cache (week {w})")
            if bz_api.is_cache_stale(self.weekly_bosses):
                logger.warning(f"  [警告] 百战排班本地缓存可能已跨周陈旧(第{w}周)，修罗/击杀进度建议在线刷新最新排班！")

        logger.info("Loading weekly active calendar (local cache only)...")
        self.active_calendar = bz_api.get_active_calendar(force_refresh=False)

        logger.info("Loading custom xiuluo boss override...")
        self.custom_xiuluo_boss = load_xiuluo_override()
        
        # Calculate 百战 progress (0-100 vs 修罗)
        roster_total, roster_xiuluo = get_weekly_roster_summary(self.weekly_bosses, self.custom_xiuluo_boss)
        for name, c in self.characters.items():
            bz = c.get("baizhan_boss")
            fights = bz.get("fights", []) if isinstance(bz, dict) else (bz if isinstance(bz, list) else [])
            progress = compute_baizhan_progress(fights, self.weekly_bosses, custom_xiuluo_boss=self.custom_xiuluo_boss)
            if progress:
                c["baizhan_progress"] = progress
            elif bz:
                c["baizhan_progress"] = {
                    "killed": 0,
                    "killed_in_roster": 0,
                    "total": roster_total,
                    "xiuluo": False,
                    "killed_bosses": [],
                    "unmatched": [],
                    "xiuluo_boss": roster_xiuluo,
                }
        
        logger.info("Loading character notes...")
        from readers.char_notes import CharNotesManager
        self.notes_mgr = CharNotesManager()
        for name, c in self.characters.items():
            perm, weekly = self.notes_mgr.get_note(name)
            c["perm_note"] = perm
            c["weekly_note"] = weekly

        # Load disk-cached baizhan API data
        for name, c in self.characters.items():
            old_c = old_chars.get(name, {})
            if old_c.get("baizhan_api"):
                c["baizhan_api"] = old_c["baizhan_api"]
            else:
                server = c.get("server", "")
                if server:
                    cached_api = bz_api.get_character_skills(server, name, force_refresh=False)
                    if cached_api and "error" not in cached_api:
                        c["baizhan_api"] = cached_api

        logger.info(f"Loaded {len(self.characters)} characters")
        return self.characters

    def fetch_active_calendar(self, force_refresh=True):
        from readers.baizhan_api import api as bz_api
        self.active_calendar = bz_api.get_active_calendar(force_refresh=force_refresh)
        return self.active_calendar

    def fetch_weekly_bosses(self, force_refresh=True):
        from readers.baizhan_api import api as bz_api
        self.weekly_bosses = bz_api.get_weekly_bosses(force_refresh=force_refresh)
        return self.weekly_bosses
    
    def fetch_baizhan_info(self, name, force_refresh=True):
        """Fetch 百战 info for one character from API (force_refresh=True)"""
        c = self.characters.get(name, {})
        if not c:
            return {"error": "角色未找到"}
        
        server = c.get("server", "")
        if not server:
            return {"error": "无区服信息"}
        
        from readers.baizhan_api import api as bz_api
        data = bz_api.get_character_skills(server, name, force_refresh=force_refresh)
        
        if "error" not in data:
            c["baizhan_api"] = data
            self.characters[name] = c
        
        return data
    
    def export_json(self, path=None):
        if not path:
            path = os.path.join(os.path.dirname(__file__), "data", "export.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "characters": list(self.characters.values()),
            "export_time": __import__("datetime").datetime.now().isoformat()
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Exported JSON to {path}")
        return path

if __name__ == "__main__":
    mgr = JX3Manager()
    mgr.load_all()
