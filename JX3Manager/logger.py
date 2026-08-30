"""
统一日志模块 - 替代 print，支持控制台+文件双输出、级别控制、自动轮转
"""
import logging
import logging.handlers
import os
from pathlib import Path

# 日志目录
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志格式
CONSOLE_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
FILE_FMT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"

# 单例缓存
_loggers = {}
_configured = False

def setup_logging(log_level="INFO"):
    """初始化全局日志配置（仅需调用一次）"""
    global _configured
    if _configured:
        return
    
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 根 logger
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    
    # 控制台 handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(CONSOLE_FMT, DATE_FMT))
    root.addHandler(console)
    
    # 通用文件 handler (所有级别)
    file_all = logging.handlers.RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8"
    )
    file_all.setLevel(logging.DEBUG)
    file_all.setFormatter(logging.Formatter(FILE_FMT, DATE_FMT))
    root.addHandler(file_all)
    
    # 错误专用文件 handler (ERROR+)
    file_err = logging.handlers.RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_err.setLevel(logging.ERROR)
    file_err.setFormatter(logging.Formatter(FILE_FMT, DATE_FMT))
    root.addHandler(file_err)
    
    _configured = True
    logging.getLogger(__name__).info(f"Logging initialized (level={log_level}, dir={LOG_DIR})")

def get_logger(name):
    """获取指定名称的 logger，自动初始化"""
    if not _configured:
        # 尝试从配置读取级别
        try:
            from config_loader import get_cached_config
            config = get_cached_config()
            level = config.get("log_level", "INFO")
        except:
            level = "INFO"
        setup_logging(level)
    
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]

# 便捷函数（兼容旧 print 调用风格）
def info(msg, *args, **kwargs):
    get_logger("app").info(msg, *args, **kwargs)

def debug(msg, *args, **kwargs):
    get_logger("app").debug(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    get_logger("app").warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    get_logger("app").error(msg, *args, **kwargs)

def exception(msg, *args, **kwargs):
    get_logger("app").exception(msg, *args, **kwargs)
