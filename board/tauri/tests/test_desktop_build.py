#!/usr/bin/env python3
"""桌面壳配置与发布物约束。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "board"
TAURI = BOARD / "tauri" / "src-tauri"
CONF = TAURI / "tauri.conf.json"
RELEASE = BOARD / "release-desktop"


class DesktopBuildContractTests(unittest.TestCase):
    def test_tauri_config_skips_installer_and_webview2(self) -> None:
        conf = json.loads(CONF.read_text(encoding="utf-8"))
        self.assertFalse(conf["bundle"]["active"])
        self.assertEqual(conf["bundle"].get("targets"), [])
        self.assertEqual(conf["bundle"]["windows"]["webviewInstallMode"]["type"], "skip")
        dumped = json.dumps(conf).lower()
        for needle in ("webview2loader", "fixedruntime", "offlineinstaller", "bootstrapper", "nsis", "wix", "msi"):
            self.assertNotIn(needle, dumped)
        self.assertEqual(conf["app"]["windows"], [])
        self.assertTrue(str(conf["app"]["security"]["csp"]).startswith("default-src http://127.0.0.1"))

    def test_package_versions_match(self) -> None:
        cargo = (TAURI / "Cargo.toml").read_text(encoding="utf-8")
        package = json.loads((BOARD / "tauri" / "package.json").read_text(encoding="utf-8"))
        self.assertIn('version = "1.0.0"', cargo)
        self.assertEqual(package["version"], "1.0.0")
        self.assertIn('default-run = "TaskBoard"', cargo)
        self.assertIn("bundled", cargo)

    def test_web_zip_script_untouched_by_desktop_script(self) -> None:
        desktop = (ROOT / "scripts" / "build_board_desktop.py").read_text(encoding="utf-8")
        web = (ROOT / "scripts" / "build_board_release.py").read_text(encoding="utf-8")
        self.assertIn("TaskBoard.exe", desktop)
        self.assertIn("release-desktop", desktop)
        self.assertNotIn("WebView2", web)
        self.assertNotIn("tauri", web.lower())

    def test_release_dir_if_present_is_single_file(self) -> None:
        if not RELEASE.exists():
            self.skipTest("尚未构建 board/release-desktop")
        names = sorted(path.name for path in RELEASE.iterdir() if path.is_file())
        self.assertEqual(names, ["TaskBoard.exe", "manifest.json"])
        blob = " ".join(str(path).lower() for path in RELEASE.rglob("*"))
        for needle in ("webview2", "python", "node.exe", "sidecar", "resources"):
            self.assertNotIn(needle, blob)
        manifest = json.loads((RELEASE / "manifest.json").read_text(encoding="utf-8"))
        exe = (RELEASE / "TaskBoard.exe").read_bytes()
        self.assertEqual(manifest["pe_machine"], "x86_64")
        self.assertEqual(manifest["webview2"], "system-only")
        self.assertFalse(manifest["bundle"])
        self.assertEqual(len(exe), manifest["size"])


if __name__ == "__main__":
    unittest.main()
