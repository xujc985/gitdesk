# -*- coding: utf-8 -*-
"""彩色历史轨道布局。输入必须为拓扑排序（子提交先于父提交）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

PALETTE = (
    "#62aeef", "#56c364", "#e3b341", "#c98bdb", "#f28b82",
    "#76d4d4", "#d29962", "#a4c56b", "#e36fae", "#8a9adf",
)


@dataclass(frozen=True)
class GraphEdge:
    from_col: int
    to_col: int
    to_row: int
    color_index: int


@dataclass
class GraphRow:
    sha: str
    column: int
    color_index: int
    edges: list[GraphEdge]
    merge: bool = False
    head: bool = False


def layout_commits(commits: Sequence) -> tuple[list[GraphRow], int]:
    """按真实父子关系分配轨道。相同分支保持相同列/颜色。

    先处理提交的所有父节点，再释放当前节点轨道，确保合并提交的第一父
    与第二父不会错误地共用一列。行末之后仍活动的轨道也计入图宽度。
    """
    active: dict[str, tuple[int, int]] = {}
    rows: list[GraphRow] = []

    def free_column(used: set[int]) -> int:
        col = 0
        while col in used:
            col += 1
        return col

    def fresh_color(used: set[int]) -> int:
        colors = {color for col, color in active.values() if col in used}
        for index in range(len(PALETTE)):
            if index not in colors:
                return index
        return len(colors) % len(PALETTE)

    for commit in commits:
        if commit.sha in active:
            col, color = active[commit.sha]
        else:
            used = {c for c, _color in active.values()}
            col = free_column(used)
            color = fresh_color(used)
        # 其他待处理父轨道仍被占用；当前节点不能抢用其中一条。
        reserved = {column for sha, (column, _color) in active.items()
                    if sha != commit.sha}
        edges: list[GraphEdge] = []
        for index, parent in enumerate(getattr(commit, "parents", ())):
            if not parent:
                continue
            if parent in active:
                pcol, pcolor = active[parent]
            else:
                pcol = col if index == 0 else free_column(reserved | {col})
                pcolor = color if index == 0 else fresh_color(reserved)
                active[parent] = (pcol, pcolor)
                reserved.add(pcol)
            edges.append(GraphEdge(col, pcol, -1, color))
        # 当前提交已出现，只有未继续指向其他父提交的同 SHA 占位才移除。
        active.pop(commit.sha, None)
        rows.append(GraphRow(commit.sha, col, color, edges,
                             merge=len(getattr(commit, "parents", ())) > 1))

    positions = {row.sha: (index, row.column) for index, row in enumerate(rows)}
    for index, row in enumerate(rows):
        row.head = bool(getattr(commits[index], "is_head", False))
        for j, parent in enumerate(getattr(commits[index], "parents", ())):
            if j < len(row.edges) and parent in positions:
                prow, pcol = positions[parent]
                row.edges[j] = GraphEdge(row.column, pcol, prow,
                                         row.edges[j].color_index)
    lanes = [0]
    for row in rows:
        lanes.append(row.column)
        lanes.extend(edge.to_col for edge in row.edges)
    return rows, max(lanes) + 1
