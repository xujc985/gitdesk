# -*- coding: utf-8 -*-
"""真实父提交拓扑的彩色分支轨道布局。"""
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
    """按真实父子关系分配彩色分支轨道，第二父与主线永不共用。"""
    active: dict[str, tuple[int, int]] = {}
    rows: list[GraphRow] = []

    def free_column(used: set[int]) -> int:
        column = 0
        while column in used:
            column += 1
        return column

    def free_color(used: set[int]) -> int:
        colors = {color for _column, color in active.values() if _column in used}
        for index in range(len(PALETTE)):
            if index not in colors:
                return index
        return len(colors) % len(PALETTE)

    for commit in commits:
        if commit.sha in active:
            col, color = active[commit.sha]
        else:
            used = {column for column, _color in active.values()}
            col, color = free_column(used), free_color(used)
        parents = [parent for parent in getattr(commit, "parents", ()) if parent]
        reserved = {column for column, _color in active.values()}
        edges: list[GraphEdge] = []
        for index, parent in enumerate(parents):
            if parent in active:
                parent_col, parent_color = active[parent]
                # 父提交轨道一旦分配就固定，不能被另一分支改写。
                # 合并节点通过不同来源的两条边自然汇流。
                if index > 0 and parent_col == col:
                    parent_col = free_column(reserved | {col})
                    parent_color = free_color(reserved | {col})
                    active[parent] = (parent_col, parent_color)
                    reserved.add(parent_col)
                # 不能把合并双方画成一条直线。
                if index > 0 and parent_col == col:
                    parent_col = free_column(reserved | {col})
                    parent_color = free_color(reserved | {col})
                    active[parent] = (parent_col, parent_color)
                    reserved.add(parent_col)
            else:
                if index == 0:
                    parent_col, parent_color = col, color
                else:
                    parent_col = free_column(reserved | {col})
                    parent_color = free_color(reserved | {col})
                    reserved.add(parent_col)
                active[parent] = (parent_col, parent_color)
            edges.append(GraphEdge(col, parent_col, -1, color))
        active.pop(commit.sha, None)
        rows.append(GraphRow(commit.sha, col, color, edges,
                             merge=len(parents) > 1))

    positions = {row.sha: (index, row.column) for index, row in enumerate(rows)}
    for index, row in enumerate(rows):
        row.head = bool(getattr(commits[index], "is_head", False))
        for parent_index, parent in enumerate(getattr(commits[index], "parents", ())):
            if parent_index < len(row.edges) and parent in positions:
                parent_row, parent_col = positions[parent]
                row.edges[parent_index] = GraphEdge(
                    row.column, parent_col, parent_row,
                    # 边的颜色跟随目标父分支，保证节点与连线一致。
                    rows[parent_row].color_index)
    lane_count = max(
        [row.column for row in rows]
        + [edge.to_col for row in rows for edge in row.edges] + [0]) + 1
    return rows, lane_count
