"""
B站评论 → JSON 导出工具
======================
将爬取的评论保存为结构化的 JSON 文件。

用法:
  python save_json.py BV1k8LX64EpC           ← 导出全部评论
  python save_json.py BV1k8LX64EpC 10        ← 指定页数
"""

import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import bilibili_comment as bili


def save_comments_to_json(bv: str, max_pages: int = 200) -> str:
    """
    爬取评论并保存为 JSON 文件。

    参数:
        bv: BV号 / AV号 / 链接
        max_pages: 爬取页数

    返回:
        JSON 文件路径
    """
    # 爬取
    ok, data, main_count, sub_count = bili.get_comments_all(
        bv, max_main_pages=max_pages
    )
    if not ok:
        raise RuntimeError(f"爬取失败: {data}")

    # 重新获取 JSON 格式
    ok, json_str, mc, sc = bili.get_comments_all(
        bv, max_main_pages=max_pages, output_format="json"
    )
    if not ok:
        raise RuntimeError(f"JSON 生成失败: {json_str}")

    # 美化并保存
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "json")
    os.makedirs(data_dir, exist_ok=True)

    ts = int(time.time())
    filename = f"bili_{bv[:10]}_{ts}.json"
    filepath = os.path.join(data_dir, filename)

    parsed = json.loads(json_str)
    output = {
        "video": bv,
        "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "main_count": len(parsed),
        "comments": parsed,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return filepath


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python save_json.py <BV号> [页数]")
        print("示例: python save_json.py BV1k8LX64EpC")
        sys.exit(1)

    bv = sys.argv[1]
    pages = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 200

    print(f"正在爬取 {bv} ({pages}页)...")
    try:
        path = save_comments_to_json(bv, pages)
        print(f"[OK] 已保存到: {path}")
    except Exception as e:
        print(f"[失败] {e}")
