#!/usr/bin/env python3
from __future__ import annotations

import unittest

from apply_semantic_public_policy import (
    merge_translation_catalog,
    sanitize_history,
    sanitize_pulses,
)
from semantic_public_policy import (
    abstract_sensitive_public_text,
    polish_public_excerpt,
    reminder_requires_routine_projection,
    semantic_risk_tags,
)


class SemanticPublicPolicyTests(unittest.TestCase):
    def test_collaboration_optional_first_person_layers_are_sanitized(self) -> None:
        source = {
            "days": [
                {
                    "date": "2026-08-10",
                    "assigned_residues": [
                        {
                            "source_kind": "collaboration_session",
                            "category": "collaboration",
                            "zh": "协作记录。",
                            "en": "Collaboration record.",
                            "request_zh": "Simon 让我核对公开页面。",
                            "request_en": "Simon asked me to verify the public page.",
                            "outcome_zh": "我完成了核对。",
                            "outcome_en": "I completed the verification.",
                            "assessment_zh": "我的判断：不要暴露 QMT 状态。",
                            "assessment_en": "My assessment: do not expose QMT status.",
                            "assessment_provenance": "owner_approved_ai_assessment",
                            "owner_response_zh": "Simon 的回应：保留第一人称。",
                            "owner_response_en": "Simon's response: keep the first person voice.",
                            "owner_response_provenance": "explicit_owner_feedback",
                            "owner_response_evidence_count": 1,
                            "completion_status": "completed",
                        }
                    ],
                }
            ]
        }

        sanitized, stats = sanitize_history(source)
        residue = sanitized["days"][0]["assigned_residues"][0]

        self.assertNotIn("QMT", residue["assessment_zh"])
        self.assertNotIn("QMT", residue["assessment_en"])
        self.assertIn("第一人称", residue["owner_response_zh"])
        self.assertIn("first person", residue["owner_response_en"])
        self.assertGreaterEqual(stats["abstracted"], 2)

    def test_collaboration_optional_first_person_layers_require_bilingual_pair(self) -> None:
        source = {
            "days": [
                {
                    "date": "2026-08-10",
                    "assigned_residues": [
                        {
                            "source_kind": "collaboration_session",
                            "zh": "协作记录。",
                            "en": "Collaboration record.",
                            "request_zh": "Simon 让我核对公开页面。",
                            "request_en": "Simon asked me to verify the public page.",
                            "outcome_zh": "我完成了核对。",
                            "outcome_en": "I completed the verification.",
                            "assessment_zh": "我的判断：保留第一人称。",
                        }
                    ],
                }
            ]
        }

        with self.assertRaisesRegex(ValueError, "optional pair"):
            sanitize_history(source)

    def test_translation_catalog_preserves_dormant_date_scoped_inputs(self) -> None:
        dormant_hash = "a" * 64
        existing = {
            "schema": "granted-hours-timetable-reminder-translations-v1",
            "translation_provenance": "public_mask_preserving_translation_v1",
            "translations": {
                dormant_hash: {
                    "source_sha256": dormant_hash,
                    "summary_en": "Dormant but required by a future rebuild.",
                    "excerpt_en": "Dormant but required by a future rebuild.",
                    "translation_provenance": "public_mask_preserving_translation_v1",
                }
            },
        }
        pulses = {
            "days": [
                {
                    "date": "2026-08-05",
                    "pulses": [
                        {
                            "category": "daily_reminder",
                            "summary_original": "今天只处理这个日期。",
                            "summary_en": "Only this date is active today.",
                            "excerpt_en": "Only this date is active today.",
                        }
                    ],
                }
            ]
        }

        merged = merge_translation_catalog(pulses, existing)

        self.assertIn(dormant_hash, merged["translations"])
        self.assertEqual(len(merged["translations"]), 2)

    def assert_abstracted(self, source: str, forbidden: tuple[str, ...]) -> str:
        result, tags = abstract_sensitive_public_text(source)
        self.assertTrue(tags)
        for value in forbidden:
            self.assertNotIn(value.casefold(), result.casefold())
        self.assertEqual(semantic_risk_tags(result), ())
        repeated, repeated_tags = abstract_sensitive_public_text(result)
        self.assertEqual(repeated, result)
        self.assertEqual(repeated_tags, ())
        return result

    def test_family_dream_becomes_bounded_abstract(self) -> None:
        result = self.assert_abstracted(
            "我昨晚做了一个梦，梦里老婆、爸爸和妈妈因为出轨争执。",
            ("老婆", "爸爸", "妈妈", "出轨"),
        )
        self.assertIn("关系、失望与宽容的交叠。", result)
        self.assertNotIn("不公开", result)

    def test_health_detail_becomes_recovery_abstract(self) -> None:
        result = self.assert_abstracted(
            "提醒我带上右美沙芬，并记录今天的低能量和情绪状态。",
            ("右美沙芬", "低能量", "情绪状态"),
        )
        self.assertIn("恢复安排", result)

    def test_masked_disease_scope_keeps_neutral_contour(self) -> None:
        source = "分析论文中与疾病名████相关的机制，并给出结论。"
        result, tags = abstract_sensitive_public_text(source)
        self.assertEqual(tags, ())
        self.assertEqual(result, source)
        self.assertEqual(semantic_risk_tags(result), ())

    def test_personal_health_reminder_is_still_abstracted_after_masking(self) -> None:
        result, tags = abstract_sensitive_public_text(
            "提醒我带上右美沙芬，并记录今天的低能量和情绪状态。"
        )
        self.assertTrue(tags)
        self.assertIn("恢复安排", result)

    def test_commercial_brief_keeps_work_meaning(self) -> None:
        result = self.assert_abstracted(
            "品牌方给了 Seedance 2.5 campaign brief 和精确上线时间。",
            ("Seedance", "campaign brief", "上线时间"),
        )
        self.assertIn("文案结构", result)

    def test_infrastructure_names_become_result_language(self) -> None:
        result = self.assert_abstracted(
            "讨论 Cloudflare API Token，并检查 QMT 状态。",
            ("Cloudflare", "API Token", "QMT"),
        )
        self.assertIn("数据链路", result)

    def test_internal_verification_chatter_is_bounded(self) -> None:
        result = self.assert_abstracted(
            "Verification status: concrete blocker; no shell/terminal was available and write_file could not run the temporary verification script.",
            ("concrete blocker", "shell/terminal", "write_file"),
        )
        self.assertIn("structure and integrity", result)

    def test_personal_psychological_judgment_is_not_published(self) -> None:
        result = self.assert_abstracted(
            "You cannot really rest because this is a source of guilt and you do not have enough trust.",
            ("source of guilt", "not have enough trust"),
        )
        self.assertIn("self-observation", result)

    def test_publishing_queue_details_are_abstracted(self) -> None:
        result = self.assert_abstracted(
            "The social-publishing queue is blocked by a scheduling quota and three drafts are waiting in the queue.",
            ("scheduling quota", "three drafts"),
        )
        self.assertIn("Public-content scheduling", result)

    def test_personal_finance_operations_are_abstracted(self) -> None:
        result = self.assert_abstracted(
            "查询真实账户持仓，使用 QMT 校验 HK.01888 的减仓触发价。",
            ("真实账户", "QMT", "HK.01888", "减仓触发价"),
        )
        self.assertIn("只读研究", result)

    def test_public_history_cleanup_uses_direct_copy(self) -> None:
        result = self.assert_abstracted(
            "检查 git 仓库的 commit 历史，把不适合公开和打码前的记录抹除。",
            ("不适合公开", "打码前", "抹除"),
        )
        self.assertEqual(result, "公开仓库历史中的信息边界检查与旧版本清理。")

    def test_safe_paragraphs_are_preserved(self) -> None:
        safe = "完成交互作品的移动端验证。"
        result, tags = abstract_sensitive_public_text(
            f"{safe}\n\n提醒我带上右美沙芬。"
        )
        self.assertTrue(tags)
        self.assertIn(safe, result)
        self.assertNotIn("右美沙芬", result)

    def test_safe_research_copy_is_unchanged(self) -> None:
        source = "比较三种交互结构，最后保留可逆路径。"
        result, tags = abstract_sensitive_public_text(source)
        self.assertEqual(result, source)
        self.assertEqual(tags, ())

    def test_masked_holding_scope_keeps_research_contour(self) -> None:
        source = "梳理 ████ 持仓结构，并比较两组证据。"
        result, tags = abstract_sensitive_public_text(source)
        self.assertEqual(tags, ())
        self.assertEqual(result, source)

    def test_reminder_routing_separates_safe_creation_from_private_operations(self) -> None:
        self.assertFalse(
            reminder_requires_routine_projection(
                "今天给源泉留 45 分钟，先坐下来再等灵感。"
            )
        )
        self.assertTrue(
            reminder_requires_routine_projection(
                "Daily Reflection: verify the startup-brief and an internal ticket."
            )
        )

    def test_full_snapshot_policy_masks_identity_and_reduces_sensitive_reminder(self) -> None:
        source = {
            "days": [
                {
                    "date": "2026-08-01",
                    "pulses": [
                        {
                            "category": "daily_reminder",
                            "summary_original": "早安，Owner。今天给源泉留 45 分钟。",
                            "summary_en": "Good morning, Owner. Give the wellspring 45 minutes today.",
                        },
                        {
                            "category": "daily_reminder",
                            "summary_original": "Verification already completed for startup-brief.",
                            "summary_en": "Verification already completed for startup-brief.",
                        },
                    ],
                }
            ]
        }
        sanitized, stats = sanitize_pulses(source, identity_terms=("Owner",))
        safe, reduced = sanitized["days"][0]["pulses"]
        self.assertNotIn("Owner", str(safe))
        self.assertEqual(safe["summary_original"].count("████"), 1)
        self.assertEqual(reduced["category"], "background_routine")
        self.assertNotIn("summary_original", reduced)
        self.assertEqual(stats["routine_reductions"], 1)

    def test_legacy_audit_copy_becomes_direct_wording(self) -> None:
        source = "整理了只读研究、证据校验与风险复核流程，具体资产、账户和操作不公开。"
        result, tags = abstract_sensitive_public_text(source)
        self.assertEqual(result, "只读研究、证据校验与风险复核。")
        self.assertEqual(tags, ("personal_finance_or_trading",))

    def test_public_excerpt_polish_rejects_system_handoffs(self) -> None:
        self.assertEqual(
            polish_public_excerpt(
                "████ turns were compacted into the summary below. This is a handoff from a previous context window."
            ),
            "",
        )
        self.assertEqual(
            polish_public_excerpt("████ve found and accomplished so far, without calling any more tools."),
            "",
        )
        self.assertEqual(
            polish_public_excerpt("████ document is too large or its size could not be verified. ████: 20 MB."),
            "",
        )

    def test_public_excerpt_polish_keeps_only_complete_sentences(self) -> None:
        source = "结果｜第一项已经完成，并保留可验证证据。第二项仍在展开，包含很多尚未写完的内容以及"
        self.assertEqual(
            polish_public_excerpt(source, max_chars=32),
            "第一项已经完成，并保留可验证证据。",
        )

    def test_public_excerpt_polish_removes_audit_labels(self) -> None:
        self.assertEqual(
            polish_public_excerpt("结果｜但要把随机生成变成可解释、可复现的控制系统"),
            "要把随机生成变成可解释、可复现的控制系统。",
        )

    def test_public_excerpt_polish_removes_attachment_and_redaction_chatter(self) -> None:
        self.assertEqual(
            polish_public_excerpt("████ 帮我比较三个方案，保留完整证据链。"),
            "帮我比较三个方案，保留完整证据链。",
        )
        polished = polish_public_excerpt(
            "做完脱敏处理之后调整 UI，并去掉已脱敏之类的字样。"
        )
        self.assertNotIn("脱敏", polished)
        self.assertEqual(
            polished,
            "完成公开边界检查之后调整 UI，并去掉内部处理提示。",
        )


if __name__ == "__main__":
    unittest.main()
