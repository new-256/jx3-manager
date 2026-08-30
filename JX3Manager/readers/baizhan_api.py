"""
BaizhanAPI - 百战数据接口
JX3API: https://www.jx3api.com
"""
import requests, json, time, os
from datetime import datetime, timedelta
from logger import get_logger
from config_loader import get_cached_config

logger = get_logger(__name__)

API_BASE = "https://www.jx3api.com"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")

def get_week_reset_time():
    """获取本周一中午 12:00 (剑网3例行维护结束与周刷节点) 的时间戳"""
    now = datetime.now()
    days_since_monday = now.weekday()
    monday = now - timedelta(days=days_since_monday)
    reset_dt = monday.replace(hour=12, minute=0, second=0, microsecond=0)
    # 若当前属于周一 12:00 之前，则当前属于上一周刷周期
    if now < reset_dt:
        reset_dt -= timedelta(days=7)
    return reset_dt.timestamp()

def get_this_monday_reset_time():
    """向后兼容别名：转调 get_week_reset_time()"""
    return get_week_reset_time()

def is_after_this_monday_noon():
    """当前时间是否已过本周一 12:00 周刷维护结束节点"""
    now = datetime.now()
    days_since_monday = now.weekday()
    monday = now - timedelta(days=days_since_monday)
    this_monday_noon = monday.replace(hour=12, minute=0, second=0, microsecond=0)
    return now >= this_monday_noon

def is_after_monday_reset():
    """当前时间是否已过周刷节点"""
    return time.time() >= get_week_reset_time()

class BaizhanAPI:
    def __init__(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        config = get_cached_config()
        self.api_key = config.get("api_key", "").strip()
        self._auto_fetched = set()  # 进程内已自动同步过的文件路径集合
    
    def _get(self, endpoint, params=None):
        if not self.api_key or self.api_key in ("your_api_key_here", ""):
            return {"error": "未配置有效的 JX3API Token，请先在系统配置中填入 API Key"}
        url = f"{API_BASE}{endpoint}"
        p = {"token": self.api_key}
        if params:
            p.update(params)
        try:
            r = requests.get(url, params=p, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get("code") == 200:
                    return data.get("data", {})
                return {"error": data.get("msg", "unknown")}
            return {"error": f"HTTP {r.status_code}"}
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return {"error": str(e)}

    def is_cache_stale(self, cached_data):
        """检查排班/日历/技能等缓存是否跨周失效（同步时间早于本周一 12:00 重置节点）"""
        if not isinstance(cached_data, dict) or not cached_data:
            return True
        sync_str = cached_data.get("_sync_time") or cached_data.get("_fetch_time")
        if sync_str:
            try:
                sync_dt = datetime.strptime(sync_str, "%Y-%m-%d %H:%M:%S")
                return sync_dt.timestamp() < get_week_reset_time()
            except Exception:
                pass
        cached_ts = cached_data.get("_cached")
        if cached_ts:
            try:
                return float(cached_ts) < get_week_reset_time()
            except Exception:
                pass
        return True
    
    def get_weekly_bosses(self, force_refresh=False):
        """获取每周百战排班数据 (默认读本地缓存；若缓存缺失或跨周陈旧且已过周一12:00，进程内自动同步一次)"""
        cache_file = os.path.join(CACHE_DIR, "weekly_bosses.json")
        cached = self._load_cache(cache_file, ignore_age=True)
        
        need_auto_sync = (not cached or self.is_cache_stale(cached)) and is_after_this_monday_noon() and (cache_file not in self._auto_fetched)
        
        if not force_refresh and not need_auto_sync:
            return cached or {}
        
        if need_auto_sync and not force_refresh:
            self._auto_fetched.add(cache_file)
            logger.info("[百战API] 检测到首领排班缓存缺失或跨周陈旧，触发单次自动在线同步...")
        
        data = self._get("/monster/weekly")
        if "error" not in data:
            data["_sync_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save_cache(cache_file, data)
            logger.info(f"[百战API] 首领排班已更新 (第{data.get('week','?')}周)")
            return data
        else:
            logger.warning(f"[百战API] 获取排班数据失败 ({data.get('error', 'unknown')})，回退使用本地缓存")
            return cached or data

    def get_active_calendar(self, force_refresh=False):
        """获取每周活动日历（包含本周武林通鉴轮换副本）(默认读本地缓存；若缓存缺失或跨周陈旧且已过周一12:00，进程内自动同步一次)"""
        cache_file = os.path.join(CACHE_DIR, "active_calendar.json")
        cached = self._load_cache(cache_file, ignore_age=True)
        
        need_auto_sync = (not cached or self.is_cache_stale(cached)) and is_after_this_monday_noon() and (cache_file not in self._auto_fetched)
        
        if not force_refresh and not need_auto_sync:
            return cached or {}
        
        if need_auto_sync and not force_refresh:
            self._auto_fetched.add(cache_file)
            logger.info("[API] 检测到活动日历缓存缺失或跨周陈旧，触发单次自动在线同步...")
        
        data = self._get("/active/calendar")
        if "error" not in data:
            data["_sync_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save_cache(cache_file, data)
            logger.info("[API] 每周活动日历已同步")
            return data
        else:
            logger.warning(f"[API] 获取活动日历失败 ({data.get('error', 'unknown')})，回退使用本地缓存")
            return cached or data
    
    def get_character_skills(self, server, name, force_refresh=False):
        """获取角色百战技能/精耐数据 (默认读本地缓存；若缓存缺失或跨周陈旧且已过周一12:00，进程内自动同步一次)"""
        cache_file = os.path.join(CACHE_DIR, f"char_{server}_{name}.json")
        cached = self._load_cache(cache_file, ignore_age=True)
        
        need_auto_sync = (not cached or self.is_cache_stale(cached)) and is_after_this_monday_noon() and (cache_file not in self._auto_fetched)
        
        if not force_refresh and not need_auto_sync:
            return cached or {}
        
        if need_auto_sync and not force_refresh:
            self._auto_fetched.add(cache_file)
            logger.info(f"[百战API] 检测到角色 [{server}] [{name}] 技能缓存缺失或跨周陈旧，触发单次自动在线同步...")
                
        data = self._get("/monster/records", {"server": server, "name": name})
        if "error" not in data:
            data["_fetch_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if "time" in data:
                try:
                    data["_api_date"] = datetime.fromtimestamp(data["time"]).strftime("%Y-%m-%d")
                except: pass
            self._save_cache(cache_file, data)
            logger.info(f"[百战API] 已更新 [{server}] [{name}] 技能数据")
            return data
        else:
            logger.warning(f"[百战API] 获取角色 [{server}] [{name}] 技能数据失败 ({data.get('error', 'unknown')})，回退使用本地缓存")
            return cached or data
    
    def _load_cache(self, path, ignore_age=False):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if isinstance(cached, dict) and "_cached" in cached and "_sync_time" not in cached:
                    try:
                        cached["_sync_time"] = datetime.fromtimestamp(cached["_cached"]).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception: pass
                if ignore_age:
                    return cached
                monday_noon = get_week_reset_time()
                if cached.get("_cached", 0) >= monday_noon:
                    return cached
            except Exception as e:
                logger.warning(f"Failed to load cache from {path}: {e}")
        return None
    
    def _save_cache(self, path, data):
        data["_cached"] = time.time()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

api = BaizhanAPI()
