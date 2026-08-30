"""
JX3Manager v3.0 - Eel + Modern Web UI
"""
import eel, os, sys, json, threading, time
from logger import get_logger

logger = get_logger(__name__)

sys.path.insert(0, os.path.dirname(__file__))
from main import JX3Manager
from readers.plugin_settings import enable_all_stats
from config_loader import validate_config, get_cached_config

config_errors = validate_config(get_cached_config())
if config_errors:
    logger.error(f"Configuration is missing or invalid: {config_errors}. Please run gui_qt.py first to setup or edit config.json.")
    sys.exit(1)

mgr = JX3Manager()

# Load skill icon mapping
ICON_MAP = {}
_icon_path = os.path.join(os.path.dirname(__file__), "data", "skill_icons.json")
if os.path.exists(_icon_path):
    with open(_icon_path, "r", encoding="utf-8") as f:
        ICON_MAP = json.load(f)


# Load JX3Box skill metadata
SKILL_META = {}
_meta_path = os.path.join(os.path.dirname(__file__), "data", "bz_skill_meta.json")
if os.path.exists(_meta_path):
    with open(_meta_path, "r", encoding="utf-8") as f:
        SKILL_META = json.load(f).get("skills", {})


# Load skill descriptions
SKILL_DESC = {}
_desc_path = os.path.join(os.path.dirname(__file__), "data", "bz_skill_desc.json")
if os.path.exists(_desc_path):
    with open(_desc_path, "r", encoding="utf-8") as f:
        SKILL_DESC = json.load(f)

def get_skill_desc(name):
    return SKILL_DESC.get(name, {})

def get_skill_meta(name):
    return SKILL_META.get(name, {})

def get_icon_url(name):
    if name in ICON_MAP:
        safe = name.replace("/", "_").replace("\\", "_") + ".png"
        return "icons/" + safe
    return ""


CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "bz_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def _cache_path(name):
    safe = name.replace("/", "_").replace(chr(92), "_")
    return os.path.join(CACHE_DIR, f"{safe}.json")

def _load_cache(name):
    p = _cache_path(name)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache for {name}: {e}")
    return None

def _save_cache(name, data):
    data["_cached_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(_cache_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@eel.expose
def load_cached_bz(name):
    """加载缓存的百战数据"""
    return _load_cache(name) or {}

@eel.expose
def refresh_data():
    logger.info("Web UI: Refreshing data...")
    mgr.load_all()
    chars = []
    for c in sorted(mgr.characters.values(), key=lambda x: (x.get("region",""), x.get("server",""), x.get("name",""))):
        prog = c.get("baizhan_progress", {})
        bz_api = c.get("baizhan_api", {})
        cd = c.get("dungeon_cd", {})
        chars.append({
            "name": c.get("name","?"),
            "region": c.get("region",""),
            "server": c.get("server",""),
            "force": c.get("force_name","?"),
            "level": c.get("level","?"),
            "equip": c.get("equip_score",0),
            "gold": c.get("gold",0),
            "contribution": c.get("contribution",0),
            "justice": c.get("justice",0),
            "pet": c.get("pet_score",0),
            "achievement": c.get("achievement_score",0),
            "bz_progress": {
                "killed": prog.get("killed",0),
                "total": prog.get("total",100),
                "xiuluo": prog.get("xiuluo", False),
                "bosses": prog.get("killed_bosses",[])
            } if prog else None,
            "bz_api": {
                "stamina": bz_api.get("skillStamina",0),
                "energy": bz_api.get("skillEnergy",0),
                "skill_count": bz_api.get("skillCount",0),
                "skills": [{"name":s.get("szSkillName","?"),"level":s.get("nLevel",0),"boss":s.get("szBossName",""),"color":s.get("nColor",0),"icon_id":s.get("dwOutSkillID",0),"type":s.get("szType",""),"icon_url":get_icon_url(s.get("szSkillName","")),"meta":get_skill_meta(s.get("szSkillName","")),"desc":get_skill_desc(s.get("szSkillName",""))} for s in sorted(bz_api.get("skillList",[]), key=lambda x:-x.get("nLevel",0))]
            } if bz_api.get("skillStamina") else None,
            "dungeons": {str(k): v for k,v in cd.items()}
        })
    
    weekly = mgr.weekly_bosses or {}
    from readers.baizhan_api import api as bz_api
    is_stale = bz_api.is_cache_stale(weekly)
    logger.info(f"Web UI: Refreshed {len(chars)} characters (stale_cache={is_stale})")
    return {
        "characters": chars,
        "weekly": {
            "week": weekly.get("week","?"),
            "boss_count": len(weekly.get("list",[])),
            "is_stale": is_stale,
            "stale_warning": f"当前百战排班为跨周离线旧缓存(第{weekly.get('week','?')}周)，击杀与修罗计算可能受影响，建议点击‘强制在线刷新’！" if is_stale else None
        }
    }

@eel.expose
def fetch_baizhan(name):
    logger.info(f"Web UI: Fetching baizhan for {name}")
    data = mgr.fetch_baizhan_info(name)
    if "error" in data:
        logger.warning(f"Fetch baizhan failed for {name}: {data['error']}")
        return {"error": data["error"]}
    skills = [{"name":s.get("szSkillName","?"),"level":s.get("nLevel",0),"boss":s.get("szBossName",""),"color":s.get("nColor",0),"icon_id":s.get("dwOutSkillID",0),"type":s.get("szType",""),"icon_url":get_icon_url(s.get("szSkillName","")),"meta":get_skill_meta(s.get("szSkillName","")),"desc":get_skill_desc(s.get("szSkillName",""))} for s in sorted(data.get("skillList",[]), key=lambda x:-x.get("nLevel",0))]
    result = {
        "stamina": data.get("skillStamina",0),
        "energy": data.get("skillEnergy",0),
        "skill_count": data.get("skillCount",0),
        "skills": skills
    }
    _save_cache(name, result)
    logger.info(f"Baizhan data fetched for {name}: {len(skills)} skills")
    return result

@eel.expose
def enable_stats(name):
    import re
    uid = None
    for d in os.listdir(mgr.my_data):
        if not d.endswith("@zhcn_hd"): continue
        ip = os.path.join(mgr.my_data, d, "info.jx3dat")
        if os.path.exists(ip):
            with open(ip,"rb") as f: txt = f.read().decode("gbk",errors="replace")
            m = re.search(r'name="([^"]+)"', txt)
            if m and m.group(1) == name: uid = d.split("@")[0]; break
    if not uid: 
        logger.warning(f"UID not found for character {name}")
        return {"error": "UID not found"}
    ok, msg = enable_all_stats(mgr.my_data, uid)
    logger.info(f"Enable stats for {name} (uid={uid}): {msg}")
    return {"ok": ok, "msg": msg}

@eel.expose
def export_json():
    path = mgr.export_json()
    logger.info(f"Exported JSON: {path}")
    return path

if __name__ == "__main__":
    web_dir = os.path.join(os.path.dirname(__file__), "web")
    index_file = os.path.join(web_dir, "index.html")
    if not os.path.exists(index_file):
        logger.error(f"Web UI entry file missing: {index_file}. Please ensure 'web/index.html' exists.")
        sys.exit(1)
    
    logger.info("Starting Web UI...")
    eel.init('web')
    eel.start('index.html', size=(1400, 850), port=0)
