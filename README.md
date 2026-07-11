# xDownloader

**A bilingual X/Twitter media downloader and local media browser for Windows.**  
**一款中英双语的 X/Twitter 媒体下载器与本地媒体浏览器。**

[![Latest Release](https://img.shields.io/github/v/release/DocJ2000/xDownloader?label=download)](https://github.com/DocJ2000/xDownloader/releases/latest)
[![Windows](https://img.shields.io/badge/Windows-installer-blue)](https://github.com/DocJ2000/xDownloader/releases/latest)
[![Bilingual UI](https://img.shields.io/badge/UI-English%20%2F%20%E4%B8%AD%E6%96%87-6c5ce7)](#interface-preview--界面预览)
[![License](https://img.shields.io/github/license/DocJ2000/xDownloader)](LICENSE)

[Changelog / 更新日志](CHANGELOG.md)

xDownloader helps you download X/Twitter media and browse your saved archive locally. It includes list sync, a timeline view, a media library, hot-applied settings, no-loss upgrades, and a guided Windows installer.

xDownloader 可以帮助你下载 X/Twitter 媒体，并在本地浏览已保存的内容。它支持列表同步、时间线、媒体库、前端即时配置、无损升级，以及可选择安装路径的 Windows 安装包。

## English

For English readers: xDownloader is a local-first, bilingual interface tool for downloading and browsing X/Twitter media on Windows.

## 中文

中文读者可以直接阅读每个章节里的中文说明。xDownloader 是一款本地优先、中英双语界面的 Windows X/Twitter 媒体下载与浏览工具。

## Download / 下载

For most users, download the installer from the latest GitHub Release:

普通用户建议直接从最新版 GitHub Release 下载安装包：

[**Download xDownloader Setup / 下载 xDownloader 安装包**](https://github.com/DocJ2000/xDownloader/releases/latest)

- `xDownloader-Setup-*.exe`: recommended guided Windows installer. It lets you choose the install folder and creates a normal Windows uninstall entry.
- `xDownloader-*-windows.zip`: portable package for users who prefer not to install.
- Source code archive: for developers who want to inspect, modify, or build the project.

- `xDownloader-Setup-*.exe`：推荐的 Windows 安装包，可以选择安装路径，并支持系统卸载入口。
- `xDownloader-*-windows.zip`：免安装便携版。
- Source code：适合想阅读、修改或自行构建项目的开发者。

## Interface Preview / 界面预览

xDownloader provides a full English and Chinese interface. You can switch languages inside the app.

xDownloader 提供完整中英文界面，可以在软件内一键切换语言。

| Home / 首页 | Settings / 设置 |
| --- | --- |
| ![xDownloader Home English](docs/assets/preview-home-en.png) | ![xDownloader Settings English](docs/assets/preview-settings-en.png) |
| ![xDownloader 中文首页](docs/assets/preview-home-zh.png) | ![xDownloader 中文设置](docs/assets/preview-settings-zh.png) |

## Highlights / 功能亮点

- Local media browser: browse downloaded images and videos without reopening original tweet links.
- Timeline view: review locally archived posts by time.
- Media library: search and page through large local media collections.
- Multi-list sync: paste X list links, sync selected lists, and merge members into one download list.
- User list tools: bulk add, deduplicate, export, paginate, and remove unavailable users with confirmation.
- Hot-applied settings: edit account credentials, save path, date range, media options, speed settings, proxy, logging, and theme from the UI.
- Adjustable checkpoint expiry: this controls how long xDownloader remembers already processed users for resume; it is not a download cooldown. Set it to `0` to always check from the beginning.
- Long-run friendly: pause, continue, terminate, preview progress, and optionally shut down Windows after a normal download completion.
- No-loss upgrades: installer users can install new versions over the existing folder while keeping local config and data.
- Bilingual by design: English and Chinese UI, README, and contribution docs.

- 本地媒体浏览器：不需要跳转原推文链接，就能浏览已下载图片和视频。
- 时间线视图：按时间查看本地归档内容。
- 媒体库：支持搜索、分页和跳转页码，适合大型本地媒体库。
- 多列表同步：直接粘贴 X 列表链接，可同步选中列表，并把成员合并进下载名单。
- 用户名单工具：批量添加、去重、导出、分页查看，并可二次确认后移除不存在用户。
- 前端即时配置：账号凭据、保存路径、时间范围、下载内容、速度设置、代理、日志和主题都能在界面修改并应用。
- 可调整断点续传有效期：它控制软件多久内记住已处理过的用户，方便继续下载；这不是下载冷却时间。设为 `0` 表示每次从头检查。
- 长任务友好：支持暂停、继续、终止、实时进度预览，也可以勾选“下载完成后自动关机”。
- 无损升级：安装包用户覆盖安装到原目录即可保留本地配置和数据。
- 双语设计：界面、README 和贡献文档都面向中英文用户。

## Privacy / 隐私说明

xDownloader is designed as a local-first tool.

xDownloader 是本地优先的软件。

- Your Cookie, Bearer Token, user list, save path, logs, and downloaded media stay on your own machine.
- The app opens a local browser UI at `http://127.0.0.1:8765/`.
- `config.json` is private local configuration and should never be committed or shared.
- Before opening issues or pull requests, remove cookies, tokens, account secrets, local private paths, logs, and downloaded media.

- Cookie、Bearer Token、用户名单、保存路径、日志和下载媒体都保存在你的本机。
- 软件使用本地浏览器界面：`http://127.0.0.1:8765/`。
- `config.json` 是私人本地配置文件，不应该提交或分享。
- 提交 issue 或 pull request 前，请删除 Cookie、Token、账号密钥、本机私人路径、日志和下载媒体。

## Run From Source / 从源码运行

```bash
pip install -r requirements.txt
copy config.example.json config.json
python xdownloader.py
```

If the UI does not open automatically, visit:

如果界面没有自动打开，请手动访问：

```text
http://127.0.0.1:8765/
```

You can also double-click:

也可以直接双击：

```text
Start xDownloader.bat
```

## Windows Installer / Windows 安装包

The recommended installer is `xDownloader-Setup-*.exe` from GitHub Releases.

推荐普通用户下载 GitHub Releases 里的 `xDownloader-Setup-*.exe`。

- Choose the install folder during setup.
- `config.json` is created in the install folder on first run.
- The installer build does not require users to install Python manually.
- Windows gets a normal uninstall entry, and the install folder also contains an uninstaller.

- 安装过程中可以选择安装路径。
- 首次运行时会在安装目录生成 `config.json`。
- 安装包版本不需要用户手动安装 Python。
- Windows 会出现标准卸载入口，安装目录里也会有卸载程序。

## No-Loss Upgrades / 无损升级

Installer users can install a newer `xDownloader-Setup-*.exe` over the existing installation folder. Existing `config.json`, download progress, and local media are preserved by default.

安装包用户可以把新的 `xDownloader-Setup-*.exe` 覆盖安装到原安装目录。默认会保留已有的 `config.json`、下载进度和本地媒体。

xDownloader writes `config.json.bak` before saving or migrating configuration, giving you a simple local fallback if configuration changes go wrong.

xDownloader 在保存或迁移配置前会写入 `config.json.bak`，如果配置改错了，可以用它作为本地备份。

You can also open **Settings** and click **Check update**. If a newer GitHub Release exists, xDownloader can download the latest installer. Choose your current install folder during setup to upgrade without losing local configuration.

也可以在 **设置** 页面点击 **检查更新**。如果 GitHub Release 有新版本，xDownloader 会提供最新安装包下载。安装时选择当前安装目录即可无损升级。

For source or portable zip users, keep your existing `config.json` next to `xdownloader.py` or `xDownloader.exe`, then replace the application files. Missing new settings are added automatically on the next start.

源码或便携版用户升级时，请保留 `xdownloader.py` 或 `xDownloader.exe` 旁边已有的 `config.json`，再替换应用文件。下次启动时软件会自动补齐新增配置项。

## X List Sync Tips / X 列表同步提示

The easiest way is to paste the X list link into the list sync table. Numeric list IDs are also supported.

最简单的方式是直接把 X 列表链接粘贴到列表同步表格中，也支持数字列表 ID。

Examples / 示例：

```text
https://x.com/i/lists/1234567890
https://x.com/openai/lists/example-list
1234567890
```

## Project Layout / 项目结构

- `xdownloader.py`: source launcher.
- `Start xDownloader.bat`: double-click launcher for source users.
- `config.example.json`: template for private `config.json`.
- `xdownloader_app/`: runtime code and browser UI.
- `packaging/`: Windows exe and installer build scripts.
- `tests/`: regression tests.
- `docs/`: screenshots, promotion copy, and project docs.

- `xdownloader.py`：源码启动入口。
- `Start xDownloader.bat`：源码用户可双击启动。
- `config.example.json`：私人配置文件 `config.json` 的模板。
- `xdownloader_app/`：运行代码和网页界面。
- `packaging/`：Windows exe 与安装包构建脚本。
- `tests/`：回归测试。
- `docs/`：截图、推广文案和项目文档。

## Build Locally / 本地构建

Build the portable exe and installer:

构建便携 exe 和安装包：

```powershell
./packaging/build_windows_exe.ps1 -Version local
```

Build only the portable exe:

只构建便携 exe：

```powershell
./packaging/build_windows_exe.ps1 -Version local -SkipInstaller
```

Generated files are written to `release/`, which is ignored by Git.

生成文件会写入 `release/`，该目录不会提交到 Git。

## Tests / 测试

```bash
python -m unittest discover -s tests -v
python -m compileall -q xdownloader.py xdownloader_app
```

## Contributing / 参与贡献

Contributions are welcome. You can help with bug fixes, UI polish, documentation, installer improvements, tests, and feature ideas.

欢迎贡献。你可以帮助修复 bug、优化界面、完善文档、改进安装包、补充测试或提出功能建议。

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

提交 pull request 前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

Commit messages should be bilingual when possible:

提交信息建议尽量中英双语：

### Bilingual commits / 双语提交

```text
Improve media pagination / 优化媒体分页
Add installer update flow / 增加安装包更新流程
```

## Roadmap Ideas / 后续方向

- Better packaged desktop shell instead of browser-only UI.
- More media playback controls.
- Safer credential import helpers.
- More automated release checks.
- More language packs if contributors are interested.

- 更完整的桌面外壳，不只依赖浏览器界面。
- 更强的媒体播放控制。
- 更安全的凭据导入辅助功能。
- 更完善的自动发布检查。
- 如果有贡献者参与，可以增加更多语言包。
