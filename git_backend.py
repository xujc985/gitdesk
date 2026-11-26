# -*- coding: utf-8 -*-
"""GitDesk 后端：封装本机 git 命令，提供结构化数据。

所有操作直接调用系统 git（与用户全局配置、凭据、SSH 代理完全兼容）。
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

# Windows 下避免弹出黑色控制台窗口
_CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


class GitError(Exception):
    def __init__(self, message: str, stderr: str = "", code: int = 1):
        super().__init__(message)
        self.stderr = stderr
        self.code = code


def run_git(args: list[str], cwd: str, timeout: int = 120,
            input_text: Optional[str] = None) -> tuple[int, str, str]:
    """执行 git 命令，返回 (returncode, stdout, stderr)。永不抛异常。"""
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            input=input_text,
            creationflags=_CREATION_FLAGS,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", "未找到 git 可执行文件，请先安装 Git"
    except subprocess.TimeoutExpired:
        return 124, "", f"命令超时（{timeout} 秒）"
    except Exception as exc:  # noqa: BLE001
        return 1, "", str(exc)


def check(args: list[str], cwd: str, timeout: int = 120,
          input_text: Optional[str] = None) -> str:
    """执行 git 命令，失败时抛 GitError，成功返回 stdout。

    PyCharm、终端或本应用的另一个任务可能短暂持有 index.lock；
    只在明确检测到索引锁时等待并重试，避免瞬时并发导致误报。
    """
    import time
    for attempt in range(4):
        code, out, err = run_git(args, cwd, timeout, input_text)
        if code == 0:
            return out
        if "index.lock" not in err or attempt == 3:
            raise GitError((err or out or f"git {' '.join(args)} 失败").strip(),
                           stderr=err, code=code)
        time.sleep(0.35 * (attempt + 1))
    raise AssertionError("unreachable")


# git 输出中使用的字段分隔符（ASCII 单元分隔符，不会出现在正常文本里）。
# 注意：不要用 %x1f 让 git 自己展开 —— Windows 命令行下 % 可能被吞掉。
US = "\x1f"


# ----------------------------- 数据结构 -----------------------------

@dataclass
class FileStatus:
    path: str
    x: str = " "          # 暂存区状态
    y: str = " "          # 工作区状态
    orig_path: str = ""   # 重命名前的路径

    @property
    def staged(self) -> bool:
        return self.x not in (" ", "?", "!")

    @property
    def unstaged(self) -> bool:
        return self.y not in (" ", "?", "!")

    @property
    def untracked(self) -> bool:
        return self.x == "?"

    @property
    def conflicted(self) -> bool:
        return (self.x, self.y) in {
            ("D", "D"), ("A", "A"), ("U", "U"),
            ("A", "U"), ("U", "A"), ("D", "U"), ("U", "D"),
        }

    STATUS_NAMES = {
        "M": "已修改", "A": "新增", "D": "已删除", "R": "重命名",
        "C": "复制", "T": "类型变化", "U": "冲突", "?": "未跟踪", "!": "已忽略",
    }

    def label(self) -> str:
        code = self.x if self.staged else self.y
        return self.STATUS_NAMES.get(code, code)


@dataclass
class RepoStatus:
    branch: str = ""
    upstream: str = ""
    ahead: int = 0
    behind: int = 0
    detached: bool = False
    merging: bool = False
    rebasing: bool = False
    files: list[FileStatus] = field(default_factory=list)

    @property
    def staged(self) -> list[FileStatus]:
        return [f for f in self.files
                if f.staged and not f.untracked and not f.conflicted]

    @property
    def unstaged(self) -> list[FileStatus]:
        return [f for f in self.files
                if f.unstaged and not f.untracked and not f.conflicted]

    @property
    def untracked(self) -> list[FileStatus]:
        return [f for f in self.files if f.untracked]

    @property
    def conflicted(self) -> list[FileStatus]:
        return [f for f in self.files if f.conflicted]


@dataclass
class Commit:
    sha: str
    short: str
    subject: str
    author: str
    email: str
    date: str
    refs: str = ""
    graph: str = ""       # 旧的字符图形（仅用于调试；UI 使用彩色轨道）
    parents: list[str] = field(default_factory=list)
    is_head: bool = False


@dataclass
class Branch:
    name: str
    current: bool = False
    remote: bool = False
    upstream: str = ""
    ahead: int = 0
    behind: int = 0
    last_subject: str = ""
    last_date: str = ""


@dataclass
class Tag:
    name: str
    sha: str = ""
    subject: str = ""
    annotated: bool = False


@dataclass
class Stash:
    index: int
    message: str
    branch: str = ""
    sha: str = ""


@dataclass
class Remote:
    name: str
    fetch_url: str = ""
    push_url: str = ""


# ----------------------------- 仓库操作 -----------------------------

class Repo:
    def __init__(self, path: str):
        path = os.path.abspath(path)
        self.path = path
        # 始终从当前输入路径定位仓库根（可位于任意深度子目录）。
        # 非仓库输入由 is_repo 统一判断，不抛出额外异常。
        code, out, _ = run_git(["rev-parse", "--show-toplevel"], path)
        if code == 0 and out.strip():
            self.path = os.path.abspath(out.strip())

    # ---- 基础 ----
    @staticmethod
    def is_repo(path: str) -> bool:
        code, out, _ = run_git(["rev-parse", "--is-inside-work-tree"], path)
        return code == 0 and out.strip() == "true"

    @staticmethod
    def init(path: str) -> None:
        os.makedirs(path, exist_ok=True)
        check(["init"], path)

    @staticmethod
    def clone(url: str, dest: str, on_output: Optional[Callable[[str], None]] = None) -> str:
        parent = os.path.dirname(os.path.abspath(dest)) or "."
        if on_output:
            # 流式输出 clone 进度
            proc = subprocess.Popen(
                ["git", "clone", "--progress", url, dest],
                cwd=parent, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=_CREATION_FLAGS,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                on_output(line.rstrip())
            proc.wait()
            if proc.returncode != 0:
                raise GitError(f"克隆失败（退出码 {proc.returncode}）")
        else:
            check(["clone", url, dest], parent, timeout=3600)
        return os.path.abspath(dest)

    def git(self, args: list[str], timeout: int = 120,
            input_text: Optional[str] = None) -> str:
        return check(args, self.path, timeout, input_text)

    # ---- 状态 ----
    def status(self) -> RepoStatus:
        st = RepoStatus()
        code, out, err = run_git(
            ["status", "--porcelain=v1", "-z", "--branch", "-uall", "--ahead-behind"],
            self.path)
        if code != 0:
            raise GitError((err or "获取状态失败").strip(), stderr=err, code=code)

        root = os.path.join(self.path, ".git")
        if not os.path.isdir(root):
            # worktree 场景 .git 是文件
            try:
                with open(root, encoding="utf-8") as fh:
                    gd = fh.read().split(":", 1)[1].strip()
                root = gd if os.path.isabs(gd) else os.path.normpath(
                    os.path.join(self.path, gd))
            except OSError:
                pass
        st.merging = os.path.exists(os.path.join(root, "MERGE_HEAD"))
        st.rebasing = (os.path.exists(os.path.join(root, "rebase-merge"))
                       or os.path.exists(os.path.join(root, "rebase-apply")))

        # -z 使用 NUL 分隔且路径不做 C 风格引号转义，兼容空格/中文/换行。
        # 重命名记录由 path\0orig_path\0 组成，不能按文本箭头拆分。
        lines = out.split("\0")
        header = lines.pop(0) if lines else ""
        for line in [header]:
            if line.startswith("## "):
                info = line[3:]
                m = re.match(r"HEAD \(no branch\)", info)
                if m or info.startswith("HEAD"):
                    st.detached = True
                    st.branch = "HEAD"
                    continue
                m = re.match(r"No commits yet on (.+?)(?:\.\.\.|$)", info)
                if m:
                    st.branch = m.group(1)
                    continue
                tracking = ""
                m = re.search(r"\[(.+)\]$", info)
                if m:
                    tracking = m.group(1)
                    info = info[:m.start()].rstrip()
                if "..." in info:
                    st.branch, st.upstream = info.split("...", 1)
                else:
                    st.branch = info
                am = re.search(r"ahead (\d+)", tracking)
                bm = re.search(r"behind (\d+)", tracking)
                st.ahead = int(am.group(1)) if am else 0
                st.behind = int(bm.group(1)) if bm else 0
                continue
        index = 0
        while index < len(lines):
            line = lines[index]
            index += 1
            if len(line) < 4:
                continue
            x, y = line[0], line[1]
            rest = line[3:]
            orig = ""
            if x in ("R", "C") and index < len(lines):
                orig = lines[index]
                index += 1
            st.files.append(FileStatus(path=rest, x=x, y=y, orig_path=orig))
        return st

    # ---- 变更 / 暂存 ----
    def stage(self, paths: list[str]) -> None:
        self.git(["add", "--"] + paths)

    def stage_all(self) -> None:
        self.git(["add", "-A"])

    def unstage(self, paths: list[str]) -> None:
        code, out, err = run_git(["restore", "--staged", "--"] + paths, self.path)
        if code != 0:
            self.git(["reset", "HEAD", "--"] + paths)  # 兼容旧版本 git

    def discard(self, paths: list[str], untracked: bool = False) -> None:
        """丢弃变更。untracked=True 时按未跟踪文件清理；否则还原已跟踪文件。

        已暂存的文件先还原暂存区再还原工作区；尚无提交（无 HEAD）的仓库里
        已跟踪文件不存在，直接跳过还原。
        """
        if untracked:
            self.git(["clean", "-fd", "--"] + paths)
            return
        if not paths:
            return
        code, _, _ = run_git(["rev-parse", "--verify", "--quiet", "HEAD"],
                             self.path)
        if code != 0:
            # 无 HEAD：暂存新文件需先从索引移除，再按用户选择的“回滚”
            # 删除工作区内容；避免静默保留数据。
            self.git(["rm", "--cached", "-r", "--ignore-unmatch", "--"] + paths)
            self.git(["clean", "-fd", "--"] + paths)
            return
        run_git(["restore", "--staged", "--"] + paths, self.path)
        self.git(["restore", "--worktree", "--"] + paths)

    def diff(self, path: Optional[str] = None, staged: bool = False,
             commit: Optional[str] = None, context: int = 3,
             worktree: bool = False) -> str:
        args = ["diff", f"--unified={context}", "--no-color"]
        if staged:
            args.append("--staged")
        if worktree:
            # 同时显示暂存和工作区相对 HEAD 的全部更改。
            args.append("HEAD")
        if commit:
            args += [commit + "^", commit] if self.has_parent(commit) else [
                "4b825dc642cb6eb9a060e54bf8d69288fbee4904", commit]
        args.append("--")
        if path:
            args.append(path)
        code, out, err = run_git(args, self.path)
        if code != 0:
            raise GitError((err or "获取差异失败").strip())
        return out

    def diff_commit(self, commit: str, path: Optional[str] = None) -> str:
        args = ["show", commit, "--format=", "--no-color", "--patch"]
        args.append("--")
        if path:
            args.append(path)
        return self.git(args)

    def has_parent(self, commit: str) -> bool:
        code, _, _ = run_git(["rev-parse", "--verify", "--quiet", commit + "^"],
                             self.path)
        return code == 0

    # ---- 提交 ----
    def commit(self, message: str, amend: bool = False,
               author: Optional[str] = None) -> str:
        args = ["commit", "-m", message]
        if amend:
            args.append("--amend")
            if not message:
                args.append("--no-edit")
        if author:
            args += ["--author", author]
        return self.git(args)

    def log(self, limit: int = 500, all_refs: bool = True,
            branch: Optional[str] = None, path: Optional[str] = None,
            grep: Optional[str] = None, author: Optional[str] = None) -> list[Commit]:
        fmt = US.join(["", "%H", "%h", "%s", "%an", "%ae", "%ad", "%D", "%P"])
        args = ["log", f"--pretty=tformat:{fmt}",
                "--date=format:%Y-%m-%d %H:%M", f"-n{limit}"]
        if all_refs:
            args.append("--all")
        if branch:
            args.append(branch)
        if grep:
            args += ["--grep", grep, "-i"]
        if author:
            args += ["--author", author]
        args.append("--topo-order")
        args.append("--")
        if path:
            args.append(path)
        code, out, err = run_git(args, self.path)
        if code != 0:
            raise GitError((err or "获取历史失败").strip())
        commits: list[Commit] = []
        for line in out.splitlines():
            if US not in line:
                continue
            graph, _, rest = line.partition(US)
            parts = rest.split(US)
            if len(parts) < 8:
                continue
            commits.append(Commit(
                graph=graph.rstrip(), sha=parts[0], short=parts[1],
                subject=parts[2], author=parts[3], email=parts[4],
                date=parts[5], refs=parts[6],
                parents=parts[7].split() if parts[7] else []))
        return commits

    def commit_detail(self, sha: str) -> str:
        return self.git(["show", sha, "--stat", "--format=fuller", "--no-color",
                         "--no-patch"]) + "\n" + self.git(
            ["show", sha, "--stat", "--format=", "--no-color"])

    def commit_files(self, sha: str) -> list[FileStatus]:
        # --root：让根提交也列出全部文件；--no-commit-id：不输出提交行
        code, out, err = run_git(
            ["diff-tree", "--root", "--no-commit-id", "--name-status",
             "-r", "-M", sha], self.path)
        if code != 0:
            raise GitError((err or "获取提交文件失败").strip())
        files: list[FileStatus] = []
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            code_letter = parts[0][0]
            if code_letter in ("R", "C") and len(parts) >= 3:
                files.append(FileStatus(path=parts[2], x=code_letter,
                                        orig_path=parts[1]))
            elif len(parts) >= 2:
                files.append(FileStatus(path=parts[1], x=code_letter))
        return files

    def show_file(self, sha: str, path: str) -> str:
        return self.git(["show", f"{sha}:{path}"])

    def blame(self, path: str) -> str:
        return self.git(["blame", "--date=short", path])

    # ---- 分支 ----
    def branches(self) -> tuple[list[Branch], list[Branch]]:
        """返回 (本地分支, 远程分支)。用 refname 命名空间直接区分，无额外子进程。"""
        fmt = US.join(["%(refname)", "%(refname:short)", "%(upstream:short)",
                       "%(upstream:track)", "%(subject)",
                       "%(committerdate:short)", "%(HEAD)"])
        code, out, err = run_git(
            ["branch", "--format", fmt, "--all", "--sort=-committerdate"],
            self.path)
        if code != 0:
            raise GitError((err or "获取分支失败").strip())
        local: list[Branch] = []
        remote: list[Branch] = []
        for line in out.splitlines():
            parts = line.split(US)
            if len(parts) < 7:
                continue
            refname, short, upstream, track, subject, date, head = parts[:7]
            is_remote = refname.startswith("refs/remotes/")
            if is_remote and short.endswith("/HEAD"):
                continue  # 远程 HEAD 符号链接
            ahead = behind = 0
            m = re.search(r"ahead (\d+)", track)
            if m:
                ahead = int(m.group(1))
            m = re.search(r"behind (\d+)", track)
            if m:
                behind = int(m.group(1))
            b = Branch(name=short, current=(head.strip() == "*"),
                       remote=is_remote, upstream=upstream,
                       ahead=ahead, behind=behind,
                       last_subject=subject, last_date=date)
            (remote if is_remote else local).append(b)
        return local, remote

    def current_branch(self) -> str:
        code, out, _ = run_git(["branch", "--show-current"], self.path)
        if code == 0 and out.strip():
            return out.strip()
        code, out, _ = run_git(["rev-parse", "--short", "HEAD"], self.path)
        return f"({out.strip()} detached)" if code == 0 else ""

    def create_branch(self, name: str, start: Optional[str] = None,
                      checkout: bool = True) -> None:
        args = ["checkout", "-b", name] if checkout else ["branch", name]
        if start:
            args.append(start)
        self.git(args)

    def checkout(self, name: str) -> None:
        self.git(["checkout", name])

    def checkout_remote(self, remote_branch: str, local_name: Optional[str] = None) -> None:
        local_name = local_name or remote_branch.split("/", 1)[-1]
        self.git(["checkout", "-b", local_name, "--track", remote_branch])

    def delete_branch(self, name: str, force: bool = False,
                      remote: bool = False, remote_name: str = "origin") -> None:
        if remote:
            self.git(["push", remote_name, "--delete", name], timeout=300)
        else:
            self.git(["branch", "-D" if force else "-d", name])

    def rename_branch(self, old: str, new: str) -> None:
        self.git(["branch", "-m", old, new])

    def set_upstream(self, branch: str, upstream: str) -> None:
        self.git(["branch", "--set-upstream-to", upstream, branch])

    def merge(self, name: str, no_ff: bool = False, squash: bool = False,
              message: Optional[str] = None) -> str:
        args = ["merge"]
        if no_ff:
            args.append("--no-ff")
        if squash:
            args.append("--squash")
        if message:
            args += ["-m", message]
        args.append(name)
        return self.git(args, timeout=300)

    def merge_abort(self) -> None:
        self.git(["merge", "--abort"])

    def rebase(self, onto: str) -> str:
        return self.git(["rebase", onto], timeout=600)

    def rebase_continue(self) -> None:
        self.git(["-c", "core.editor=true", "rebase", "--continue"], timeout=300)

    def rebase_abort(self) -> None:
        self.git(["rebase", "--abort"])

    def cherry_pick(self, sha: str) -> str:
        return self.git(["cherry-pick", sha])

    def revert(self, sha: str) -> str:
        return self.git(["revert", "--no-edit", sha])

    def reset(self, mode: str, target: str = "HEAD") -> str:
        assert mode in ("soft", "mixed", "hard")
        return self.git(["reset", f"--{mode}", target])

    def reflog(self, limit: int = 200) -> str:
        return self.git(["reflog", f"-n{limit}", "--date=local"])

    # ---- 远程 ----
    def remotes(self) -> list[Remote]:
        code, out, err = run_git(["remote", "-v"], self.path)
        if code != 0:
            raise GitError((err or "获取远程失败").strip())
        remotes: dict[str, Remote] = {}
        for line in out.splitlines():
            m = re.match(r"(\S+)\s+(\S+)\s+\((fetch|push)\)", line)
            if not m:
                continue
            name, url, kind = m.groups()
            r = remotes.setdefault(name, Remote(name=name))
            if kind == "fetch":
                r.fetch_url = url
            else:
                r.push_url = url
        return list(remotes.values())

    def add_remote(self, name: str, url: str) -> None:
        self.git(["remote", "add", name, url])

    def remove_remote(self, name: str) -> None:
        self.git(["remote", "remove", name])

    def set_remote_url(self, name: str, url: str) -> None:
        self.git(["remote", "set-url", name, url])

    def fetch(self, remote: Optional[str] = None, prune: bool = True) -> str:
        args = ["fetch", "--all"] if not remote else ["fetch", remote]
        if prune:
            args.append("--prune")
        return self.git(args, timeout=600)

    def pull(self, rebase: bool = False, remote: Optional[str] = None,
             branch: Optional[str] = None) -> str:
        args = ["pull"]
        if rebase:
            args.append("--rebase")
        if remote:
            args.append(remote)
        if branch:
            args.append(branch)
        return self.git(args, timeout=600)

    def push(self, remote: Optional[str] = None, branch: Optional[str] = None,
             set_upstream: bool = False, force: bool = False,
             tags: bool = False) -> str:
        args = ["push"]
        if force:
            args.append("--force-with-lease")
        if tags:
            args.append("--tags")
        if set_upstream:
            args.append("-u")
        if remote:
            args.append(remote)
        if branch:
            args.append(branch)
        return self.git(args, timeout=600)

    # ---- Stash ----
    def stashes(self) -> list[Stash]:
        code, out, err = run_git(
            ["stash", "list", "--format=" + US.join(["%gd", "%H", "%gs"])],
            self.path)
        if code != 0:
            return []
        result: list[Stash] = []
        for line in out.splitlines():
            parts = line.split(US)
            if len(parts) < 3:
                continue
            m = re.search(r"\{(\d+)\}", parts[0])
            result.append(Stash(
                index=int(m.group(1)) if m else 0,
                message=parts[2], sha=parts[1]))
        return result

    def stash_push(self, message: str = "", include_untracked: bool = False,
                   keep_index: bool = False) -> str:
        args = ["stash", "push"]
        if include_untracked:
            args.append("-u")
        if keep_index:
            args.append("--keep-index")
        if message:
            args += ["-m", message]
        return self.git(args)

    def stash_apply(self, index: int = 0, pop: bool = False,
                    sha: str = "") -> str:
        target = sha if pop and sha else f"stash@{{{index}}}"
        # pop 仍要求 stash ref，apply 可以用不可变 SHA，避免预览/应用串项。
        return self.git(["stash", "pop" if pop else "apply", target])

    def stash_drop(self, index: int = 0, sha: str = "") -> str:
        if sha:
            stashes = self.stashes()
            match = next((s.index for s in stashes if s.sha == sha), None)
            if match is None:
                raise GitError("该贮藏已不存在，请刷新后重试。")
            index = match
        return self.git(["stash", "drop", f"stash@{{{index}}}"])

    def stash_show(self, index: int = 0, sha: str = "") -> str:
        return self.git(["stash", "show", "-p", sha or f"stash@{{{index}}}"])

    # ---- 标签 ----
    def tags(self) -> list[Tag]:
        fmt = US.join(["%(refname:short)", "%(objectname:short)",
                       "%(subject)", "%(objecttype)"])
        code, out, err = run_git(["tag", "--list", "--format", fmt,
                                  "--sort=-creatordate"], self.path)
        if code != 0:
            raise GitError((err or "获取标签失败").strip())
        result = []
        for line in out.splitlines():
            parts = line.split(US)
            if len(parts) < 4:
                continue
            result.append(Tag(name=parts[0], sha=parts[1], subject=parts[2],
                              annotated=(parts[3] == "tag")))
        return result

    def create_tag(self, name: str, message: Optional[str] = None,
                   target: Optional[str] = None) -> None:
        args = ["tag"]
        if message:
            args += ["-a", name, "-m", message]
        else:
            args.append(name)
        if target:
            args.append(target)
        self.git(args)

    def delete_tag(self, name: str, remote: Optional[str] = None) -> None:
        self.git(["tag", "-d", name])
        if remote:
            self.git(["push", remote, ":refs/tags/" + name], timeout=300)

    def push_tag(self, name: str, remote: str = "origin") -> str:
        return self.git(["push", remote, name], timeout=300)

    # ---- 子模块 / Worktree ----
    def submodules(self) -> str:
        code, out, err = run_git(["submodule", "status", "--recursive"], self.path)
        if code != 0:
            return err.strip()
        return out.strip()

    def submodule_update(self, init: bool = True, recursive: bool = True) -> str:
        args = ["submodule", "update"]
        if init:
            args.append("--init")
        if recursive:
            args.append("--recursive")
        return self.git(args, timeout=900)

    def submodule_add(self, url: str, path: str) -> str:
        return self.git(["submodule", "add", url, path], timeout=900)

    def worktrees(self) -> str:
        return self.git(["worktree", "list"])

    def worktree_add(self, path: str, branch: Optional[str] = None,
                     new_branch: Optional[str] = None) -> str:
        args = ["worktree", "add"]
        if new_branch:
            args += ["-b", new_branch]
        args.append(path)
        if branch:
            args.append(branch)
        return self.git(args)

    def worktree_remove(self, path: str, force: bool = False) -> str:
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(path)
        return self.git(args)

    # ---- 配置 ----
    def config_get(self, key: str) -> str:
        code, out, _ = run_git(["config", "--get", key], self.path)
        return out.strip() if code == 0 else ""

    def config_set(self, key: str, value: str, global_: bool = False) -> None:
        args = ["config"] + (["--global"] if global_ else []) + [key, value]
        self.git(args)

    def ahead_behind_of(self, left: str, right: str) -> tuple[int, int]:
        code, out, _ = run_git(["rev-list", "--left-right", "--count",
                                f"{left}...{right}"], self.path)
        if code != 0:
            return 0, 0
        parts = out.split()
        return (int(parts[0]), int(parts[1])) if len(parts) == 2 else (0, 0)


# ----------------------------- 后台执行器 -----------------------------

class TaskRunner:
    """在后台线程执行 git 操作，避免阻塞 UI。"""

    def __init__(self, ui_callback: Callable[[str, object], None]):
        self.ui_callback = ui_callback  # (kind, payload)，必须在主线程安全地调用
        self._running = 0
        self._lock = threading.Lock()
        self._pending: dict[str, list] = {}
        self._write_lock = threading.Lock()  # 同一工作区写操作串行

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._running > 0

    def run(self, name: str, fn: Callable[[], object],
            on_ok: Optional[Callable[[object], None]] = None,
            on_err: Optional[Callable[[Exception], None]] = None,
            on_done: Optional[Callable[[], None]] = None,
            write: bool = False, coalesce: bool = False) -> None:
        """执行任务。写操作串行；同名读取可合并为最后一次结果回调。"""
        with self._lock:
            if coalesce and name in self._pending:
                self._pending[name] = [on_ok, on_err, on_done]
                return
            self._running += 1
            if coalesce:
                self._pending[name] = [on_ok, on_err, on_done]
        self.ui_callback("task-start", name)

        def worker() -> None:
            err: Optional[Exception] = None
            result: object = None
            try:
                if write:
                    with self._write_lock:
                        result = fn()
                else:
                    result = fn()
            except Exception as exc:  # noqa: BLE001
                err = exc
            finally:
                with self._lock:
                    self._running -= 1
                    callbacks = self._pending.pop(name, None) if coalesce else None
                ok_callback, err_callback, done_callback = callbacks or (on_ok, on_err, on_done)
                self.ui_callback("task-result",
                                 (name, result, err, ok_callback, err_callback, done_callback))

        threading.Thread(target=worker, daemon=True).start()
