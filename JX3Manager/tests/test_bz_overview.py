"""
百战招式全账号总览与核心招式分类映射单元测试
"""
import os
import sys
import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# 确保无图形界面模式
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bz_core_skills import (
    load_core_skill_categories,
    derive_core_skill_categories,
    get_best_candidate_skill,
    CORE_CATEGORY_SLOTS,
)
from gui_qt import AllAccountsBaizhanDialog, BaizhanSkillsDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_load_core_skill_categories_normal():
    """测试 load_core_skill_categories 返回 7 个档位且顺序与类型严格正确"""
    cats = load_core_skill_categories()
    assert len(cats) == 7
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

    # 验证关键候选技能归类
    jing_1m = next(c["candidates"] for c in cats if c["group"] == "打精" and c["window"] == "1分钟")
    assert "厄毒爆发" in jing_1m
    assert "蚀骨之花" in jing_1m

    nai_1m = next(c["candidates"] for c in cats if c["group"] == "打耐" and c["window"] == "1分钟")
    assert "黑煞落贪狼" in nai_1m

    hf_core = next(c["candidates"] for c in cats if c["group"] == "回复" and c["window"] == "核心")
    assert "万蛇骨" in hf_core


def test_core_skill_categories_fallback_on_missing_or_corrupt_file(tmp_path):
    """测试配置文件缺失或损坏时，自动推导兜底不抛异常且仍返回 7 档"""
    non_existent_file = str(tmp_path / "non_existent.json")
    cats = load_core_skill_categories(non_existent_file)
    assert len(cats) == 7
    for i, (grp, win) in enumerate(CORE_CATEGORY_SLOTS):
        assert cats[i]["group"] == grp
        assert cats[i]["window"] == win

    # 损坏文件测试
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{corrupt_json: true", encoding="utf-8")
    cats_bad = load_core_skill_categories(str(bad_file))
    assert len(cats_bad) == 7

    # 缺失部分档位测试
    incomplete_file = tmp_path / "incomplete.json"
    incomplete_file.write_text('{"categories": [{"group": "打精", "window": "1分钟", "candidates": []}]}', encoding="utf-8")
    cats_inc = load_core_skill_categories(str(incomplete_file))
    assert len(cats_inc) == 7


def test_get_best_candidate_skill():
    """测试取候选中等级最高招式的选取逻辑"""
    candidates = ["黑煞落贪狼", "血狱隐杀", "七荒黑牙"]

    # 1. 多个候选技能，取等级最高的
    skill_list_1 = [
        {"szSkillName": "血狱隐杀", "nLevel": 5},
        {"szSkillName": "黑煞落贪狼", "nLevel": 8},
        {"szSkillName": "七荒黑牙", "nLevel": 6},
    ]
    best, learned = get_best_candidate_skill(skill_list_1, candidates)
    assert best is not None
    assert best["szSkillName"] == "黑煞落贪狼"
    assert best["nLevel"] == 8
    assert len(learned) == 3
    assert learned[0]["szSkillName"] == "黑煞落贪狼"

    # 2. 角色无该档位任何候选技能
    skill_list_2 = [
        {"szSkillName": "定波式", "nLevel": 7},
        {"szSkillName": "空穴来风", "nLevel": 10},
    ]
    best_2, learned_2 = get_best_candidate_skill(skill_list_2, candidates)
    assert best_2 is None
    assert len(learned_2) == 0

    # 3. nLevel=0 视为未学习
    skill_list_3 = [
        {"szSkillName": "黑煞落贪狼", "nLevel": 0},
        {"szSkillName": "七荒黑牙", "nLevel": "0"},
    ]
    best_3, learned_3 = get_best_candidate_skill(skill_list_3, candidates)
    assert best_3 is None
    assert len(learned_3) == 0

    # 4. 空候选或空技能列表
    assert get_best_candidate_skill([], candidates) == (None, [])
    assert get_best_candidate_skill(skill_list_1, []) == (None, [])
    assert get_best_candidate_skill(None, candidates) == (None, [])


def test_all_accounts_baizhan_dialog_ui(qapp):
    """测试 AllAccountsBaizhanDialog 构造、行数、列数、表头与无数据单元格展示"""
    mock_mgr = MagicMock()

    # 构造假数据（3个角色，其中一个无百战数据）
    mock_chars = [
        {
            "name": "角色A",
            "server": "梦江南",
            "force": "纯阳",
            "baizhan_api": {
                "skillStamina": 250000,
                "skillEnergy": 270000,
                "skillList": [
                    {"szSkillName": "厄毒爆发", "nLevel": 10},
                    {"szSkillName": "蚀骨之花", "nLevel": 7},
                    {"szSkillName": "黑煞落贪狼", "nLevel": 9},
                    {"szSkillName": "七荒黑牙", "nLevel": 5},
                    {"szSkillName": "定波式", "nLevel": 6},
                    {"szSkillName": "海蛇投枪", "nLevel": 8},
                    {"szSkillName": "万蛇骨", "nLevel": 10},
                ],
            },
        },
        {
            "name": "角色B",
            "server": "测试区服A",
            "force": "七秀",
            "baizhan_api": {
                "skillStamina": 120000,
                "skillEnergy": 150000,
                "skillList": [
                    {"szSkillName": "黑煞落贪狼", "nLevel": 3},
                ],
            },
        },
        {
            "name": "角色C",
            "server": "测试区服B",
            "force": "万花",
            # 无 baizhan_api
        },
    ]

    dlg = AllAccountsBaizhanDialog(mock_mgr, mock_chars)
    assert dlg.windowTitle() == "📊 全账号百战技能总览"
    assert not dlg.windowIcon().isNull()

    # 断言行数与列数
    assert dlg.table.rowCount() == 3
    assert dlg.table.columnCount() == 12

    # 断言表头
    expected_headers = [
        "角色", "服务器", "门派", "百战精", "百战耐",
        "打精·1分钟", "打精·30S", "打精·10S",
        "打耐·1分钟", "打耐·30S", "打耐·10S", "回复·核心"
    ]
    for col, expected in enumerate(expected_headers):
        assert dlg.table.horizontalHeaderItem(col).text() == expected

    # 角色A (row 0)
    assert dlg.table.item(0, 0).text() == "角色A"
    assert dlg.table.item(0, 3).text() == "250,000"
    assert dlg.table.item(0, 4).text() == "270,000"
    assert dlg.table.item(0, 5).text() == "厄毒爆发 Lv10"
    assert dlg.table.item(0, 6).text() == "—"  # 打精 30S 候选为空
    assert dlg.table.item(0, 7).text() == "定波式 Lv6"
    assert dlg.table.item(0, 8).text() == "黑煞落贪狼 Lv9"
    assert dlg.table.item(0, 9).text() == "七荒黑牙 Lv5"
    assert dlg.table.item(0, 10).text() == "海蛇投枪 Lv8"
    assert dlg.table.item(0, 11).text() == "万蛇骨 Lv10"

    # 角色B (row 1): 打精未学习
    assert dlg.table.item(1, 0).text() == "角色B"
    assert dlg.table.item(1, 5).text() == "未学习"
    assert dlg.table.item(1, 8).text() == "黑煞落贪狼 Lv3"

    # 角色C (row 2): 无百战数据
    assert dlg.table.item(2, 0).text() == "角色C"
    assert dlg.table.item(2, 3).text() == "-"
    assert dlg.table.item(2, 4).text() == "-"
    for col in range(5, 12):
        assert dlg.table.item(2, col).text() == "无数据"

    # 顶部统计
    assert "共 <b>3</b> 个角色" in dlg.lbl_stats.text()
    assert "有百战数据 <b>2</b> 个" in dlg.lbl_stats.text()

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
