"""
B站扫码登录
===========
通过 B 站官方 OAuth 流程，生成二维码 → 用户扫码 → 获取 Cookie。

流程：
  1. 调用生成二维码 API → 获得二维码图片URL + qrcode_key
  2. 下载二维码并保存为本地图片
  3. 轮询扫码状态 API，直到用户扫码并确认
  4. 从响应中提取 Cookie（SESSDATA / bili_jct / DedeUserID）
  5. 保存到本地 cookie_manager

API 参考: https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/login/login_action/QRCode.md
"""

import time
import json
import requests
from typing import Optional
from io import BytesIO
from . import cookie_manager as cm

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"

# 扫码状态码
QR_NOT_SCANNED = 86101   # 未扫码
QR_SCANNED = 86090       # 已扫码待确认
QR_EXPIRED = 86038       # 二维码过期
QR_CONFIRMED = 0         # 已确认（登录成功）


def generate_qrcode() -> Optional[dict]:
    """
    第一步：请求 B 站生成二维码。

    返回:
      {
        "url":        二维码图片 URL（用于下载/展示）
        "qrcode_key": 轮询用的 key
        "image_path": 本地保存的二维码图片路径
        "session":    requests.Session（用于后续轮询）
      }
    或 None（失败时）
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    # 先访问首页获取初始 Cookie
    session.get("https://www.bilibili.com/", timeout=10)

    resp = session.get(QR_GENERATE_URL, timeout=10)
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"生成二维码失败: HTTP {resp.status_code}, 响应: {resp.text[:200]}")

    if data.get("code") != 0:
        raise RuntimeError(f"生成二维码失败: {data.get('message', '未知错误')}")

    url = data["data"]["url"]
    qrcode_key = data["data"]["qrcode_key"]

    # 用 URL 生成二维码图片
    import qrcode
    import os
    img_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    os.makedirs(img_dir, exist_ok=True)
    img_path = os.path.join(img_dir, "bili_qrcode.png")

    qr_img = qrcode.make(url)
    qr_img.save(img_path)

    return {
        "url": url,
        "qrcode_key": qrcode_key,
        "image_path": img_path,
        "session": session,  # 保留 session 用于后续轮询
    }


def poll_login(qrcode_key: str, session: requests.Session,
               timeout: int = 120, interval: float = 1.5) -> Optional[dict]:
    """
    第二步：轮询扫码状态，直到用户扫码确认或超时。

    参数:
      qrcode_key: generate_qrcode 返回的 key
      session:    generate_qrcode 返回的 session（保持 Cookie 连贯）
      timeout:    超时秒数（默认 120 秒）
      interval:   轮询间隔秒数（默认 1.5 秒）

    返回:
      {
        "cookies": 登录后的 Cookie 字典,
        "status":  "success" / "expired" / "timeout"
      }
    """
    start = time.time()

    while time.time() - start < timeout:
        resp = session.get(QR_POLL_URL, params={"qrcode_key": qrcode_key}, timeout=10)
        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(f"轮询失败: HTTP {resp.status_code}, 响应: {resp.text[:200]}")

        if data.get("code") != 0:
            raise RuntimeError(f"轮询失败: {data.get('message', '未知错误')}")

        poll_data = data.get("data", {})
        code = poll_data.get("code", -1)

        if code == QR_CONFIRMED:
            # 登录成功！Cookie 在返回的 url 参数里
            from urllib.parse import unquote, parse_qs
            login_url = poll_data.get("url", "")
            cookies = {}
            if "?" in login_url:
                qs = login_url.split("?", 1)[1]
                for kv in qs.split("&"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        if k in ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid"):
                            cookies[k] = unquote(v)
            # 补充 session 里的其他 cookie（buvid3 等）
            cookies.update(dict(session.cookies.get_dict()))
            return {"cookies": cookies, "status": "success", "raw": poll_data}

        elif code == QR_EXPIRED:
            return {"status": "expired", "cookies": None}

        # code == QR_NOT_SCANNED or QR_SCANNED，继续轮询
        # 可选输出提示信息
        # print(poll_data.get("message", ""))

        time.sleep(interval)

    return {"status": "timeout", "cookies": None}


async def async_poll_login(qrcode_key: str, session: requests.Session,
                           timeout: int = 120, interval: float = 1.5,
                           progress_callback=None) -> dict:
    """
    异步轮询扫码状态（不阻塞事件循环）。

    参数:
      progress_callback(msg) — 每次轮询后回调，用于 bot 输出进度
    """
    import asyncio
    start = time.time()

    while time.time() - start < timeout:
        resp = session.get(QR_POLL_URL, params={"qrcode_key": qrcode_key}, timeout=10)
        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(f"轮询失败: HTTP {resp.status_code}, 响应: {resp.text[:200]}")

        if data.get("code") != 0:
            raise RuntimeError(f"轮询失败: {data.get('message', '未知错误')}")

        poll_data = data.get("data", {})
        code = poll_data.get("code", -1)

        if code == QR_CONFIRMED:
            from urllib.parse import unquote, parse_qs
            login_url = poll_data.get("url", "")
            cookies = {}
            if "?" in login_url:
                qs = login_url.split("?", 1)[1]
                for kv in qs.split("&"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        if k in ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid"):
                            cookies[k] = unquote(v)
            cookies.update(dict(session.cookies.get_dict()))
            return {"cookies": cookies, "status": "success", "raw": poll_data}

        elif code == QR_EXPIRED:
            return {"status": "expired", "cookies": None}

        # 进度回调
        if progress_callback:
            msg = poll_data.get("message", "")
            await progress_callback(msg)

        await asyncio.sleep(interval)

    return {"status": "timeout", "cookies": None}


async def async_full_login_flow(timeout: int = 120, progress_callback=None) -> dict:
    """
    异步完整扫码登录流程（不阻塞事件循环）。
    """
    try:
        qr = generate_qrcode()
        if not qr:
            return {"success": False, "message": "生成二维码失败"}

        if progress_callback:
            await progress_callback("二维码已生成，请用 Bilibili App 扫码")

        result = await async_poll_login(
            qr["qrcode_key"], qr["session"],
            timeout=timeout, progress_callback=progress_callback,
        )

        if result["status"] == "success":
            save_path = cm.save_cookies(result["cookies"])
            return {
                "success": True,
                "message": f"登录成功！Cookie 已保存",
                "image_path": qr["image_path"],
                "cookies": result["cookies"],
            }
        elif result["status"] == "expired":
            return {"success": False, "message": "二维码已过期，请重新生成", "image_path": qr["image_path"]}
        else:
            return {"success": False, "message": f"登录超时（{timeout}秒），请重试", "image_path": qr["image_path"]}

    except Exception as e:
        return {"success": False, "message": f"登录失败: {e}"}


def full_login_flow(timeout: int = 120) -> dict:
    """
    完整扫码登录流程：生成二维码 → 等待扫码 → 保存 Cookie。

    返回:
      {
        "success": True/False,
        "image_path": 二维码图片路径（用于展示）,
        "message":   提示信息,
        "cookies":   Cookie 字典（成功时）,
      }
    """
    try:
        # 1. 生成二维码
        qr = generate_qrcode()
        if not qr:
            return {"success": False, "message": "生成二维码失败"}

        # 2. 轮询
        result = poll_login(qr["qrcode_key"], qr["session"], timeout=timeout)

        if result["status"] == "success":
            # 3. 保存 Cookie
            save_path = cm.save_cookies(result["cookies"])
            return {
                "success": True,
                "message": f"登录成功！Cookie 已保存到 {save_path}",
                "image_path": qr["image_path"],
                "cookies": result["cookies"],
            }

        elif result["status"] == "expired":
            return {
                "success": False,
                "message": "二维码已过期，请重新生成",
                "image_path": qr["image_path"],
            }

        else:
            return {
                "success": False,
                "message": f"登录超时（{timeout}秒），请重试",
                "image_path": qr["image_path"],
            }

    except Exception as e:
        return {"success": False, "message": f"登录失败: {e}"}


# ─── 独立运行 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  B站扫码登录工具")
    print("=" * 50)
    print("  1. 生成二维码")
    print("  2. 打开 Bilibili App 扫码")
    print("  3. 确认登录")
    print("=" * 50)

    result = full_login_flow(timeout=120)

    if result.get("image_path"):
        print(f"\n二维码已保存到: {result['image_path']}")
        print("请用 Bilibili App 扫描该二维码图片")

    print(f"\n结果: {result.get('message')}")

    if result.get("success"):
        cookies = result["cookies"]
        print(f"\nSESSDATA: {cookies.get('SESSDATA', '')[:20]}...")
        print(f"bili_jct: {cookies.get('bili_jct', '')[:10]}...")
        print(f"DedeUserID: {cookies.get('DedeUserID', '')}")
