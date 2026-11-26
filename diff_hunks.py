# -*- coding: utf-8 -*-
"""Unified diff 的分块模型与 patch 构造（纯 Python，可测试）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DiffHunk:
    header: str
    lines: list[str]
    index: int

    @property
    def patch(self) -> str:
        return self.header + "\n" + "\n".join(self.lines) + "\n"


def parse_hunks(diff: str) -> list[DiffHunk]:
    """提取每个 @@ 块，保留上下文行与 +/- 行。文件头由 patch_for_hunks 提供。"""
    lines = diff.splitlines()
    hunks: list[DiffHunk] = []
    index = -1
    for line in lines:
        if line.startswith("@@"):
            index += 1
            hunks.append(DiffHunk(line, [], index))
        elif index >= 0:
            hunks[index].lines.append(line)
    return hunks


def patch_for_hunks(diff: str, indices: list[int]) -> str:
    """用原文件 diff 头和选中的 hunk 构造仅暂存 patch。"""
    selected = set(indices)
    header: list[str] = []
    for line in diff.splitlines():
        if line.startswith("@@"):
            break
        if line.startswith(("diff ", "index ", "--- ", "+++ ", "new file",
                            "deleted file", "similarity ", "rename ", "old mode",
                            "new mode", "mode ")):
            header.append(line)
    body = [hunk.patch.rstrip("\n") for hunk in parse_hunks(diff) if hunk.index in selected]
    if not body:
        raise ValueError("未选择任何差异块")
    return "\n".join(header + body) + "\n"
