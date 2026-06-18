"""
Cookie 管理器
=============
负责 B站 Cookie 的本地持久化存储与加载。
"""

import os
import json
import time
from typing import Optional


COOKIE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
COOKIE_FILE = os.path.join(COOKIE_DIR, "bili_cookies.json")


def save_cookies(cookies: dict) -> str:
    """将 Cookie 字典保存到本地文件"""
    os.makedirs(COOKIE_DIR, exist_ok=True)
    data = {
        "cookies": cookies,
        "saved_at": int(time.time()),
        "saved_at_str": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return COOKIE_FILE


def load_cookies() -> Optional[dict]:
    """从本地文件加载 Cookie 字典，文件不存在时返回 None"""
    if not os.path.exists(COOKIE_FILE):
        return None
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("cookies")
    except (json.JSONDecodeError, KeyError):
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
    """删除本地 Cookie 文件"""
    if os.path.exists(COOKIE_FILE):
        os.remove(COOKIE_FILE)


def is_logged_in() -> bool:
    """检查是否已有登录态的 Cookie"""
    cookies = load_cookies()
    if not cookies:
        return False
    # 关键字段：SESSDATA 存在即视为已登录
    return bool(cookies.get("SESSDATA"))
