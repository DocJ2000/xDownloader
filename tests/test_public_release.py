import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "xdownloader_app"


class PublicReleaseTest(unittest.TestCase):
    def test_readme_is_bilingual(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## English", readme)
        self.assertIn("## 中文", readme)
        self.assertIn("中英双语", readme)
        self.assertIn("bilingual interface", readme.lower())
        self.assertIn("Start xDownloader.bat", readme)
        self.assertIn("xdownloader.py", readme)

    def test_obvious_launcher_files_exist(self):
        launcher = ROOT / "xdownloader.py"
        batch = ROOT / "Start xDownloader.bat"
        self.assertTrue(launcher.exists())
        self.assertTrue(batch.exists())
        self.assertIn("from xdownloader_app.server import main", launcher.read_text(encoding="utf-8"))
        self.assertIn("--smoke-test", launcher.read_text(encoding="utf-8"))
        self.assertIn("python xdownloader.py", batch.read_text(encoding="utf-8"))

    def test_runtime_files_live_in_app_subfolder(self):
        for name in ["server.py", "index.html", "main.py", "src"]:
            self.assertFalse((ROOT / name).exists(), f"{name} should not be in the public root")
            self.assertTrue((APP_DIR / name).exists(), f"{name} should live in xdownloader_app")

    def test_root_keeps_only_human_entry_points(self):
        manual_files = [
            "README.md",
            "LICENSE",
            "CONTRIBUTING.md",
            "requirements.txt",
            "config.example.json",
            "xdownloader.py",
            "Start xDownloader.bat",
        ]
        for name in manual_files:
            self.assertTrue((ROOT / name).exists(), f"{name} should stay visible at the root")

    def test_contribution_templates_exist(self):
        for name in [
            ".github/ISSUE_TEMPLATE/bug_report.md",
            ".github/ISSUE_TEMPLATE/feature_request.md",
            ".github/pull_request_template.md",
        ]:
            self.assertTrue((ROOT / name).exists(), f"{name} should exist")

    def test_obsolete_internal_files_are_not_published(self):
        obsolete_paths = [
            "docs/README_修复指南.md",
            "docs/superpowers",
            "xdownloader_app/app.py",
            "xdownloader_app/app.spec",
            "xdownloader_app/start.bat",
            "xdownloader_app/X-Download.spec",
            "xdownloader_app/X-Download-debug.spec",
            "xdownloader_app/_scan_all.py",
            "xdownloader_app/_fix_all.py",
            "xdownloader_app/_fix_orphan_rows.py",
            "xdownloader_app/_fix_single_folder.py",
        ]
        for name in obsolete_paths:
            self.assertFalse((ROOT / name).exists(), f"{name} should not be published")

    def test_windows_exe_packaging_is_reproducible_without_committing_artifacts(self):
        build_script = ROOT / "packaging" / "build_windows_exe.ps1"
        installer_script = ROOT / "packaging" / "xdownloader.iss"
        workflow = ROOT / ".github" / "workflows" / "build-windows-exe.yml"
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertTrue(build_script.exists())
        self.assertIn("pyinstaller", build_script.read_text(encoding="utf-8").lower())
        self.assertTrue(installer_script.exists())
        installer_text = installer_script.read_text(encoding="utf-8")
        self.assertIn("UninstallDisplayName", installer_text)
        self.assertIn("DefaultDirName", installer_text)
        self.assertIn("config.example.json", installer_text)
        self.assertNotIn('Name: "{app}\\config.json"', installer_text)
        self.assertNotIn('Name: "{app}\\download_progress.json"', installer_text)
        self.assertTrue(workflow.exists())
        self.assertIn("softprops/action-gh-release", workflow.read_text(encoding="utf-8"))
        self.assertIn("iscc", workflow.read_text(encoding="utf-8").lower())
        for ignored in ["build/", "dist/", "release/", "*.spec"]:
            self.assertIn(ignored, gitignore)

    def test_readme_has_preview_and_bilingual_commit_policy(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for preview in [
            "docs/assets/preview-home-en.png",
            "docs/assets/preview-home-zh.png",
            "docs/assets/preview-settings-en.png",
            "docs/assets/preview-settings-zh.png",
        ]:
            self.assertIn(preview, readme)
            self.assertTrue((ROOT / preview).exists())
        self.assertIn("Interface Preview / 界面预览", readme)
        self.assertIn("Download xDownloader Setup / 下载 xDownloader 安装包", readme)
        self.assertIn("Bilingual commits", readme)
        self.assertIn("双语提交", readme)

    def test_readme_documents_no_loss_upgrades(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("No-loss upgrades", readme)
        self.assertIn("config.json.bak", readme)
        self.assertIn("无损升级", readme)


if __name__ == "__main__":
    unittest.main()
