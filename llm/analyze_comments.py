"""
评论 AI 分析模块
================
读取 data/json/ 下的评论，通过 AstrBot 内置 LLM 进行分析。
"""

import json
import glob
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "json")


def build_prompt_from_comments(data: dict, max_comments: int = 20,
                                custom_prompt: str = "") -> str:
    """将评论数据组装成 LLM 提示词"""
    comments = data.get("comments", [])
    lines = [f"视频: {data.get('video', '未知')}，共 {len(comments)} 条评论\n"]
    for i, c in enumerate(comments[:max_comments], 1):
        user = c.get("user", "匿名")
        content = c.get("content", "")
        likes = c.get("likes", 0)
        lines.append(f"{i}. {user}: {content} [赞{likes}]")
    lines.append("")
    if custom_prompt:
        lines.append(custom_prompt)
    else:
        lines.append("请总结以上B站评论：1. 整体情感倾向 2. 主要讨论话题 3. 高赞观点")
    return "\n".join(lines)


def find_latest_json() -> str | None:
    """返回 data/json/ 下最新的 JSON 文件路径"""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    return files[-1] if files else None


def load_latest_comments() -> dict | None:
    """加载最新的评论 JSON"""
    path = find_latest_json()
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
