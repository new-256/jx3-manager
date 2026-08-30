# Config loader
import json, os, sys
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {"game_path": "", "api_key": "", "export_dir": "data", "auto_refresh_minutes": 30, "log_level": "INFO" }

def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
                config = json.load(fp)
                for k, v in DEFAULT_CONFIG.items():
                    config.setdefault(k, v)
                return config
        except Exception as e:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    global __config
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    __config = config.copy()

def validate_config(config):
    errors = []
    if not config.get("game_path"): errors.append("game_path missing")
    elif not os.path.exists(config["game_path"]): errors.append("game_path not exist")
    if not config.get("api_key"): errors.append("api_key missing")
    return errors

def get_config():
    config = load_config()
    # No blocking input() calls here. The frontend should handle missing configs.
    return config

__config = None
def get_cached_config():
    global __config
    if __config is None: __config = get_config()
    return __config
