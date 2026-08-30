"""
JX3Manager - 游戏路径自动检测模块
提供剑网3游戏 interface 目录（包含 my#data）的自动探测与合法性校验。
"""
import os
import sys
from pathlib import Path

# 常见盘符与相对安装路径列表（便于单元测试 monkeypatch）
COMMON_DRIVES = ["C", "D", "E", "F", "G", "H"]
COMMON_SUBPATHS = [
    os.path.join("游戏", "JX3"),
    "JX3",
    "剑网3",
    "剑侠情缘3",
    os.path.join("Games", "JX3"),
    os.path.join("Game", "JX3"),
    os.path.join("Kingsoft", "JX3"),
    os.path.join("Program Files", "JX3"),
    os.path.join("Program Files (x86)", "JX3"),
]

# 探测子目录序列（按优先级从高到低）
PROBE_SUBDIRS = [
    os.path.join("bin", "zhcn_hd", "interface"),
    os.path.join("bin", "zhcn", "interface"),
    "interface",
    "",
]


def is_valid_game_path(p: str | Path | None) -> bool:
    """
    判断给定路径是否为有效的游戏 interface 路径。
    有效标准：路径存在，并且其下存在 my#data 子目录。
    """
    if not p:
        return False
    try:
        norm_p = os.path.normpath(str(p).strip().strip('"').strip("'"))
        if not os.path.isdir(norm_p):
            return False
        my_data = os.path.join(norm_p, "my#data")
        return os.path.isdir(my_data)
    except Exception:
        return False


def _probe_root_candidates(root_dir: str) -> str | None:
    """
    兼容探测序列：依次尝试以下子路径，返回第一个包含 my#data 的有效 interface 绝对路径：
    1. {根}/bin/zhcn_hd/interface
    2. {根}/bin/zhcn/interface
    3. {根}/interface
    4. {根} 本身
    """
    if not root_dir or not isinstance(root_dir, str):
        return None
    try:
        clean_root = os.path.normpath(root_dir.strip().strip('"').strip("'"))
        if not os.path.isdir(clean_root):
            return None
        
        for sub in PROBE_SUBDIRS:
            candidate = os.path.normpath(os.path.join(clean_root, sub)) if sub else clean_root
            if is_valid_game_path(candidate):
                return os.path.abspath(candidate)
    except Exception:
        pass
    return None


def _probe_path_with_parents(dir_path: str, max_depth: int = 3) -> str | None:
    """
    从指定目录开始，以及逐级向上 max_depth 级父目录，分别尝试兼容探测序列。
    """
    if not dir_path or not isinstance(dir_path, str):
        return None
    try:
        curr = os.path.normpath(dir_path.strip().strip('"').strip("'"))
        if not os.path.exists(curr):
            return None
        if os.path.isfile(curr):
            curr = os.path.dirname(curr)

        curr = os.path.abspath(curr)
        for _ in range(max_depth + 1):
            res = _probe_root_candidates(curr)
            if res:
                return res
            parent = os.path.dirname(curr)
            if parent == curr:  # 到达根目录
                break
            curr = parent
    except Exception:
        pass
    return None


def _scan_registry_entries() -> list[tuple[str, str]]:
    """
    扫描 Windows 注册表中的卸载项。
    返回列表: [(display_name, raw_path_str), ...]
    """
    entries = []
    try:
        import winreg
    except ImportError:
        return entries

    reg_roots = [
        (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
        (winreg.HKEY_CURRENT_USER, "HKCU")
    ]
    reg_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    access_flags = [
        winreg.KEY_READ,
    ]
    if hasattr(winreg, "KEY_WOW64_64KEY"):
        access_flags.append(winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
    if hasattr(winreg, "KEY_WOW64_32KEY"):
        access_flags.append(winreg.KEY_READ | winreg.KEY_WOW64_32KEY)

    seen_keys = set()
    for root_key, _ in reg_roots:
        for sub_path in reg_paths:
            for flag in access_flags:
                try:
                    with winreg.OpenKey(root_key, sub_path, 0, flag) as key:
                        num_subkeys = winreg.QueryInfoKey(key)[0]
                        for i in range(num_subkeys):
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                full_key_id = (root_key, sub_path, subkey_name)
                                if full_key_id in seen_keys:
                                    continue
                                seen_keys.add(full_key_id)

                                with winreg.OpenKey(key, subkey_name) as skey:
                                    try:
                                        display_name, _ = winreg.QueryValueEx(skey, "DisplayName")
                                        if not display_name or not isinstance(display_name, str):
                                            continue
                                        dn_lower = display_name.lower()
                                        if "剑网" in display_name or "jx3" in dn_lower:
                                            # 收集候选路径来源
                                            raw_cands = []
                                            for val_name in ("DisplayIcon", "InstallLocation", "UninstallString"):
                                                try:
                                                    val, _ = winreg.QueryValueEx(skey, val_name)
                                                    if val and isinstance(val, str):
                                                        raw_cands.append(val)
                                                except Exception:
                                                    pass
                                            for cand in raw_cands:
                                                entries.append((display_name.strip(), cand.strip()))
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                except Exception:
                    pass
    return entries


def _clean_path_candidate(raw_str: str) -> str:
    """清理包含图标索引、参数或引号的原始路径字符串"""
    if not raw_str:
        return ""
    s = raw_str.strip().strip('"').strip("'")
    # 去除 ,0 或 ,1 等图标索引后缀
    if "," in s:
        s = s.split(",")[0].strip().strip('"').strip("'")
    return s


# 浅层扫描的游戏根标记：出现任一即认为该目录可能是游戏根或启动器所在
_SHALLOW_MARKERS = ("SeasunGame.exe",)


def _shallow_scan_drive(drive_root: str, max_depth: int = 2) -> str | None:
    """
    在盘符根目录向下 max_depth 级目录内浅层扫描游戏标记（SeasunGame.exe / bin 目录）。
    命中后从标记位置向上回溯最多 4 级，逐级走探测序列找有效 interface。
    深度受限保证耗时可控；任何异常静默跳过。
    """
    if not drive_root or not os.path.isdir(drive_root):
        return None
    try:
        marker_hits = []
        curr_depth = 0
        # os.walk 浅层遍历：限制向下层级
        for dirpath, dirnames, filenames in os.walk(drive_root):
            depth = dirpath[len(drive_root):].count(os.sep)
            if depth > max_depth:
                dirnames[:] = []
                continue
            # 跳过明显的系统/噪声目录，减少无效遍历
            dirnames[:] = [
                d for d in dirnames
                if d.lower() not in (
                    "$recycle.bin", "windows", "program files", "program files (x86)",
                    "programdata", "appdata", "system volume information",
                    "node_modules", "__pycache__",
                )
            ]
            for marker in _SHALLOW_MARKERS:
                if marker in filenames:
                    marker_hits.append(dirpath)
            # 直接命中 bin 目录（游戏根特征）也记为候选
            if "bin" in dirnames and os.path.isdir(os.path.join(dirpath, "bin", "zhcn_hd")):
                marker_hits.append(dirpath)
            if len(marker_hits) >= 8:  # 足够多的候选即可提前结束
                break

        # 从每个标记位置向上回溯，尝试探测序列
        seen = set()
        for hit in marker_hits:
            result = _probe_path_with_parents(hit, max_depth=4)
            if result and result not in seen:
                return result
    except Exception:
        pass
    return None


def detect_game_path(current_path: str | None = None) -> tuple[str | None, str]:
    """
    自动检测剑网3客户端 interface 目录路径。

    探测顺序：
    a) 当前配置的 game_path 若已含 my#data 直接返回（来源 "当前配置"）；
    b) 当前配置路径的父目录逐级向上 3 级内找 my#data（来源 "配置目录推导"）；
    c) 注册表扫描（来源形如 "注册表(剑网3系列启动器)"）；
    d) 常见路径兜底（来源 "常见路径"）。

    返回:
      (interface_path, source_desc) 或 (None, "")
    """
    # a) 当前配置检测
    if current_path:
        try:
            if is_valid_game_path(current_path):
                return (os.path.normpath(os.path.abspath(current_path)), "当前配置")
        except Exception:
            pass

        # b) 当前配置推导（向上 3 级内）
        try:
            derived = _probe_path_with_parents(current_path, max_depth=3)
            if derived:
                return (derived, "配置目录推导")
        except Exception:
            pass

    # c) 注册表扫描
    try:
        entries = _scan_registry_entries()
        for display_name, raw_cand in entries:
            clean_cand = _clean_path_candidate(raw_cand)
            if not clean_cand:
                continue
            found = _probe_path_with_parents(clean_cand, max_depth=3)
            if found:
                return (found, f"注册表({display_name})")
    except Exception:
        pass

    # d) 常见路径兜底
    try:
        available_drives = [d for d in COMMON_DRIVES if os.path.exists(f"{d}:\\")] or COMMON_DRIVES
        for drive in available_drives:
            drive_root = f"{drive}:\\"
            for sub in COMMON_SUBPATHS:
                target_root = os.path.join(drive_root, sub)
                found = _probe_root_candidates(target_root)
                if found:
                    return (found, "常见路径")
    except Exception:
        pass

    # e) 浅层全盘扫描（拷贝到任意目录的绿色版游戏，无注册表记录时的最后手段）
    #    限制深度：盘符根目录向下最多 2 级目录内寻找 SeasunGame.exe 游戏启动器标记，
    #    命中后从启动器位置向上回溯找游戏根再走探测序列；目录深度可控，耗时可接受。
    try:
        available_drives = [d for d in COMMON_DRIVES if os.path.exists(f"{d}:\\")]
        for drive in available_drives:
            drive_root = f"{drive}:\\"
            found = _shallow_scan_drive(drive_root, max_depth=2)
            if found:
                return (found, "全盘浅层扫描")
    except Exception:
        pass

    return (None, "")
