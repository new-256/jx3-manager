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

# 默认等级颜色规则：按角色已学最高等级着色（可在分类配置界面调节）
# 规则自上而下匹配，命中即用；最后一条（等级最高段）加粗显示
DEFAULT_LEVEL_COLORS: List[Dict[str, Any]] = [
    {"min": 1, "max": 8, "color": "#e53935"},    # 1-8级 红色
    {"min": 9, "max": 9, "color": "#fdd835"},    # 9级 黄色
    {"min": 10, "max": 999, "color": "#43a047"}, # 10级及以上 绿色
]

# 各档默认展示技能数（表格单元格内垂直列出的技能条数）
DEFAULT_DISPLAY_COUNT = 5

_STRIKE_RE = re.compile(r"\[([\d/.]+)\]\s*点(精神打击|耐力打击)")


def get_strike_values(desc_path: Optional[str] = None) -> Dict[str, Dict[str, int]]:
    """
    从 bz_skill_desc.json 解析各招式满级(数值数组最后一段)的打击值。

    返回 {招式名: {"精神": 满级精神打击值, "耐力": 满级耐力打击值}}，
    只含描述里带数值数组的招式（156 个中约 82 条匹配）。
    用于各档候选按满级打精/打耐数值排序。
    """
    actual = _find_data_file("bz_skill_desc.json", desc_path)
    out: Dict[str, Dict[str, int]] = {}
    if not actual or not os.path.exists(actual):
        return out
    try:
        with open(actual, "r", encoding="utf-8") as f:
            descs = json.load(f)
    except Exception as e:
        logger.warning(f"读取 bz_skill_desc.json 打击值失败: {e}")
        return out
    for name, info in descs.items():
        if not isinstance(info, dict):
            continue
        detail = info.get("detail", "") or ""
        for vals, kind in _STRIKE_RE.findall(detail):
            try:
                full = int(vals.split("/")[-1])
            except (ValueError, TypeError):
                continue
            key = "精神" if kind == "精神打击" else "耐力"
            d = out.setdefault(name, {})
            # 同一招式同类型多次匹配取最大值
            d[key] = max(d.get(key, 0), full)
    return out


def get_level_colors(config_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    读取等级颜色规则配置（bz_core_skills.json 的 level_colors 字段）。
    缺失或格式非法时返回默认规则 DEFAULT_LEVEL_COLORS。
    每条规则: {"min": int, "max": int, "color": "#rrggbb"}
    """
    path = config_path or get_core_skills_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("level_colors")
            if isinstance(raw, list) and raw:
                rules = []
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    try:
                        mn = int(item.get("min", 1))
                        mx = int(item.get("max", 1))
                        color = str(item.get("color", "")).strip()
                        if mn <= mx and color.startswith("#") and len(color) in (4, 7, 9):
                            rules.append({"min": mn, "max": mx, "color": color})
                    except (ValueError, TypeError):
                        continue
                if rules:
                    return rules
        except Exception as e:
            logger.warning(f"读取等级颜色规则失败: {e}")
    return [dict(r) for r in DEFAULT_LEVEL_COLORS]


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
    从 bz_skill_cost.json (jx3box 来源) 读取招式消耗点数 {招式名: 点数}。

    消耗点数 = 该招式占用的技能格数量。百战玩法最多 3 个技能槽位，
    即携带招式的点数合计不能超过 3。

    数据来源: https://node.jx3box.com/monster/skills 的 nCost 字段，
    覆盖全部 156 个百战招式。分布：1点 146 个 / 2点 6 个 / 3点 4 个。

    若 jx3box 文件不存在则回退到 bz_skill_meta.json 的 dbm_cost。
    """
    for fname in ("bz_skill_cost.json", "bz_skill_meta.json"):
        actual = _find_data_file(fname, meta_path)
        if not actual or not os.path.exists(actual):
            continue
        try:
            with open(actual, "r", encoding="utf-8") as f:
                data = json.load(f)
            if fname == "bz_skill_cost.json":
                src = data.get("costs", {})
            else:
                src = {}
                for info in (data.get("skills", {}) if isinstance(data, dict) else {}).values():
                    if isinstance(info, dict) and info.get("dbm_cost") is not None:
                        src[info["name"]] = int(info["dbm_cost"])
            return {k: int(v) for k, v in src.items() if v is not None}
        except Exception as e:
            logger.warning(f"读取 {fname} 消耗点数失败: {e}")
            continue
    return {}


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


def get_skill_cooldowns(cd_path: Optional[str] = None) -> Dict[str, Optional[int]]:
    """
    从 bz_skill_cd.json (jx3box 来源) 读取招式调息时间 {招式名: 秒数或 None}。

    数据来源: https://node.jx3box.com/monster/skills 的 ParsedSkill.tooltip，
    从中提取 'N秒调息' / '无调息时间'。覆盖全部 156 个招式，其中 146 个有
    明确数值（0 表示无调息时间），10 个无调息数据（网页显示 '-'，值为 None）。

    分布：0秒 6 / 10秒 52 / 25秒 6 / 30秒 55 / 50秒 2 / 60秒 24 / 300秒 1。
    """
    actual = _find_data_file("bz_skill_cd.json", cd_path)
    if not actual or not os.path.exists(actual):
        return {}
    try:
        with open(actual, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("cooldowns", {})
        out: Dict[str, Optional[int]] = {}
        for name, cd in raw.items():
            if cd is None:
                out[name] = None
            else:
                try:
                    out[name] = int(cd)
                except (ValueError, TypeError):
                    out[name] = None
        return out
    except Exception as e:
        logger.warning(f"读取 bz_skill_cd.json 失败: {e}")
    return {}


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

    档位规则（按 bz_skill_cd.json 的 jx3box 调息时间，实测与级别基本对应）：
      - 10秒       -> 10S   档
      - 30秒       -> 30S   档
      - 60秒       -> 1分钟 档
      - 0秒(无调息)/25/50/300秒 -> 就近归档 (0/10->10S, 25/30/50->30S, 60/300->1分钟)
      - 无调息数据 (None, 网页显示 '-') -> 10S 档（待手动划分）
      - 回复类统一归入 '核心' 档

    候选排序：打精/打耐按描述中满级(数组末段)打击值降序 —— 默认配置即
    各档满级数值最高的技能排前面，配合 display_count=5 取 Top5；
    回复类按招式名排序。默认 display_count=5。

    覆盖统计：156 个招式中 146 个有明确调息时间，10 个无数据归 10S 档。
    """
    actual_desc_path = _find_data_file("bz_skill_desc.json", desc_path)

    descs: Dict[str, Dict[str, Any]] = {}
    if actual_desc_path and os.path.exists(actual_desc_path):
        try:
            with open(actual_desc_path, "r", encoding="utf-8") as f:
                descs = json.load(f)
        except Exception as e:
            logger.warning(f"读取 bz_skill_desc.json 失败: {e}")

    cds = get_skill_cooldowns()
    strikes = get_strike_values(desc_path=actual_desc_path)

    def window_for(name: str) -> str:
        """按 jx3box 调息时间分档，无数据归 10S"""
        cd = cds.get(name)
        if cd is None:
            return "10S"
        if cd <= 10:            # 0(无调息)/10 秒
            return "10S"
        if cd <= 30:            # 25/30 秒
            return "30S"
        return "1分钟"          # 50/60/300 秒

    def strike_key(grp: str, name: str):
        """该档打击类型的满级数值（降序排序用），无数据排最后"""
        key = "精神" if grp == "打精" else "耐力"
        v = (strikes.get(name) or {}).get(key, 0)
        return v

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

    # 按档位重新分配 打精/打耐；同档内按满级打击值降序（默认取数值最高的前 5 个）
    for grp in ("打精", "打耐"):
        all_names = list(buckets[(grp, "10S")])
        buckets[(grp, "10S")] = []
        buckets[(grp, "30S")] = []
        buckets[(grp, "1分钟")] = []
        for name in all_names:
            win = window_for(name)
            buckets[(grp, win)].append(name)
        for win in ("10S", "30S", "1分钟"):
            buckets[(grp, win)].sort(key=lambda n: strike_key(grp, n), reverse=True)

    for (grp, win) in buckets:
        if grp in ("打精", "打耐"):
            pass  # 已按打击值排序

    category_map = buckets

    return [
        {
            "group": grp,
            "window": win,
            "candidates": category_map.get((grp, win), []),
            "enabled": True,
            "display_count": DEFAULT_DISPLAY_COUNT,
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
    config_path: Optional[str] = None,
    level_colors: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """
    将核心技能分类配置写回 json 文件。
    保留 _note/_rule 说明字段，UTF-8 编码，ensure_ascii=False，indent=2。
    level_colors 为等级颜色规则列表（None 时沿用文件里已有的配置，再无则用默认值）。
    写失败返回 False 并记录 warning，不抛异常。
    """
    path = config_path or get_core_skills_config_path()
    try:
        # 未显式传入时沿用文件里已有的 level_colors 配置
        if level_colors is None:
            level_colors = None
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        old = json.load(f)
                    if isinstance(old.get("level_colors"), list) and old["level_colors"]:
                        level_colors = old["level_colors"]
                except Exception:
                    pass
            if level_colors is None:
                level_colors = [dict(r) for r in DEFAULT_LEVEL_COLORS]

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
            "_note": "核心技能分类映射，可手动编辑或通过UI配置。每档 candidates 里列出候选技能名（打精/打耐按满级打击值降序），表格取角色已学候选中等级最高的前 N 个展示（默认 5 个）。留空则该档显示 —。level_colors 为表格等级颜色规则（自上而下匹配，min/max 为等级区间，color 为十六进制颜色）。",
            "_rule": "默认由 bz_skill_desc.json(打击类型+满级打击值排序) + bz_skill_cd.json(jx3box 调息时间分档: <=10s→10S, <=30s→30S, >30s→1分钟) 自动推导；display_count 默认 5",
            "level_colors": level_colors,
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
