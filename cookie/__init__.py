"""
Cookie 管理包
=============
提供 B站 Cookie 的扫码登录获取、本地持久化存储/加载功能。

模块：
  cookie_manager — Cookie 的本地读写（存/取/删/检查）
  bili_login    — B站扫码登录流程（生成二维码 → 轮询 → 获取 Cookie）
"""

from . import *
__all__ = ["cookie_manager", "bili_login"]
