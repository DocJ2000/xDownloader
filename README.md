# xDownloader

## English

xDownloader is a local X/Twitter media downloader and browser. It downloads media and text tweets for configured users, can sync users from an X list, and provides a local web UI for browsing users, timeline items, and media.

### Quick Start

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Create your private config:

   ```bash
   copy config.example.json config.json
   ```

3. Start the app:

   - Double-click `Start xDownloader.bat` on Windows, or
   - Run `python xdownloader.py`

4. Open the local UI if it does not open automatically:

   ```text
   http://127.0.0.1:8765/
   ```

### Project Layout

- `xdownloader.py` and `Start xDownloader.bat` are the visible launchers.
- `config.example.json` is the template for your private `config.json`.
- `xdownloader_app/` contains the runtime code and web UI.
- `tests/` contains the regression tests.

### Configuration

Private values such as `cookie`, `bearer_token`, `save_path`, and `user_list` belong in `config.json`. That file is ignored by Git and should never be committed.

Most personal settings can be edited from the Settings tab in the web UI. The frontend defaults to English and can switch between English and Chinese with the `EN/中` button.

### CLI

The desktop/web launcher is recommended. Advanced users can run CLI commands from the repository root:

```bash
python -m xdownloader_app.main download
python -m xdownloader_app.main list-sync --list-id <list_id>
python -m xdownloader_app.main text
```

### Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q xdownloader.py xdownloader_app
```

### Contributing

Contributions are welcome. Please read `CONTRIBUTING.md`, open an issue for larger changes, and include tests for behavior changes.

## 中文

xDownloader 是一个本地 X/Twitter 媒体下载器和浏览器。它可以按用户下载媒体和文字推文，可以从 X 列表同步用户，并提供本地网页界面浏览用户、时间线内容和媒体库。

### 快速开始

1. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

2. 创建你的私人配置：

   ```bash
   copy config.example.json config.json
   ```

3. 启动软件：

   - Windows 下双击 `Start xDownloader.bat`，或
   - 运行 `python xdownloader.py`

4. 如果浏览器没有自动打开，访问：

   ```text
   http://127.0.0.1:8765/
   ```

### 项目结构

- `xdownloader.py` 和 `Start xDownloader.bat` 是放在根目录的明显启动入口。
- `config.example.json` 是私人配置 `config.json` 的模板。
- `xdownloader_app/` 存放运行代码和网页界面。
- `tests/` 存放回归测试。

### 配置说明

`cookie`、`bearer_token`、`save_path`、`user_list` 等私人信息放在 `config.json`。该文件已被 Git 忽略，不应该提交到公开仓库。

大多数个人配置都可以在网页界面的“设置”页填写。前端默认英文，可以通过 `EN/中` 按钮在英文和中文之间切换。

### 命令行

推荐使用桌面/网页启动入口。高级用户可以在仓库根目录运行：

```bash
python -m xdownloader_app.main download
python -m xdownloader_app.main list-sync --list-id <list_id>
python -m xdownloader_app.main text
```

### 测试

```bash
python -m unittest discover -s tests -v
python -m compileall -q xdownloader.py xdownloader_app
```

### 参与贡献

欢迎贡献。请先阅读 `CONTRIBUTING.md`；较大的改动建议先开 issue 讨论；涉及行为变化的 PR 请附带测试。
