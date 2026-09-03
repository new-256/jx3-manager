"""
JX3Manager - 百战核心招式分类映射模块
提供核心技能分类（打精/打耐/回复 各CD档位）的推导、加载与候选招式等级匹配逻辑。
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# 7 个标准档位定义元组: (group, window)
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
            "candidates": category_map.get((grp, win), [])
        }
        for grp, win in CORE_CATEGORY_SLOTS
    ]


def load_core_skill_categories(config_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    加载核心技能分类映射配置。
    若配置文件不存在、格式损坏或缺失档位，则自动推导兜底，保证永不报错并严格返回 7 档。
    """
    path = config_path or get_core_skills_config_path()
    
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            raw_cats = data.get("categories", [])
            if isinstance(raw_cats, list) and len(raw_cats) > 0:
                loaded_map = {}
                for item in raw_cats:
                    if isinstance(item, dict):
                        g = item.get("group", "")
                        w = item.get("window", "")
                        c = item.get("candidates", [])
                        if isinstance(c, list):
                            loaded_map[(g, w)] = c
                
                all_slots_exist = all(slot in loaded_map for slot in CORE_CATEGORY_SLOTS)
                if all_slots_exist:
                    return [
                        {
                            "group": grp,
                            "window": win,
                            "candidates": loaded_map.get((grp, win), [])
                        }
                        for grp, win in CORE_CATEGORY_SLOTS
                    ]
        except Exception as e:
            logger.warning(f"读取 {path} 出错，将使用自动推导兜底: {e}")

    # 兜底自动推导
    return derive_core_skill_categories()


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
