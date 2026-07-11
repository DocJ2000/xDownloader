# Contributing / 参与贡献

Thanks for helping improve xDownloader. This project welcomes bug fixes, documentation improvements, UI refinements, installer improvements, tests, and well-scoped features.

感谢你帮助改进 xDownloader。本项目欢迎 bug 修复、文档改进、界面优化、安装包改进、测试补充，以及范围清晰的新功能。

## Before You Start / 开始之前

- Open an issue first for large behavior changes, installer changes, or changes that affect local configuration.
- Do not commit `config.json`, cookies, bearer tokens, downloaded media, logs, local private paths, or generated release artifacts.
- Keep root-level files approachable for normal users. Runtime code should stay under `xdownloader_app/`.
- User-facing text should be updated in both English and Chinese when possible.

- 较大的行为变化、安装包变化、影响本地配置的变化，请先开 issue 讨论。
- 不要提交 `config.json`、Cookie、Bearer Token、下载媒体、日志、本机私人路径或生成的 release 产物。
- 根目录应保持适合普通用户浏览；运行层代码应放在 `xdownloader_app/` 下。
- 面向用户的文字尽量同步更新英文和中文。

## Local Development / 本地开发

```bash
pip install -r requirements.txt
copy config.example.json config.json
python xdownloader.py
```

Then open:

然后访问：

```text
http://127.0.0.1:8765/
```

## Tests / 测试

Run checks before opening a pull request:

提交 pull request 前请运行：

```bash
python -m unittest discover -s tests -v
python -m compileall -q xdownloader.py xdownloader_app
```

If you change frontend JavaScript inside `xdownloader_app/index.html`, also run a syntax check with Node.js if available:

如果修改了 `xdownloader_app/index.html` 里的前端 JavaScript，并且本机有 Node.js，也建议运行语法检查：

```bash
node -e "const fs=require('fs'); const html=fs.readFileSync('xdownloader_app/index.html','utf8'); const script=html.match(/<script>([\s\S]*)<\/script>/)[1]; new Function(script); console.log('JS syntax OK');"
```

## Pull Requests / Pull Request 要求

- Describe what changed and why.
- Include tests for behavior changes.
- Keep unrelated refactors out of the PR.
- Remove screenshots or logs that expose private accounts, cookies, tokens, local paths, or downloaded private media.
- Use bilingual commit messages when practical, for example: `Improve settings layout / 优化设置页布局`.

- 说明改了什么，以及为什么改。
- 行为变化请附带测试。
- 不要混入无关重构。
- 截图或日志中不要暴露私人账号、Cookie、Token、本机路径或下载的私人媒体。
- 提交信息尽量中英双语，例如：`Improve settings layout / 优化设置页布局`。

## Good First Contributions / 适合新贡献者的方向

- Improve README wording or translations.
- Add screenshots or small UI polish.
- Add regression tests for existing behavior.
- Improve installer documentation.
- Report clear bugs with reproduction steps and sanitized logs.

- 改进 README 文案或翻译。
- 增加截图或小范围界面优化。
- 为现有行为补充回归测试。
- 改进安装包文档。
- 提交带复现步骤和脱敏日志的 bug 报告。
