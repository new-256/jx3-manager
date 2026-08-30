import os
import sys
import json
import pytest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from main import (
    filter_cd_dungeon_ids,
    load_huanjiang_points,
    load_huanjiang_points_full,
    save_huanjiang_points,
    JX3Manager,
)

DUNGEON_NAMES_MOCK = {
    299: "武林通鉴·秘境",
    482: "武林通鉴·团队秘境",
    562: "百战异闻录",
    586: "范阳夜变",
    636: "25人英雄敖龙岛",
    793: "阆风悬城",
    794: "25人普通冰火岛·荒血路",
    795: "白帝江关",
    999: "副本999",
}

def test_filter_cd_dungeon_ids_default_hidden():
    sorted_dids = [299, 482, 562, 586, 636, 793, 794, 795, 999]
    raid_names = ["阆风悬城", "冰火岛·荒血路", "白帝江关"]

    visible, hidden = filter_cd_dungeon_ids(
        sorted_dids,
        dungeon_names=DUNGEON_NAMES_MOCK,
        raid_names=raid_names,
        show_legacy=False
    )

    # 562 excluded
    assert 562 not in visible and 562 not in hidden
    # 299, 482 (武林通鉴) should be visible
    assert 299 in visible
    assert 482 in visible
    # 793 (阆风悬城), 794 (25人普通冰火岛·荒血路), 795 (白帝江关) should be visible
    assert 793 in visible
    assert 794 in visible
    assert 795 in visible
    # 586 (范阳夜变), 636 (25人英雄敖龙岛), 999 (副本999) should be hidden
    assert 586 in hidden
    assert 636 in hidden
    assert 999 in hidden
    assert set(visible + hidden) == {299, 482, 586, 636, 793, 794, 795, 999}

def test_filter_cd_dungeon_ids_show_legacy():
    sorted_dids = [299, 482, 562, 586, 636, 793, 794, 795, 999]
    raid_names = ["阆风悬城", "冰火岛·荒血路", "白帝江关"]

    visible, hidden = filter_cd_dungeon_ids(
        sorted_dids,
        dungeon_names=DUNGEON_NAMES_MOCK,
        raid_names=raid_names,
        show_legacy=True
    )

    assert 562 not in visible
    assert hidden == []
    assert visible == [299, 482, 586, 636, 793, 794, 795, 999]

def test_filter_cd_dungeon_ids_empty_raid():
    sorted_dids = [299, 586, 793]
    visible, hidden = filter_cd_dungeon_ids(
        sorted_dids,
        dungeon_names=DUNGEON_NAMES_MOCK,
        raid_names=[],
        show_legacy=False
    )
    assert visible == [299]
    assert hidden == [586, 793]

def test_huanjiang_compatibility_and_timestamps(monkeypatch, tmp_path):
    test_json = tmp_path / "huanjiang_test.json"
    
    # 1. Write legacy format (int values)
    legacy_data = {
        "角色A": 50,
        "角色B": 100
    }
    with open(test_json, "w", encoding="utf-8") as f:
        json.dump(legacy_data, f)

    import main
    monkeypatch.setattr(main, "HUANJIANG_PATH", str(test_json))

    # Test load_huanjiang_points backward compatibility
    compat = load_huanjiang_points()
    assert compat == {"角色A": 50, "角色B": 100}

    # Test load_huanjiang_points_full with legacy data
    full = load_huanjiang_points_full()
    assert full["角色A"]["points"] == 50
    assert full["角色A"]["updated_at"] is None
    assert full["角色B"]["points"] == 100
    assert full["角色B"]["updated_at"] is None

    # Test update_huanjiang_points
    mgr = JX3Manager()
    mgr.characters = {
        "角色A": {"name": "角色A"},
        "角色C": {"name": "角色C"}
    }
    mgr.update_huanjiang_points("角色A", 88)

    assert mgr.characters["角色A"]["huanjiang_points"] == 88
    assert mgr.characters["角色A"]["huanjiang_updated_at"] is not None

    # Verify JSON file has been migrated to new structure
    with open(test_json, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["角色A"]["points"] == 88
    assert saved["角色A"]["updated_at"] is not None
    # 角色B was preserved
    assert saved["角色B"]["points"] == 100

    # Test load_huanjiang_points with new structure
    compat2 = load_huanjiang_points()
    assert compat2["角色A"] == 88
    assert compat2["角色B"] == 100
