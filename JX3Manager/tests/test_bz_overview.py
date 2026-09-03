"""
百战招式全账号总览与核心招式分类映射及 UI 配置单元测试
"""
import os
import sys
import json
import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication, QListWidgetItem
from PyQt6.QtCore import Qt

# 确保无图形界面模式
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bz_core_skills import (
    load_core_skill_categories,
    save_core_skill_categories,
    derive_core_skill_categories,
    get_all_known_skills,
    get_skill_meta,
    get_best_candidate_skill,
    get_top_candidate_skills,
    get_verified_cooldowns,
    get_skill_levels,
    SKILL_LEVEL_WINDOW,
    CORE_CATEGORY_SLOTS,
)
from gui_qt import CoreSkillsConfigDialog, AllAccountsBaizhanDialog, BaizhanSkillsDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_get_verified_cooldowns_only_returns_id_matched():
    """
    冷却校验回归测试：baizhan_skills_enriched.json 的冷却是早期按招式名匹配通用技能库
    得到的，大量百战招式与门派技能重名导致冷却取自错误技能。
    get_verified_cooldowns 必须只返回 dwID 与本地 id/in_id 对得上的招式。
    """
    verified = get_verified_cooldowns()
    assert isinstance(verified, dict)
    # 全部值必须是 int
    assert all(isinstance(v, int) for v in verified.values())

    # 黑煞落贪狼 ID 可对上，冷却 60 秒，必须在校验表中
    assert verified.get("黑煞落贪狼") == 60

    # 这些招式的 enriched 冷却来自同名的其他技能，必须被剔除
    for bad in ("厄毒爆发", "蚀骨之花", "血狱隐杀", "七荒黑牙"):
        assert bad not in verified, f"{bad} 的冷却不可信（ID 不匹配），不应通过校验"

    # 可信数量应远小于招式总数（实测 12/156），防止回退到全量误信
    assert len(verified) < 30


def test_derive_only_tiers_verified_cooldown_skills():
    """档位分配合规性：1分钟/30S 档的招式必须有级别(2-3级)或经过验证的冷却"""
    cats = derive_core_skill_categories()
    lv = get_skill_levels()
    verified = get_verified_cooldowns()

    for c in cats:
        if c["window"] in ("1分钟", "30S"):
            for sname in c["candidates"]:
                level = lv.get(sname)
                cd = verified.get(sname)
                ok = (level is not None) or (cd is not None)
                assert ok, f"{sname} 既无级别又无验证冷却，不应分入 {c['window']} 档"
                if level is not None:
                    # 级别规则：1级=10S, 2级=30S, 3级=1分钟
                    if c["window"] == "1分钟":
                        assert level == 3, f"{sname} 级别={level} 不应分入 1分钟 档"
                    elif c["window"] == "30S":
                        assert level == 2, f"{sname} 级别={level} 不应分入 30S 档"


def test_get_skill_levels_parses_dbm_note():
    """
    招式级别解析回归测试：bz_skill_meta.json 的 dbm_note 形如
    '绿 消耗点数：1  1级'，需正确解出末尾的 N级。
    暂定规则：1级=10S, 2级=30S, 3级=1分钟。
    """
    levels = get_skill_levels()
    assert isinstance(levels, dict)
    assert all(isinstance(v, int) for v in levels.values())
    # 级别只应出现 1/2/3
    assert set(levels.values()) <= {1, 2, 3}

    # 已知样例：破裂 note='绿 消耗点数：1  1级' -> 1级
    assert levels.get("破裂") == 1
    # 定波式 note='紫 消耗点数：1  2级' -> 2级
    assert levels.get("定波式") == 2
    # 黑煞落贪狼 为 3级，且其经 ID 验证的冷却=60s，与 3级->1分钟 规则自洽
    assert levels.get("黑煞落贪狼") == 3

    # 无级别标注的条目不应出现（note 形如 ' 消耗点数：1 '）
    assert "特制金创药" not in levels

    # 映射规则常量正确
    assert SKILL_LEVEL_WINDOW == {1: "10S", 2: "30S", 3: "1分钟"}


def test_derive_uses_level_as_primary_tier_rule():
    """级别应作为分档主依据：3级招式进 1分钟档，2级进 30S 档，1级进 10S 档"""
    cats = derive_core_skill_categories()
    lv = get_skill_levels()
    by_slot = {(c["group"], c["window"]): c["candidates"] for c in cats}

    # 黑煞落贪狼 3级 且为打耐 -> 打耐·1分钟
    assert "黑煞落贪狼" in by_slot[("打耐", "1分钟")]
    # 定波式 2级 且为打精 -> 打精·30S
    assert "定波式" in by_slot[("打精", "30S")]

    # 反向校验：每个 1级招式都不应出现在 1分钟/30S 档
    for (grp, win), names in by_slot.items():
        if win in ("1分钟", "30S"):
            for n in names:
                assert lv.get(n) != 1, f"{n} 是1级却被分入 {win} 档"


def test_load_core_skill_categories_normal():
    """测试 load_core_skill_categories 返回默认档位且顺序与类型严格正确"""
    cats = load_core_skill_categories()
    assert len(cats) >= 7
    expected_slots = [
        ("打精", "1分钟"),
        ("打精", "30S"),
        ("打精", "10S"),
        ("打耐", "1分钟"),
        ("打耐", "30S"),
        ("打耐", "10S"),
        ("回复", "核心"),
    ]
    for i, (grp, win) in enumerate(expected_slots):
        assert cats[i]["group"] == grp
        assert cats[i]["window"] == win
        assert isinstance(cats[i]["candidates"], list)
        assert "enabled" in cats[i]
        assert "display_count" in cats[i]

    # 验证关键候选技能归类（按级别分档：1级=10S / 2级=30S / 3级=1分钟）
    # 打精·1分钟: 3级招式
    jing_1m = next(c["candidates"] for c in cats if c["group"] == "打精" and c["window"] == "1分钟")
    assert len(jing_1m) == 3
    assert "帝骖龙翔" in jing_1m
    # 打精·10S: 1级+无级别招式
    jing_10s = next(c["candidates"] for c in cats if c["group"] == "打精" and c["window"] == "10S")
    assert "厄毒爆发" in jing_10s  # 无级别，默认归 10S
    assert "蚀骨之花" in jing_10s  # 无级别，默认归 10S
    assert len(jing_10s) == 32

    nai_1m = next(c["candidates"] for c in cats if c["group"] == "打耐" and c["window"] == "1分钟")
    assert "黑煞落贪狼" in nai_1m  # 3级，cd=60 已验证
    assert "疯狂疾走" in nai_1m    # 3级
    assert len(nai_1m) == 3

    hf_core = next(c["candidates"] for c in cats if c["group"] == "回复" and c["window"] == "核心")
    assert "万蛇骨" in hf_core


def test_core_skill_categories_fallback_on_missing_or_corrupt_file(tmp_path):
    """测试配置文件缺失或损坏或为空时，自动推导兜底不抛异常且返回带 enabled 与 display_count 的 7 档"""
    non_existent_file = str(tmp_path / "non_existent.json")
    cats = load_core_skill_categories(non_existent_file)
    assert len(cats) == 7
    for i, (grp, win) in enumerate(CORE_CATEGORY_SLOTS):
        assert cats[i]["group"] == grp
        assert cats[i]["window"] == win
        assert cats[i]["enabled"] is True
        assert cats[i]["display_count"] == 1

    # 损坏文件测试
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{corrupt_json: true", encoding="utf-8")
    cats_bad = load_core_skill_categories(str(bad_file))
    assert len(cats_bad) == 7
    assert cats_bad[0]["enabled"] is True

    # 空 categories 列表测试 -> 兜底推导
    empty_file = tmp_path / "empty.json"
    empty_file.write_text('{"categories": []}', encoding="utf-8")
    cats_empty = load_core_skill_categories(str(empty_file))
    assert len(cats_empty) == 7


def test_save_and_load_core_skill_categories_roundtrip(tmp_path):
    """测试 save_core_skill_categories 与 load_core_skill_categories 往返一致"""
    cfg_file = str(tmp_path / "custom_skills.json")
    custom_cats = [
        {
            "group": "自定义输出",
            "window": "爆发",
            "candidates": ["黑煞落贪狼", "厄毒爆发"],
            "enabled": False,
            "display_count": 3
        },
        {
            "group": "特种辅助",
            "window": "解控",
            "candidates": ["万蛇骨"],
            "enabled": True,
            "display_count": 2
        }
    ]

    ok = save_core_skill_categories(custom_cats, config_path=cfg_file)
    assert ok is True
    assert os.path.exists(cfg_file)

    loaded = load_core_skill_categories(config_path=cfg_file)
    assert len(loaded) == 2
    assert loaded[0]["group"] == "自定义输出"
    assert loaded[0]["window"] == "爆发"
    assert loaded[0]["candidates"] == ["黑煞落贪狼", "厄毒爆发"]
    assert loaded[0]["enabled"] is False
    assert loaded[0]["display_count"] == 3

    assert loaded[1]["group"] == "特种辅助"
    assert loaded[1]["window"] == "解控"
    assert loaded[1]["candidates"] == ["万蛇骨"]
    assert loaded[1]["enabled"] is True
    assert loaded[1]["display_count"] == 2


def test_legacy_format_auto_fill_defaults(tmp_path):
    """测试旧格式配置（无 enabled / display_count 字段）加载后自动补齐默认值 True / 1"""
    cfg_file = tmp_path / "legacy.json"
    cfg_file.write_text(json.dumps({
        "categories": [
            {"group": "打精", "window": "1分钟", "candidates": ["厄毒爆发"]},
            {"group": "打耐", "window": "30S", "candidates": ["七荒黑牙"]}
        ]
    }), encoding="utf-8")

    loaded = load_core_skill_categories(str(cfg_file))
    assert len(loaded) == 2
    assert loaded[0]["enabled"] is True
    assert loaded[0]["display_count"] == 1
    assert loaded[1]["enabled"] is True
    assert loaded[1]["display_count"] == 1


def test_custom_categories_arbitrary_count(tmp_path):
    """测试配置包含 5 个自定义分类（非标准 7 档）时能原样加载，不被强制改回 7 档"""
    cfg_file = tmp_path / "five_cats.json"
    cats_data = [
        {"group": f"分类{i}", "window": f"档位{i}", "candidates": [], "enabled": True, "display_count": 1}
        for i in range(5)
    ]
    cfg_file.write_text(json.dumps({"categories": cats_data}), encoding="utf-8")

    loaded = load_core_skill_categories(str(cfg_file))
    assert len(loaded) == 5
    for i in range(5):
        assert loaded[i]["group"] == f"分类{i}"
        assert loaded[i]["window"] == f"档位{i}"


def test_get_top_candidate_skills():
    """测试 get_top_candidate_skills 等级降序、优先级、top_n 数量截取与兜底"""
    candidates = ["黑煞落贪狼", "血狱隐杀", "七荒黑牙", "定波式"]
    skill_list = [
        {"szSkillName": "血狱隐杀", "nLevel": 5},
        {"szSkillName": "黑煞落贪狼", "nLevel": 8},
        {"szSkillName": "七荒黑牙", "nLevel": 8},  # 等级与黑煞相同，但黑煞在 candidates 中排第0位，优先级更高
        {"szSkillName": "定波式", "nLevel": 3},
    ]

    # top_n = 3
    top3 = get_top_candidate_skills(skill_list, candidates, top_n=3)
    assert len(top3) == 3
    assert top3[0]["szSkillName"] == "黑煞落贪狼"  # Lv8, 候选序0
    assert top3[1]["szSkillName"] == "七荒黑牙"    # Lv8, 候选序2
    assert top3[2]["szSkillName"] == "血狱隐杀"    # Lv5

    # top_n = 10 (大于实际已学数量 4)
    top10 = get_top_candidate_skills(skill_list, candidates, top_n=10)
    assert len(top10) == 4

    # top_n = 1 与 get_best_candidate_skill 一致性
    top1 = get_top_candidate_skills(skill_list, candidates, top_n=1)
    best, _ = get_best_candidate_skill(skill_list, candidates)
    assert len(top1) == 1
    assert top1[0] == best

    # 无已学技能
    empty_res = get_top_candidate_skills([], candidates, top_n=3)
    assert empty_res == []

    # top_n <= 0
    assert get_top_candidate_skills(skill_list, candidates, top_n=0) == []


def test_get_all_known_skills_and_meta():
    """测试获取已知技能列表及单技能元数据"""
    skills = get_all_known_skills()
    assert isinstance(skills, list)
    if skills:
        assert "黑煞落贪狼" in skills
        meta = get_skill_meta("黑煞落贪狼")
        assert isinstance(meta, dict)
        assert "cooldown" in meta
        assert "detail" in meta


def test_core_skills_config_dialog_ui(qapp, tmp_path):
    """测试 CoreSkillsConfigDialog 界面交互（使用独立临时配置文件，绝不污染真实数据）"""
    tmp_config = tmp_path / "test_bz_config.json"
    init_cats = [
        {"group": "测试打精", "window": "1分钟", "candidates": ["厄毒爆发"], "enabled": True, "display_count": 2},
        {"group": "测试打耐", "window": "30S", "candidates": ["七荒黑牙"], "enabled": False, "display_count": 1},
    ]
    save_core_skill_categories(init_cats, str(tmp_config))

    dlg = CoreSkillsConfigDialog(config_path=str(tmp_config))
    assert dlg.windowTitle() == "⚙ 百战技能分类配置"
    assert dlg.list_categories.count() == 2

    # 断言左列表项文字与勾选状态
    item0 = dlg.list_categories.item(0)
    item1 = dlg.list_categories.item(1)
    assert "测试打精·1分钟" in item0.text()
    assert item0.checkState() == Qt.CheckState.Checked
    assert "测试打耐·30S" in item1.text()
    assert item1.checkState() == Qt.CheckState.Unchecked

    # 选中第 0 项，检查右侧 spinbox 和 candidates
    dlg.list_categories.setCurrentRow(0)
    assert dlg.spin_display_count.value() == 2
    assert dlg.list_candidates.count() == 1

    # 选中第 1 项，检查右侧 spinbox
    dlg.list_categories.setCurrentRow(1)
    assert dlg.spin_display_count.value() == 1
    assert dlg.list_candidates.count() == 1

    # 模拟新增分类
    new_cat = {
        "group": "自定义辅助",
        "window": "核心",
        "candidates": ["万蛇骨"],
        "enabled": True,
        "display_count": 1
    }
    dlg.categories.append(new_cat)
    dlg.refresh_categories_list(select_idx=2)
    assert dlg.list_categories.count() == 3

    # 保存配置并验证写回文件
    dlg.save_config()
    assert dlg.saved is True

    saved_cats = load_core_skill_categories(str(tmp_config))
    assert len(saved_cats) == 3
    assert saved_cats[2]["group"] == "自定义辅助"

    dlg.close()


def test_all_accounts_baizhan_dialog_ui_and_features(qapp, tmp_path):
    """测试 AllAccountsBaizhanDialog 多技能换行展示、分类禁用列减少以及分类配置弹窗交互"""
    mock_mgr = MagicMock()
    tmp_config = tmp_path / "test_overview_config.json"

    # 设置 2 个分类：一个展示2个技能，一个被禁用
    config_cats = [
        {
            "group": "打精",
            "window": "10S",
            "candidates": ["定波式", "空穴来风", "冥府滑行"],
            "enabled": True,
            "display_count": 2
        },
        {
            "group": "打耐",
            "window": "1分钟",
            "candidates": ["黑煞落贪狼", "血狱隐杀"],
            "enabled": True,
            "display_count": 1
        },
        {
            "group": "隐藏分类",
            "window": "测试",
            "candidates": ["万蛇骨"],
            "enabled": False,  # 禁用
            "display_count": 1
        }
    ]
    save_core_skill_categories(config_cats, str(tmp_config))

    mock_chars = [
        {
            "name": "测试角色A",
            "server": "测试区服A",
            "force": "纯阳",
            "baizhan_api": {
                "skillStamina": 250000,
                "skillEnergy": 270000,
                "skillList": [
                    {"szSkillName": "定波式", "nLevel": 8},
                    {"szSkillName": "空穴来风", "nLevel": 6},
                    {"szSkillName": "黑煞落贪狼", "nLevel": 10},
                ],
            },
        },
        {
            "name": "测试角色B",
            "server": "测试区服B",
            "force": "七秀",
            "baizhan_api": {
                "skillStamina": 100000,
                "skillEnergy": 120000,
                "skillList": [],
            },
        }
    ]

    dlg = AllAccountsBaizhanDialog(mock_mgr, mock_chars, config_path=str(tmp_config))

    # 断言列数：基础5列 + 2个启用的技能分类列 = 7列（禁用的分类不出现）
    assert dlg.table.columnCount() == 7
    expected_headers = ["角色", "服务器", "门派", "百战精", "百战耐", "打精·10S", "打耐·1分钟"]
    for col, h in enumerate(expected_headers):
        assert dlg.table.horizontalHeaderItem(col).text() == h

    # 检查第 0 行测试角色A（display_count=2 的打精·10S 列，索引 5）
    cell_text = dlg.table.item(0, 5).text()
    assert "\n" in cell_text
    lines = cell_text.split("\n")
    assert len(lines) == 2
    assert lines[0] == "定波式 Lv8"
    assert lines[1] == "空穴来风 Lv6"

    # 检查打耐·1分钟（display_count=1，索引 6）
    assert dlg.table.item(0, 6).text() == "黑煞落贪狼 Lv10"

    # 检查顶部工具栏按钮文字
    assert hasattr(dlg, "btn_config")
    assert dlg.btn_config.text() == "⚙ 分类配置"

    dlg.close()


def test_baizhan_skills_dialog_overview_button(qapp, monkeypatch):
    """测试 BaizhanSkillsDialog 中包含全账号总览按钮并能正确调用弹窗"""
    mock_mgr = MagicMock()
    mock_chars = [{"name": "测试角色", "server": "测试区服A", "baizhan_api": {}}]

    dlg = BaizhanSkillsDialog(mock_mgr, mock_chars)
    assert hasattr(dlg, "btn_all_overview"), "BaizhanSkillsDialog 缺少 btn_all_overview 按钮"
    assert dlg.btn_all_overview.text() == "📊 全账号总览"
    assert dlg.btn_all_overview.objectName() == "PrimaryBtn"
    assert "以表格展示全部角色" in dlg.btn_all_overview.toolTip()

    called = False
    def mock_exec(self):
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(AllAccountsBaizhanDialog, "exec", mock_exec)
    dlg.btn_all_overview.click()
    assert called, "点击全账号总览按钮未触发 AllAccountsBaizhanDialog.exec"

    dlg.close()
