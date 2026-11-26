# -*- coding: utf-8 -*-
"""PyCharm 风格多车道提交拓扑布局。"""
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
    """分配真实分支轨道：主线稳定，多个并行分支各占一列。

    输入必须是 topo-order（子先于父）。每个活跃父提交对应一条分支，
    当前节点消费自己的分支，其余活跃分支保留。第二父需要新分支时
    分配下一个空闲车道，不把不同分支折叠到同一颜色/列。
    """
    # sha -> (lane, color)，表示该提交还未在历史中出现。
    active: dict[str, tuple[int, int]] = {}
    rows: list[GraphRow] = []

    def free_lane(reserved: set[int]) -> int:
        lane = 0
        while lane in reserved:
            lane += 1
        return lane

    def free_color(reserved: set[int]) -> int:
        used = {color for lane, color in active.values() if lane in reserved}
        for color in range(len(PALETTE)):
            if color not in used:
                return color
        return len(used) % len(PALETTE)

    for commit in commits:
        if commit.sha in active:
            lane, color = active.pop(commit.sha)
        else:
            occupied = {lane for lane, _color in active.values()}
            lane, color = free_lane(occupied), free_color(occupied)
        # 其他待出现的提交仍在各自分支上，不能被当前提交覆盖。
        reserved = {lane for lane, _color in active.values()}
        parents = [p for p in getattr(commit, "parents", ()) if p]
        edges: list[GraphEdge] = []
        for index, parent in enumerate(parents):
            if parent in active:
                parent_lane, parent_color = active[parent]
                # 同一提交被多个分支需要时，第一父继承当前主线；
                # 第二父若与当前列重合，则为该父分支保留独立车道。
                if index == 0:
                    parent_lane, parent_color = lane, color
                elif parent_lane == lane:
                    parent_lane = free_lane(reserved | {lane})
                    parent_color = free_color(reserved | {lane})
                    reserved.add(parent_lane)
                    active[parent] = (parent_lane, parent_color)
            else:
                if index == 0:
                    parent_lane, parent_color = lane, color
                else:
                    parent_lane = free_lane(reserved | {lane})
                    parent_color = free_color(reserved | {lane})
                    reserved.add(parent_lane)
                active[parent] = (parent_lane, parent_color)
            edges.append(GraphEdge(lane, parent_lane, -1, color))
        # 当前节点已出现，其他分支继续存在；不要把整条历史删掉。
        rows.append(GraphRow(commit.sha, lane, color, edges,
                             merge=len(parents) > 1))

    # 第二父边的颜色跟随目标分支；主线颜色不因合流跳变。
    positions = {row.sha: (index, row.column) for index, row in enumerate(rows)}
    for index, row in enumerate(rows):
        row.head = bool(getattr(commits[index], "is_head", False))
        for parent_index, parent in enumerate(getattr(commits[index], "parents", ())):
            if parent_index < len(row.edges) and parent in positions:
                parent_row, parent_lane = positions[parent]
                row.edges[parent_index] = GraphEdge(
                    row.column, parent_lane, parent_row,
                    rows[parent_row].color_index)
    lane_count = max(
        [row.column for row in rows]
        + [edge.to_col for row in rows for edge in row.edges] + [0]) + 1
    return rows, lane_count
