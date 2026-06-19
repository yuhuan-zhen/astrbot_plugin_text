"""
Bilibili 视频评论爬虫 (v4 — 全量爬取 + 子评论)
=================================================
功能：
  - 懒加载 API 爬取一级评论（热度和时间双模式合并去重）
  - 全量爬取每条评论下的所有子回复
  - 先轻量预览，再按需深入

API 参考: https://github.com/SocialSisterYi/bilibili-API-collect
"""

import time
import json
import requests
from typing import Optional, Callable
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from cookie import cookie_manager as cm



# ─── 常量 ────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}

# 全局 session + Cookie
_session = None


def _get_session() -> requests.Session:
    """获取带 Cookie 的全局 session（懒加载）"""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
        # 加载本地 Cookie
        cookies = cm.load_cookies()
        if cookies:
            _session.cookies.update(cookies)
        # 先访问首页获取临时 Cookie
        _session.get("https://www.bilibili.com/", timeout=10)
    return _session


COMMENT_TYPE_VIDEO = 1
MODE_HOT = 3          # 按热度
MODE_TIME = 2         # 按时间
REQUEST_INTERVAL = 0.3


# ─── 工具函数 ────────────────────────────────────────────────────────

def bv2aid(bvid: str) -> Optional[int]:
    """BV 号 → AV 号 (aid)"""
    url = "https://api.bilibili.com/x/web-interface/view"
    resp = requests.get(url, params={"bvid": bvid}, headers=HEADERS, timeout=10)
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"BV 转 AID 失败: {data.get('message', '未知错误')}")
    return data["data"]["aid"]


def parse_bv_or_aid(input_str: str) -> int:
    """自动识别 BV 号/AV 号/链接，返回 aid"""
    if "bilibili.com" in input_str:
        if "video/" in input_str:
            bv = input_str.split("video/")[1].split("?")[0].split("/")[0]
            return bv2aid(bv)
        raise ValueError("无法从链接中解析出视频 ID")
    if input_str.upper().startswith("BV"):
        return bv2aid(input_str.strip())
    aid_str = input_str.strip().lower().replace("av", "")
    if aid_str.isdigit():
        return int(aid_str)
    raise ValueError(f"无法解析视频标识符: {input_str}")


# ─── 一级评论：懒加载 API ──────────────────────────────────────────

def fetch_comments_page(oid: int, offset: str = "", mode: int = MODE_HOT) -> dict:
    """获取一页一级评论"""
    url = "https://api.bilibili.com/x/v2/reply/main"
    params = {
        "oid": oid, "type": COMMENT_TYPE_VIDEO, "mode": mode,
        "pagination_str": json.dumps({"offset": offset}),
    }
    resp = _get_session().get(url, params=params, timeout=10)
    if resp.status_code == 412:
        raise RuntimeError("API_BANNED")
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取评论失败: {data.get('message', '未知错误')}")

    page_data = data.get("data", {})
    cursor = page_data.get("cursor", {})
    pagination_reply = cursor.get("pagination_reply", {})

    return {
        "replies": page_data.get("replies", []),
        "offset": pagination_reply.get("next_offset", ""),
        "is_end": cursor.get("is_end", True),
        "all_count": cursor.get("all_count", 0),
    }


def _fetch_all_legacy(oid: int, max_pages: int, sort: int,
                      progress_callback: Callable = None) -> list:
    """旧版页码 API 降级方案"""
    all_replies = []
    for page in range(1, max_pages + 1):
        url = "https://api.bilibili.com/x/v2/reply"
        params = {"type": COMMENT_TYPE_VIDEO, "oid": oid,
                  "pn": page, "ps": 20, "sort": sort}
        resp = _get_session().get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            break
        replies = data.get("data", {}).get("replies", [])
        if not replies:
            break
        all_replies.extend(replies)
        if progress_callback:
            progress_callback(page, data.get("data", {}).get("page", {}).get("count", 0))
        # 判断是否还有下一页
        page_info = data.get("data", {}).get("page", {})
        if page_info.get("num", 0) * 20 >= page_info.get("count", 0):
            break
        time.sleep(REQUEST_INTERVAL)
    return all_replies


def fetch_all_comments(oid: int, max_pages: int = 200, mode: int = MODE_HOT,
                       progress_callback: Callable = None) -> list:
    """
    循环翻页获取一级评论。
    优先懒加载 API，遇 412 自动降级到旧版页码 API + Cookie。
    """
    try:
        return _fetch_all_lazy(oid, max_pages, mode, progress_callback)
    except RuntimeError as e:
        if "API_BANNED" in str(e):
            sort_val = 0 if mode == MODE_TIME else 2
            return _fetch_all_legacy(oid, max_pages, sort_val, progress_callback)
        raise


def _fetch_all_lazy(oid: int, max_pages: int, mode: int,
                    progress_callback: Callable = None) -> list:
    """新版懒加载分页"""
    all_replies = []
    offset = ""
    page = 0

    while page < max_pages:
        try:
            result = fetch_comments_page(oid, offset, mode)
            replies = result["replies"]
            if not replies:
                break
            all_replies.extend(replies)
            page += 1
            if progress_callback:
                progress_callback(page, result["all_count"])
            if result["is_end"] or not result["offset"]:
                break
            offset = result["offset"]
            time.sleep(REQUEST_INTERVAL)
        except Exception as e:
            print(f"[警告] 第 {page + 1} 页获取失败: {e}")
            break

    return all_replies


def fetch_all_comments_merged(oid: int, max_pages: int = 200,
                              progress_callback: Callable = None) -> list:
    """
    合并热度 + 时间排序，去重，拿到更多不重复评论。

    B 站 API 有深度限制（通常 ~44 页 ~900 条），
    但热度和时间排序的评论集合有差异，合并能拿到更多。
    """
    seen = set()

    def _dedup(replies):
        new = []
        for r in replies:
            rpid = r.get("rpid")
            if rpid not in seen:
                seen.add(rpid)
                new.append(r)
        return new

    # 先爬热度
    hot = fetch_all_comments(oid, max_pages, MODE_HOT, progress_callback)
    result = _dedup(hot)

    # 再爬时间
    time.sleep(REQUEST_INTERVAL)
    time_sorted = fetch_all_comments(oid, max_pages, MODE_TIME, progress_callback)
    result.extend(_dedup(time_sorted))

    return result


# ─── 子评论：页码 API ─────────────────────────────────────────────

def fetch_sub_comments_page(oid: int, root_rpid: int,
                            page: int = 1, page_size: int = 10) -> dict:
    """获取某条评论下的一页子回复"""
    url = "https://api.bilibili.com/x/v2/reply/reply"
    params = {
        "oid": oid, "type": COMMENT_TYPE_VIDEO,
        "root": root_rpid, "ps": page_size, "pn": page,
    }
    resp = _get_session().get(url, params=params, timeout=10)
    if resp.status_code == 412:
        raise RuntimeError("API_BANNED")
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取子评论失败: {data.get('message', '未知错误')}")

    page_data = data.get("data", {})
    page_info = page_data.get("page", {})
    total = page_info.get("count", 0)
    current = page_info.get("num", page)
    size = page_info.get("size", page_size)

    return {
        "replies": page_data.get("replies", []),
        "page": current,
        "total": total,
        "has_more": current * size < total,
    }


def fetch_all_sub_comments(oid: int, root_rpid: int,
                           max_pages: int = 50, page_size: int = 10) -> list:
    """获取某条评论下的全部子回复（自动翻页直到取完）"""
    all_replies = []
    page = 1

    while page <= max_pages:
        try:
            result = fetch_sub_comments_page(oid, root_rpid, page, page_size)
            replies = result["replies"]
            if not replies:
                break
            all_replies.extend(replies)
            if not result["has_more"]:
                break
            page += 1
            time.sleep(REQUEST_INTERVAL)
        except Exception as e:
            print(f"[警告] 子评论第 {page} 页获取失败: {e}")
            break

    return all_replies


# ─── 全量爬取（一级 + 全部子评论） ────────────────────────────────

def crawl_all(oid: int, max_main_pages: int = 200, max_sub_pages: int = 50,
              progress_callback: Callable = None) -> dict:
    """
    全量爬取：合并热度+时间主评论 → 展开每条评论的全部子回复。

    返回:
      {
        "main_count": 主评论数,
        "sub_count":  子评论总数,
        "total":      总条数,
        "main_replies": 带 sub_replies 字段的评论列表
      }
    """
    # 第一步：爬一级评论
    if progress_callback:
        progress_callback(0, 0, tag="main")

    main_replies = fetch_all_comments_merged(oid, max_main_pages,
        lambda p, c: progress_callback(p, c, tag="main") if progress_callback else None)

    # 第二步：爬子评论
    total_main = len(main_replies)
    sub_total = 0

    for i, reply in enumerate(main_replies):
        rpid = reply.get("rpid")
        rcount = reply.get("rcount", 0)
        if rcount > 0:
            try:
                subs = fetch_all_sub_comments(oid, rpid, max_pages=max_sub_pages)
                reply["sub_replies"] = subs
                sub_total += len(subs)
            except Exception as e:
                print(f"[跳过] 评论 {rpid} 子评论获取失败: {e}")
                reply["sub_replies"] = []
        else:
            reply["sub_replies"] = []

        if progress_callback:
            progress_callback(i + 1, total_main, tag="sub", sub_total=sub_total)

        time.sleep(REQUEST_INTERVAL * 0.5)

    return {
        "main_count": total_main,
        "sub_count": sub_total,
        "total": total_main + sub_total,
        "main_replies": main_replies,
    }


# ─── 独立爬子评论 ────────────────────────────────────────────────

def get_sub_comments(oid: int, rpid: int, max_pages: int = 20,
                     output_format: str = "text"):
    """专门爬取某条评论的全部子回复"""
    try:
        replies = fetch_all_sub_comments(oid, rpid, max_pages=max_pages)
        if output_format == "json":
            result = _subs_to_json(replies, rpid)
        elif output_format == "raw":
            result = json.dumps(replies, ensure_ascii=False, indent=2)
        else:
            result = _format_subs(replies, rpid)
        return True, result, len(replies)
    except Exception as e:
        return False, f"[错误] {e}", 0


# ─── 格式化 ──────────────────────────────────────────────────────────

def _format_subs(replies: list, rpid: int) -> str:
    lines = [f"--- 评论 #{rpid} 的子回复 ({len(replies)} 条) ---"]
    for i, sub in enumerate(replies, 1):
        member = sub.get("member", {})
        content = sub.get("content", {})
        ctime = sub.get("ctime", 0)
        t = time.strftime("%Y-%m-%d %H:%M", time.localtime(ctime))
        lines.append(
            f"  [{i}] {member.get('uname', '匿名')} ({t})\n"
            f"       {content.get('message', '')}"
        )
    return "\n".join(lines)


def _subs_to_json(replies: list, rpid: int) -> str:
    simplified = []
    for sub in replies:
        member = sub.get("member", {})
        content = sub.get("content", {})
        simplified.append({
            "rpid": sub.get("rpid"),
            "user": member.get("uname"),
            "uid": member.get("mid"),
            "time": sub.get("ctime"),
            "time_str": time.strftime("%Y-%m-%d %H:%M",
                                       time.localtime(sub.get("ctime", 0))),
            "content": content.get("message"),
            "likes": sub.get("like"),
            "parent_rpid": rpid,
        })
    return json.dumps(simplified, ensure_ascii=False, indent=2)


def format_comment(reply: dict, indent: int = 0, show_subs: bool = False) -> str:
    """格式化单条评论"""
    prefix = "  " * indent
    member = reply.get("member", {})
    content = reply.get("content", {})
    uname = member.get("uname", "匿名")
    message = content.get("message", "")
    likes = reply.get("like", 0)
    rpid = reply.get("rpid", 0)
    ctime = reply.get("ctime", 0)
    time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(ctime))

    lines = [
        f"{prefix}--- 评论 #{rpid} ---",
        f"{prefix} 用户: {uname}",
        f"{prefix} 时间: {time_str}",
        f"{prefix} 点赞: {likes}",
        f"{prefix} 内容: {message}",
    ]

    if show_subs:
        subs = reply.get("sub_replies", [])
        if subs:
            lines.append(f"{prefix}  |-> 子回复 ({len(subs)} 条):")
            for sub in subs[:10]:
                sub_member = sub.get("member", {})
                sub_content = sub.get("content", {})
                lines.append(
                    f'{prefix}      {sub_member.get("uname", "匿名")}: '
                    f'{sub_content.get("message", "")[:80]}'
                )
            if len(subs) > 10:
                lines.append(f"{prefix}      ... 还有 {len(subs) - 10} 条")
        elif reply.get("replies"):
            lines.append(f"{prefix}  |-> 回复 ({len(reply['replies'])} 条):")
            for sub in reply["replies"][:5]:
                sub_member = sub.get("member", {})
                sub_content = sub.get("content", {})
                lines.append(
                    f'{prefix}      {sub_member.get("uname", "匿名")}: '
                    f'{sub_content.get("message", "")}'
                )
            if len(reply["replies"]) > 5:
                lines.append(f"{prefix}      ... 还有 {len(reply['replies']) - 5} 条")
    else:
        rcount = reply.get("rcount", 0)
        subs = reply.get("sub_replies", [])
        actual = len(subs) if subs else rcount
        if actual:
            lines.append(f"{prefix}  |-> 子回复共 {actual} 条 (使用 --subs 展开)")

    return "\n".join(lines)


def format_all_comments(replies: list, show_subs: bool = False) -> str:
    lines = [f"共获取 {len(replies)} 条评论", "=" * 50]
    for i, reply in enumerate(replies, 1):
        lines.append(f"\n[{i}]")
        lines.append(format_comment(reply, show_subs=show_subs))
    return "\n".join(lines)


def comments_to_json(replies: list, filepath: str = None,
                     include_subs: bool = False) -> str:
    simplified = []
    for reply in replies:
        member = reply.get("member", {})
        content = reply.get("content", {})
        item = {
            "rpid": reply.get("rpid"),
            "user": member.get("uname"),
            "uid": member.get("mid"),
            "avatar": member.get("avatar"),
            "time": reply.get("ctime"),
            "time_str": time.strftime("%Y-%m-%d %H:%M",
                                       time.localtime(reply.get("ctime", 0))),
            "content": content.get("message"),
            "likes": reply.get("like"),
            "replies_count": reply.get("rcount", 0),
        }
        if include_subs:
            subs = reply.get("sub_replies", [])
            item["sub_replies"] = [
                {
                    "rpid": s.get("rpid"),
                    "user": s.get("member", {}).get("uname"),
                    "uid": s.get("member", {}).get("mid"),
                    "time": s.get("ctime"),
                    "content": s.get("content", {}).get("message"),
                    "likes": s.get("like"),
                }
                for s in subs
            ]
        simplified.append(item)

    json_str = json.dumps(simplified, ensure_ascii=False, indent=2)
    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json_str)
    return json_str


# ─── 对外统一接口 ──────────────────────────────────────────────────

def get_comments(input_str: str, max_pages: int = 200, sort: str = "hot",
                 output_format: str = "text", include_subs: bool = False,
                 sub_max_pages: int = 50, merge_both: bool = False):
    """
    对外统一接口。

    参数:
      input_str:     BV号 / AV号 / 链接
      max_pages:     每轮最多爬取页数（实际 API 可能提前结束）
      sort:          "hot" / "time"
      output_format: "text" / "json" / "raw"
      include_subs:  True=展开子回复
      sub_max_pages: 每条评论最多爬取子回复页数
      merge_both:    True=合并热度+时间排序去重，拿到更多评论
    """
    try:
        aid = parse_bv_or_aid(input_str)

        if merge_both:
            all_replies = fetch_all_comments_merged(aid, max_pages)
        else:
            mode = MODE_TIME if sort == "time" else MODE_HOT
            all_replies = fetch_all_comments(aid, max_pages=max_pages, mode=mode)

        # 如果需要子评论
        if include_subs:
            total_main = len(all_replies)
            for i, reply in enumerate(all_replies):
                rpid = reply.get("rpid")
                rcount = reply.get("rcount", 0)
                if rcount > 0:
                    try:
                        subs = fetch_all_sub_comments(aid, rpid, max_pages=sub_max_pages)
                        reply["sub_replies"] = subs
                    except Exception:
                        reply["sub_replies"] = []
                else:
                    reply["sub_replies"] = []
                time.sleep(REQUEST_INTERVAL * 0.5)

        if output_format == "json":
            result = comments_to_json(all_replies, include_subs=include_subs)
        elif output_format == "raw":
            result = json.dumps(all_replies, ensure_ascii=False, indent=2)
        else:
            result = format_all_comments(all_replies, show_subs=include_subs)

        return True, result, len(all_replies)

    except Exception as e:
        return False, f"[错误] {e}", 0


def get_comments_all(input_str: str, max_main_pages: int = 200,
                     max_sub_pages: int = 50, output_format: str = "text"):
    """
    全量爬取：合并热度+时间主评论 → 展开全部子评论 → 保存。

    返回 (是否成功, 数据字符串, 主评论数, 子评论数)
    """
    try:
        aid = parse_bv_or_aid(input_str)
        result = crawl_all(aid, max_main_pages, max_sub_pages)

        main_replies = result["main_replies"]

        if output_format == "json":
            data = comments_to_json(main_replies, include_subs=True)
        else:
            data = format_all_comments(main_replies, show_subs=True)

        return True, data, result["main_count"], result["sub_count"]

    except Exception as e:
        return False, f"[错误] {e}", 0, 0
