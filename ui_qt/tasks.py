# -*- coding: utf-8 -*-
"""单个 QThread 后台执行器（Qt 信号驱动，结果在主线程派发）。"""
from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot


class Task(QObject):
    execute_requested = Signal()
    finished = Signal(object, object, object, object)

    def __init__(self, runner, name, fn, callbacks, repo, write):
        super().__init__()
        self.runner, self.name, self.fn = runner, name, fn
        self.callbacks, self.repo, self.write = callbacks, repo, write
        self.execute_requested.connect(self.execute, Qt.ConnectionType.QueuedConnection)
        self.finished.connect(runner.dispatch)

    @Slot()
    def execute(self):
        if not self.runner.alive:
            # 关闭时仍执行已接受的 Git，完成后由 complete 自然退出线程；
            # 不允许任务队列悬在半截。
            pass
        elif not self.write and self.repo is not self.runner.repo:
            self.runner.complete(self)
            self.deleteLater()
            return
        try:
            result, error = self.fn(), None
        except Exception as exc:
            result, error = None, exc
        self.finished.emit(self, result, error, self.callbacks)
        self.runner.complete(self)
        self.deleteLater()


class Scheduler(QObject):
    wake = Signal()

    def __init__(self, runner):
        super().__init__()
        self.runner = runner
        self.wake.connect(self.start_next, Qt.ConnectionType.QueuedConnection)

    @Slot()
    def start_next(self):
        self.runner._start_next()


class TaskRunner(QObject):
    task_started = Signal(str)
    task_finished = Signal(str)

    def __init__(self):
        super().__init__()
        self.repo = None
        self.alive = True
        self._lock = threading.RLock()
        self._busy = 0
        self._pending: set[str] = set()
        self._tasks: set[Task] = set()
        self._queued: list[Task] = []
        self._executing = False
        self.thread = QThread(self)
        self.thread.setObjectName("GitDesk-Worker")
        self.scheduler = Scheduler(self)
        self.scheduler.moveToThread(self.thread)
        self._wake = self.scheduler.wake
        self.thread.start()

    @property
    def busy(self):
        with self._lock:
            return self._busy > 0

    def set_repo(self, repo):
        self.repo = repo

    def run(self, name: str, fn: Callable, on_ok: Callable | None = None,
            on_err: Callable | None = None, write: bool = False,
            coalesce: bool = False) -> Task | None:
        if not self.alive:
            return None
        with self._lock:
            if coalesce and name in self._pending:
                for pending in self._tasks:
                    if pending.name == name and pending.repo is self.repo:
                        pending.callbacks = (on_ok, on_err)
                        break
                return None
            self._busy += 1
            if coalesce:
                self._pending.add(name)
        task = Task(self, name, fn, (on_ok, on_err), self.repo, write)
        task.moveToThread(self.thread)
        self._tasks.add(task)
        self._queued.append(task)
        self.task_started.emit(name)
        self._wake.emit()
        return task

    @Slot()
    def _start_next(self):
        if self._executing or not self._queued:
            if not self.alive and not self._executing:
                self.thread.quit()
            return
        # shutdown 后不再接收新任务，但队列中已接受的 Git 必须排空，
        # 否则 _executing/busy 永远不会归零。
        self._executing = True
        task = self._queued.pop(0)
        # 信号从 worker 发给 task（也在 worker），QueuedConnection 保证
        # 任务不会意外在 GUI 线程直接执行。
        task.execute_requested.emit()

    def complete(self, task: Task):
        with self._lock:
            self._pending.discard(task.name)
            self._busy = max(0, self._busy - 1)
        self._executing = False
        if not self.alive and not self._queued:
            self.thread.quit()
        self.task_finished.emit(task.name)
        self._wake.emit()

    @Slot(object, object, object, object)
    def dispatch(self, task, result, error, callbacks):
        self._tasks.discard(task)
        if self.alive and (task.write or task.repo is self.repo):
            on_ok, on_err = callbacks
            if error is not None:
                if on_err:
                    on_err(error)
            elif on_ok:
                on_ok(result)

    def shutdown(self):
        """停止接受新任务，让 worker 处理完当前 Git 后退出。

        不能在 GUI 线程 sleep 等结果：结果回调需要 GUI 事件循环。这里让
        当前任务完成时直接 quit worker；调用方关闭窗口仍很短，不会强杀 Git。
        """
        self.alive = False
        if not self.busy:
            self.thread.quit()
        # 若任务正忙，complete() 会在当前 Git 结束后调用 quit()；
        # 此处仅等待事件循环退出，不阻塞正在执行的 Git。
        self.thread.wait(12000)
