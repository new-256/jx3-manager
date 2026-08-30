import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from main import compute_baizhan_progress


class TestComputeBaizhanProgress:
    def _make_weekly_bosses(self, boss_names, week=1, start_ts=None, end_ts=None):
        now = datetime.now()
        if start_ts is None:
            start = (now - timedelta(days=now.weekday())).replace(hour=12, minute=0, second=0, microsecond=0)
            start_ts = int(start.timestamp())
        if end_ts is None:
            end_ts = int((datetime.fromtimestamp(start_ts) + timedelta(days=7)).timestamp())
        boss_list = [{"name": name} for name in boss_names]
        return {
            "week": week,
            "list": boss_list,
            "start": start_ts,
            "end": end_ts,
            "boss": boss_names[0] if boss_names else ""
        }

    def _make_fight(self, boss, time_str):
        return {"boss": boss, "time": time_str}

    def test_empty_fights_returns_none(self):
        weekly = self._make_weekly_bosses(["Boss1", "Boss2"])
        result = compute_baizhan_progress([], weekly)
        assert result is None

    def test_empty_weekly_bosses_returns_none(self):
        fights = [self._make_fight("Boss1", "2026-08-04-14-30-00")]
        result = compute_baizhan_progress(fights, {})
        assert result is None

    def test_none_weekly_bosses_returns_none(self):
        fights = [self._make_fight("Boss1", "2026-08-04-14-30-00")]
        result = compute_baizhan_progress(fights, None)
        assert result is None

    @freeze_time("2026-08-04 15:00:00")
    def test_practice_boss_excluded(self):
        weekly = self._make_weekly_bosses(["Boss1", "Boss2"])
        fights = [
            self._make_fight("剑圣幻影", "2026-08-04-14-30-00"),
            self._make_fight("Boss1", "2026-08-04-15-00-00"),
        ]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["killed"] == 1
        assert result["killed_bosses"] == ["Boss1"]

    @freeze_time("2026-08-04 15:00:00")
    def test_fight_before_week_start_excluded(self):
        weekly = self._make_weekly_bosses(["Boss1"])
        fights = [self._make_fight("Boss1", "2026-08-03-10-00-00")]
        result = compute_baizhan_progress(fights, weekly)
        assert result is None

    @freeze_time("2026-08-04 15:00:00")
    def test_fight_after_week_end_excluded(self):
        weekly = self._make_weekly_bosses(["Boss1"])
        fights = [self._make_fight("Boss1", "2026-08-11-14-00-00")]
        result = compute_baizhan_progress(fights, weekly)
        assert result is None

    @freeze_time("2026-08-04 15:00:00")
    def test_fight_within_week_counted(self):
        weekly = self._make_weekly_bosses(["Boss1", "Boss2"])
        fights = [
            self._make_fight("Boss1", "2026-08-04-14-30-00"),
            self._make_fight("Boss2", "2026-08-06-10-00-00"),
        ]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["killed"] == 2
        assert result["killed_in_roster"] == 2
        assert result["total"] == 2

    @freeze_time("2026-08-04 15:00:00")
    def test_duplicate_boss_deduplicated(self):
        weekly = self._make_weekly_bosses(["Boss1"])
        fights = [
            self._make_fight("Boss1", "2026-08-04-14-00-00"),
            self._make_fight("Boss1", "2026-08-04-15-00-00"),
            self._make_fight("Boss1", "2026-08-05-10-00-00"),
        ]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["killed"] == 1
        assert result["killed_bosses"] == ["Boss1"]

    @freeze_time("2026-08-04 15:00:00")
    def test_killed_in_roster_vs_unmatched(self):
        weekly = self._make_weekly_bosses(["BossA", "BossB"])
        fights = [
            self._make_fight("BossA", "2026-08-04-14-00-00"),
            self._make_fight("BossC", "2026-08-04-15-00-00"),
        ]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["killed"] == 2
        assert result["killed_in_roster"] == 1
        assert result["killed_bosses"] == ["BossA", "BossC"]
        assert result["unmatched"] == ["BossC"]

    @freeze_time("2026-08-04 15:00:00")
    def test_xiuluo_boss_marked(self):
        weekly = self._make_weekly_bosses(["XiuluoBoss", "NormalBoss"])
        fights = [self._make_fight("XiuluoBoss", "2026-08-04-14-00-00")]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["xiuluo"] is True

    @freeze_time("2026-08-04 15:00:00")
    def test_xiuluo_boss_not_killed_false(self):
        weekly = self._make_weekly_bosses(["XiuluoBoss", "NormalBoss"])
        fights = [self._make_fight("NormalBoss", "2026-08-04-14-00-00")]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["xiuluo"] is False

    @freeze_time("2026-08-04 15:00:00")
    def test_invalid_time_format_skipped(self):
        weekly = self._make_weekly_bosses(["Boss1"])
        fights = [
            self._make_fight("Boss1", "invalid-time"),
            self._make_fight("Boss1", "2026-08-04-14-00-00"),
        ]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["killed"] == 1

    @freeze_time("2026-08-04 15:00:00")
    def test_none_time_skipped(self):
        weekly = self._make_weekly_bosses(["Boss1"])
        fights = [
            {"boss": "Boss1", "time": None},
            self._make_fight("Boss1", "2026-08-04-14-00-00"),
        ]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["killed"] == 1

    @freeze_time("2026-08-04 15:00:00")
    def test_killed_bosses_ordered_by_time(self):
        weekly = self._make_weekly_bosses(["Boss1", "Boss2", "Boss3"])
        fights = [
            self._make_fight("Boss3", "2026-08-04-16-00-00"),
            self._make_fight("Boss1", "2026-08-04-14-00-00"),
            self._make_fight("Boss2", "2026-08-04-15-00-00"),
        ]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["killed_bosses"] == ["Boss1", "Boss2", "Boss3"]

    @freeze_time("2026-08-04 15:00:00")
    def test_weekly_bosses_deduplicated(self):
        weekly = self._make_weekly_bosses(["Boss1", "Boss1", "Boss2"])
        fights = [self._make_fight("Boss1", "2026-08-04-14-00-00")]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["total"] == 2
        assert result["killed_in_roster"] == 1

    @freeze_time("2026-08-04 15:00:00")
    def test_stale_weekly_bosses_filters_out_last_week_fights(self):
        # API cache is from last week (2026-07-27 12:00 ~ 2026-08-03 12:00)
        last_week_start = int(datetime(2026, 7, 27, 12, 0, 0).timestamp())
        last_week_end = int(datetime(2026, 8, 3, 12, 0, 0).timestamp())
        weekly = self._make_weekly_bosses(["Boss1", "Boss2"], week=1, start_ts=last_week_start, end_ts=last_week_end)
        
        # Fight happened last week (2026-07-28) and fight happened this week (2026-08-04)
        fights = [
            self._make_fight("Boss1", "2026-07-28-15-00-00"),
            self._make_fight("Boss2", "2026-08-04-14-00-00"),
        ]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["killed"] == 1
        assert result["killed_bosses"] == ["Boss2"]

    @freeze_time("2026-08-04 15:00:00")
    def test_stale_weekly_bosses_all_last_week_returns_none(self):
        last_week_start = int(datetime(2026, 7, 27, 12, 0, 0).timestamp())
        last_week_end = int(datetime(2026, 8, 3, 12, 0, 0).timestamp())
        weekly = self._make_weekly_bosses(["Boss1"], week=1, start_ts=last_week_start, end_ts=last_week_end)
        fights = [self._make_fight("Boss1", "2026-07-28-15-00-00")]
        result = compute_baizhan_progress(fights, weekly)
        assert result is None

    @freeze_time("2026-08-04 15:00:00")
    def test_fight_at_exact_monday_noon_counted(self):
        weekly = self._make_weekly_bosses(["Boss1"])
        fights = [self._make_fight("Boss1", "2026-08-03-12-00-00")]
        result = compute_baizhan_progress(fights, weekly)
        assert result is not None
        assert result["killed"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

