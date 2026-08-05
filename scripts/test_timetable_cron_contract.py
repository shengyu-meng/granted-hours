#!/usr/bin/env python3
"""Focused tests for the live timetable cron v6 installer."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "update_timetable_cron_privacy_contract.py"
FREE_ID = "free-test-id"
DIALOGUE_ID = "dialogue-test-id"
FREE_NAME = "白夜自由时段 · nightly autonomous roam"
DIALOGUE_NAME = "授时：前一日工作对话脱敏同步"
CLOSURE_NAME = "授时：每日自由创作与日历闭环"
MARKER = "[授时每日公开闭环契约 v8]"


class TimetableCronContractTests(unittest.TestCase):
    def test_free_roam_stale_publish_section_is_stripped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            stale_section = (
                "公开归档与日历闭环（有公开产物时必做）：\n"
                "1. 只使用 canonical public worktree。\n"
                "9. commit `Archive YYYY-MM-DD <slug>`；push `git push origin HEAD:main`。\n"
                "13. 若某步卡住/失败，立即停止该步并报告，不等到超时；GitHub 已成功而 Cloudflare 失败时不回滚 GitHub。\n"
            )
            source = {
                "jobs": [
                    {
                        "id": FREE_ID,
                        "name": FREE_NAME,
                        "prompt": "create locally\n\n" + stale_section,
                        "deliver": "origin",
                        "origin": {
                            "platform": "test",
                            "destination": "private",
                        },
                        "workdir": temporary_directory,
                    },
                    {
                        "id": DIALOGUE_ID,
                        "name": DIALOGUE_NAME,
                        "prompt": "sync yesterday\n",
                    },
                ]
            }
            jobs = Path(temporary_directory) / "jobs.json"
            jobs.write_text(json.dumps(source), encoding="utf-8")
            os.chmod(jobs, 0o600)
            subprocess.run(
                ["python3", str(SCRIPT), str(jobs), "--write"],
                check=True,
                capture_output=True,
                text=True,
            )
            catalog = json.loads(jobs.read_text(encoding="utf-8"))
            by_name = {job["name"]: job for job in catalog["jobs"]}
            free_prompt = by_name[FREE_NAME]["prompt"]
            self.assertNotIn("公开归档与日历闭环（有公开产物时必做）", free_prompt)
            self.assertNotIn("push `git push origin HEAD:main`", free_prompt)
            self.assertIn("本任务禁止执行任何公开归档", free_prompt)
            self.assertEqual(free_prompt.count(MARKER), 1)

    def test_installs_three_role_specific_jobs_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = {
                "jobs": [
                    {
                        "id": FREE_ID,
                        "name": FREE_NAME,
                        "prompt": "create locally\n\n[授时公开语义隐私契约 v5]\n- old\n",
                        "deliver": "origin",
                        "origin": {
                            "platform": "test",
                            "destination": "private",
                        },
                        "workdir": temporary_directory,
                    },
                    {
                        "id": DIALOGUE_ID,
                        "name": DIALOGUE_NAME,
                        "prompt": "sync yesterday\n",
                    },
                ]
            }
            jobs = Path(temporary_directory) / "jobs.json"
            jobs.write_text(json.dumps(source), encoding="utf-8")
            os.chmod(jobs, 0o600)
            first = subprocess.run(
                ["python3", str(SCRIPT), str(jobs), "--write"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("targets=3; changed=3", first.stdout)
            self.assertEqual(jobs.stat().st_mode & 0o777, 0o600)
            catalog = json.loads(jobs.read_text(encoding="utf-8"))
            by_name = {job["name"]: job for job in catalog["jobs"]}
            self.assertEqual(
                set(by_name),
                {FREE_NAME, DIALOGUE_NAME, CLOSURE_NAME},
            )
            for job in by_name.values():
                self.assertEqual(job["prompt"].count(MARKER), 1)
                self.assertNotIn("[授时公开语义隐私契约 v5]", job["prompt"])
            self.assertIn("只负责自由创作", by_name[FREE_NAME]["prompt"])
            self.assertIn("import_collaboration_events.py", by_name[DIALOGUE_NAME]["prompt"])
            self.assertIn("从旧到新", by_name[CLOSURE_NAME]["prompt"])
            self.assertIn("granted-hours-closure-transaction-v1", by_name[CLOSURE_NAME]["prompt"])
            self.assertIn("当前 dirty 路径集合与 `owned_paths` **完全相等**", by_name[CLOSURE_NAME]["prompt"])
            self.assertIn("禁止退回无 `--date` 的全语料导入", by_name[CLOSURE_NAME]["prompt"])
            self.assertEqual(
                by_name[CLOSURE_NAME]["schedule"]["expr"],
                "35 6 * * *",
            )
            self.assertTrue(by_name[CLOSURE_NAME]["enabled"])

            second = subprocess.run(
                ["python3", str(SCRIPT), str(jobs), "--write"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("targets=3; changed=0", second.stdout)
            self.assertEqual(jobs.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
