# Changelog / 更新日志

## v0.3.2

### English

This release is the first public cumulative upgrade after `v0.3.1`. It includes all local improvements that were not previously uploaded to GitHub.

- Added in-app update checking from Settings.
- Added installer download and open flow for no-loss upgrades.
- Added GitHub Release page fallback when the GitHub API is rate-limited.
- Added direct page jump on the Media tab for large libraries.
- Added page jump controls to Timeline and paginated user list management.
- Improved visual module separation across pages.
- Added optional shutdown after a normal download completion.
- Auto shutdown does not run after pause, termination, or failed downloads.
- Added clearer failed-download feedback in the frontend.
- Added local `download_history.json` tracking for the last 3 normal download completions.
- Each history entry records completion time, elapsed duration, processed users, new media count, new text tweet count, and newly added storage size.
- Pause, termination, and failed downloads do not create history entries.
- Added recent download history to the Download page and API status output.
- Improved README with stronger download entry, screenshots, privacy notes, feature highlights, no-loss upgrade instructions, and bilingual contribution guidance.
- Added a promotion kit with GitHub About copy, topics, release copy, social posts, forum posts, and SEO keywords.
- Added GitHub repository settings guidance for About, Topics, pinned description, and starter issue ideas.
- Added a reusable bilingual Release template.
- Rewrote issue and pull request templates in clear English and Chinese.
- Rewrote contribution documentation and fixed old mojibake text in public release tests.
- Preserved bilingual English and Chinese UI and documentation.
- Added regression tests for update checks, pagination, auto shutdown, recent download history, frontend rendering, and public release text.

### 中文

这个版本是 `v0.3.1` 之后第一次上传到 GitHub 的公开累计更新，包含此前所有尚未上传的本地优化。

- 设置页新增应用内检查更新。
- 新增安装包下载和打开流程，方便无损升级。
- GitHub API 被限流时，会自动使用 GitHub Release 页面兜底检查。
- 媒体页新增页码输入跳转，大型媒体库不用一页一页翻。
- 时间线和下载用户名单也加入完整分页跳转能力。
- 优化各页面模块之间的视觉分区。
- 新增可选“下载正常完成后自动关机”。
- 暂停、终止或下载失败时不会触发自动关机。
- 前端新增更明确的下载失败提示。
- 新增本地 `download_history.json`，保存最近 3 次正常完成的下载记录。
- 每条记录包含完成时间、历时多久、处理用户数、新增媒体数、新增文字推文数和新增容量大小。
- 暂停、终止或失败的下载不会写入历史记录。
- 下载页新增“最近下载”模块，下载状态 API 新增最近下载历史输出。
- 改进 README，强化下载入口、截图预览、隐私说明、功能亮点、无损升级说明和双语贡献说明。
- 新增推广文案包，包含 GitHub About 文案、Topics、Release 文案、社交平台文案、论坛长文案和 SEO 关键词。
- 新增 GitHub 仓库设置建议，包含 About、Topics、置顶描述和初始 issue 建议。
- 新增可复用的中英双语 Release 模板。
- 重写 issue 和 pull request 模板，改成清晰的中英文版本。
- 重写贡献文档，并修复公开发布测试中的旧乱码文本。
- 保留中英文双语界面和文档。
- 新增回归测试，覆盖更新检查、分页、自动关机、最近下载历史、前端渲染和公开发布文本。
