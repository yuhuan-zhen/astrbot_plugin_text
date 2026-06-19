from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import File, Plain
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from core import bilibili_comment as bili
from cookie import bili_login
from astrbot.api import AstrBotConfig



@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):  # AstrBotConfig 继承自 Dict，拥有字典的所有方法
        super().__init__(context)
        self.config = config
        # 支持直接保存配置
        # self.config.save_config() # 保存配置
    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!") # 发送一条纯文本消息

    @filter.command("yuhuan")
    async def getuid(self,event: AstrMessageEvent):
        user_name = event.get_sender_id()
        if user_name == "yuhuan":
            yield event.plain_result("yuhuan1")
        else:
            yield event.plain_result(event.get_sender_id()+'123')

    # @filter.event_message_type(filter.EventMessageType.ALL)
    # async def jianting(self, event: AstrMessageEvent):
    #     yield event.plain_result('成功')


    @filter.command("bilicomment")
    async def bilicomment(self, event: AstrMessageEvent):
        """爬取B站评论 → 存CSV → 发送 → 删除"""
        import os, csv, json, time

        # 读取配置
        default_pages = self.config.get("default_pages", 5)
        include_subs = self.config.get("include_subs", False)
        sort_by = self.config.get("sort_by", "hot")

        bv = event.message_str.replace("bilicomment", "").strip()
        parts = bv.split()
        bv = parts[0] if parts else bv
        pages = default_pages

        # 命令行参数覆盖配置
        for p in parts[1:]:
            if p.isdigit():
                pages = int(p)
            elif p == "--subs":
                include_subs = True

        if not bv:
            yield event.plain_result(
                f"用法: /bilicomment BV号\n"
                f"当前配置: {pages}页, {'展开子评论' if include_subs else '仅主评论'}, 排序:{sort_by}"
            )
            return

        yield event.plain_result(f"正在爬取 {bv} 的评论... ({pages}页, {sort_by})")
        ok, data, main_count, sub_count = bili.get_comments_all(
            bv, max_main_pages=pages
        )

        if not ok:
            yield event.plain_result(f"爬取失败: {data}")
            return

        # 存 CSV
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)

        ts = int(time.time())
        csv_name = f"bili_{bv[:10]}_{ts}.csv"
        csv_path = os.path.join(data_dir, csv_name)

        # 从 get_comments_all 拿到的 data 里提取评论
        # data 是 format_all_comments 返回的可读文本，需要重新调 JSON 接口拿结构化数据
        ok2, json_data, mc, sc = bili.get_comments_all(bv, output_format="json")
        if not ok2:
            yield event.plain_result(f"评论爬取成功，但CSV生成失败: {json_data}")
            return

        import json as _json
        comments = _json.loads(json_data)

        import stat
        _csv_fd = os.open(csv_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                          stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        with os.fdopen(_csv_fd, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["层级", "rpid", "用户", "UID", "评论内容", "点赞数", "时间", "所属主评论"])
            for c in comments:
                writer.writerow([
                    "主评论",
                    c.get("rpid", ""),
                    c.get("user", ""),
                    c.get("uid", ""),
                    c.get("content", "").replace("\n", " "),
                    c.get("likes", 0),
                    c.get("time_str", ""),
                    "",
                ])
                for sub in c.get("sub_replies", []):
                    writer.writerow([
                        "子回复",
                        sub.get("rpid", ""),
                        sub.get("user", ""),
                        sub.get("uid", ""),
                        sub.get("content", "").replace("\n", " "),
                        sub.get("likes", 0),
                        sub.get("time_str", ""),
                        c.get("rpid", ""),
                    ])

        # 发送 CSV 文件（注册到文件服务，go-cqhttp 通过 HTTP 下载）
        try:
            from astrbot.core import file_token_service
            import socket
            token = await file_token_service.register_file(csv_path, timeout=120)
            host_ip = socket.gethostbyname(socket.gethostname())
            file_url = f"http://{host_ip}:6185/api/file/{token}"
            from astrbot.core.message.message_event_result import MessageEventResult
            result = MessageEventResult()
            result.chain = [
                Plain(f"共 {main_count} 条主评论 + {sub_count} 条子评论"),
                File(name=csv_name, url=file_url),
            ]
            event.set_result(result)
            yield
        except Exception as e:
            yield event.plain_result(f"评论已爬取 ({main_count}+{sub_count}条)，但文件发送失败: {e}\n文件保留在: {csv_path}")
            return

        # 同时保存 JSON
        json_dir = os.path.join(os.path.dirname(__file__), "data", "json")
        os.makedirs(json_dir, exist_ok=True)
        json_name = f"bili_{bv[:10]}_{ts}.json"
        json_path = os.path.join(json_dir, json_name)
        _json_fd = os.open(json_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                           stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        with os.fdopen(_json_fd, "w", encoding="utf-8") as f:
            json.dump({"video": bv, "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "main_count": len(comments), "comments": comments},
                      f, ensure_ascii=False, indent=2)

        # AI 总结（根据配置）
        if self.config.get("llm_summary", False):
            try:
                from llm import analyze_comments as ac
                custom_prompt = self.config.get("llm_keywords", "")
                prompt = ac.build_prompt_from_comments(
                    {"video": bv, "comments": comments},
                    max_comments=20,
                    custom_prompt=custom_prompt,
                )
                umo = event.unified_msg_origin
                provider_id = await self.context.get_current_chat_provider_id(umo)
                resp = await self.context.llm_generate(
                    chat_provider_id=provider_id,
                    prompt=prompt,
                )
                yield event.plain_result(f"AI 总结：\n{resp.completion_text}")
            except Exception as e:
                yield event.plain_result(f"AI 分析失败: {e}")

        # 发送成功后删除（根据配置）
        if self.config.get("auto_delete_csv", True):
            try:
                os.remove(csv_path)
            except Exception:
                pass


    # async def test(self, event: AstrMessageEvent,video_uid: str):
    #     bili.bv2aid(video_uid: str)
    #     # async for result in event.get_video_comments(video_uid):
    #     yield

    @filter.command("bililogin")
    async def bililogin(self, event: AstrMessageEvent):
        import asyncio

        yield event.plain_result("正在生成 B站 登录二维码...")

        try:
            qr = bili_login.generate_qrcode()
        except Exception as e:
            yield event.plain_result(f"生成二维码失败: {e}")
            return

        yield event.plain_result("请用 Bilibili App 扫描下方二维码登录（120秒内有效）")
        yield event.image_result(qr["image_path"])

        # 手动轮询，每隔几秒 yield 一次进度
        session = qr["session"]
        key = qr["qrcode_key"]
        url = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < 120:
            resp = session.get(url, params={"qrcode_key": key}, timeout=10)
            data = resp.json()
            code = data.get("data", {}).get("code", -1)
            msg = data.get("data", {}).get("message", "")

            if code == 0:  # 登录成功
                bili_login.cm.save_cookies(dict(session.cookies))
                yield event.plain_result("登录成功！Cookie 已保存")
                return
            elif code == 86038:  # 二维码过期
                yield event.plain_result("二维码已过期，请重新 /bililogin")
                return

            # 每 15 秒提醒一次
            elapsed = int(asyncio.get_event_loop().time() - start)
            if elapsed > 0 and elapsed % 15 == 0:
                yield event.plain_result(f"等待扫码中... ({elapsed}秒 / 120秒)")

            await asyncio.sleep(1.5)

        yield event.plain_result("登录超时（120秒），请重新 /bililogin")

    @filter.command("biliai")
    async def biliai(self, event: AstrMessageEvent):
        """调用 AI 分析最新爬取的评论"""
        from llm import analyze_comments

        data = analyze_comments.load_latest_comments()
        if not data:
            yield event.plain_result("data/json/ 下没有评论 JSON，请先 /bilicomment")
            return

        prompt = analyze_comments.build_prompt_from_comments(data)
        comments = data.get("comments", [])
        yield event.plain_result(f"正在分析 {len(comments)} 条评论...")

        try:
            umo = event.unified_msg_origin
            provider_id = await self.context.get_current_chat_provider_id(umo)
            resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
            )
            yield event.plain_result(resp.completion_text)
        except Exception as e:
            yield event.plain_result(f"AI 分析失败: {e}")

    @filter.command("bililogout")
    async def bililogout(self, event: AstrMessageEvent):
        """删除已保存的B站Cookie"""
        from cookie import cookie_manager as cm

        if not cm.is_logged_in():
            yield event.plain_result("当前没有已保存的 Cookie")
            return

        cm.clear_cookies()
        yield event.plain_result("B站 Cookie 已删除")

    @filter.command("sendcsv")
    async def sendcsv(self, event: AstrMessageEvent):
        """发送 data 目录下的 CSV 文件到 QQ"""
        import os, glob, base64

        data_dir = os.path.join(os.path.dirname(__file__), "data")
        csv_files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
        name = event.message_str.replace("sendcsv", "").strip()

        # 无参数 → 列出可用文件
        if not name:
            if not csv_files:
                yield event.plain_result("data 目录下没有 CSV 文件")
                return
            lines = [f"data 目录下共有 {len(csv_files)} 个 CSV 文件："]
            for i, f in enumerate(csv_files, 1):
                fname = os.path.basename(f)
                size = os.path.getsize(f)
                lines.append(f"  {i}. {fname} ({size} 字节)")
            lines.append("")
            lines.append("发送: /sendcsv <文件名>")
            yield event.plain_result("\n".join(lines))
            return

        # 有参数 → 查找匹配文件
        matched = [f for f in csv_files if name.lower() in os.path.basename(f).lower()]
        if not matched:
            yield event.plain_result(f"未找到包含「{name}」的 CSV 文件")
            return

        file_path = matched[0]
        file_name = os.path.basename(file_path)

        # 读文件 → base64
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        # 用 bot 原生的 call_action 发送文件(base64方式)
        bot = event.bot
        session_id = event.session_id
        is_group = "Group" in event.get_message_type().__class__.__name__

        payload = {
            "file": f"base64://{b64}",
            "name": file_name,
        }

        try:
            if is_group:
                await bot.call_action("send_group_msg", group_id=session_id, messages=[{"type": "file", "data": payload}])
            else:
                await bot.call_action("send_private_msg", user_id=session_id, messages=[{"type": "file", "data": payload}])
            yield event.plain_result(f"已发送 {file_name}")
        except Exception as e:
            yield event.plain_result(f"发送失败: {e}")


    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
