"""
JX3Manager - 百战核心招式分类映射模块
提供核心技能分类（打精/打耐/回复 各CD档位与自定义分类）的推导、加载、保存与候选招式等级匹配逻辑。
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# 7 个标准档位定义元组: (group, window)，用于“恢复默认”及推导基准
CORE_CATEGORY_SLOTS: List[Tuple[str, str]] = [
    ("打精", "1分钟"),
    ("打精", "30S"),
    ("打精", "10S"),
    ("打耐", "1分钟"),
    ("打耐", "30S"),
    ("打耐", "10S"),
    ("回复", "核心"),
]


def get_data_dir() -> str:
    """获取 JX3Manager 的 data 目录绝对路径"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def get_core_skills_config_path() -> str:
    """获取 bz_core_skills.json 配置文件路径"""
    return os.path.join(get_data_dir(), "bz_core_skills.json")


def _find_data_file(filename: str, explicit_path: Optional[str] = None) -> Optional[str]:
    """在多个候选路径中查找数据文件"""
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path
    
    candidates = [
        os.path.join(get_data_dir(), filename),
        os.path.join(os.path.dirname(get_data_dir()), "data", filename),
        os.path.join(os.path.dirname(os.path.dirname(get_data_dir())), "data", filename),
        os.path.join("data", filename),
        os.path.join("JX3Manager", "data", filename),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


# 招式级别 -> CD 档位映射（暂定规则：1级=10S, 2级=30S, 3级=60S）
SKILL_LEVEL_WINDOW: Dict[int, str] = {
    1: "10S",
    2: "30S",
    3: "1分钟",
}


def get_skill_levels(meta_path: Optional[str] = None) -> Dict[str, int]:
    """
    从 bz_skill_meta.json 的 dbm_note 解析招式级别 {招式名: 级别}。

    dbm_note 形如 '绿 消耗点数：1  1级' / '紫 消耗点数：1  2级'，
    末尾的 'N级' 即招式级别。部分条目无级别标注（形如 ' 消耗点数：1 '），
    这类返回中不含该招式。

    实测 156 个招式中 61 个可解析出级别（1级31个 / 2级21个 / 3级9个）。
    """
    actual = _find_data_file("bz_skill_meta.json", meta_path)
    levels: Dict[str, int] = {}
    if not actual or not os.path.exists(actual):
        return levels
    try:
        with open(actual, "r", encoding="utf-8") as f:
            data = json.load(f)
        skills = data.get("skills", {}) if isinstance(data, dict) else {}
        for name, info in skills.items():
            if not isinstance(info, dict):
                continue
            note = info.get("dbm_note") or ""
            m = re.search(r"(\d+)\s*级", note)
            if m:
                try:
                    levels[name] = int(m.group(1))
                except (ValueError, TypeError):
                    continue
    except Exception as e:
        logger.warning(f"读取 bz_skill_meta.json 失败: {e}")
    return levels


def get_skill_costs(meta_path: Optional[str] = None) -> Dict[str, int]:
    """
    从 bz_skill_meta.json 解析招式消耗点数 {招式名: 点数}。

    消耗点数 = 该招式占用的技能格数量。百战玩法最多 3 个技能槽位，
    即携带招式的点数合计不能超过 3。实测分布：1点 91个 / 2点 8个 / 3点 3个。

    该字段与招式级别（CD 档位）是两个独立维度，用于配置界面的独立筛选。
    """
    actual = _find_data_file("bz_skill_meta.json", meta_path)
    costs: Dict[str, int] = {}
    if not actual or not os.path.exists(actual):
        return costs
    try:
        with open(actual, "r", encoding="utf-8") as f:
            data = json.load(f)
        skills = data.get("skills", {}) if isinstance(data, dict) else {}
        for name, info in skills.items():
            if not isinstance(info, dict):
                continue
            cost = info.get("dbm_cost")
            if cost is None:
                continue
            try:
                costs[name] = int(cost)
            except (ValueError, TypeError):
                continue
    except Exception as e:
        logger.warning(f"读取 bz_skill_meta.json 消耗点数失败: {e}")
    return costs


def get_verified_cooldowns(
    enriched_path: Optional[str] = None,
    skills_path: Optional[str] = None
) -> Dict[str, int]:
    """
    返回【经 ID 校验确认可信】的招式冷却表 {招式名: 冷却秒数}。

    baizhan_skills_enriched.json 的冷却是早期按“招式名”去通用技能库匹配得到的，
    而大量百战招式与门派/其他技能重名，匹配到了错误的技能。
    此处用 baizhan_skills.json 的权威 id / in_id 反查校验：
    只有 enriched 的 dwID 与本地 id 或 in_id 对得上，其冷却才采信。
    实测 156 个招式中仅 12 个通过校验。
    """
    actual_enriched = _find_data_file("baizhan_skills_enriched.json", enriched_path)
    actual_skills = _find_data_file("baizhan_skills.json", skills_path)

    enriched: Dict[str, Dict[str, Any]] = {}
    if actual_enriched and os.path.exists(actual_enriched):
        try:
            with open(actual_enriched, "r", encoding="utf-8") as f:
                data = json.load(f)
                enriched = data.get("skills", {}) if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"读取 baizhan_skills_enriched.json 失败: {e}")

    id_map: Dict[str, Tuple[Any, Any]] = {}
    if actual_skills and os.path.exists(actual_skills):
        try:
            with open(actual_skills, "r", encoding="utf-8") as f:
                data = json.load(f)
                for s in (data.get("skills") or []):
                    if isinstance(s, dict) and s.get("name"):
                        id_map[s["name"]] = (s.get("id"), s.get("in_id"))
        except Exception as e:
            logger.warning(f"读取 baizhan_skills.json 失败: {e}")

    verified: Dict[str, int] = {}
    for name, info in enriched.items():
        if not isinstance(info, dict):
            continue
        cd = info.get("cooldown")
        if cd is None:
            continue
        ids = id_map.get(name)
        if not ids:
            continue
        if info.get("dwID") in ids:
            try:
                verified[name] = int(cd)
            except (ValueError, TypeError):
                continue
    return verified


def derive_core_skill_categories(
    desc_path: Optional[str] = None,
    enriched_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    从 bz_skill_desc.json (招式描述) 自动推导核心招式分类。

    分类规则（打击类型，来自招式描述，可信）：
      - 描述含 '精神打击' -> 打精
      - 描述含 '耐力打击' -> 打耐
      - 描述含 '恢复' 且 ('气血' or '精神' or '耐力') -> 回复

    档位规则（按 bz_skill_meta.json 的 dbm_note 中的 N级，级别是权威数据）：
      - 1级 -> 10S  档
      - 2级 -> 30S  档
      - 3级 -> 1分钟 档
      - 无级别 -> 10S 档（待用户手动划分）
      - 回复类统一归入 '核心' 档
      - 候选按招式名排序；默认补全 enabled=True, display_count=1

    覆盖统计：156 个招式中 61 个有级别，95 个无级别（默认归 10S 档）。
    冷却数据（enriched、验证冷却）因早期按名称匹配通用技能库、仅 8% 可信，
    已不作为分档依据。
    """
    actual_desc_path = _find_data_file("bz_skill_desc.json", desc_path)

    descs: Dict[str, Dict[str, Any]] = {}
    if actual_desc_path and os.path.exists(actual_desc_path):
        try:
            with open(actual_desc_path, "r", encoding="utf-8") as f:
                descs = json.load(f)
        except Exception as e:
            logger.warning(f"读取 bz_skill_desc.json 失败: {e}")

    lv = get_skill_levels()

    def window_for(name: str) -> str:
        """按级别分档，无级别归 10S"""
        level = lv.get(name)
        if level is not None:
            return SKILL_LEVEL_WINDOW.get(level, "10S")
        return "10S"

    buckets: Dict[Tuple[str, str], List[str]] = {slot: [] for slot in CORE_CATEGORY_SLOTS}

    for name, info in descs.items():
        if not isinstance(info, dict):
            continue
        detail = info.get("detail", "")
        if not detail:
            continue

        if "精神打击" in detail:
            buckets[("打精", "10S")].append(name)  # placeholder, 下面按档位重新分配
        if "耐力打击" in detail:
            buckets[("打耐", "10S")].append(name)
        if "恢复" in detail and ("气血" in detail or "精神" in detail or "耐力" in detail):
            buckets[("回复", "核心")].append(name)

    # 按档位重新分配 打精/打耐
    for grp in ("打精", "打耐"):
        all_names = list(buckets[(grp, "10S")])
        buckets[(grp, "10S")] = []
        buckets[(grp, "30S")] = []
        buckets[(grp, "1分钟")] = []
        for name in all_names:
            win = window_for(name)
            buckets[(grp, win)].append(name)

    for lst in buckets.values():
        lst.sort()

    category_map = buckets

    return [
        {
            "group": grp,
            "window": win,
            "candidates": category_map.get((grp, win), []),
            "enabled": True,
            "display_count": 1,
        }
        for grp, win in CORE_CATEGORY_SLOTS
    ]


def load_core_skill_categories(config_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    加载核心技能分类映射配置。
    若配置文件不存在、格式损坏或 categories 列表为空，则自动推导兜底。
    支持任意数量和名称的分类；每档确保包含 group, window, candidates, enabled, display_count 字段。
    """
    path = config_path or get_core_skills_config_path()
    
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            raw_cats = data.get("categories", [])
            if isinstance(raw_cats, list) and len(raw_cats) > 0:
                result = []
                for item in raw_cats:
                    if isinstance(item, dict):
                        g = str(item.get("group", "")).strip()
                        w = str(item.get("window", "")).strip()
                        c = item.get("candidates", [])
                        if not isinstance(c, list):
                            c = []
                        enabled = item.get("enabled", True)
                        if not isinstance(enabled, bool):
                            enabled = True
                        display_count = item.get("display_count", 1)
                        try:
                            display_count = int(display_count)
                            if display_count < 1:
                                display_count = 1
                        except (ValueError, TypeError):
                            display_count = 1

                        result.append({
                            "group": g,
                            "window": w,
                            "candidates": c,
                            "enabled": enabled,
                            "display_count": display_count,
                        })
                if result:
                    return result
        except Exception as e:
            logger.warning(f"读取 {path} 出错，将使用自动推导兜底: {e}")

    # 兜底自动推导
    return derive_core_skill_categories()


def save_core_skill_categories(
    categories: List[Dict[str, Any]],
    config_path: Optional[str] = None
) -> bool:
    """
    将核心技能分类配置写回 json 文件。
    保留 _note 与 _rule 说明字段，UTF-8 编码，ensure_ascii=False，indent=2。
    写失败返回 False 并记录 warning，不抛异常。
    """
    path = config_path or get_core_skills_config_path()
    try:
        cleaned_cats = []
        for c in categories:
            if not isinstance(c, dict):
                continue
            g = str(c.get("group", "")).strip()
            w = str(c.get("window", "")).strip()
            c_list = c.get("candidates", [])
            if not isinstance(c_list, list):
                c_list = []
            enabled = bool(c.get("enabled", True))
            try:
                display_count = max(1, int(c.get("display_count", 1)))
            except (ValueError, TypeError):
                display_count = 1

            cleaned_cats.append({
                "group": g,
                "window": w,
                "candidates": c_list,
                "enabled": enabled,
                "display_count": display_count,
            })

        data = {
            "_note": "核心技能分类映射，可手动编辑或通过UI配置。每档 candidates 里列出候选技能名，表格取角色已学候选中等级最高的前 N 个展示。留空则该档显示 —",
            "_rule": "默认由 bz_skill_desc.json(打击类型) + baizhan_skills_enriched.json(冷却) 自动推导：cd>=31→1分钟档, 11-30→30S档, <=10→10S档",
            "categories": cleaned_cats
        }
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.warning(f"保存核心技能分类至 {path} 失败: {e}")
        return False


def get_all_known_skills(desc_path: Optional[str] = None) -> List[str]:
    """
    从 bz_skill_desc.json 读取全部已知技能名称并排序返回。
    文件缺失或读取失败返回 []。
    """
    actual_path = _find_data_file("bz_skill_desc.json", desc_path)
    if not actual_path or not os.path.exists(actual_path):
        return []
    try:
        with open(actual_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return sorted(list(data.keys()))
        return []
    except Exception as e:
        logger.warning(f"读取全部已知技能失败: {e}")
        return []


def get_skill_meta(
    name: str,
    desc_path: Optional[str] = None,
    enriched_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取单个技能的元数据（冷却与详细描述），供 UI 提示与展示使用。
    返回: {"cooldown": int|None, "detail": str}
    """
    cooldown = None
    detail = ""

    actual_desc_path = _find_data_file("bz_skill_desc.json", desc_path)
    if actual_desc_path and os.path.exists(actual_desc_path):
        try:
            with open(actual_desc_path, "r", encoding="utf-8") as f:
                descs = json.load(f)
            if isinstance(descs, dict) and name in descs:
                info = descs[name]
                if isinstance(info, dict):
                    detail = str(info.get("detail", ""))
        except Exception as e:
            logger.warning(f"读取技能描述失败: {e}")

    actual_enriched_path = _find_data_file("baizhan_skills_enriched.json", enriched_path)
    if actual_enriched_path and os.path.exists(actual_enriched_path):
        try:
            with open(actual_enriched_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                skills = data.get("skills", {})
                if isinstance(skills, dict) and name in skills:
                    cd_val = skills[name].get("cooldown")
                    if cd_val is not None:
                        try:
                            cooldown = int(cd_val)
                        except (ValueError, TypeError):
                            cooldown = None
        except Exception as e:
            logger.warning(f"读取技能CD数据失败: {e}")

    return {"cooldown": cooldown, "detail": detail}


def get_top_candidate_skills(
    skill_list: Optional[List[Dict[str, Any]]],
    candidates: List[str],
    top_n: int = 1
) -> List[Dict[str, Any]]:
    """
    在该档 candidates 候选中找角色已学 (nLevel > 0) 的技能，返回前 top_n 个（按等级降序，等级相同按 candidates 顺序）。
    若无或 top_n <= 0 则返回 []。
    """
    if not skill_list or not candidates or top_n <= 0:
        return []

    candidates_set = set(candidates)
    candidate_order = {name: idx for idx, name in enumerate(candidates)}

    learned: List[Dict[str, Any]] = []
    for s in skill_list:
        if not isinstance(s, dict):
            continue
        name = s.get("szSkillName", "")
        lvl = s.get("nLevel", 0)
        try:
            lvl_int = int(lvl)
        except (ValueError, TypeError):
            lvl_int = 0

        if name in candidates_set and lvl_int > 0:
            learned.append(s)

    if not learned:
        return []

    def sort_key(s: Dict[str, Any]) -> Tuple[int, int]:
        lvl = s.get("nLevel", 0)
        try:
            lvl_int = int(lvl)
        except (ValueError, TypeError):
            lvl_int = 0
        name = s.get("szSkillName", "")
        order = candidate_order.get(name, 9999)
        return (lvl_int, -order)

    learned.sort(key=sort_key, reverse=True)
    return learned[:top_n]


def get_best_candidate_skill(
    skill_list: Optional[List[Dict[str, Any]]],
    candidates: List[str]
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    在该档 candidates 候选中找角色已学 (nLevel > 0) 的技能。
    返回: (best_skill, learned_candidates)
      - best_skill: 等级最高的技能 dict (若无则为 None)
      - learned_candidates: 该角色在该档已学的所有候选技能列表 (按等级从高到低排序)
    """
    if not skill_list or not candidates:
        return None, []

    candidates_set = set(candidates)
    candidate_order = {name: idx for idx, name in enumerate(candidates)}

    learned: List[Dict[str, Any]] = []
    for s in skill_list:
        if not isinstance(s, dict):
            continue
        name = s.get("szSkillName", "")
        lvl = s.get("nLevel", 0)
        try:
            lvl_int = int(lvl)
        except (ValueError, TypeError):
            lvl_int = 0

        if name in candidates_set and lvl_int > 0:
            learned.append(s)

    if not learned:
        return None, []

    def sort_key(s: Dict[str, Any]) -> Tuple[int, int]:
        lvl = s.get("nLevel", 0)
        try:
            lvl_int = int(lvl)
        except (ValueError, TypeError):
            lvl_int = 0
        name = s.get("szSkillName", "")
        order = candidate_order.get(name, 9999)
        return (lvl_int, -order)

    learned.sort(key=sort_key, reverse=True)
    return learned[0], learned
