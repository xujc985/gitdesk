# -*- coding: utf-8 -*-
"""独立包启动冒烟测试：真实创建临时仓库，启动、截图环境信息并优雅退出。

用法：python packaging/smoke_test.py <应用路径>
开发环境也可用 python main.py 运行；不依赖打包机桌面人工点击。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def run() -> int:
    if len(sys.argv) != 2:
        print("用法：python packaging/smoke_test.py <应用路径>", file=sys.stderr)
        return 2
    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        print(f"应用不存在：{executable}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="gitdesk-package-smoke-") as temp:
        repo = Path(temp) / "仓库 with space"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "Package Test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "package@test.local"], cwd=repo, check=True)
        (repo / "readme.md").write_text("# GitDesk 打包验证\n", encoding="utf-8")
        subprocess.run(["git", "add", "readme.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "package smoke"], cwd=repo, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        env = os.environ.copy()
        env["GITDESK_SMOKE_EXIT_MS"] = "4500"
        env["GITDESK_SMOKE_LOG"] = os.environ.get(
            "GITDESK_SMOKE_LOG",
            str(Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
                / "GitDesk" / "package-smoke.json"))
        log = Path(env["GITDESK_SMOKE_LOG"])
        log.parent.mkdir(parents=True, exist_ok=True)
        if not env.get("DISPLAY") and sys.platform != "darwin":
            # Windows CI runners 通常没有交互桌面；offscreen 只影响验证，
            # 实际用户启动仍使用原生 Windows GUI。
            env.setdefault("QT_QPA_PLATFORM", "offscreen")
        # cwd 不在开发目录，防止意外导入源码/开发环境资源。
        process = subprocess.Popen([str(executable), str(repo)], cwd=temp, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            # windowed 程序不附加控制台管道；退出状态与 JSON 日志为准。
            returncode = process.wait(timeout=45)
            stdout = stderr = ""
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            print("打包应用未在 45 秒内正常退出", file=sys.stderr)
            for candidate in (Path.home() / ".gitdesk" / "startup-error.log",
                              Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
                              / "GitDesk" / "startup-error.log"):
                if candidate.is_file():
                    print(f"启动日志 {candidate}:\n" + candidate.read_text(encoding="utf-8")[-2500:],
                          file=sys.stderr)
            return 1
        if process.returncode != 0:
            print(f"应用退出码 {process.returncode}\n{stdout}\n{stderr}", file=sys.stderr)
            return 1
        if not log.is_file():
            print(f"未生成启动验证日志：{log}\n{stdout}\n{stderr}", file=sys.stderr)
            return 1
        content = log.read_text(encoding="utf-8")
        for expected in ('"status": "ok"', '"repository":', '"history": 1',
                         '"icon": true', '"qt":'):
            if expected not in content:
                print(f"启动验证内容缺失 {expected}：{content}", file=sys.stderr)
                return 1
        print(f"打包冒烟测试通过：{content.strip()}")
        return 0


if __name__ == "__main__":
    raise SystemExit(run())
