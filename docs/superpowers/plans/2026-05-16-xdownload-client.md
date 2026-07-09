# X-Download Desktop Client — 实施计划

**架构**: pywebview 桌面壳 + server.py 后端 API + index.html 纯前端

**文件**:
- 新增: `app.py` — 桌面入口
- 修改: `server.py` — 新增搜索/配置/下载/统计 API
- 重写: `index.html` — 双主题 + 4 Tab + 搜索 + 设置页
- 更新: `requirements.txt` — 加 `pywebview`

---

## Task 1: app.py — 桌面入口

```python
# f:\x\X-download\app.py
import threading
import time
import webview
from server import create_app, PORT

def start_server():
    create_app().run(host='127.0.0.1', port=PORT, threaded=True)

t = threading.Thread(target=start_server, daemon=True)
t.start()
time.sleep(0.5)
webview.create_window('X-Download', f'http://127.0.0.1:{PORT}', width=1280, height=800, min_size=(900, 600))
webview.start()
```

server.py 需改为 Flask 实例化模式（不直接 `serve_forever`）。

---

## Task 2: server.py — 改造为 Flask 并新增 API

当前 `server.py` 用 `http.server`，改为 Flask（已有 httpx，pip 装 flask）。保留原有 3 个 API，新增 4 个。

**新增 API:**

1. `GET /api/stats` — 遍历 DOWNLOAD_ROOT 统计用户数/媒体数/推文数
2. `GET /api/search?q=xxx` — 搜 username 和 CSV 内 content 字段
3. `GET /api/config` — 读 config.json 返回 JSON（cookie 脱敏只显示前 20 字符）
4. `POST /api/config` — body JSON 写回 config.json 对应 key（深层嵌套用 lodash 式 set，Python 手动处理 `mode.has_video` → `config['mode']['has_video']`）

---

## Task 3: index.html — 完整重写

单文件 HTML，内嵌所有 CSS/JS。

**结构:**
```
┌──────┬──────────────────────┐
│ nav  │      header          │
│ icons│    (search bar)       │
│      ├──────────────────────┤
│ 📋   │  main-content        │
│ 🔍   │  (tab content)       │
│ ⬇   │                      │
│ ⚙   │                      │
│      │                      │
│ ──── │                      │
│stats │                      │
└──────┴──────────────────────┘
```

**主题系统:** CSS 变量，`document.documentElement.dataset.theme = 'dark-glass'|'magazine'`

**4 Tab 实现:**
- 浏览页: 复用现有 `get_user_tweets` API + 媒体网格 + 灯箱
- 搜索页: 300ms 防抖 → `/api/search?q=` → 结果分"用户"和"推文"两栏
- 下载页: 输入用户名 → POST `/api/download/start` → 轮询 `/api/download/status`
- 设置页: 7 个分组表单 → POST `/api/config` 保存

下载状态轮询：`POST /api/download/start` 启动子线程跑 `main.py` 的函数，通过 `queue.Queue` 传递日志 + 进度，前端每 1s 轮询 `/api/download/status` 拿 `{'running': true, 'logs': [...], 'current': 5, 'total': 100}`

---

## Task 4: requirements.txt

```
httpx>=0.25.0
flask>=3.0.0
pywebview>=5.0.0
```

---

## 实施顺序

1. `server.py` → Flask 改造 + 新 API
2. `app.py` → 桌面入口
3. `requirements.txt` → 更新依赖
4. `index.html` → 完整前端重写

每个文件写完验证一次 `python app.py` 能否正常启动。
