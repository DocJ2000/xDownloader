# X-Download Desktop Client — Design Spec

## Overview

将现有 X-Download 命令行工具包装为独立桌面客户端，提供浏览、搜索、下载、配置四大功能，支持暗黑玻璃/杂志极简双主题切换。

- **打包目标**: 独立 `.exe`（PyInstaller），无需安装浏览器或 Node.js
- **技术栈**: pywebview（桌面壳）+ Python 后端（server.py 扩展）+ 纯前端 HTML/CSS/JS（内嵌）

---

## Architecture

```
app.py                      ← 入口：启动 server，打开 webview
  ├── server.py (扩展)       ← API 服务层
  │     /api/users          用户列表
  │     /api/user/{}/tweets 用户时间线
  │     /api/search         搜索（用户名+推文内容）
  │     /api/download       触发下载
  │     /api/download/status 下载进度
  │     /api/config         读/写配置
  │     /api/stats          整体统计
  │
  ├── main.py (模块导入)     ← 下载逻辑，被 server 按需调用
  │     cmd_download() / cmd_text() / cmd_list_sync()
  │
  └── index.html (替换)      ← 前端，内嵌于 webview
```

**进程模型**: server 跑在后台线程，webview 指向 `http://127.0.0.1:{port}`，全在同一个 Python 进程内。

---

## Frontend Layout

```
┌──────────────┬─────────────────────────────────┐
│  🗂 X-Down   │  🔎 搜索用户名或推文...          │  ← 通用搜索栏
│              │                                  │
│  📋 浏览     │  ┌──────────────────────────┐   │
│  🔍 搜索     │  │                          │   │
│  ⬇ 下载      │  │   当前 Tab 的主内容区      │   │
│  ⚙ 设置      │  │                          │   │
│              │  │                          │   │
│  ─────────   │  │                          │   │
│  用户: 443   │  └──────────────────────────┘   │
│  媒体: 12K   │                                  │
│  推文: 5K    │                                  │
└──────────────┴─────────────────────────────────┘
```

- **左侧**: 85px 宽图标导航栏 + 可选展开的用户列表
- **顶部**: 全局搜索栏（始终可见）
- **主区域**: 4 个 Tab 切换

---

## Tab 1 — 浏览 (Browse)

用户侧边栏 → 时间线浏览，复用并美化现有 `index.html` 逻辑。

**改进点**:
- 用户列表显示头像色块 + 名称 + 媒体/推文数
- 时间线卡片：头像色块 + 用户名 + 时间 + 文本 + 媒体网格 + 互动数据
- 媒体网格智能布局: 1图大图 / 2图并列 / 3图三列 / 4+图两列网格
- 图片点击灯箱（左右箭头翻页）
- 视频内嵌播放（controls）
- 加载状态骨架屏
- 下拉刷新"加载更多"（按时间分页）

---

## Tab 2 — 搜索 (Search)

**搜索范围**: 已下载的用户名 + 推文文本内容

**交互**:
1. 输入关键词（≥2字符），300ms 防抖后自动搜索
2. 结果分两栏:
   - **匹配的用户** (按匹配度排序): 点击跳转到浏览 Tab 该用户时间线
   - **匹配的推文** (按时间倒序): 直接显示推文卡片，可展开媒体

**后端实现**: server 遍历所有用户文件夹的 CSV 文件，在内存中做全文匹配（数据量小，不需要搜索引擎）

---

## Tab 3 — 下载 (Download)

**功能**:
- 输入框：手动输入用户名（逗号分隔），或从配置的 user_list 选择
- 复选框：下载媒体 / 下载文字推文 / 自动同步列表
- 下载按钮 + 停止按钮
- 实时日志面板（滚动输出，类似终端）
- 进度条（当前用户 x/总数）

**后端实现**: `server.py` 开子线程调用 `main.py` 的下载函数，通过队列把日志行和进度推送给前端（SSE 或 WebSocket，首选 SSE 简单够用）

---

## Tab 4 — 设置 (Settings)

设置页分为 5 个分组，所有修改点"保存"后即时写入 `config.json`。需重启生效的项标注 ⚡。

### 分组 1: 账号
| 字段 | config key | 说明 |
|------|-----------|------|
| Cookie | `cookie` | 含 auth_token + ct0 的完整 cookie 字符串 |
| Bearer Token | `bearer_token` | Twitter API bearer token |

### 分组 2: 网络
| 字段 | config key | 说明 |
|------|-----------|------|
| 代理地址 (VPN端口) | `proxy` | 如 `http://127.0.0.1:7890`，留空为直连 |

### 分组 3: 下载
| 字段 | config key | 说明 |
|------|-----------|------|
| 下载路径 | `save_path` | 媒体 & 推文保存目录，如 `downloads` |
| 时间范围 | `time_range` | 格式 `2020-01-01:2026-12-31`，只下载此区间的推文 |
| 图片格式 | `image_format` | `orig` / `jpg` / `png` |
| 包含视频 | `mode.has_video` | 是否下载视频 |
| 包含转发 | `mode.has_retweet` | 是否下载转推 |
| 包含高亮 | `mode.has_highlights` | 是否下载高亮推文 |
| 包含喜欢 | `mode.has_likes` | 是否下载喜欢的内容 |
| 最大并发 ⚡ | `download.max_concurrent` | 同时下载的并发数 |
| 缓存 ⚡ | `download.enable_cache` | 是否启用缓存跳过已下载 |

### 分组 4: 下载名单
| 字段 | config key | 说明 |
|------|-----------|------|
| 用户列表 | `user_list` | 手动编辑用户名列表，每行一个 |
| 自动同步列表 | `list_sync.enabled` | 每次下载前自动从 Twitter 列表拉人 |
| 列表 ID | `list_sync.list_id` | Twitter list ID |
| 列表所有者 | `list_sync.list_owner` | list 所有者的 screen name |
| 列表名 | `list_sync.list_slug` | list 的 slug |
| 文字推文名单 | `text_download.user_list` | 文字下载专用用户列表 |

### 分组 5: 外观
| 字段 | config key | 说明 |
|------|-----------|------|
| 主题 | `theme` | `dark-glass` / `magazine`，即时切换 |

### 分组 6: 文字下载
| 字段 | config key | 说明 |
|------|-----------|------|
| 最大推文数 | `text_download.max_tweets` | 每个用户最多下载多少条 |
| 请求延迟 | `text_download.request_delay` | 请求间隔(秒) |
| 最大重试 | `text_download.max_retries` | 失败重试次数 |

### 分组 7: 重试
| 字段 | config key | 说明 |
|------|-----------|------|
| 用户重试次数 | `retry.max_user_retries` | 每个用户最多重试几次 |
| 重试间隔(秒) | `retry.delay_seconds` | 重试等待秒数 |

保存后自动重载配置（除标注 ⚡ 项需重启客户端）。

---

## Theme System

通过 CSS 变量实现双主题，在 `<html>` 上切换 `data-theme="dark-glass"` / `data-theme="magazine"`。

### Dark Glass 主题配色

| 变量 | 值 |
|------|-----|
| 背景 | `#0a0a0f` |
| 面板 | `rgba(18,18,24,0.85)` backdrop-blur |
| 卡片 | `rgba(25,25,35,0.6)` |
| 主文字 | `#e0e0e0` |
| 次文字 | `#888` |
| 主色 | `#6c5ce7` (紫色) |
| 强调 | `#a29bfe` |
| 分割线 | `rgba(255,255,255,0.06)` |
| 圆角 | 12px |
| 字体 | 'Inter', system-ui |

### Magazine 主题配色

| 变量 | 值 |
|------|-----|
| 背景 | `#faf8f5` |
| 面板 | `#ffffff` |
| 卡片 | `#ffffff` border: 1px solid #e8e4dd |
| 主文字 | `#1a1a1a` |
| 次文字 | `#6b6b6b` |
| 主色 | `#c49a2b` (琥珀金) |
| 强调 | `#8b6914` |
| 分割线 | `#e8e4dd` |
| 圆角 | 4px |
| 字体 | 'Noto Serif SC' 标题, 'PingFang SC' 正文 |

---

## API Design

### 现有 API（保留）
- `GET /api/users` — 用户列表
- `GET /api/user/{screen_name}/tweets` — 时间线
- `GET /media/{folder}/{filename}` — 静态文件

### 新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search?q=xxx` | 搜索，返回 `{users: [...], tweets: [...]}` |
| GET | `/api/stats` | 统计: `{total_users, total_media, total_tweets}` |
| GET | `/api/config` | 读配置（脱敏 cookie/bearer） |
| POST | `/api/config` | 写配置，body: JSON |
| POST | `/api/download/start` | 启动下载, body: `{users: [...], options: {...}}` |
| GET | `/api/download/status` | SSE 流，实时推送日志行和进度 |

---

## Packaging

**PyInstaller 配置**:
- 入口: `app.py`
- 隐藏导入: `src.*`, `httpx`, `pywebview`
- 数据文件: `index.html`, `config.json`
- 输出: 单个文件夹或 `--onefile`

**启动流程**:
1. Python 启动 server（后台线程）
2. 等待 server ready
3. 打开 pywebview 窗口指向 `http://127.0.0.1:{port}`
4. 窗口关闭时停止 server

---

## Files Changed / Created

| 文件 | 操作 |
|------|------|
| `app.py` | **新增** — 桌面入口 |
| `server.py` | **扩展** — 新增搜索/下载/配置/统计 API |
| `index.html` | **重写** — 完整前端，双主题 + 4 Tab |
| `requirements.txt` | **更新** — 加 pywebview, pyinstaller |

---

## Out of Scope

- 用户登录 / OAuth（cookie 仍需手动获取后填入设置）
- 多语言
- 云端同步
- 数据库存储（继续用 CSV + 文件系统）
