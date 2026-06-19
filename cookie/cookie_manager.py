"""
Cookie 管理器
=============
负责 B站 Cookie 的本地持久化存储与加载。
"""

import os
import json
import time
from typing import Optional


_THIS_DIR = os.path.dirname(os.path.dirname(__file__))
COOKIE_DIR = os.path.join(_THIS_DIR, "data")

# 备选路径（兼容服务器上多份插件副本的情况）
_ALT_ROOTS = []
for _p in ["/AstrBot/data/plugins/astrbot_plugin_text",
            "/bin/data/plugins/astrbot_plugin_text"]:
    if os.path.isdir(_p):
        _ALT_ROOTS.append(_p)

COOKIE_FILE = os.path.join(COOKIE_DIR, "bili_cookies.json")


def save_cookies(cookies: dict) -> str:
    """将 Cookie 字典保存到本地文件（写所有可能的位置）"""
    data = {
        "cookies": cookies,
        "saved_at": int(time.time()),
        "saved_at_str": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    dirs_to_write = {COOKIE_DIR}
    for root in _ALT_ROOTS:
        dirs_to_write.add(os.path.join(root, "data"))
    for d in dirs_to_write:
        os.makedirs(d, exist_ok=True)
        fp = os.path.join(d, "bili_cookies.json")
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return COOKIE_FILE


def load_cookies() -> Optional[dict]:
    """从本地文件加载 Cookie 字典，搜索多个可能位置"""
    paths_to_try = [COOKIE_FILE]
    for root in _ALT_ROOTS:
        if root != _THIS_DIR:
            paths_to_try.append(os.path.join(root, "data", "bili_cookies.json"))

    for fp in paths_to_try:
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("cookies")
            except (json.JSONDecodeError, KeyError):
                continue
    return None


def get_cookie_header() -> dict:
    """
    从本地加载 Cookie 并组装成请求头格式。
    返回 dict，可直接传入 requests 的 headers 或 Session 使用。
    """
    cookies = load_cookies()
    if not cookies:
        return {}
    # 拼成 "key1=value1; key2=value2" 格式
    return {"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}


def clear_cookies():
    """删除所有位置的 Cookie 文件"""
    paths = [COOKIE_FILE]
    for root in _ALT_ROOTS:
        if root != _THIS_DIR:
            paths.append(os.path.join(root, "data", "bili_cookies.json"))
    for fp in paths:
        if os.path.exists(fp):
            os.remove(fp)


def is_logged_in() -> bool:
    """检查是否已有登录态的 Cookie"""
    cookies = load_cookies()
    if not cookies:
        return False
    # 关键字段：SESSDATA 存在即视为已登录
    return bool(cookies.get("SESSDATA"))
