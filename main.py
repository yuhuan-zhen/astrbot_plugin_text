from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from data.plugins.astrbot_plugin_text import bilibili_comment as bili


@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

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
        bv = event.message_str.replace("bilicomment", "").strip()
        if not bv:
            yield event.plain_result("用法: /bilicomment BV号")
            return
        ok, data, count = bili.get_comments(bv, max_pages=2)
        if ok:
            yield event.plain_result(f"共 {count} 条评论:\n{data[:1500]}")
        else:
            yield event.plain_result(f"失败: {data}")




    # async def test(self, event: AstrMessageEvent,video_uid: str):
    #     bili.bv2aid(video_uid: str)
    #     # async for result in event.get_video_comments(video_uid):
    #     yield
    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
