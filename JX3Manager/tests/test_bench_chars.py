"""
待选区 (BenchManager) 数据层与 GUI 交互单元测试
"""
import os
import sys
import json
import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

# 确保无图形界面模式
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from readers.bench_chars import BenchManager
from main import JX3Manager, filter_out_benched
from gui_qt import MainWindow, BenchManagerDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_bench_manager_crud_and_idempotence(tmp_path):
    """测试 BenchManager 增删改查、幂等性、toggle 返回值及持久化往返"""
    bench_file = str(tmp_path / "test_bench.json")
    mgr = BenchManager(bench_file)

    assert mgr.count() == 0
    assert not mgr.is_benched("测试角色A")

    # 添加
    mgr.add("测试角色A")
    assert mgr.is_benched("测试角色A")
    assert mgr.count() == 1

    # 幂等添加
    mgr.add("测试角色A")
    assert mgr.count() == 1

    mgr.add("测试角色B")
    assert mgr.count() == 2
    assert mgr.get_all() == ["测试角色A", "测试角色B"]

    # 移除
    mgr.remove("测试角色A")
    assert not mgr.is_benched("测试角色A")
    assert mgr.count() == 1

    # 幂等移除
    mgr.remove("测试角色A")
    assert mgr.count() == 1

    # Toggle 测试
    # 当前 测试角色B 为 True，toggle 后应变为 False 并返回 False
    res = mgr.toggle("测试角色B")
    assert res is False
    assert not mgr.is_benched("测试角色B")

    # 当前 测试角色B 为 False，toggle 后应变为 True 并返回 True
    res2 = mgr.toggle("测试角色B")
    assert res2 is True
    assert mgr.is_benched("测试角色B")

    # 持久化文件往返加载测试
    mgr_reloaded = BenchManager(bench_file)
    assert mgr_reloaded.count() == 1
    assert mgr_reloaded.is_benched("测试角色B")
    assert mgr_reloaded.get_all() == ["测试角色B"]


def test_bench_manager_corrupted_file(tmp_path):
    """测试文件损坏时 load 不抛出异常且保持为空集合"""
    corrupt_file = str(tmp_path / "corrupt_bench.json")
    with open(corrupt_file, "w", encoding="utf-8") as f:
        f.write("{invalid json content!!!")

    mgr = BenchManager(corrupt_file)
    assert mgr.count() == 0
    assert mgr.get_all() == []


def test_filter_out_benched_pure_function():
    """测试 filter_out_benched 纯函数在混合、空、全待选列表下的行为"""
    assert filter_out_benched([]) == []

    all_benched = [
        {"name": "测试角色A", "is_benched": True},
        {"name": "测试角色B", "is_benched": True},
    ]
    assert filter_out_benched(all_benched) == []

    mixed = [
        {"name": "测试角色A", "is_benched": False},
        {"name": "测试角色B", "is_benched": True},
        {"name": "测试角色C"},  # 无 is_benched 字段视为活跃
    ]
    res = filter_out_benched(mixed)
    assert len(res) == 2
    assert [c["name"] for c in res] == ["测试角色A", "测试角色C"]


def test_main_window_bench_filtering(qapp, tmp_path, monkeypatch):
    """测试 MainWindow 在勾选与不勾选'显示待选区'时的表格呈现与汇总条断言"""
    monkeypatch.setattr(MainWindow, "refresh_data", lambda self: None)

    bench_file = str(tmp_path / "bench.json")
    bench_mgr = BenchManager(bench_file)
    bench_mgr.add("测试角色B")

    mgr = JX3Manager(game_path=str(tmp_path))
    mgr.bench_mgr = bench_mgr

    chars = {
        "测试角色A": {
            "name": "测试角色A",
            "server": "测试区服A",
            "region": "测试大区",
            "force_name": "纯阳",
            "level": 120,
            "equip_score": 250000,
            "is_benched": False,
            "dungeon_cd": {},
            "baizhan_progress": {"killed": 5, "total": 12, "xiuluo": False},
        },
        "测试角色B": {
            "name": "测试角色B",
            "server": "测试区服A",
            "region": "测试大区",
            "force_name": "万花",
            "level": 120,
            "equip_score": 240000,
            "is_benched": True,
            "dungeon_cd": {},
            "baizhan_progress": {"killed": 2, "total": 12, "xiuluo": False},
        },
        "测试角色C": {
            "name": "测试角色C",
            "server": "测试区服A",
            "region": "测试大区",
            "force_name": "七秀",
            "level": 120,
            "equip_score": 260000,
            "is_benched": False,
            "dungeon_cd": {},
            "baizhan_progress": {"killed": 12, "total": 12, "xiuluo": True},
        },
    }
    mgr.characters = chars

    win = MainWindow(mgr)
    win.on_data_loaded(chars)

    # 1. 默认状态：未勾选'显示待选区角色'
    assert win.chk_show_bench.isChecked() is False
    assert win.table_roles.rowCount() == 2
    names_in_roles = [win.table_roles.item(r, 0).text() for r in range(win.table_roles.rowCount())]
    assert "测试角色A" in names_in_roles
    assert "测试角色C" in names_in_roles
    assert "测试角色B" not in names_in_roles
    assert "🪑 测试角色B" not in names_in_roles

    # 核心断言：汇总统计中角色总数必须为 2（排除待选角色）
    assert "角色总数 2" in win.lbl_cd_summary.text()

    # 待选区计数提示
    assert not win.btn_bench_count.isHidden()
    assert "待选区 1 人" in win.btn_bench_count.text()

    # 2. 勾选'显示待选区角色'
    win.chk_show_bench.setChecked(True)
    assert win.table_roles.rowCount() == 3
    names_in_roles_checked = [win.table_roles.item(r, 0).text() for r in range(win.table_roles.rowCount())]
    assert "🪑 测试角色B" in names_in_roles_checked

    # 核心断言：勾选后表格显示待选角色，但汇总统计依然只统计活跃角色（角色总数依然为 2）
    assert "角色总数 2" in win.lbl_cd_summary.text()

    # 取消勾选恢复
    win.chk_show_bench.setChecked(False)
    assert win.table_roles.rowCount() == 2
    assert "角色总数 2" in win.lbl_cd_summary.text()


def test_bench_manager_dialog(qapp, tmp_path, monkeypatch):
    """测试 BenchManagerDialog 列表展示及'全部移出'操作"""
    bench_file = str(tmp_path / "bench.json")
    bench_mgr = BenchManager(bench_file)
    bench_mgr.add("测试角色X")
    bench_mgr.add("测试角色Y")

    mgr = JX3Manager(game_path=str(tmp_path))
    mgr.bench_mgr = bench_mgr
    mgr.characters = {
        "测试角色X": {"name": "测试角色X", "is_benched": True},
        "测试角色Y": {"name": "测试角色Y", "is_benched": True},
    }

    dlg = BenchManagerDialog(mgr)
    assert dlg.list_bench.count() == 2
    assert not dlg.list_bench.isHidden()
    assert dlg.lbl_empty.isHidden()

    # 模拟用户点击"全部移出"并确认
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    dlg.remove_all_chars()

    assert dlg.list_bench.count() == 0
    assert not dlg.lbl_empty.isHidden()
    assert dlg.list_bench.isHidden()
    assert bench_mgr.count() == 0
    assert mgr.characters["测试角色X"]["is_benched"] is False
    assert mgr.characters["测试角色Y"]["is_benched"] is False
