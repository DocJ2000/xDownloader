# Contributing / 参与贡献

## English

Thanks for helping improve xDownloader. This project welcomes bug fixes, documentation improvements, UI refinements, and well-scoped features.

### Before You Start

- Open an issue first for large behavior changes.
- Do not commit `config.json`, cookies, bearer tokens, downloaded media, logs, or local paths.
- Keep root-level files approachable for users. Runtime code should stay under `xdownloader_app/`.

### Development

```bash
pip install -r requirements.txt
copy config.example.json config.json
python xdownloader.py
```

Run checks before opening a pull request:

```bash
python -m unittest discover -s tests -v
python -m compileall -q xdownloader.py xdownloader_app
```

### Pull Requests

- Describe what changed and why.
- Include tests for behavior changes.
- Keep unrelated refactors out of the PR.
- Update README text in both English and Chinese when user-facing behavior changes.

## 中文

感谢你帮助改进 xDownloader。本项目欢迎 bug 修复、文档改进、界面优化和范围清晰的新功能。

### 开始之前

- 较大的行为变化请先开 issue 讨论。
- 不要提交 `config.json`、cookie、bearer token、下载媒体、日志或本机路径。
- 根目录应保持适合普通用户浏览；运行代码应放在 `xdownloader_app/` 下。

### 本地开发

```bash
pip install -r requirements.txt
copy config.example.json config.json
python xdownloader.py
```

提交 PR 前请运行：

```bash
python -m unittest discover -s tests -v
python -m compileall -q xdownloader.py xdownloader_app
```

### Pull Request 要求

- 说明改了什么以及为什么改。
- 行为变化请附带测试。
- 不要混入无关重构。
- 面向用户的行为变化需要同步更新 README 的英文和中文说明。
