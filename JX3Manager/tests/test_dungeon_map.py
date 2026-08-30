import pytest
import os
import json
import tempfile
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from readers.dungeon_map import (
    DEFAULT_DUNGEON_NAMES,
    get_dungeon_names,
    load_dungeon_names,
    write_dungeon_names,
    learn_dungeon_names,
    LOG_PATTERN,
)
import readers.dungeon_map as dm


class TestDungeonMap:
    def test_log_pattern_match(self):
        # 正常首领名
        name1 = "2026-08-09-16-47-05-白帝江关(518)-首领1(70102).jcl"
        m1 = LOG_PATTERN.match(name1)
        assert m1 is not None
        assert m1.group(2) == "白帝江关"
        assert int(m1.group(3)) == 518

        # 首领名为空情况
        name2 = "2026-08-09-17-11-56-浪客行·苍离岛(527)-(103889).jcl"
        m2 = LOG_PATTERN.match(name2)
        assert m2 is not None
        assert m2.group(2) == "浪客行·苍离岛"
        assert int(m2.group(3)) == 527

    def test_priority_merging(self, monkeypatch, tmp_path):
        # 测试三层优先级合并
        test_data_dir = tmp_path / "data"
        test_data_dir.mkdir()
        user_file = test_data_dir / "dungeon_names.json"
        learned_file = test_data_dir / "dungeon_names_learned.json"

        monkeypatch.setattr(dm, "DATA_DIR", str(test_data_dir))
        monkeypatch.setattr(dm, "DUNGEON_NAMES_FILE", str(user_file))
        monkeypatch.setattr(dm, "DUNGEON_NAMES_LEARNED_FILE", str(learned_file))
        monkeypatch.setattr(dm, "_LEARNED_NAMES", {})
        monkeypatch.setattr(dm, "_LAST_MTIME", 0.0)

        # 1. 纯默认静态表
        names1 = get_dungeon_names()
        assert names1[299] == "武林通鉴·秘境"
        assert names1[341] == "武林通鉴·团队"
        assert 518 not in names1

        # 2. 模拟学习到新 ID 518，以及已有的 299(不同名字)
        dm._LEARNED_NAMES = {518: "白帝江关", 299: "狼牙堡·狼神殿"}
        names2 = get_dungeon_names()
        # 518 新增成功
        assert names2[518] == "白帝江关"
        # 299 静态表已有，学习结果不覆盖静态表
        assert names2[299] == "武林通鉴·秘境"

        # 3. 模拟人工覆盖 (dungeon_names.json)
        user_file.write_text(json.dumps({"341": "冰火岛·荒血路", "299": "人工指定狼神殿"}), encoding="utf-8")
        names3 = get_dungeon_names()
        # 341 被人工覆盖
        assert names3[341] == "冰火岛·荒血路"
        # 299 被人工覆盖
        assert names3[299] == "人工指定狼神殿"
        # 518 仍然来自学习
        assert names3[518] == "白帝江关"

    def test_learn_dungeon_names_flow(self, monkeypatch, tmp_path):
        test_my_data = tmp_path / "my_data"
        acc_dir = test_my_data / "user1@zhcn_hd" / "userdata" / "combat_logs"
        acc_dir.mkdir(parents=True)

        # 创建几个模拟战斗日志文件
        (acc_dir / "2026-08-01-12-00-00-白帝江关(518)-Boss1(101).jcl").write_text("dummy")
        (acc_dir / "2026-08-01-12-05-00-白帝江关(518)-Boss2(102).jcl").write_text("dummy")
        (acc_dir / "2026-08-01-12-10-00-测试副本(999)-Boss1(103).jcl").write_text("dummy")

        test_data_dir = tmp_path / "data"
        test_data_dir.mkdir()
        user_file = test_data_dir / "dungeon_names.json"
        learned_file = test_data_dir / "dungeon_names_learned.json"

        monkeypatch.setattr(dm, "DATA_DIR", str(test_data_dir))
        monkeypatch.setattr(dm, "DUNGEON_NAMES_FILE", str(user_file))
        monkeypatch.setattr(dm, "DUNGEON_NAMES_LEARNED_FILE", str(learned_file))
        monkeypatch.setattr(dm, "_LEARNED_NAMES", {})
        monkeypatch.setattr(dm, "_LAST_MTIME", 0.0)

        # 首次学习
        learned = learn_dungeon_names(str(test_my_data))
        assert learned[518] == "白帝江关"
        assert learned[999] == "测试副本"
        assert os.path.exists(str(learned_file))

        # 验证缓存写入
        with open(str(learned_file), "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["names"]["518"] == "白帝江关"

        # 二次调用应直接命中缓存
        learned2 = learn_dungeon_names(str(test_my_data))
        assert learned2[518] == "白帝江关"

    def test_write_dungeon_names(self, monkeypatch, tmp_path):
        test_data_dir = tmp_path / "data"
        test_data_dir.mkdir()
        user_file = test_data_dir / "dungeon_names.json"
        learned_file = test_data_dir / "dungeon_names_learned.json"

        monkeypatch.setattr(dm, "DATA_DIR", str(test_data_dir))
        monkeypatch.setattr(dm, "DUNGEON_NAMES_FILE", str(user_file))
        monkeypatch.setattr(dm, "DUNGEON_NAMES_LEARNED_FILE", str(learned_file))
        monkeypatch.setattr(dm, "_LEARNED_NAMES", {})
        monkeypatch.setattr(dm, "_LAST_MTIME", 0.0)

        assert write_dungeon_names(888, "自定义测试秘境") is True
        names = get_dungeon_names()
        assert names[888] == "自定义测试秘境"
