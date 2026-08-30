"""
dungeon_map - 副本 ID 与名称映射管理及 combat_logs 场景名自动学习

自动轮替机制保证:
游戏战斗日志 (jcl) 文件名格式为 YYYY-MM-DD-HH-MM-SS-<场景名>(<场景ID>)-<首领名>(<NPC ID>).jcl。
当游戏更新或开放新副本时，玩家只要进本/打本一次，客户端就会在 userdata/combat_logs 目录下
生成带有正式场景名称和场景 ID 的 .jcl 战斗日志文件。
DungeonCDReader.read_all() 在每次读取副本 CD 时会自动触发 learn_dungeon_names()，
通过扫描战斗日志提取最新的 场景ID -> 场景名 映射，从而实现未来所有新副本的零配置自动识别。
若某个副本 ID 尚未打过且无任何日志，则兜底显示为 '副本{id}'，并在 unknown_ids 中予以标记。

映射合并优先级 (从低到高):
1. DEFAULT_DUNGEON_NAMES: 代码静态兜底表
2. learned_names: 自动学习结果 (仅填补缺失 ID，不覆盖默认/人工已有条目)
3. data/dungeon_names.json: 人工覆盖配置 (优先级最高，用户可任意纠正或自定义名称)
"""
import os
import re
import json
from collections import defaultdict, Counter
from logger import get_logger

logger = get_logger(__name__)

DEFAULT_DUNGEON_NAMES = {
    299: "武林通鉴·秘境",
    301: "武林通鉴·秘境",
    341: "武林通鉴·团队",
    364: "武林通鉴·团队",
    482: "武林通鉴·团队",
    573: "武林通鉴·团队",
    586: "武林通鉴·团队",
    636: "武林通鉴·团队",
    562: "百战异闻录",
    793: "阆风悬城",
    794: "阆风悬城·普通",
    795: "阆风悬城·英雄",
}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DUNGEON_NAMES_FILE = os.path.join(DATA_DIR, "dungeon_names.json")
DUNGEON_NAMES_LEARNED_FILE = os.path.join(DATA_DIR, "dungeon_names_learned.json")

_LEARNED_NAMES = {}
_LAST_MTIME = 0.0
DUNGEON_NAMES = dict(DEFAULT_DUNGEON_NAMES)

LOG_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2})-\d{2}-\d{2}-\d{2}-(.+?)\((\d+)\)-([^(]*)\(\d+\)\.jcl$')


def _load_user_overrides():
    """加载 data/dungeon_names.json 中的人工覆盖配置"""
    if os.path.exists(DUNGEON_NAMES_FILE):
        try:
            with open(DUNGEON_NAMES_FILE, "r", encoding="utf-8") as f:
                user_names = json.load(f)
                if isinstance(user_names, dict):
                    res = {}
                    for k, v in user_names.items():
                        try:
                            res[int(k)] = str(v)
                        except (ValueError, TypeError):
                            res[k] = str(v)
                    return res
        except Exception as e:
            logger.warning(f"Failed to load {DUNGEON_NAMES_FILE}: {e}")
    return {}


def _load_learned_cache():
    """从 data/dungeon_names_learned.json 读取已学习的缓存"""
    global _LEARNED_NAMES, _LAST_MTIME
    if os.path.exists(DUNGEON_NAMES_LEARNED_FILE):
        try:
            with open(DUNGEON_NAMES_LEARNED_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if isinstance(cached, dict):
                    mtime = cached.get("max_mtime", 0.0)
                    names = cached.get("names", {})
                    if isinstance(names, dict):
                        _LEARNED_NAMES = {int(k): str(v) for k, v in names.items()}
                        _LAST_MTIME = float(mtime)
                        return True
        except Exception as e:
            logger.warning(f"Failed to load {DUNGEON_NAMES_LEARNED_FILE}: {e}")
    return False


def get_dungeon_names():
    """
    返回合并后的完整映射 = DEFAULT_DUNGEON_NAMES（静态兜底）
    ← 学习结果（自动，仅填补缺失 ID，不覆盖人工/默认已有条目）
    ← data/dungeon_names.json（人工覆盖，优先级最高）。
    结果缓存在模块级变量 DUNGEON_NAMES。
    """
    global DUNGEON_NAMES, _LEARNED_NAMES

    # 1. 静态兜底
    merged = dict(DEFAULT_DUNGEON_NAMES)

    # 2. 自动学习结果（仅填补 DEFAULT_DUNGEON_NAMES 中没有的 ID）
    if not _LEARNED_NAMES:
        _load_learned_cache()
    for did, name in _LEARNED_NAMES.items():
        if did not in merged:
            merged[did] = name

    # 3. 人工覆盖（最高优先级）
    user_overrides = _load_user_overrides()
    for did, name in user_overrides.items():
        merged[did] = name

    DUNGEON_NAMES.clear()
    DUNGEON_NAMES.update(merged)
    return dict(DUNGEON_NAMES)


def load_dungeon_names():
    """兼容层函数: 返回合并后的副本名称映射"""
    return get_dungeon_names()


def write_dungeon_names(did, name):
    """把新映射写入 dungeon_names.json 并更新全局 DUNGEON_NAMES"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        data = {}
        if os.path.exists(DUNGEON_NAMES_FILE):
            try:
                with open(DUNGEON_NAMES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[str(did)] = str(name)
        with open(DUNGEON_NAMES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        get_dungeon_names()
        return True
    except Exception as e:
        logger.error(f"Failed to write dungeon_names.json: {e}")
        return False


def learn_dungeon_names(my_data_path):
    """
    扫描 my_data_path 下所有账号的 combat_logs 目录中的 .jcl 文件名，
    自动学习 场景ID -> 场景名称 映射。
    具备 mtime 缓存机制，仅在 combat_logs 目录更新时重新扫描。
    """
    global _LEARNED_NAMES, _LAST_MTIME
    if not my_data_path or not os.path.exists(my_data_path):
        if not _LEARNED_NAMES:
            _load_learned_cache()
            get_dungeon_names()
        return dict(_LEARNED_NAMES)

    # 1. 查找所有账号目录下的 combat_logs
    cl_dirs = []
    try:
        for entry in os.scandir(my_data_path):
            if entry.is_dir() and entry.name.endswith("@zhcn_hd"):
                cl_dir = os.path.join(entry.path, "userdata", "combat_logs")
                if os.path.isdir(cl_dir):
                    cl_dirs.append(cl_dir)
    except Exception as e:
        logger.warning(f"Error listing my_data_path {my_data_path}: {e}")

    if not cl_dirs:
        if not _LEARNED_NAMES:
            _load_learned_cache()
            get_dungeon_names()
        return dict(_LEARNED_NAMES)

    # 2. 计算最大 mtime
    max_mtime = 0.0
    for d in cl_dirs:
        try:
            mtime = os.path.getmtime(d)
            if mtime > max_mtime:
                max_mtime = mtime
        except Exception:
            pass

    # 3. 内存缓存命中检查
    if _LAST_MTIME > 0 and max_mtime > 0 and _LAST_MTIME == max_mtime and _LEARNED_NAMES:
        return dict(_LEARNED_NAMES)

    # 4. 文件缓存命中检查
    if os.path.exists(DUNGEON_NAMES_LEARNED_FILE):
        try:
            with open(DUNGEON_NAMES_LEARNED_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if isinstance(cached, dict):
                    cached_mtime = cached.get("max_mtime", 0.0)
                    cached_names = cached.get("names", {})
                    if cached_mtime == max_mtime and max_mtime > 0 and isinstance(cached_names, dict) and cached_names:
                        _LEARNED_NAMES = {int(k): str(v) for k, v in cached_names.items()}
                        _LAST_MTIME = max_mtime
                        get_dungeon_names()
                        logger.debug(f"Loaded {len(_LEARNED_NAMES)} learned dungeon names from cache (mtime={max_mtime})")
                        return dict(_LEARNED_NAMES)
        except Exception as e:
            logger.warning(f"Failed to read {DUNGEON_NAMES_LEARNED_FILE}: {e}")

    # 5. 执行完整扫描
    id_counts = defaultdict(Counter)
    total_files = 0
    for cl_dir in cl_dirs:
        try:
            for entry in os.scandir(cl_dir):
                if entry.is_file() and entry.name.endswith(".jcl"):
                    total_files += 1
                    m = LOG_PATTERN.match(entry.name)
                    if m:
                        scene_name = m.group(2)
                        scene_id = int(m.group(3))
                        id_counts[scene_id][scene_name] += 1
        except Exception as e:
            logger.warning(f"Error scanning combat_logs in {cl_dir}: {e}")

    learned_result = {}
    for did, counter in id_counts.items():
        best_name, _ = counter.most_common(1)[0]
        if len(counter) > 1:
            logger.warning(f"Dungeon ID {did} has conflicting scene names: {dict(counter)}, selected '{best_name}'")
        learned_result[did] = best_name

    _LEARNED_NAMES = learned_result
    _LAST_MTIME = max_mtime
    logger.info(f"Learned {len(_LEARNED_NAMES)} dungeon names from {total_files} combat logs (mtime={max_mtime})")

    # 6. 保存到文件缓存
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(DUNGEON_NAMES_LEARNED_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "max_mtime": max_mtime,
                "names": {str(k): v for k, v in _LEARNED_NAMES.items()}
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save {DUNGEON_NAMES_LEARNED_FILE}: {e}")

    get_dungeon_names()
    return dict(_LEARNED_NAMES)


# 初始化加载
get_dungeon_names()
