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
        if log.exists():
            log.unlink()
        if not env.get("DISPLAY") and sys.platform != "darwin":
            # Windows CI runners 通常没有交互桌面；offscreen 只影响验证，
            # 实际用户启动仍使用原生 Windows GUI。
            env.setdefault("QT_QPA_PLATFORM", "offscreen")
        # cwd 不在开发目录，防止意外导入源码/开发环境资源。
        process = subprocess.Popen([str(executable), str(repo)], cwd=temp, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 45
        while not log.is_file() and time.monotonic() < deadline:
            if process.poll() is not None:
                break
            time.sleep(0.25)
        if process.poll() is None:
            # 启动与历史已验证：CI 的 windowed 进程不应卡在用户关闭流程。
            # 仅结束本测试启动的进程，绝不操作其他 GitDesk 实例。
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        returncode = process.returncode
        stdout = stderr = ""
        if returncode is None:
            print("打包应用未能正常结束", file=sys.stderr)
            return 1
        if returncode != 0 and log.is_file():
            # Windows terminate 可能返回 1；已有完整成功报告则以报告为准。
            print(f"验证进程结束码 {returncode}，读取启动报告：{log}")
        if returncode != 0 and not log.is_file():
            print(f"应用退出码 {returncode}\n{stdout}\n{stderr}", file=sys.stderr)
            return 1
        if not log.is_file():
            print(f"未生成启动验证日志：{log}（进程返回码 {returncode}）\n{stdout}\n{stderr}", file=sys.stderr)
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
