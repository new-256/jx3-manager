import os
import json
from logger import get_logger

logger = get_logger(__name__)

class BenchManager:
    def __init__(self, data_file=None):
        if data_file is None:
            data_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bench_chars.json")
        self.data_file = data_file
        self.benched = set()
        self.load()

    def load(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    benched_list = content.get("benched", [])
                    if isinstance(benched_list, list):
                        self.benched = {str(x) for x in benched_list if x}
                    else:
                        self.benched = set()
            except Exception as e:
                logger.warning(f"Failed to load bench chars: {e}")
                self.benched = set()
        else:
            self.benched = set()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump({
                    "benched": sorted(list(self.benched))
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save bench chars: {e}")

    def is_benched(self, name) -> bool:
        if not name:
            return False
        return name in self.benched

    def add(self, name) -> None:
        if not name:
            return
        if name not in self.benched:
            self.benched.add(name)
            self.save()

    def remove(self, name) -> None:
        if not name:
            return
        if name in self.benched:
            self.benched.remove(name)
            self.save()

    def toggle(self, name) -> bool:
        if self.is_benched(name):
            self.remove(name)
            return False
        else:
            self.add(name)
            return True

    def get_all(self) -> list[str]:
        return sorted(list(self.benched))

    def count(self) -> int:
        return len(self.benched)
