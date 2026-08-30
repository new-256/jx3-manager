import os
import urllib.request
import json
import re

# Local storage directory for official JX3Box boss avatars
AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "boss_avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

_BOSS_DATA_CACHE = None

def fetch_jx3box_boss_metadata():
    """
    Fetch official boss metadata list from JX3Box API (https://node.jx3box.com/monster/boss)
    """
    global _BOSS_DATA_CACHE
    if _BOSS_DATA_CACHE:
        return _BOSS_DATA_CACHE

    url = "https://node.jx3box.com/monster/boss"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8")).get("data", [])
            _BOSS_DATA_CACHE = data
            return data
    except Exception as e:
        print(f"Error fetching JX3Box boss metadata: {e}")
        return []

def get_official_avatar_url(boss_item):
    """
    Construct exact official avatar URL based on JX3Box frontend formula:
    avatar = https://img.jx3box.com/pve/baizhan/{base_name}_{ImageFrame}.png
    """
    img_path = boss_item.get("ImagePath", "")
    frame = boss_item.get("ImageFrame", 0)

    if not img_path:
        return None

    match = re.search(r"\\([^\\]+)\.", img_path)
    if not match:
        return None

    base_name = match.group(1).lower()
    return f"https://img.jx3box.com/pve/baizhan/{base_name}_{frame}.png"

def download_boss_avatar(boss_name):
    """
    Download and cache the exact official JX3Box avatar image for a given boss name.
    """
    file_path = os.path.join(AVATAR_DIR, f"{boss_name}.png")

    bosses = fetch_jx3box_boss_metadata()
    match_items = [b for b in bosses if b.get("szName") == boss_name]

    if not match_items and "·" in boss_name:
        short_name = boss_name.split("·")[0]
        match_items = [b for b in bosses if b.get("szName") == short_name]

    if not match_items:
        return None

    match_item = match_items[0]
    avatar_url = get_official_avatar_url(match_item)
    if not avatar_url:
        return None

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        req = urllib.request.Request(avatar_url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status == 200:
                img_bytes = resp.read()
                if len(img_bytes) > 200:
                    with open(file_path, "wb") as f:
                        f.write(img_bytes)
                    return file_path
    except Exception as e:
        print(f"Failed to download avatar for {boss_name} from {avatar_url}: {e}")

    return None

def download_all_official_avatars(force=True):
    """
    Bulk download all official boss avatars from JX3Box into local cache.
    """
    bosses = fetch_jx3box_boss_metadata()
    results = {}
    print(f"Found {len(bosses)} boss records from JX3Box.")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for item in bosses:
        name = item.get("szName")
        if not name:
            continue

        file_path = os.path.join(AVATAR_DIR, f"{name}.png")
        if not force and os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
            results[name] = file_path
            continue

        avatar_url = get_official_avatar_url(item)
        if not avatar_url:
            continue

        try:
            req = urllib.request.Request(avatar_url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    img_bytes = resp.read()
                    if len(img_bytes) > 200:
                        with open(file_path, "wb") as f:
                            f.write(img_bytes)
                        results[name] = file_path
                        print(f"  ✓ {name} -> {avatar_url} ({len(img_bytes)} bytes)")
        except Exception:
            continue

    print(f"Successfully downloaded {len(results)} official boss avatars!")
    return results

if __name__ == "__main__":
    download_all_official_avatars(force=True)
