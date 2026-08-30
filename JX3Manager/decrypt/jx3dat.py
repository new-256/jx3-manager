"""
JX3DAT Decryptor - AES-128解密模块
已知: KBaseX64.dll 使用 AES-128 加密 .jx3dat 文件
待完成: 找到正确的密钥
"""
import os, struct
from Crypto.Cipher import AES

# Candidate keys found near aes128_encrypt in KBaseX64.dll
CANDIDATE_KEYS = [
    b"abaabaabaaba\x00\x00\x00\x00",
    b"balabalabala\x00\x00\x00\x00",
]

def try_decrypt(filepath, key=None):
    """尝试解密 .jx3dat 文件"""
    with open(filepath, "rb") as f:
        data = f.read()
    
    results = []
    keys_to_try = [key] if key else CANDIDATE_KEYS
    
    for k in keys_to_try:
        # Pad data to 16-byte boundary for ECB
        padded = data + b'\x00' * (16 - len(data) % 16) if len(data) % 16 else data
        
        # Try ECB
        try:
            cipher = AES.new(k, AES.MODE_ECB)
            plain = cipher.decrypt(padded)
            if plain[:6] == b'return' or plain[:1] == b't':
                results.append(("ECB", k, plain))
        except: pass
        
        # Try CBC with first 16 bytes as IV
        if len(data) >= 32:
            try:
                iv = data[:16]
                ct = data[16:]
                pad_len = 16 - len(ct) % 16 if len(ct) % 16 else 0
                if pad_len: ct += b'\x00' * pad_len
                cipher = AES.new(k, AES.MODE_CBC, iv)
                plain = cipher.decrypt(ct)
                results.append(("CBC", k, plain[:50]))
            except: pass
    
    return results

def search_key_in_dll(dll_path):
    """Search for potential AES keys in DLL data sections"""
    with open(dll_path, "rb") as f:
        data = f.read()
    
    # Find aes128_encrypt location
    pos = data.find(b"aes128_encrypt")
    if pos < 0: return []
    
    # Extract surrounding bytes - look for 16-byte aligned constants
    candidates = []
    for offset in range(max(0, pos-256), min(len(data), pos+256)):
        # Check if 16 bytes at this offset could be a key
        chunk = data[offset:offset+16]
        if len(chunk) == 16:
            # Keys usually have high entropy
            unique = len(set(chunk))
            if unique >= 10:  # At least 10 unique bytes
                candidates.append((offset, chunk))
    
    return candidates
