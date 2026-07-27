#!/usr/bin/env python3
"""Focused deterministic tests for historical timetable reconstruction."""
from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import build_timetable_data as builder


class TimetableBuilderTests(unittest.TestCase):
    WITHHELD_DATES = {
        "2026-05-23",
        "2026-05-24",
        "2026-05-30",
        "2026-05-31",
        "2026-06-13",
        "2026-06-14",
        "2026-06-27",
        "2026-07-05",
        "2026-07-11",
        "2026-07-19",
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.public_days = builder.read_json(builder.DEFAULT_PUBLIC_DAYS)
        cls.config = builder.read_json(builder.DEFAULT_CONFIG)
        cls.history = builder.load_history(builder.DEFAULT_HISTORY)
        cls.pulses = builder.load_pulses(builder.DEFAULT_PULSES)
        cls.legacy = builder.load_legacy(builder.DEFAULT_LEGACY_OVERRIDES)

    def build(self, public_days=None):
        return builder.build_data(
            public_days or self.public_days,
            self.config,
            self.legacy,
            self.history,
            self.pulses,
        )

    def test_authored_history_covers_every_current_public_date(self) -> None:
        public_dates = {entry["date"] for entry in self.public_days}
        self.assertEqual(public_dates, set(self.history))
        self.assertEqual(len(public_dates), len(self.public_days))

    def test_history_uses_faithful_summaries_with_explicit_redaction(self) -> None:
        provenance = Counter()
        for day_date, entry in self.history.items():
            provenance[entry["provenance"]] += 1
            self.assertEqual(
                set(entry),
                {"date", "provenance", "assigned_residues"},
                f"{day_date} must not retain focus/medium/workflow generation fields",
            )
            self.assertGreaterEqual(len(entry["assigned_residues"]), 2)
            self.assertLessEqual(len(entry["assigned_residues"]), 6)
            signatures = set()
            for residue in entry["assigned_residues"]:
                self.assertEqual(
                    set(residue),
                    {
                        "category",
                        "en",
                        "zh",
                        "redaction_status",
                        "redaction_count",
                        "source_kind",
                        "faithfulness",
                    },
                )
                self.assertIn(residue["category"], builder.REQUIRED_TAXONOMY)
                self.assertIn(residue["redaction_status"], {"none", "partial", "withheld"})
                self.assertIsInstance(residue["redaction_count"], int)
                self.assertGreaterEqual(residue["redaction_count"], 0)
                self.assertIn(
                    residue["source_kind"],
                    {"daily_record", "maintenance_record", "task_card", "public_post_archive", "withheld"},
                )
                self.assertEqual(residue["faithfulness"], "faithful_summary")
                self.assertLessEqual(len(residue["zh"]), 90, f"{day_date} Chinese summary is too long for a duration block")
                self.assertLessEqual(len(residue["en"]), 300, f"{day_date} English summary is too long for a duration block")
                public_copy = f"{residue['en']} {residue['zh']}"
                self.assertIsNone(builder.SENSITIVE_ASSIGNED_WORK_RE.search(public_copy))
                self.assertIsNone(builder.PRIVATE_OPERATIONAL_CONTEXT_RE.search(public_copy))
                self.assertIsNone(builder.EDUCATION_IDENTITY_RE.search(public_copy))
                self.assertIsNone(builder.PROPOSAL_TITLE_CONTEXT_RE.search(public_copy))
                self.assertNotRegex(residue["en"], r"(?:/Users/|\\Users\\|\.md\b|session[_ -]?id|chat[_ -]?id)")
                self.assertNotRegex(residue["zh"], r"(?:/Users/|\\Users\\|\.md\b|会话ID|聊天ID)")
                if residue["redaction_status"] == "none":
                    self.assertEqual(residue["redaction_count"], 0)
                else:
                    self.assertGreater(residue["redaction_count"], 0)
                    self.assertIn("████", residue["en"])
                    self.assertIn("████", residue["zh"])
                signature = (residue["category"], residue["en"], residue["zh"])
                self.assertNotIn(signature, signatures)
                signatures.add(signature)

        expected_provenance = Counter(entry["provenance"] for entry in self.history.values())
        self.assertEqual(provenance, expected_provenance)
        self.assertEqual(
            {day_date for day_date, entry in self.history.items() if entry["provenance"] == "withheld"},
            self.WITHHELD_DATES,
        )

    def test_historical_output_is_continuous_diverse_and_artwork_free(self) -> None:
        output = self.build()
        phrases = Counter()
        schedules = set()
        category_patterns = Counter()
        category_counts = Counter()
        for day in output["days"]:
            self.assertGreaterEqual(len(day["task_residues"]), 2)
            self.assertLessEqual(len(day["task_residues"]), 6)
            builder.validate_tasks(day["date"], day["task_residues"], self.config["autonomous_hour"])
            schedules.add(
                tuple(
                    (task["start"], task["end"], task["zh"], task["en"])
                    for task in day["task_residues"]
                )
            )
            category_patterns[tuple(task["category"] for task in day["task_residues"])] += 1
            for task in day["task_residues"]:
                phrases[(task["zh"], task["en"])] += 1
                category_counts[task["category"]] += 1
                self.assertNotIn(day["title_en"].lower(), task["en"].lower())
                self.assertNotIn(day["title_zh"], task["zh"])

        self.assertGreaterEqual(len(phrases), 100)
        self.assertGreaterEqual(len(schedules), 60)
        self.assertLessEqual(max(phrases.values()), 10)
        # Faithful records may repeat the same medium mix (for example two
        # maintenance residues around the autonomous hour). Phrase diversity,
        # not artificial category shuffling, is the public-truthfulness gate.
        self.assertLessEqual(max(category_patterns.values()), 20)
        self.assertGreaterEqual(category_counts["social_media_organization"], 20)
        expected_provenance = Counter(entry["provenance"] for entry in self.history.values())
        self.assertEqual(
            Counter(day["history_provenance"] for day in output["days"]),
            expected_provenance,
        )

    def test_build_is_deterministic(self) -> None:
        first = json.dumps(self.build(), ensure_ascii=False, sort_keys=True)
        second = json.dumps(self.build(), ensure_ascii=False, sort_keys=True)
        self.assertEqual(first, second)

    def test_every_public_day_has_public_safe_real_scheduler_pulses(self) -> None:
        output = self.build()
        allowed_categories = set(builder.PULSE_DEFINITIONS)
        self.assertEqual(
            {day["date"] for day in output["days"]},
            set(self.pulses),
        )
        for day in output["days"]:
            self.assertTrue(day["background_pulses"], f"{day['date']} needs real run evidence")
            starts = [builder.minutes(pulse["start"]) for pulse in day["background_pulses"]]
            self.assertEqual(starts, sorted(starts))
            for pulse in day["background_pulses"]:
                self.assertEqual(pulse["origin"], "background")
                self.assertIn(pulse["category"], allowed_categories)
                self.assertGreaterEqual(pulse["count"], 1)
                self.assertRegex(pulse["start"], r"^\d{2}:\d{2}$")
                self.assertNotIn("job", json.dumps(pulse, ensure_ascii=False).lower())
            timeline = day["timeline_events"]
            self.assertEqual(
                timeline,
                sorted(
                    timeline,
                    key=lambda event: (
                        builder.minutes(event["start"]),
                        builder.timeline_event_priority(event),
                    ),
                ),
            )
            self.assertEqual(
                sum(event["origin"] == "self" for event in timeline),
                1,
            )

    def test_autonomous_media_and_main_bgm_playlist_are_complete_and_latest_first(self) -> None:
        output = self.build()
        self.assertEqual(len(output["bgm_playlist"]), len(output["days"]))
        self.assertEqual(
            [item["date"] for item in output["bgm_playlist"]],
            sorted((day["date"] for day in output["days"]), reverse=True),
        )
        for item in output["bgm_playlist"]:
            self.assertRegex(item["bgm_url"], r"^https://.+\.mp3$")
            self.assertTrue(item["title_en"].strip())
            self.assertTrue(item["title_zh"].strip())
        for day in output["days"]:
            autonomous = day["autonomous_work"]
            archive_root = f"{output['canonical_base_url']}archive/{day['date'][:4]}/{day['date'][5:7]}/{day['date']}/"
            self.assertEqual(day["archive_url"], archive_root)
            self.assertEqual(day["live_url"], f"{archive_root}live/")
            self.assertRegex(autonomous["preview_url"], r"^https://.+preview\.png$")
            self.assertRegex(autonomous["gif_url"], r"^https://.+preview\.gif$")
            self.assertRegex(autonomous["bgm_url"], r"^https://.+\.mp3$")
            self.assertEqual(autonomous["preview_url"], f"{archive_root}assets/preview.png")
            self.assertEqual(autonomous["gif_url"], f"{archive_root}assets/preview.gif")
            self.assertEqual(autonomous["visual_preview_url"], f"{archive_root}assets/visual-preview.webp")
            self.assertRegex(autonomous["visual_preview_url"], r"^https://.+visual-preview\.webp$")
            self.assertTrue(autonomous["bgm_url"].startswith(f"{archive_root}live/"))

    def test_task_names_use_token_boundaries_and_stay_specific(self) -> None:
        self.assertFalse(builder.keyword_matches("AI", "Maintain daily evidence", "维护每日证据"))
        self.assertFalse(builder.keyword_matches("thesis", "Synthesize the review brief", "综合复核简报"))
        name_zh, name_en = builder.derive_task_name(
            "research_synthesis",
            "Compare maintenance claims against current evidence",
            "将维护主张与当前证据比较",
        )
        self.assertEqual((name_zh, name_en), ("证据链复核", "Evidence-chain review"))
        self.assertEqual(
            builder.derive_task_name(
                "code_development",
                "Implement explicit embed=calendar mode for cross-origin iframe operation",
                "实现显式 embed=calendar 模式以支持跨域 iframe 运行",
            ),
            ("网页嵌入开发", "Web embed development"),
        )
        self.assertEqual(
            builder.derive_task_name(
                "research_synthesis",
                "Review capability claims against observed system behavior",
                "依据观察到的系统行为复核能力主张",
            ),
            ("能力声明核验", "Capability claim verification"),
        )
        self.assertEqual(
            builder.derive_task_name("system_maintenance", "Perform routine maintenance", "执行例行维护"),
            ("系统维护工作", "System maintenance work"),
        )
        extractive = builder.derive_authored_task_name(
            "research_synthesis",
            "Review a neutral bounded question without stronger domain evidence",
            "复核一个没有更强领域证据的有边界问题",
        )
        self.assertEqual(extractive, ("复核一个没有更强领域证据的有边界…", "Review a neutral bounded question without…"))
        self.assertNotIn("finance", extractive[1].lower())
        self.assertNotIn("版权", extractive[0])

        output = self.build()
        fallback_names = {
            "公开内容编排",
            "文稿整理与修订",
            "功能开发与验证",
            "专题研究与综合",
            "Agent 系统运维",
            "系统维护工作",
            "视觉内容制作",
        }
        names = [task["task_name_zh"] for day in output["days"] for task in day["task_residues"]]
        self.assertGreaterEqual(len(set(names)), 50)
        self.assertLessEqual(sum(name in fallback_names for name in names) / len(names), 0.1)
        self.assertEqual(sum(name in fallback_names for name in names), 0)
        for day in output["days"]:
            for task in day["task_residues"]:
                self.assertEqual(
                    (task["task_name_zh"], task["task_name_en"]),
                    builder.derive_authored_task_name(task["category"], task["en"], task["zh"]),
                    f"{day['date']} must not use fuzzy naming for authored history",
                )

    def test_every_day_has_an_authored_or_semantic_theme_motif(self) -> None:
        output = self.build()
        motifs = {day["theme_motif"] for day in output["days"]}
        self.assertTrue(motifs.issubset(builder.THEME_MOTIFS))
        self.assertGreaterEqual(len(motifs), 7)
        self.assertTrue(all(day["theme_motif"] for day in output["days"]))
        may_17 = next(day for day in output["days"] if day["date"] == "2026-05-17")
        self.assertEqual(may_17["theme_motif"], "room")

        unmatched = copy.deepcopy(self.public_days[0])
        unmatched.update(
            {
                "date": "2099-01-01",
                "title_en": "Honest Calibration",
                "title_zh": "诚实校准",
                "variable_en": "Calibration",
                "variable_zh": "校准",
            }
        )
        with self.assertRaisesRegex(SystemExit, "needs an authored theme_motif_overrides entry"):
            builder.derive_theme_motif(unmatched, self.config)

        invalid_config = copy.deepcopy(self.config)
        invalid_config["theme_motif_overrides"]["2026-05-14"] = "random-hash"
        with self.assertRaisesRegex(SystemExit, "unknown theme motif"):
            builder.validate_config(invalid_config)

    def test_tasks_expose_readable_public_types_colors_icons_and_estimated_duration(self) -> None:
        output = self.build()
        allowed_types = {
            "grant_proposal",
            "social_content",
            "investment_research",
            "software_development",
            "thesis_review",
            "course_materials",
            "research_analysis",
            "document_writing",
            "visual_design",
            "system_operations",
            "redacted_record",
        }
        for day in output["days"]:
            durations = []
            for task in day["task_residues"]:
                duration = builder.minutes(task["end"]) - builder.minutes(task["start"])
                durations.append(duration)
                self.assertEqual(task["duration_minutes"], duration)
                self.assertEqual(task["time_provenance"], "estimated")
                self.assertIn(task["task_type"], allowed_types)
                self.assertTrue(task["task_type_zh"].strip())
                self.assertTrue(task["task_type_en"].strip())
                self.assertRegex(task["task_color"], r"^[a-z][a-z0-9-]+$")
                self.assertRegex(task["task_icon"], r"^[a-z][a-z0-9-]+$")
            self.assertGreater(len(set(durations)), 1, f"{day['date']} needs visibly varied estimated blocks")

        july_18 = next(day for day in output["days"] if day["date"] == "2026-07-18")
        self.assertIn("grant_proposal", {task["task_type"] for task in july_18["task_residues"]})
        july_26 = next(day for day in output["days"] if day["date"] == "2026-07-26")
        self.assertTrue(
            all(
                task["task_type"] == "software_development"
                for task in july_26["task_residues"]
                if task["category"] == "code_development"
            )
        )
        social_task = next(
            task
            for day in output["days"]
            for task in day["task_residues"]
            if task["category"] == "social_media_organization"
        )
        self.assertEqual(social_task["task_type"], "social_content")
        market_tasks = [
            task
            for day in output["days"]
            for task in day["task_residues"]
            if task["task_type"] == "investment_research"
        ]
        self.assertTrue(market_tasks)
        self.assertTrue(
            any(any(token in task["en"].lower() for token in ("market", "stock", "a-share", "investment")) for task in market_tasks)
        )

    def test_finance_domain_precedes_the_execution_medium(self) -> None:
        cases = [
            (
                "code_development",
                "Check that market-data gaps cannot silently become investment signals",
                "检查市场数据缺口不会静默转化为投资信号",
            ),
            (
                "social_media_organization",
                "Draft a public post about an investment-research result",
                "撰写一条介绍投资研究结果的公开帖",
            ),
            (
                "system_maintenance",
                "Repair the market-data monitoring service",
                "修复市场数据监控服务",
            ),
            (
                "research_synthesis",
                "Challenge an investment thesis with market counterevidence",
                "以市场反证检验投资论点",
            ),
            (
                "document_processing",
                "Publish a financial research briefing",
                "发布金融研究简报",
            ),
            (
                "research_synthesis",
                "Challenge a materials-stocks thesis with public evidence",
                "以公开证据检验材料股票投资论点",
            ),
            (
                "research_synthesis",
                "Build a confidence-labeled premarket digest that cannot trigger trades",
                "建立带置信度标签且不能触发交易的盘前简报",
            ),
        ]
        for category, en, zh in cases:
            with self.subTest(category=category, en=en):
                self.assertEqual(
                    builder.derive_task_type(category, en, zh)["task_type"],
                    "investment_research",
                )

        negatives = [
            (
                "code_development",
                "Repair a non-financial public website",
                "修复一个非金融公共网站",
                "software_development",
            ),
            (
                "system_maintenance",
                "Audit evidence freshness for the archive",
                "审计归档证据的新鲜度",
                "system_operations",
            ),
            (
                "social_media_organization",
                "Schedule a public artwork post",
                "安排一条公共艺术作品帖",
                "social_content",
            ),
        ]
        for category, en, zh, expected in negatives:
            with self.subTest(category=category, en=en):
                self.assertEqual(builder.derive_task_type(category, en, zh)["task_type"], expected)

    def test_education_and_proposal_context_gates_are_precise(self) -> None:
        education_leaks = [
            "Completed an accounting thesis review",
            "Prepared MBA stress-management course templates",
            "Reviewed the Faculty of Business application",
            "完成会计本科论文评阅",
            "依据某学院规范整理课程",
            "完成数智财会人才培养项目申报书",
        ]
        for text in education_leaks:
            with self.subTest(text=text):
                self.assertTrue(
                    builder.EDUCATION_IDENTITY_RE.search(text)
                    or builder.PROPOSAL_TITLE_CONTEXT_RE.search(text)
                )

        allowed = [
            "Audit evidence freshness for a public archive",
            "Review an investment thesis against market evidence",
            "整理投资研究与金融市场证据",
        ]
        for text in allowed:
            with self.subTest(text=text):
                self.assertIsNone(builder.EDUCATION_IDENTITY_RE.search(text))
                self.assertIsNone(builder.PROPOSAL_TITLE_CONTEXT_RE.search(text))

    def test_authored_and_inferred_name_semantics_are_table_driven(self) -> None:
        cases = [
            {
                "label": "cross-origin iframe",
                "category": "code_development",
                "en": "Implement explicit embed=calendar mode for cross-origin iframe operation",
                "zh": "实现显式 embed=calendar 模式以支持跨域 iframe 运行",
                "authored": ("网页嵌入开发", "Web embed development"),
                "inferred": ("网页嵌入开发", "Web embed development"),
            },
            {
                "label": "capability claim",
                "category": "research_synthesis",
                "en": "Review capability claims against observed system behavior",
                "zh": "依据观察到的系统行为复核能力主张",
                "authored": ("能力声明核验", "Capability claim verification"),
                "inferred": ("能力声明核验", "Capability claim verification"),
            },
            {
                "label": "source freshness without rights",
                "category": "research_synthesis",
                "en": "Verify public-source freshness and separate confirmed findings from open questions",
                "zh": "核验公开来源的新鲜度并区分已确认发现与待解问题",
                "authored": ("核验公开来源的新鲜度并区分已确认…", "Verify public-source freshness and separate confirmed…"),
                "inferred": ("来源时效核验", "Source freshness verification"),
            },
            {
                "label": "decision-useful is not finance",
                "category": "research_synthesis",
                "en": "Review decision-useful deltas without promoting advisory material",
                "zh": "复核有决策价值的变化，不抬升建议型材料",
                "authored": ("决策变化复核", "Decision-useful change review"),
                "inferred": ("决策变化复核", "Decision-useful change review"),
            },
            {
                "label": "generic maintenance",
                "category": "system_maintenance",
                "en": "Perform routine maintenance",
                "zh": "执行例行维护",
                "authored": ("执行例行维护", "Perform routine maintenance"),
                "inferred": ("系统维护工作", "System maintenance work"),
            },
        ]
        for case in cases:
            with self.subTest(case["label"]):
                args = (case["category"], case["en"], case["zh"])
                self.assertEqual(builder.derive_authored_task_name(*args), case["authored"])
                self.assertEqual(builder.derive_task_name(*args), case["inferred"])

    def synthetic_public_days(self) -> list[dict]:
        from datetime import date, timedelta
        synthetic_days = copy.deepcopy(self.public_days)
        last_date = date.fromisoformat(synthetic_days[-1]["date"])
        future_date = (last_date + timedelta(days=1)).isoformat()
        synthetic = copy.deepcopy(synthetic_days[-1])
        synthetic.update(
            {
                "date": future_date,
                "title_en": "Synthetic Future Aperture",
                "title_zh": "合成未来孔径",
                "variable_en": "Aperture",
                "variable_zh": "孔径",
                "preview": f"archive/2026/07/{future_date}/assets/preview.png",
                "visual_preview": f"archive/2026/07/{future_date}/assets/visual-preview.webp",
                "gif": f"archive/2026/07/{future_date}/assets/preview.gif",
                "bgm": f"archive/2026/07/{future_date}/live/{future_date}-synthetic-future-aperture-bgm.mp3",
                "archive_url": f"archive/2026/07/{future_date}/",
                "live_url": f"archive/2026/07/{future_date}/live/",
            }
        )
        synthetic_days.append(synthetic)
        return synthetic_days

    def test_public_media_urls_cannot_escape_the_canonical_archive(self) -> None:
        tampered = copy.deepcopy(self.public_days)
        tampered[0]["live_url"] = "https://attacker.invalid/fake-live/"
        with self.assertRaisesRegex(SystemExit, "live_url must stay on the canonical live path"):
            self.build(tampered)

        day = self.public_days[0]
        canonical_live = f"{self.config['canonical_base_url']}archive/{day['date'][:4]}/{day['date'][5:7]}/{day['date']}/live/"
        for escape in ("../assets/escaped.mp3", "%2e%2e/assets/escaped.mp3"):
            with self.subTest(escape=escape):
                tampered = copy.deepcopy(self.public_days)
                tampered[0]["bgm"] = f"{canonical_live}{escape}"
                with self.assertRaisesRegex(SystemExit, "bgm must stay on the canonical live path"):
                    self.build(tampered)

    def test_synthetic_future_day_uses_assigned_work_inferred_fallback(self) -> None:
        synthetic_days = self.synthetic_public_days()
        output = self.build(synthetic_days)
        future = output["days"][-1]
        self.assertEqual(future["date"], synthetic_days[-1]["date"])
        self.assertEqual(future["history_provenance"], "inferred")
        self.assertGreaterEqual(len(future["task_residues"]), 5)
        self.assertLessEqual(len(future["task_residues"]), 8)
        builder.validate_tasks(future["date"], future["task_residues"], self.config["autonomous_hour"])
        self.assertNotIn(synthetic_days[-1]["date"], self.history)
        for task in future["task_residues"]:
            self.assertNotIn(future["title_en"].lower(), task["en"].lower())
            self.assertNotIn(future["title_zh"], task["zh"])

        alternate = copy.deepcopy(synthetic_days[-1])
        alternate.update(
            {
                "title_en": "Entirely Different Autonomous Work",
                "title_zh": "完全不同的自主作品",
                "variable_en": "Different variable",
                "variable_zh": "不同变量",
            }
        )
        self.assertEqual(
            builder.inferred_history(synthetic_days[-1])["assigned_residues"],
            builder.inferred_history(alternate)["assigned_residues"],
            "future assigned work must not be templated from autonomous artwork metadata",
        )

    def test_synthetic_public_days_cli_output_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            public_days_path = temporary / "days.json"
            output_path = temporary / "timetable-data.js"
            public_days_path.write_text(
                json.dumps(self.synthetic_public_days(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            command = [
                "python3",
                str(builder.ROOT / "scripts" / "build_timetable_data.py"),
                "--public-days",
                str(public_days_path),
                "--output",
                str(output_path),
            ]
            subprocess.run(command, cwd=builder.ROOT, check=True, capture_output=True, text=True)
            first = output_path.read_bytes()
            subprocess.run(command, cwd=builder.ROOT, check=True, capture_output=True, text=True)
            self.assertEqual(first, output_path.read_bytes())
            self.assertIn(b'"history_provenance": "inferred"', first)
            self.assertNotIn(b"Entirely Different Autonomous Work", first)

    def test_missing_current_history_cannot_silently_fall_back(self) -> None:
        incomplete_history = dict(self.history)
        incomplete_history.pop(self.public_days[0]["date"])
        with self.assertRaisesRegex(SystemExit, "missing authored history"):
            builder.build_data(
                self.public_days,
                self.config,
                self.legacy,
                incomplete_history,
                self.pulses,
            )


if __name__ == "__main__":
    unittest.main()
