#!/usr/bin/env python3
from __future__ import annotations

import unittest

from semantic_public_policy import (
    abstract_sensitive_public_text,
    polish_public_excerpt,
    semantic_risk_tags,
)


class SemanticPublicPolicyTests(unittest.TestCase):
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
