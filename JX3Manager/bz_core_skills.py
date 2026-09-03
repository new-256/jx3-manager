"""
JX3Manager - 百战核心招式分类映射模块
提供核心技能分类（打精/打耐/回复 各CD档位与自定义分类）的推导、加载、保存与候选招式等级匹配逻辑。
"""

import os
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


def derive_core_skill_categories(
    desc_path: Optional[str] = None,
    enriched_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    从 bz_skill_desc.json (打击类型) 与 baizhan_skills_enriched.json (冷却CD) 自动推导 7 档核心技能。
    规则:
      - 描述含 '精神打击' -> 打精
      - 描述含 '耐力打击' -> 打耐
      - 描述含 '恢复' 且 ('气血' in 描述 or '精神' in 描述 or '耐力' in 描述) -> 回复
      - CD分档: CD >= 31 -> 1分钟档; 11 <= CD <= 30 -> 30S档; CD <= 10 -> 10S档
      - 回复分档: window 为 '核心'
      - 每档 candidates 按 (cd 降序, 技能名 降序) 排序
      - 默认补全 enabled=True, display_count=1
    """
    actual_desc_path = _find_data_file("bz_skill_desc.json", desc_path)
    actual_enriched_path = _find_data_file("baizhan_skills_enriched.json", enriched_path)

    descs: Dict[str, Dict[str, Any]] = {}
    if actual_desc_path and os.path.exists(actual_desc_path):
        try:
            with open(actual_desc_path, "r", encoding="utf-8") as f:
                descs = json.load(f)
        except Exception as e:
            logger.warning(f"读取 bz_skill_desc.json 失败: {e}")

    enriched_skills: Dict[str, Dict[str, Any]] = {}
    if actual_enriched_path and os.path.exists(actual_enriched_path):
        try:
            with open(actual_enriched_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                enriched_skills = data.get("skills", {}) if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"读取 baizhan_skills_enriched.json 失败: {e}")

    jing_1m: List[Tuple[str, int]] = []
    jing_30s: List[Tuple[str, int]] = []
    jing_10s: List[Tuple[str, int]] = []
    nai_1m: List[Tuple[str, int]] = []
    nai_30s: List[Tuple[str, int]] = []
    nai_10s: List[Tuple[str, int]] = []
    hf_core: List[Tuple[str, int]] = []

    for name, info in descs.items():
        if not isinstance(info, dict):
            continue
        detail = info.get("detail", "")
        if not detail:
            continue

        cd_val = enriched_skills.get(name, {}).get("cooldown", 0)
        try:
            cd = int(cd_val) if cd_val is not None else 0
        except (ValueError, TypeError):
            cd = 0

        is_jing = "精神打击" in detail
        is_nai = "耐力打击" in detail
        is_hf = "恢复" in detail and ("气血" in detail or "精神" in detail or "耐力" in detail)

        if is_jing:
            if cd >= 31:
                jing_1m.append((name, cd))
            elif cd >= 11:
                jing_30s.append((name, cd))
            else:
                jing_10s.append((name, cd))

        if is_nai:
            if cd >= 31:
                nai_1m.append((name, cd))
            elif cd >= 11:
                nai_30s.append((name, cd))
            else:
                nai_10s.append((name, cd))

        if is_hf:
            hf_core.append((name, cd))

    for lst in (jing_1m, jing_30s, jing_10s, nai_1m, nai_30s, nai_10s, hf_core):
        lst.sort(key=lambda x: (x[1], x[0]), reverse=True)

    category_map = {
        ("打精", "1分钟"): [x[0] for x in jing_1m],
        ("打精", "30S"): [x[0] for x in jing_30s],
        ("打精", "10S"): [x[0] for x in jing_10s],
        ("打耐", "1分钟"): [x[0] for x in nai_1m],
        ("打耐", "30S"): [x[0] for x in nai_30s],
        ("打耐", "10S"): [x[0] for x in nai_10s],
        ("回复", "核心"): [x[0] for x in hf_core],
    }

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
