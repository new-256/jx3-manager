import os
import json
from datetime import datetime, timedelta
from logger import get_logger

logger = get_logger(__name__)

def get_week_reset_ts():
    """获取本周一 12:00 重置时间戳（若当前早于周一 12:00 则返回上周一 12:00）"""
    now = datetime.now()
    days_since_monday = now.weekday()
    last_monday = now - timedelta(days=days_since_monday)
    monday_12pm = last_monday.replace(hour=12, minute=0, second=0, microsecond=0)
    if now < monday_12pm:
        monday_12pm -= timedelta(days=7)
    return int(monday_12pm.timestamp())

def get_last_monday_7am_ts():
    """向后兼容别名：转调 get_week_reset_ts()"""
    return get_week_reset_ts()

class CharNotesManager:
    def __init__(self, data_file=None):
        if data_file is None:
            data_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "char_notes.json")
        self.data_file = data_file
        self.notes = {}
        self.last_reset = 0
        self.load()

    def load(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    self.notes = content.get("notes", {})
                    self.last_reset = content.get("last_reset", 0)
            except Exception as e:
                logger.error(f"Failed to load char notes: {e}")
                self.notes = {}
                self.last_reset = 0
        else:
            self.notes = {}
            self.last_reset = 0

        self.check_weekly_reset()

    def check_weekly_reset(self):
        cur_monday = get_week_reset_ts()
        if self.last_reset < cur_monday:
            logger.info("Weekly reset triggered for character notes (clearing weekly reset notes)...")
            for char_name, n_data in self.notes.items():
                if isinstance(n_data, dict):
                    n_data["weekly_note"] = ""
            self.last_reset = cur_monday
            self.save()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump({
                    "last_reset": self.last_reset,
                    "notes": self.notes
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save char notes: {e}")

    def get_note(self, char_name):
        n_data = self.notes.get(char_name, {})
        if isinstance(n_data, dict):
            return n_data.get("perm_note", ""), n_data.get("weekly_note", "")
        return "", ""

    def set_perm_note(self, char_name, text):
        if char_name not in self.notes or not isinstance(self.notes[char_name], dict):
            self.notes[char_name] = {"perm_note": "", "weekly_note": ""}
        self.notes[char_name]["perm_note"] = text
        self.save()

    def set_weekly_note(self, char_name, text):
        if char_name not in self.notes or not isinstance(self.notes[char_name], dict):
            self.notes[char_name] = {"perm_note": "", "weekly_note": ""}
        self.notes[char_name]["weekly_note"] = text
        self.save()
