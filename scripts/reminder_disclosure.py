#!/usr/bin/env python3
"""Audited, fixed-template projection for private reminder responses.

Raw responses are inspected only in memory. Public output is selected from
fixed bilingual templates and non-sensitive enums; no source span is copied,
hashed, encoded, measured, or otherwise serialized.
"""
from __future__ import annotations

import re

FIXED_REDACTION_BLOCK = "████"
DISCLOSURE_POLICY = "limited_masked_reminder_v1"
DISCLOSURE_AUTHORIZATION = "explicit_user_authorization_2026-07-29"
ACTION_PROVENANCE = "limited_masked_action_semantics_v1"
PROJECTION_PROVENANCE = "audited_bilingual_template_v1"
REDACTION_POLICY = "fixed_template_blocks_v1"

MOTIF_RULES = (
    (
        "source_proximity",
        re.compile(
            r"(?i)(?:靠近源泉|靠近(?:内在)?源头|回到(?:内在)?源头|"
            r"return(?:ing)?\s+(?:attention\s+)?(?:back\s+)?to\s+(?:an?\s+|the\s+|your\s+)?"
            r"(?:inner\s+)?source|closer?\s+to\s+(?:an?\s+|the\s+|your\s+)?(?:inner\s+)?source)"
        ),
    ),
    (
        "external_scoreboard",
        re.compile(
            r"(?i)(?:外部记分板|外部记分牌|外部评分|外界打分|他人的评分|"
            r"external\s+score(?:board)?|outside\s+score(?:board)?)"
        ),
    ),
    (
        "comfort_rest",
        re.compile(
            r"(?i)(?:休息|疲惫|疲劳|过度伸展|过度消耗|透支|自我关怀|自我体谅|"
            r"安慰(?!剂)|宽慰|没关系|辛苦了|照顾自己|对自己温柔|温柔(?:地)?对待自己|"
            r"允许自己(?:休息|慢下来|停一停|喘口气|不完美|脆弱|没有答案|"
            r"暂时不解决|先不解决|被照顾|感到疲惫|(?=[。！!？?，,；;：:\s]|$))|"
            r"(?:不必|不用)(?:再|总是|一直|急着)?(?:向[^，。！？\n]{1,10})?"
            r"(?:证明自己|证明你(?:自己)?(?:的)?价值|证明你值得|证明自身价值|"
            r"证明自己的价值)|"
            r"\b(?:it['’]s|it\s+is)\s+okay(?=[.!?,;:]|$)|"
            r"\bbe\s+gentle\s+with\s+yourself\b|"
            r"\b(?:you\s+are|you['’]re)\s+enough\b|"
            r"\b(?:you\s+)?(?:do\s+not|don['’]t)\s+have\s+to\s+prove"
            r"(?:\s+(?:yourself|anything|your\s+worth|"
            r"that\s+you(?:\s+are|['’]re)\s+enough))?(?=[.!?]|$)|"
            r"comfort|self[- ]compassion|permission\s+to\s+rest|"
            r"\brest\b|fatigue|tired|overextend(?:ed|ing|s)?)"
        ),
    ),
    (
        "attention_boundaries",
        re.compile(
            r"(?i)(?:把注意力.{0,16}(?:收回|带回|回到自己)|注意力.{0,12}(?:自己|边界)|"
            r"回到自己|守住边界|边界感|return(?:ing)?\s+attention\s+to\s+(?:your)?self|"
            r"bring(?:ing)?\s+attention\s+back|attention\s+boundar(?:y|ies)|\bboundar(?:y|ies)\b)"
        ),
    ),
    (
        "uncertainty_unfinished",
        re.compile(
            r"(?i)(?:不确定|未完成|未竟|不必(?:立刻)?解决|无需(?:立刻)?解决|暂不解决|"
            r"允许.{0,12}(?:悬而未决|没有答案|不解决)|uncertaint(?:y|ies)|unfinished(?:ness)?|"
            r"need\s+not\s+resolve|permission\s+not\s+to\s+resolve|leave\s+it\s+unresolved)"
        ),
    ),
    (
        "ai_human_care",
        re.compile(
            r"(?i)(?:(?:AI|人工智能).{0,24}(?:人类|human).{0,24}(?:照料|关怀|校准|care|calibrat)|"
            r"(?:人类|human).{0,24}(?:AI|人工智能).{0,24}(?:照料|关怀|校准|care|calibrat)|"
            r"AI[–-]human\s+(?:care|calibrat))"
        ),
    ),
)

MOTIF_TEMPLATES = {
    "source_proximity": (
        "这次校准把注意力重新带回内在源头。",
        "This calibration brings attention back toward an inner source.",
    ),
    "external_scoreboard": (
        "这次校准松开外部评分的牵引，把判断带回自身尺度。",
        "This calibration loosens the pull of external scoreboards and returns judgment to an inner measure.",
    ),
    "comfort_rest": (
        "这次内在天气允许疲惫被看见，也允许休息与自我体谅。",
        "This inner weather lets fatigue be seen and makes room for rest and self-compassion.",
    ),
    "attention_boundaries": (
        "这次校准把注意力带回自身，也为边界留出位置。",
        "This calibration returns attention to the self and leaves room for boundaries.",
    ),
    "uncertainty_unfinished": (
        "这次内在天气允许不确定与未完成暂时保持开放。",
        "This inner weather lets uncertainty and unfinishedness remain open for now.",
    ),
    "ai_human_care": (
        "这次校准关注 AI 与人之间如何更审慎地彼此照料。",
        "This calibration attends to more careful care between AI and human.",
    ),
}

ACTION_RULES = (
    (
        "document_or_learning_action",
        re.compile(
            r"(?i)(?:thes(?:is|es)|dissertation|manuscript|document|course|institution|"
            r"proposal|application|paper|lesson|论文|文稿|文档|课程|机构|院校|申报|申请|材料)"
        ),
    ),
    (
        "collaboration_or_meeting_action",
        re.compile(
            r"(?i)(?:collaborat(?:e|ion|ive)|meeting|client|appointment|workshop|"
            r"协作|合作|会议|会面|客户|约谈|工作坊)"
        ),
    ),
    (
        "project_or_delivery_action",
        re.compile(
            r"(?i)(?:project|repo(?:sitory)?|release|launch|ship(?:ped|ping)?|completion|"
            r"complete(?:d|s|ing)?|项目|代码库|仓库|发布|上线|交付|完成)"
        ),
    ),
    (
        "private_life_logistics",
        re.compile(
            r"(?i)(?:health|medical|family|household|finance|financial|travel|location|"
            r"account|amount|address|currency|健康|医疗|家人|家庭|财务|金额|账户|旅行|出行|"
            r"地点|位置|地址)"
        ),
    ),
    (
        "relationship_action",
        re.compile(
            r"(?i)(?:contact|call|message|reply|respond|conversation|relationship|"
            r"联系|致电|消息|回复|回应|对话|关系)"
        ),
    ),
)

ACTION_TEMPLATES = {
    "document_or_learning_action": (
        f"这一天只显出一处与 {FIXED_REDACTION_BLOCK} 相关的文档或学习轮廓；对象与去向保持遮挡。",
        f"This day reveals only a document or learning contour around {FIXED_REDACTION_BLOCK}; "
        "the subject and destination remain masked.",
    ),
    "collaboration_or_meeting_action": (
        f"这一天只显出一处与 {FIXED_REDACTION_BLOCK} 相关的协作或会面轮廓；角色与议题保持遮挡。",
        f"This day reveals only a collaboration or meeting contour around {FIXED_REDACTION_BLOCK}; "
        "roles and topic remain masked.",
    ),
    "project_or_delivery_action": (
        f"一项围绕 {FIXED_REDACTION_BLOCK} 的项目或交付轮廓，是公开层留下的全部。",
        f"A project or delivery contour around {FIXED_REDACTION_BLOCK} is all the public layer retains.",
    ),
    "private_life_logistics": (
        f"这一天有一部分生活被留在 {FIXED_REDACTION_BLOCK} 之后；公开层不再追问。",
        f"A part of this day's life remains behind {FIXED_REDACTION_BLOCK}; "
        "the public layer asks no further.",
    ),
    "relationship_action": (
        f"这一天只显出一处与 {FIXED_REDACTION_BLOCK} 相关的联系或关系轮廓；人物与缘由保持遮挡。",
        f"This day reveals only a contact or relational contour around {FIXED_REDACTION_BLOCK}; "
        "people and reasons remain masked.",
    ),
}

TIME_LABELS = {
    "morning": ("晨间校准", "Morning calibration"),
    "evening": ("暮间回声", "Evening echo"),
}


def classify_motif(text: str) -> str:
    return next(
        (motif for motif, pattern in MOTIF_RULES if pattern.search(text)),
        "none",
    )


def classify_action_structure(text: str) -> str:
    return next(
        (
            action_structure
            for action_structure, pattern in ACTION_RULES
            if pattern.search(text)
        ),
        "none",
    )


def render_reminder_projection(
    motif: str,
    action_structure: str,
    time_bucket: str,
) -> dict:
    """Render public output only from enums and fixed bilingual templates."""
    if motif not in {*MOTIF_TEMPLATES, "none"}:
        raise ValueError("Unknown reminder motif")
    if action_structure not in {*ACTION_TEMPLATES, "none"}:
        raise ValueError("Unknown reminder action structure")

    motif_copy = MOTIF_TEMPLATES.get(motif)
    action_copy = ACTION_TEMPLATES.get(action_structure)
    if motif_copy and action_copy:
        projection_kind = "combined"
    elif motif_copy:
        projection_kind = "inner_weather"
    elif action_copy:
        projection_kind = "masked_only"
    else:
        projection_kind = "opaque"

    if motif_copy:
        label_zh, label_en = TIME_LABELS.get(
            time_bucket,
            ("内在天气", "Inner weather"),
        )
    elif action_copy:
        label_zh, label_en = "遮挡残影", "Masked residue"
    else:
        label_zh, label_en = "私人提醒", "Private reminder"

    summary_zh = " ".join(
        part[0] for part in (motif_copy, action_copy) if part is not None
    ) or f"这条提醒只留下：{FIXED_REDACTION_BLOCK}。"
    summary_en = " ".join(
        part[1] for part in (motif_copy, action_copy) if part is not None
    ) or f"This reminder leaves only this: {FIXED_REDACTION_BLOCK}."
    redaction_count = 1 if action_copy or not motif_copy else 0
    return {
        "label_zh": label_zh,
        "label_en": label_en,
        "summary_zh": summary_zh,
        "summary_en": summary_en,
        "motif": motif,
        "action_structure": action_structure,
        "projection_kind": projection_kind,
        "redaction_policy": REDACTION_POLICY,
        "redaction_count": redaction_count,
        "projection_provenance": PROJECTION_PROVENANCE,
    }


def project_limited_reminder_response(
    responses: list[str],
    time_bucket: str,
) -> dict:
    """Classify source evidence in memory and return fixed public templates."""
    combined = "\n".join(response for response in responses if response)
    return render_reminder_projection(
        classify_motif(combined),
        classify_action_structure(combined),
        time_bucket,
    )
