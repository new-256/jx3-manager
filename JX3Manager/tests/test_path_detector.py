"""
单元测试：JX3Manager/path_detector.py 游戏路径自动检测模块
测试覆盖：
- is_valid_game_path 有效性判定
- 当前配置直接命中
- 配置路径填浅时向上推导
- 注册表分支探测（通过假枚举函数离线隔离）
- 常见路径兜底分支
- 兼容探测序列优先级
- 探测失败兜底返回
"""
import os
import sys
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import path_detector
from path_detector import is_valid_game_path, detect_game_path, _probe_root_candidates


@pytest.fixture
def fake_game_tree():
    """创建一个标准的剑网3假目录树 (root/bin/zhcn_hd/interface/my#data)"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = os.path.abspath(tmp_dir)
        interface_dir = os.path.join(root, "bin", "zhcn_hd", "interface")
        my_data = os.path.join(interface_dir, "my#data")
        os.makedirs(my_data, exist_ok=True)
        yield {
            "root": root,
            "interface_dir": os.path.normpath(interface_dir),
            "zhcn_hd_dir": os.path.normpath(os.path.join(root, "bin", "zhcn_hd")),
            "my_data": os.path.normpath(my_data)
        }


def test_is_valid_game_path(fake_game_tree):
    # 包含 my#data 目录的 interface 路径应有效
    assert is_valid_game_path(fake_game_tree["interface_dir"]) is True
    
    # 根目录、无 my#data 的目录应无效
    assert is_valid_game_path(fake_game_tree["root"]) is False
    assert is_valid_game_path(fake_game_tree["zhcn_hd_dir"]) is False
    assert is_valid_game_path("") is False
    assert is_valid_game_path(None) is False
    assert is_valid_game_path(os.path.join(fake_game_tree["root"], "non_exist")) is False


def test_is_valid_game_path_file_not_dir(tmp_path):
    # 如果 my#data 是一个普通文件而不是目录，则判定为无效
    dummy_file = tmp_path / "my#data"
    dummy_file.write_text("test")
    assert is_valid_game_path(str(tmp_path)) is False


def test_detect_from_current_config_exact(fake_game_tree):
    # 当传入的路径正是 interface_dir 时，直接返回（来源 "当前配置"）
    found, source = detect_game_path(fake_game_tree["interface_dir"])
    assert found == fake_game_tree["interface_dir"]
    assert source == "当前配置"


def test_detect_from_current_config_shallow_derivation(fake_game_tree):
    # 测试填浅一级：bin/zhcn_hd
    found, source = detect_game_path(fake_game_tree["zhcn_hd_dir"])
    assert found == fake_game_tree["interface_dir"]
    assert source == "配置目录推导"

    # 测试填浅至游戏根目录：root
    found2, source2 = detect_game_path(fake_game_tree["root"])
    assert found2 == fake_game_tree["interface_dir"]
    assert source2 == "配置目录推导"


def test_detect_from_registry_branch(fake_game_tree, monkeypatch):
    # 构造假注册表条目：指向 SeasunGame.exe
    launcher_exe = os.path.join(fake_game_tree["root"], "SeasunGame", "SeasunGame.exe")
    os.makedirs(os.path.dirname(launcher_exe), exist_ok=True)
    with open(launcher_exe, "w") as f:
        f.write("")

    mock_entries = [
        ("剑网3系列启动器", f'"{launcher_exe}",0'),
    ]
    monkeypatch.setattr(path_detector, "_scan_registry_entries", lambda: mock_entries)

    # 传入 None 作为当前路径，应该从注册表扫描并推导出真实 interface 路径
    found, source = detect_game_path(None)
    assert found == fake_game_tree["interface_dir"]
    assert source == "注册表(剑网3系列启动器)"


def test_detect_from_common_paths_branch(monkeypatch):
    # 模拟注册表未命中
    monkeypatch.setattr(path_detector, "_scan_registry_entries", lambda: [])

    with tempfile.TemporaryDirectory() as tmp_dir:
        # 在临时目录下构造驱动器根目录与常见相对路径
        # 例如 drive_dir / "游戏" / "JX3" / "bin" / "zhcn_hd" / "interface" / "my#data"
        drive_dir = os.path.abspath(tmp_dir)
        jx3_root = os.path.join(drive_dir, "游戏", "JX3")
        interface_dir = os.path.join(jx3_root, "bin", "zhcn_hd", "interface")
        os.makedirs(os.path.join(interface_dir, "my#data"), exist_ok=True)

        # Monkeypatch 常见盘符探测
        monkeypatch.setattr(path_detector, "COMMON_DRIVES", ["Z_MOCK"])
        
        # 拦截 os.path.exists 对模拟盘符的处理
        orig_exists = os.path.exists
        def mock_exists(path):
            if path.startswith("Z_MOCK:\\"):
                rel = path[len("Z_MOCK:\\"):]
                actual = os.path.join(drive_dir, rel)
                return orig_exists(actual)
            return orig_exists(path)

        orig_isdir = os.path.isdir
        def mock_isdir(path):
            if path.startswith("Z_MOCK:\\"):
                rel = path[len("Z_MOCK:\\"):]
                actual = os.path.join(drive_dir, rel)
                return orig_isdir(actual)
            return orig_isdir(path)

        monkeypatch.setattr(os.path, "exists", mock_exists)
        monkeypatch.setattr(os.path, "isdir", mock_isdir)

        found, source = detect_game_path(None)
        assert source == "常见路径"
        assert found is not None
        assert found.endswith(os.path.join("bin", "zhcn_hd", "interface"))


def test_probe_sequence_priority(tmp_path):
    # 兼容探测序列测试：
    # 1. 只有 bin/zhcn 时应匹配 bin/zhcn/interface
    root1 = tmp_path / "client1"
    dir1 = root1 / "bin" / "zhcn" / "interface" / "my#data"
    dir1.mkdir(parents=True)
    res1 = _probe_root_candidates(str(root1))
    assert res1 == str(root1 / "bin" / "zhcn" / "interface")

    # 2. 只有 interface 时应匹配 interface
    root2 = tmp_path / "client2"
    dir2 = root2 / "interface" / "my#data"
    dir2.mkdir(parents=True)
    res2 = _probe_root_candidates(str(root2))
    assert res2 == str(root2 / "interface")

    # 3. 根目录自身即包含 my#data
    root3 = tmp_path / "client3"
    dir3 = root3 / "my#data"
    dir3.mkdir(parents=True)
    res3 = _probe_root_candidates(str(root3))
    assert res3 == str(root3)


def test_detect_not_found(monkeypatch):
    # 注册表与常见路径均未命中
    monkeypatch.setattr(path_detector, "_scan_registry_entries", lambda: [])
    monkeypatch.setattr(path_detector, "COMMON_DRIVES", [])
    
    found, source = detect_game_path("/non/existent/path/xyz")
    assert found is None
    assert source == ""

# ===== 浅层全盘扫描分支（拷贝的绿色版游戏，无注册表） =====
from path_detector import _shallow_scan_drive

def test_shallow_scan_finds_copied_game(tmp_path, monkeypatch):
    """游戏拷贝到任意目录（无注册表记录）时，浅层扫描能通过 SeasunGame.exe 标记找到"""
    import os
    root = tmp_path / "我的备份" / "JX3"
    (root / "bin" / "zhcn_hd" / "interface" / "my#data").mkdir(parents=True)
    (root / "SeasunGame" ).mkdir()
    (root / "SeasunGame" / "SeasunGame.exe").write_text("stub")
    r = _shallow_scan_drive(str(tmp_path), max_depth=2)
    assert r and os.path.samefile(r, root / "bin" / "zhcn_hd" / "interface")

def test_shallow_scan_finds_by_bin_marker(tmp_path):
    """无 SeasunGame.exe 但有 bin/zhcn_hd 结构时也能命中"""
    root = tmp_path / "game" / "JX3"
    (root / "bin" / "zhcn_hd" / "interface" / "my#data").mkdir(parents=True)
    r = _shallow_scan_drive(str(tmp_path), max_depth=2)
    assert r is not None

def test_shallow_scan_skips_system_dirs(tmp_path):
    """Windows/Program Files 等系统目录不应被扫描"""
    import os
    sysdir = tmp_path / "Windows" / "游戏藏这也不该被扫" / "JX3"
    (sysdir / "bin" / "zhcn_hd" / "interface" / "my#data").mkdir(parents=True)
    r = _shallow_scan_drive(str(tmp_path), max_depth=2)
    assert r is None

def test_detect_full_pipeline_copied_game(tmp_path, monkeypatch):
    """端到端：无配置+无注册表，浅层扫描兜底命中拷贝的游戏"""
    import path_detector as pd
    monkeypatch.setattr(pd, "_scan_registry_entries", lambda: [])
    monkeypatch.setattr(pd, "COMMON_DRIVES", ["X"])
    # 把 X: 指到 tmp_path —— 通过替换 detect 内的盘符存在性检查
    monkeypatch.setattr(pd.os.path, "exists", lambda p: True if p == "X:\\" else __import__("os").path.exists(p))
    monkeypatch.setattr(pd, "_shallow_scan_drive", lambda drive_root, max_depth=2: str(tmp_path / "JX3" / "bin" / "zhcn_hd" / "interface") if drive_root == "X:\\" else None)
    (tmp_path / "JX3" / "bin" / "zhcn_hd" / "interface" / "my#data").mkdir(parents=True)
    src, source = pd.detect_game_path(None)
    assert src is not None and source == "全盘浅层扫描"
