#!/usr/bin/env python3
"""Apply the owner-approved 2026-08-11 delivered-work card merge deterministically."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "metadata" / "timetable-history.json"


def card(date: str, start: str, end: str, category: str, request_zh: str,
         request_en: str, outcome_zh: str, outcome_en: str,
         *, evidence_count: int = 1, assessment_zh: str = "",
         assessment_en: str = "") -> dict:
    request_zh = request_zh.rstrip("。") + "。"
    request_en = request_en.replace(". ", "; ").rstrip(".") + "."
    outcome_zh = (
        outcome_zh.replace("。 ", "；").rstrip("。")
        + "；我经审核后通过授权通道送回结果。"
    )
    outcome_en = (
        outcome_en.replace(". ", "; ").rstrip(".")
        + "; I returned it through the authorized channel after review."
    )
    result = {
        "category": category,
        "en": f"{date} · Owner-approved delivered-work residue",
        "zh": f"{date}｜经所有者批准的已送达工作残影",
        "redaction_status": "none",
        "redaction_count": 0,
        "source_kind": "collaboration_session",
        "faithfulness": "faithful_summary",
        "evidence_count": evidence_count,
        "agent_labels": ["Hermes"],
        "start": start,
        "end": end,
        "time_provenance": "observed_message_envelope",
        "session_count": 1,
        "delegated_agent_count": 0,
        "returned_agent_count": 0,
        "request_zh": request_zh,
        "request_en": request_en,
        "outcome_zh": outcome_zh,
        "outcome_en": outcome_en,
        "completion_status": "completed",
        "pair_provenance": "assistant_result_summary",
    }
    if bool(assessment_zh) != bool(assessment_en):
        raise ValueError("Approved assessments must be bilingual")
    if assessment_zh:
        result.update(
            {
                "assessment_zh": assessment_zh.rstrip("。") + "。",
                "assessment_en": assessment_en.rstrip(".") + ".",
                "assessment_provenance": "owner_approved_ai_assessment",
            }
        )
    return result


APPROVED = {
    "2026-08-04": [
        card("2026-08-04", "12:46", "21:05", "research_synthesis",
             "解释三种实验条件，确认题目、答案和语义地图的生成方式，并用人话说明配对胜负、显著性与置信区间。",
             "Explain the three experimental conditions, identify how the questions, answers, and semantic maps were generated, and translate paired wins, significance, and confidence intervals into plain language.",
             "确认题目与答案由固定模板和随机种子合成，地图由词汇相似度确定性聚类生成；重复实验支持“地图优于平铺列表”，但尚不支持“按任务出现的地图优于始终可见的地图”。",
             "Confirmed that questions and answers came from fixed templates and random seeds, while maps came from deterministic lexical clustering. Repeated trials support map over flat list, but not yet task-triggered map over always-visible map.", evidence_count=5,
             assessment_zh="地图的帮助已有重复证据，适应性地图的额外价值尚未被证明。",
             assessment_en="The map's benefit has repeated evidence; the extra value of an adaptive map has not yet been demonstrated."),
        card("2026-08-04", "23:56", "23:59", "system_maintenance",
             "统一例行任务的模型路由，移除遗留覆盖，并核对所有会调用模型的计划任务是否落到预期配置。",
             "Unify model routing for scheduled work, remove legacy overrides, and verify that every model-calling job resolved to the intended configuration.",
             "清理旧覆盖，统一两条调度路径，并完成全量配置回读。",
             "Removed the old overrides, aligned the two scheduling paths, and read back the full effective configuration.",
             assessment_zh="统一入口比继续叠加补丁更可靠。",
             assessment_en="A unified entry point is more reliable than another layer of patches."),
    ],
    "2026-08-05": [
        card("2026-08-05", "10:51", "14:00", "code_development",
             "补发最近三天缺失的日历与互动作品，并修复让自动闭环反复停住的问题。",
             "Restore the three missing calendar days and interactive works, and repair the condition that repeatedly stopped the automatic closure.",
             "恢复并发布了 8 月 3 日至 5 日的作品和日历，同时修正日期登记与事务恢复，让后续闭环能够继续。",
             "Restored and published the works and calendar for August 3–5, then repaired date registration and transaction recovery so the closure could continue.", evidence_count=4,
             assessment_zh="缺失不是创作停止，而是已完成作品被发布链路挡在门外。",
             assessment_en="The gap did not mean creation had stopped; completed works had been held outside by the publication path."),
    ],
    "2026-08-06": [
        card("2026-08-06", "16:56", "17:10", "research_synthesis",
             "研究一个公开的 AI 工作流仓库，并说明它的实现机制。",
             "Study a public AI-workflow repository and explain how it works.",
             "确认它把应用脚手架、工作流编排、评测、会话和成本管理连接成一个本地工作台，使构建、评测与改进成为日常循环。",
             "Found that it connects app scaffolding, workflow orchestration, evaluation, sessions, and cost management in one local workbench, turning build, evaluate, and improve into an everyday loop.",
             assessment_zh="它把评测与修订放到了创作过程内部。",
             assessment_en="It places evaluation and revision inside the act of making."),
    ],
    "2026-08-07": [
        card("2026-08-07", "01:25", "14:22", "research_synthesis",
             "整理并送回三份来自公开来源的材料简报。",
             "Organize and return three briefs from public sources.",
             "整理并送回三份公开材料简报，涉及代码安全审计、AI 参与的城市设计和一个公开网页案例；保留了可复核机制，并标出尚未完成的核验。",
             "Organized and returned three public-source briefs covering code-security auditing, AI-assisted urban design, and a public web case; preserved verifiable mechanisms and marked what still lacked verification.", evidence_count=3),
    ],
    "2026-08-08": [
        card("2026-08-08", "13:21", "15:45", "system_maintenance",
             "把主动对话与定时任务的模型和推理配置分开，并确认新主动对话会读取更新后的设置。",
             "Separate model and reasoning settings for active conversations from scheduled work, and confirm that a new conversation would read the updated settings.",
             "完成两条路径的分流，并做了配置回读、请求解析和新会话冒烟测试；定时任务保持原运行路径。",
             "Separated the two paths and verified the effective configuration, request resolution, and a fresh-session smoke test; scheduled work retained its existing route.", evidence_count=2,
             assessment_zh="分流让两种时间各自遵守配置契约。",
             assessment_en="The split makes two kinds of time obey their own configuration contracts."),
    ],
    "2026-08-10": [
        card("2026-08-10", "16:35", "19:27", "research_synthesis",
             "按原顺序整理并送回八份公开材料简报。",
             "Organize and return eight public-source briefs in their original order.",
             "按原顺序整理并送回八份公开材料简报，涉及远程 AI 开发、任务型 Agent、3D 网页、本地推理、文献工作流、天文学、生成媒介和动画管线。",
             "Organized and returned eight public-source briefs in their original order, spanning remote AI development, task-oriented agents, 3D web work, local inference, literature workflows, astronomy, generative media, and animation pipelines.", evidence_count=8,
             assessment_zh="保留每项的机制与限制，没有把排队或投递状态当作独立成果。",
             assessment_en="Each item's mechanisms and limits were retained without treating queue or delivery status as a separate achievement."),
        card("2026-08-10", "17:28", "17:31", "research_synthesis",
             "检查近期 AI 简报的重复问题并修正去重规则。",
             "Inspect repetition in recent AI briefs and repair the deduplication rules.",
             "确认主要噪音不是跨日重复链接，而是同一期来源和主题过度集中；收紧了来源集中度、同主题上限和去重检查。",
             "Found that the main noise was not repeated links across days, but excessive concentration of sources and topics within one edition; tightened source concentration, same-topic caps, and deduplication checks.",
             assessment_zh="允许同源补充，不等于允许同一个来源占据整期。",
             assessment_en="Allowing useful follow-ups from one source does not mean letting that source occupy an entire edition."),
        card("2026-08-10", "19:25", "23:20", "research_synthesis",
             "确认当天收到的材料是否都已按原顺序逐项整理并送回；如有缺项，补齐后再给出审计。",
             "Verify whether every item received that day had been organized and returned in the original order, filling any gaps before reporting the audit.",
             "核对了对话内可以确认的八项材料，补齐缺项并完成逐项整理。",
             "Verified the eight items supported by the conversation, filled the missing pieces, and completed the item-by-item organization.", evidence_count=2),
    ],
}


def main() -> int:
    source = json.loads(HISTORY.read_text(encoding="utf-8"))
    by_date = {day["date"]: day for day in source["days"]}
    for day_date, approved in APPROVED.items():
        day = by_date[day_date]
        retained = [r for r in day["assigned_residues"] if r.get("source_kind") != "collaboration_session"]
        day["assigned_residues"] = [*approved, *retained[: max(0, 10 - len(approved))]]
        day["provenance"] = (
            "withheld"
            if any(r.get("source_kind") == "withheld" for r in day["assigned_residues"])
            else "dialogue_based"
        )
    serialized = json.dumps(source, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=HISTORY.parent, delete=False) as out:
        out.write(serialized)
        temp = Path(out.name)
    os.chmod(temp, 0o600)
    os.replace(temp, HISTORY)
    print(f"Applied approved audit cards for {len(APPROVED)} dates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
