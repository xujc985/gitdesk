# -*- coding: utf-8 -*-
"""GitDesk 后端单元测试：在临时目录中构建真实仓库，逐项验证 git_backend。

运行方式：
    python -m pytest tests/ -v
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import git_backend as gb


def git_ok() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


@unittest.skipUnless(git_ok(), "需要本机安装 git")
class RepoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="gitdesk-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo_path = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo_path)
        gb.Repo.init(self.repo_path)
        self.repo = gb.Repo(self.repo_path)
        self.repo.config_set("user.name", "GitDesk 测试")
        self.repo.config_set("user.email", "gitdesk@test.local")
        self.repo.config_set("commit.gpgsign", "false")
        self.repo.config_set("core.autocrlf", "false")
        # 与本机默认分支名解耦：测试统一用 master
        self.repo.git(["symbolic-ref", "HEAD", "refs/heads/master"])

    # ---------- 辅助 ----------
    def write(self, name: str, content: str) -> str:
        path = os.path.join(self.repo_path, name)
        os.makedirs(os.path.dirname(path) or self.repo_path, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return name

    def commit_file(self, name: str, content: str, message: str) -> str:
        self.write(name, content)
        self.repo.stage([name])
        self.repo.commit(message)
        return self.repo.git(["rev-parse", "HEAD"]).strip()

    def make_bare_origin(self) -> str:
        bare = os.path.join(self.tmp, "origin.git")
        code, _, err = gb.run_git(["init", "--bare", bare], self.tmp)
        self.assertEqual(code, 0, err)
        return bare


class TestRepoInitAndStatus(RepoTestCase):
    def test_is_repo(self):
        self.assertTrue(gb.Repo.is_repo(self.repo_path))
        self.assertFalse(gb.Repo.is_repo(self.tmp))

    def test_init_creates_repo(self):
        self.assertTrue(os.path.isdir(os.path.join(self.repo_path, ".git")))

    def test_status_untracked(self):
        self.write("hello.txt", "你好，GitDesk\n")
        st = self.repo.status()
        self.assertEqual(st.branch, "master")  # 或 main
        self.assertEqual(len(st.untracked), 1)
        self.assertEqual(st.untracked[0].path, "hello.txt")

    def test_status_staged_and_modified(self):
        self.commit_file("a.txt", "v1\n", "初始提交")
        self.write("a.txt", "v2\n")          # 工作区修改
        self.write("b.txt", "new\n")          # 未跟踪
        self.repo.stage(["b.txt"])            # 暂存 b
        st = self.repo.status()
        self.assertEqual([f.path for f in st.staged], ["b.txt"])
        self.assertEqual([f.path for f in st.unstaged], ["a.txt"])
        self.assertEqual(st.unstaged[0].label(), "已修改")

    def test_unicode_spaces_and_rename_paths(self):
        self.write("目录/你好 世界.txt", "旧内容\n")
        self.write("普通.txt", "a\n")
        self.repo.stage_all()
        self.repo.commit("初始")
        self.write("目录/你好 世界.txt", "新内容\n")
        self.repo.git(["mv", "普通.txt", "目录/重命名 文件.txt"])
        self.write("未跟踪 文件.txt", "new\n")
        st = self.repo.status()
        paths = {f.path for f in st.files}
        self.assertEqual(paths, {"目录/你好 世界.txt", "目录/重命名 文件.txt", "未跟踪 文件.txt"})
        renamed = next(f for f in st.files if f.x == "R")
        self.assertEqual(renamed.orig_path, "普通.txt")
        self.repo.unstage([renamed.path])
        self.repo.stage([renamed.path])
        self.assertIn(renamed.path, {f.path for f in self.repo.status().staged})

    def test_repo_subdirectory_normalizes_root(self):
        sha = self.commit_file("sub/中文 a.txt", "hello\n", "子目录提交")
        subrepo = gb.Repo(os.path.join(self.repo_path, "sub"))
        self.assertEqual(os.path.normcase(os.path.realpath(subrepo.path)),
                         os.path.normcase(os.path.realpath(self.repo_path)))
        self.assertIn("hello", subrepo.diff_commit(sha, "sub/中文 a.txt"))

    def test_conflict_file_only_in_conflict_group(self):
        self.commit_file("a.txt", "base\n", "base")
        self.repo.create_branch("side")
        self.commit_file("a.txt", "side\n", "side")
        self.repo.checkout("master")
        self.commit_file("a.txt", "master\n", "master")
        with self.assertRaises(gb.GitError):
            self.repo.merge("side")
        st = self.repo.status()
        self.assertEqual([f.path for f in st.conflicted], ["a.txt"])
        self.assertFalse(st.staged)
        self.assertFalse(st.unstaged)

    def test_empty_repo_discard_staged_file(self):
        self.write("new.txt", "new\n")
        self.repo.stage(["new.txt"])
        self.repo.discard(["new.txt"])
        self.assertFalse(os.path.exists(os.path.join(self.repo_path, "new.txt")))
        self.assertFalse(self.repo.status().files)

    def test_conflict_stage_resolution(self):
        self.commit_file("a.txt", "base\n", "base")
        self.repo.create_branch("side")
        self.commit_file("a.txt", "side\n", "side")
        self.repo.checkout("master")
        self.commit_file("a.txt", "master\n", "master")
        with self.assertRaises(gb.GitError):
            self.repo.merge("side")
        self.assertIn("master", self.repo.conflict_file("a.txt", "ours"))
        self.assertIn("side", self.repo.conflict_file("a.txt", "theirs"))
        self.repo.resolve_conflict("a.txt", "theirs")
        with open(os.path.join(self.repo_path, "a.txt"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "side\n")
        self.assertFalse(self.repo.status().conflicted)

    def test_apply_patch_cached_only_selected_hunk(self):
        self.commit_file("a.txt", "one\n\n\n\n\n\n\n\n\n\nten\n", "base")
        self.write("a.txt", "ONE\n\n\n\n\n\n\n\n\n\nTEN\n")
        diff = self.repo.diff("a.txt")
        from diff_hunks import parse_hunks, patch_for_hunks
        self.assertTrue(parse_hunks(diff))
        self.repo.apply_patch_cached(patch_for_hunks(diff, [0]))
        self.assertIn("+ONE", self.repo.diff("a.txt", staged=True))

    def test_ahead_behind(self):
        bare = self.make_bare_origin()
        self.commit_file("a.txt", "v1\n", "c1")
        self.repo.add_remote("origin", bare)
        self.repo.push("origin", "master", set_upstream=True)
        st = self.repo.status()
        self.assertEqual(st.upstream, "origin/master")
        self.commit_file("b.txt", "v\n", "c2")  # 领先 1
        st = self.repo.status()
        self.assertEqual(st.ahead, 1)
        self.assertEqual(st.behind, 0)


class TestStageDiscard(RepoTestCase):
    def test_stage_unstage(self):
        self.commit_file("a.txt", "1\n", "init")
        self.write("a.txt", "2\n")
        self.repo.stage(["a.txt"])
        self.assertEqual(len(self.repo.status().staged), 1)
        self.repo.unstage(["a.txt"])
        self.assertEqual(len(self.repo.status().staged), 0)
        self.assertEqual(len(self.repo.status().unstaged), 1)

    def test_stage_all(self):
        self.commit_file("a.txt", "1\n", "init")
        self.write("a.txt", "2\n")
        self.write("b.txt", "x\n")
        self.repo.stage_all()
        st = self.repo.status()
        self.assertEqual(len(st.staged), 2)
        self.assertEqual(len(st.unstaged), 0)

    def test_discard_tracked(self):
        self.commit_file("a.txt", "origin\n", "init")
        self.write("a.txt", "broken\n")
        self.repo.discard(["a.txt"])
        with open(os.path.join(self.repo_path, "a.txt"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "origin\n")

    def test_discard_untracked(self):
        self.write("tmp.txt", "temp\n")
        self.repo.discard(["tmp.txt"], untracked=True)
        self.assertFalse(os.path.exists(os.path.join(self.repo_path, "tmp.txt")))


class TestDiff(RepoTestCase):
    def test_diff_unstaged(self):
        self.commit_file("a.txt", "old\n", "init")
        self.write("a.txt", "new\n")
        out = self.repo.diff("a.txt")
        self.assertIn("-old", out)
        self.assertIn("+new", out)

    def test_diff_staged(self):
        self.commit_file("a.txt", "old\n", "init")
        self.write("a.txt", "new\n")
        self.repo.stage(["a.txt"])
        self.assertIn("+new", self.repo.diff("a.txt", staged=True))

    def test_diff_commit_and_root(self):
        sha = self.commit_file("a.txt", "one\n", "第一个提交")  # 根提交
        out = self.repo.diff_commit(sha)
        self.assertIn("+one", out)
        sha2 = self.commit_file("a.txt", "two\n", "第二个提交")
        out = self.repo.diff_commit(sha2)
        self.assertIn("+two", out)
        self.assertNotIn("+one", out)

    def test_show_file(self):
        sha = self.commit_file("a.txt", "历史内容\n", "init")
        self.write("a.txt", "现在的内容\n")
        self.assertEqual(self.repo.show_file(sha, "a.txt"), "历史内容\n")


class TestCommitAndLog(RepoTestCase):
    def test_commit_and_log(self):
        self.commit_file("a.txt", "1\n", "初始提交")
        self.commit_file("b.txt", "2\n", "修复：登录问题 #42")
        commits = self.repo.log(all_refs=False)
        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0].subject, "修复：登录问题 #42")
        self.assertEqual(commits[1].subject, "初始提交")
        self.assertEqual(len(commits[0].short), 7)
        self.assertEqual(commits[0].author, "GitDesk 测试")

    def test_log_grep_and_author(self):
        self.commit_file("a.txt", "1\n", "修复 bug")
        self.commit_file("b.txt", "2\n", "新增功能")
        hits = self.repo.log(grep="修复", all_refs=False)
        self.assertEqual(len(hits), 1)
        hits = self.repo.log(author="GitDesk", all_refs=False)
        self.assertEqual(len(hits), 2)

    def test_log_path_filter(self):
        self.commit_file("a.txt", "1\n", "改 a")
        self.commit_file("b.txt", "2\n", "改 b")
        hits = self.repo.log(path="a.txt", all_refs=False)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].subject, "改 a")

    def test_amend(self):
        self.commit_file("a.txt", "1\n", "原始信息")
        self.write("b.txt", "2\n")
        self.repo.stage(["b.txt"])
        self.repo.commit("修改后的信息", amend=True)
        commits = self.repo.log(all_refs=False)
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0].subject, "修改后的信息")

    def test_commit_files(self):
        sha = self.commit_file("a.txt", "1\n", "init")
        sha2 = self.commit_file("b.txt", "2\n", "second")
        files = self.repo.commit_files(sha2)
        self.assertEqual([(f.x, f.path) for f in files], [("A", "b.txt")])
        files = self.repo.commit_files(sha)  # 根提交
        self.assertEqual([(f.x, f.path) for f in files], [("A", "a.txt")],
                         msg=f"根提交 diff-tree 应返回 a.txt，实际 {[(f.x, f.path) for f in files]}")


class TestBranches(RepoTestCase):
    def test_create_checkout_delete(self):
        self.commit_file("a.txt", "1\n", "init")
        self.repo.create_branch("feature-x")
        self.assertEqual(self.repo.current_branch(), "feature-x")
        self.repo.checkout("master")
        self.assertEqual(self.repo.current_branch(), "master")
        self.repo.delete_branch("feature-x")
        local, _ = self.repo.branches()
        self.assertEqual([b.name for b in local], ["master"])

    def test_branches_list(self):
        self.commit_file("a.txt", "1\n", "init")
        self.repo.create_branch("dev", checkout=False)
        local, _ = self.repo.branches()
        names = sorted(b.name for b in local)
        self.assertEqual(names, ["dev", "master"])
        cur = [b for b in local if b.current]
        self.assertEqual(cur[0].name, "master")

    def test_rename_branch(self):
        self.commit_file("a.txt", "1\n", "init")
        self.repo.create_branch("old-name")
        self.repo.rename_branch("old-name", "new-name")
        local, _ = self.repo.branches()
        self.assertIn("new-name", [b.name for b in local])

    def test_merge_and_no_ff(self):
        self.commit_file("a.txt", "base\n", "base")
        self.repo.create_branch("feature")
        self.commit_file("f.txt", "feat\n", "feature 工作")
        self.repo.checkout("master")
        self.repo.merge("feature", no_ff=True, message="合并 feature")
        commits = self.repo.log(all_refs=False)
        self.assertTrue(any("合并 feature" in c.subject for c in commits))
        self.assertTrue(os.path.exists(os.path.join(self.repo_path, "f.txt")))

    def test_merge_conflict_and_abort(self):
        self.commit_file("a.txt", "base\n", "base")
        self.repo.create_branch("conflict-br")
        self.commit_file("a.txt", "theirs\n", "theirs")
        self.repo.checkout("master")
        self.commit_file("a.txt", "ours\n", "ours")
        with self.assertRaises(gb.GitError):
            self.repo.merge("conflict-br")
        st = self.repo.status()
        self.assertTrue(st.merging)
        self.assertEqual(len(st.conflicted), 1)
        self.repo.merge_abort()
        self.assertFalse(self.repo.status().merging)

    def test_rebase_and_abort(self):
        self.commit_file("a.txt", "base\n", "base")
        self.repo.create_branch("feature")
        self.commit_file("f.txt", "feat\n", "feat commit")
        self.repo.checkout("master")
        self.commit_file("m.txt", "main\n", "main commit")
        self.repo.checkout("feature")
        self.repo.rebase("master")  # 无冲突，应成功
        commits = self.repo.log(all_refs=False)
        subjects = [c.subject for c in commits]
        self.assertIn("feat commit", subjects)
        self.assertIn("main commit", subjects)
        # rebase 后 feat 提交应在 main 提交之上（历史更靠后显示）
        self.assertLess(subjects.index("feat commit"), subjects.index("main commit"))

    def test_cherry_pick_and_revert(self):
        self.commit_file("a.txt", "1\n", "init")
        self.repo.create_branch("side")
        sha = self.commit_file("side.txt", "side\n", "side 提交")
        self.repo.checkout("master")
        self.repo.cherry_pick(sha)
        self.assertTrue(os.path.exists(os.path.join(self.repo_path, "side.txt")))
        self.repo.revert(sha)
        self.assertFalse(os.path.exists(os.path.join(self.repo_path, "side.txt")))

    def test_reset_modes(self):
        sha1 = self.commit_file("a.txt", "1\n", "c1")
        self.commit_file("b.txt", "2\n", "c2")
        self.repo.reset("soft", sha1)
        self.assertEqual(len(self.repo.status().staged), 1)   # b.txt 留在暂存区
        self.repo.reset("hard", "HEAD")                        # 清空
        self.assertEqual(len(self.repo.status().files), 0)

    def test_reflog(self):
        self.commit_file("a.txt", "1\n", "init")
        self.repo.create_branch("tmp")
        out = self.repo.reflog()
        self.assertIn("checkout", out)


class TestRemotes(RepoTestCase):
    def test_add_list_seturl_remove(self):
        self.commit_file("a.txt", "1\n", "init")
        self.repo.add_remote("origin", "https://example.com/x.git")
        remotes = self.repo.remotes()
        self.assertEqual(remotes[0].name, "origin")
        self.assertIn("example.com", remotes[0].fetch_url)
        self.repo.set_remote_url("origin", "https://example.com/y.git")
        self.assertIn("y.git", self.repo.remotes()[0].fetch_url)
        self.repo.remove_remote("origin")
        self.assertEqual(self.repo.remotes(), [])

    def test_push_fetch_pull(self):
        bare = self.make_bare_origin()
        self.commit_file("a.txt", "1\n", "c1")
        self.repo.add_remote("origin", bare)
        self.repo.push("origin", "master", set_upstream=True)
        # 克隆出另一个仓库并提交，然后本仓库 pull
        clone2 = os.path.join(self.tmp, "clone2")
        gb.Repo.clone(bare, clone2)
        r2 = gb.Repo(clone2)
        r2.config_set("user.name", "T2")
        r2.config_set("user.email", "t2@t.local")
        with open(os.path.join(clone2, "from2.txt"), "w") as fh:
            fh.write("from clone2\n")
        r2.stage(["from2.txt"])
        r2.commit("来自 clone2 的提交")
        r2.push("origin", "master")
        self.repo.pull()
        self.assertTrue(os.path.exists(os.path.join(self.repo_path, "from2.txt")))
        st = self.repo.status()
        self.assertEqual((st.ahead, st.behind), (0, 0))

    def test_clone(self):
        self.commit_file("a.txt", "1\n", "c1")
        dest = os.path.join(self.tmp, "cloned")
        gb.Repo.clone(self.repo_path, dest)
        self.assertTrue(gb.Repo.is_repo(dest))
        self.assertTrue(os.path.exists(os.path.join(dest, "a.txt")))


class TestStash(RepoTestCase):
    def test_stash_cycle(self):
        self.commit_file("a.txt", "base\n", "init")
        self.write("a.txt", "dirty\n")
        self.write("new.txt", "n\n")
        self.repo.stash_push("做一半的改动", include_untracked=True)
        st = self.repo.status()
        self.assertEqual(len(st.files), 0)
        stashes = self.repo.stashes()
        self.assertEqual(len(stashes), 1)
        self.assertIn("做一半的改动", stashes[0].message)
        self.repo.stash_apply(0)
        self.assertEqual(len(self.repo.status().files), 2)
        self.repo.stash_drop(0)
        self.assertEqual(self.repo.stashes(), [])

    def test_stash_pop_and_show(self):
        self.commit_file("a.txt", "base\n", "init")
        self.write("a.txt", "dirty\n")
        self.repo.stash_push()
        patch = self.repo.stash_show(0)
        self.assertIn("+dirty", patch)
        self.repo.stash_apply(0, pop=True)
        self.assertEqual(self.repo.stashes(), [])
        self.assertEqual(len(self.repo.status().files), 1)


class TestTags(RepoTestCase):
    def test_tag_cycle(self):
        sha = self.commit_file("a.txt", "1\n", "init")
        self.repo.create_tag("v1.0", message="第一个版本", target=sha)
        self.repo.create_tag("light", target=sha)
        tags = self.repo.tags()
        by_name = {t.name: t for t in tags}
        self.assertTrue(by_name["v1.0"].annotated)
        self.assertFalse(by_name["light"].annotated)
        self.repo.delete_tag("light")
        self.assertNotIn("light", [t.name for t in self.repo.tags()])

    def test_tag_push_and_remote_delete(self):
        self.commit_file("a.txt", "1\n", "init")
        bare = self.make_bare_origin()
        self.repo.add_remote("origin", bare)
        self.repo.push("origin", "master", set_upstream=True)
        self.repo.create_tag("v2.0", message="release")
        self.repo.push_tag("v2.0")
        code, out, _ = gb.run_git(["ls-remote", "--tags", "origin"], self.repo_path)
        self.assertIn("v2.0", out)
        self.repo.delete_tag("v2.0", remote="origin")
        code, out, _ = gb.run_git(["ls-remote", "--tags", "origin"], self.repo_path)
        self.assertNotIn("v2.0", out)


class TestConfigAndMisc(RepoTestCase):
    def test_config(self):
        self.repo.config_set("gitdesk.test", "hello")
        self.assertEqual(self.repo.config_get("gitdesk.test"), "hello")

    def test_ahead_behind_of(self):
        self.commit_file("a.txt", "1\n", "c1")
        self.repo.create_branch("side")          # side 从 c1 出发（master 也在 c1）
        self.repo.checkout("master")
        self.commit_file("b.txt", "2\n", "c2")   # master 前进 c2
        self.repo.checkout("side")               # side 仍在 c1
        self.commit_file("c.txt", "3\n", "c3")   # side 前进 c3
        ahead, behind = self.repo.ahead_behind_of("master", "side")
        self.assertEqual((ahead, behind), (1, 1))

    def test_blame(self):
        self.commit_file("a.txt", "line1\n", "init")
        out = self.repo.blame("a.txt")
        self.assertIn("GitDesk 测试", out)

    def test_git_error_message(self):
        with self.assertRaises(gb.GitError) as ctx:
            self.repo.checkout("不存在的分支")
        self.assertTrue(ctx.exception.args[0])


if __name__ == "__main__":
    unittest.main()
