# Release Template / Release 模板

Use this template when drafting a new GitHub Release.

发布新的 GitHub Release 时可以使用这个模板。

```markdown
# xDownloader v0.3.x

## English

If the previous public release is older than the last local version, write this as a cumulative upgrade. Example: "This release note is written as a cumulative upgrade from `v0.3.1` to `v0.3.2`."

### Downloads

- `xDownloader-Setup-v0.3.x.exe`: recommended Windows installer. Choose the existing install folder to upgrade without losing local configuration or media.
- `xDownloader-v0.3.x-windows.zip`: portable executable package.
- Source code archive: for developers.

### Highlights

- Added optional shutdown after normal download completion.
- Download shutdown will not run after pause, termination, or failure.
- Added clearer failed-download feedback in the UI.
- Improved README, contribution docs, issue templates, and promotion copy.
- Preserved English / Chinese bilingual UI and docs.

### Privacy

Cookie, Bearer Token, user list, save path, logs, and downloaded media stay on your own machine. Do not share `config.json`.

## 中文

如果上一个公开 Release 早于本地最新版本，请把发布说明写成累计更新。例如：“这份发布说明按从 `v0.3.1` 升级到 `v0.3.2` 的累计更新来写。”

### 下载

- `xDownloader-Setup-v0.3.x.exe`：推荐 Windows 安装包。升级时选择原安装目录即可保留本地配置和媒体。
- `xDownloader-v0.3.x-windows.zip`：便携可执行版本。
- Source code：开发者源码包。

### 更新亮点

- 新增可选“下载正常完成后自动关机”。
- 暂停、终止或失败时不会触发自动关机。
- 下载失败时前端会显示更明确的失败提示。
- 改进 README、贡献文档、Issue 模板和推广文案。
- 保留中英文双语界面和文档。

### 隐私说明

Cookie、Bearer Token、用户名单、保存路径、日志和下载媒体都保存在你的本机。请不要分享 `config.json`。
```
