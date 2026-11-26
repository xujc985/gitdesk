# -*- coding: utf-8 -*-
"""跨平台启动文件与资源的轻量检查。"""
from __future__ import annotations

import os
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PlatformAssetsTest(unittest.TestCase):
    def test_icon_formats(self):
        self.assertTrue((ROOT / "assets" / "gitdesk.svg").read_text(encoding="utf-8").startswith("<svg"))
        png = (ROOT / "assets" / "gitdesk.png").read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        ico = (ROOT / "assets" / "gitdesk.ico").read_bytes()
        reserved, kind, count = struct.unpack("<HHH", ico[:6])
        self.assertEqual((reserved, kind), (0, 1))
        self.assertGreaterEqual(count, 5)

    def test_unix_launchers_use_python3_and_lf(self):
        for name in ("run.sh", "install-linux.sh", "run-macos.command"):
            data = (ROOT / name).read_bytes()
            self.assertTrue(data.startswith(b"#!/"))
            self.assertNotIn(b"\r\n", data)
            self.assertIn(b"python3", data) if name == "run.sh" else None

        self.assertTrue((ROOT / "assets" / "gitdesk.icns").is_file())
        icns = (ROOT / "assets" / "gitdesk.icns").read_bytes()
        self.assertEqual(icns[:4], b"icns")
        self.assertGreater(len(icns), 1024)

    def test_packaging_assets_and_workflow(self):
        spec = (ROOT / "packaging" / "gitdesk.spec").read_text(encoding="utf-8")
        self.assertIn("onedir", spec)
        self.assertIn("assets", spec)
        self.assertIn("QtWebEngine", spec)
        for name in ("build-windows.ps1", "build-linux.sh", "build-macos.sh"):
            script = (ROOT / "packaging" / name).read_text(encoding="utf-8")
            self.assertIn("smoke_test.py", script)
        workflow = ROOT / ".github" / "workflows" / "build.yml"
        self.assertTrue(workflow.is_file())
        for platform in ("windows-latest", "ubuntu-latest", "macos-latest"):
            self.assertIn(platform, workflow.read_text(encoding="utf-8"))

    def test_windows_shortcut_uses_icon(self):
        script = (ROOT / "install-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("gitdesk.ico", script)
        self.assertIn("WScript.Shell", script)


if __name__ == "__main__":
    unittest.main()
