# B站评论爬虫插件

一个功能完整的 AstrBot 插件，支持爬取 B站 视频评论、扫码登录、多格式导出、AI 分析总结。

## 功能特性

- **评论爬取** — 支持 BV 号 / AV 号 / 完整链接，自动识别输入
- **全量获取** — 合并热度+时间双排序去重，爬取更多不重复评论
- **子评论** — 自动爬取每条评论下的全部楼中楼回复
- **自动降级** — 新版 API 被拦截时自动切换旧版 API + Cookie
- **扫码登录** — 通过 `/bililogin` 扫码登录，Cookie 本地持久化
- **多格式导出** — CSV / JSON / Excel 三种格式可选
- **文件发送** — 爬取结果自动发送到 QQ
- **AI 分析** — 调用 AstrBot 已配置的 LLM 进行评论总结，提示词可自定义

## 安装

### 方式一：AstrBot 插件市场（如果已上架）

在 AstrBot WebUI → 插件管理 → 插件市场中搜索安装。

### 方式二：手动安装

```bash
# 进入 AstrBot 插件目录
cd /AstrBot/data/plugins

# 克隆仓库
git clone https://github.com/yuhuan-zhen/astrbot_plugin_text.git

# 安装依赖
pip install requests qrcode Pillow openpyxl
```

### 方式三：直接下载

下载仓库 ZIP，解压到 `AstrBot/data/plugins/astrbot_plugin_text/`，重启 AstrBot。

## 指令说明

| 指令 | 功能 | 示例 |
|------|------|------|
| `/bilicomment BV号` | 爬取评论并发送文件 | `/bilicomment BV1k8LX64EpC` |
| `/bilicomment BV号 20` | 指定爬取页数 | `/bilicomment BV1k8LX64EpC 20` |
| `/bilicomment BV号 --subs` | 展开子评论 | `/bilicomment BV1k8LX64EpC --subs` |
| `/bililogin` | B站扫码登录 | 生成二维码 → App扫码 → 自动保存Cookie |
| `/bililogout` | 删除已保存的 Cookie | — |
| `/biliai` | AI 分析最新爬取的评论 | 需先执行 `/bilicomment` |
| `/sendcsv` | 列出并发送 data/ 下的 CSV | `/sendcsv` → 选文件发送 |

## 配置

在 AstrBot WebUI → 插件配置中修改，或直接编辑 `data/config/astrbot_plugin_text_config.json`。

| 配置项 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| `default_pages` | int | 5 | 默认爬取页数 |
| `include_subs` | bool | false | 是否展开子评论 |
| `sort_by` | string | hot | 排序方式（hot/time） |
| `fasong_csv` | bool | true | 保存并发送 CSV |
| `fasong_json` | bool | false | 保存并发送 JSON |
| `fasong_excel` | bool | false | 保存并发送 Excel |
| `auto_delete_csv` | bool | true | 发送后自动删除文件 |
| `llm_summary` | bool | false | 启用 AI 评论总结 |
| `llm_keywords` | text | "" | AI 总结自定义提示词 |

## 目录结构

```
astrbot_plugin_text/
├── main.py                      # 插件入口（所有 Bot 指令）
├── metadata.yaml                # 插件元信息
├── _conf_schema.json            # 配置模板
├── requirements.txt             # 依赖清单
├── core/
│   ├── bilibili_comment.py      # 评论爬取核心
│   └── save.py                  # 文件保存工具（CSV / JSON / Excel）
├── cookie/
│   ├── __init__.py
│   ├── bili_login.py            # 扫码登录
│   └── cookie_manager.py        # Cookie 持久化
└── llm/
    ├── analyze_comments.py      # 评论 AI 分析
    └── analyze.py               # 独立 LLM 分析脚本
```

## 依赖

```
requests>=2.28.0       # 调用 B站 API
qrcode>=7.4            # 生成登录二维码
Pillow>=9.0.0          # 二维码图片输出
openpyxl>=3.0.0        # Excel 导出（可选，不用 Excel 可不装）
```

## 常见问题

### 文件发送失败（EACCES: permission denied）

Linux 服务器上 Lagrange 可能无法读取插件生成的 CSV 文件。解决方案：
- 确保 `cmd_config.json` 中 `callback_api_base` 配置正确（如 `http://localhost:6185`）
- 或使用 `/sendcsv` 命令手动发送

### 只爬取到少量评论

- 先执行 `/bililogin` 扫码登录，未登录状态下 B站 API 限制严格
- 检查 `default_pages` 配置是否过小
- 云服务器 IP 可能被 B站 限流，可尝试使用家用网络

### 导入报错

如果遇到 `No module named '...'` 错误，确保插件目录在 AstrBot 的插件加载路径下，且依赖已安装。

## 开源协议

MIT License

## 参考与致谢

本项目参考了以下开源项目：

- [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) — 社交媒体爬虫框架
- [astrbot_plugin_biliVideo](https://github.com/storyAura/astrbot_plugin_biliVideo) — AstrBot B站视频插件

## 贡献

欢迎提交 Issue 和 Pull Request。
