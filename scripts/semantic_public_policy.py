#!/usr/bin/env python3
"""Semantic privacy policy for public timetable prose.

The public calendar may preserve useful meaning, but it must not serialize
intimate family narratives, health details, unpublished commercial briefs, or
named infrastructure status.  The policy therefore prefers a bounded abstract
statement, then entity masking, and only drops content when no safe meaning
remains.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticRule:
    tag: str
    pattern: re.Pattern[str]
    abstract_zh: str
    abstract_en: str


RULES = (
    SemanticRule(
        "intimate_family_dream",
        re.compile(
            r"(?is)(?:\b(?:dream|nightmare)\b|梦|梦见|做了.{0,8}梦)"
            r".{0,180}(?:spouse|wife|husband|parent|father|mother|family|"
            r"老婆|妻子|丈夫|伴侣|父母|爸爸|妈妈|我爸|我妈|家庭|出轨)"
            r"|(?:spouse|wife|husband|parent|father|mother|family|"
            r"老婆|妻子|丈夫|伴侣|父母|爸爸|妈妈|我爸|我妈|家庭|出轨)"
            r".{0,180}(?:\b(?:dream|nightmare)\b|梦|梦见)",
        ),
        "讨论了私人经验中关系、失望与宽容的交叠，具体叙事不公开。",
        "Examined how disappointment, tolerance, and relationships overlap in a private experience; the underlying narrative remains private.",
    ),
    SemanticRule(
        "health_or_emotional_state",
        re.compile(
            r"(?is)右美沙芬|具体药物|服药|吃药|药物|病情|疾病|症状|身体不适|"
            r"身体状态|低能量|情绪状态|心理状态|焦虑|抑郁|崩溃|逃避|"
            r"没力气|只想躺|dextromethorphan|medication|medical condition|"
            r"physical condition|low[- ]energy|emotional state|mental health",
        ),
        "记录了个人恢复安排，具体身心细节不公开。",
        "Recorded a personal recovery arrangement; specific physical and emotional details remain private.",
    ),
    SemanticRule(
        "family_or_caregiving",
        re.compile(
            r"(?is)老婆|妻子|丈夫|伴侣|孩子|小孩|我娃|带娃|陪娃|父职|父亲|"
            r"母亲|爸爸|妈妈|父子|父女|儿子|女儿|家人|家庭安排|亲子|"
            r"\bspouse\b|\bwife\b|\bhusband\b|\bpartner\b|\bchild(?:ren)?\b|"
            r"\bfatherhood\b|\bmotherhood\b|\bparenting\b|\bcaregiving\b",
        ),
        "讨论了长期创作、日常责任与稳定照护之间的平衡，具体关系信息不公开。",
        "Discussed the balance between long-term creative work, daily responsibilities, and dependable care; relationship details remain private.",
    ),
    SemanticRule(
        "unpublished_commercial_brief",
        re.compile(
            r"(?is)品牌方|品牌活动|品牌新生|商业邀约|媒体邀约|邀请函|媒体名称|"
            r"邀约媒介|联系人|开户人|开户行|账户信息|发布会时间|上线时间|"
            r"采购项目|传播合作|豆包专业版|Seedance\s*2(?:\.5)?|Seedream\s*5(?:\.0)?|"
            r"\bbrand brief\b|\bcampaign brief\b|\bcommercial brief\b|"
            r"\bmedia invitation\b|\bprocurement brief\b|\bembargo(?:ed)?\b",
        ),
        "整理了一项公开传播合作的文案结构、协作流程与发布节奏，具体主体和活动信息不公开。",
        "Structured the copy, collaboration flow, and release cadence for a public communication project; specific parties and campaign details remain private.",
    ),
    SemanticRule(
        "named_infrastructure_status",
        re.compile(
            r"(?is)API\s*Token|access[_ -]?token|Cloudflare|Wrangler|"
            r"\bQMT\b|qmt_[a-z0-9_]+|Workers?\s+API|"
            r"部署令牌|接口令牌|访问令牌",
        ),
        "核对了外部服务权限、部署与数据链路的可用性，具体平台和技术细节不公开。",
        "Checked the availability of external-service permissions, deployment, and data paths; platform names and technical details remain private.",
    ),
    SemanticRule(
        "internal_verification_chatter",
        re.compile(
            r"(?is)verification\s+status|verification\s+summary|concrete\s+blocker|"
            r"file[- ]mutation\s+verifier|ad[- ]hoc[- ]verified|no\s+(?:shell|terminal)|"
            r"read_file|write_file|search_files|shell_exec|sensitive\s+system\s+path|"
            r"temp(?:orary)?\s+(?:verification\s+)?script|"
            r"运行时核验|执行阻塞|临时验证脚本|文件变更验证器|内部校验脚本",
        ),
        "核验了提醒记录的结构与完整性，内部执行细节不公开。",
        "Checked the reminder record for structural integrity; internal execution details remain private.",
    ),
    SemanticRule(
        "personal_psychological_interpretation",
        re.compile(
            r"(?is)source\s+of\s+guilt|not\s+enough\s+trust|deceiv(?:e|ing)\s+yourself|"
            r"you\s+can(?:no|'t)\s+really\s+rest|if\s+you\s+feel\s+(?:empty|bored)|"
            r"you\s+are\s+not\s+a\s+machine|no\s+progress.{0,30}terrible|"
            r"内疚|不够信任|欺骗自己|无法真正休息|感到空虚|你不是机器|"
            r"没有进展.{0,20}(?:可怕|糟糕)",
        ),
        "保留了一条关于节奏、休息与自我观察的温和提醒，具体心理判断不公开。",
        "Retained a gentle reminder about pace, rest, and self-observation; specific psychological interpretations remain private.",
    ),
    SemanticRule(
        "publishing_operation",
        re.compile(
            r"(?is)social[- ]publishing\s+queue|scheduling\s+quota|"
            r"drafts?.{0,80}waiting\s+in\s+the\s+queue|"
            r"weibo.{0,80}(?:schedul|quota|queue)|"
            r"发布队列|定时配额|排队稿件|微博.{0,40}(?:定时|配额|队列)",
        ),
        "核对了一项公开内容的排期与归档，具体平台、稿件和运行状态不公开。",
        "Checked scheduling and archiving for a public-content item; platform, draft, and operational details remain private.",
    ),
    SemanticRule(
        "personal_finance_or_trading",
        re.compile(
            r"(?is)持仓|仓位|试仓|真实账户|真实仓位|金融终端|触发价|"
            r"止盈|止损|补仓|减仓|买入|卖出|申购套利|"
            r"\b(?:HK|US|SZ|SH)\.\d{3,6}\b|\bQMT\b|\bFutu\b|\bSWHY\b|"
            r"\bportfolio\s+(?:holding|position|allocation|exposure)s?\b|"
            r"\bholdings?\s+(?:query|snapshot|automation)\b|"
            r"\btrading\s+account\b|\bbuy[/ ]sell\b",
        ),
        "整理了只读研究、证据校验与风险复核流程，具体资产、账户和操作不公开。",
        "Structured a read-only research, evidence-checking, and risk-review workflow; specific assets, accounts, and actions remain private.",
    ),
)

_ABSTRACT_MARKERS = tuple(
    value
    for rule in RULES
    for value in (rule.abstract_zh, rule.abstract_en)
)
_HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def semantic_risk_tags(text: str) -> tuple[str, ...]:
    """Return semantic-risk tags without echoing the matched private text."""
    remainder = text
    for marker in _ABSTRACT_MARKERS:
        remainder = remainder.replace(marker, "")
    return tuple(rule.tag for rule in RULES if rule.pattern.search(remainder))


def projection_tags(text: str) -> tuple[str, ...]:
    """Return both newly detected risks and tags already abstracted earlier."""
    tags: list[str] = []
    for rule in RULES:
        if (
            rule.pattern.search(text)
            or rule.abstract_zh in text
            or rule.abstract_en in text
        ) and rule.tag not in tags:
            tags.append(rule.tag)
    return tuple(tags)


def abstract_for_tags(tags: tuple[str, ...], language: str) -> str:
    """Build a stable bilingual-safe abstraction for an ordered tag set."""
    values: list[str] = []
    for rule in RULES:
        if rule.tag not in tags:
            continue
        value = rule.abstract_en if language == "en" else rule.abstract_zh
        if value not in values:
            values.append(value)
    return "\n".join(values)


def abstract_sensitive_public_text(text: str) -> tuple[str, tuple[str, ...]]:
    """Abstract sensitive blocks while preserving surrounding safe prose."""
    if not text:
        return text, ()

    parts = re.split(r"(\n[ \t]*\n)", text)
    output: list[str] = []
    applied: list[str] = []
    for part in parts:
        if not part or re.fullmatch(r"\n[ \t]*\n", part):
            output.append(part)
            continue
        if part.strip() in _ABSTRACT_MARKERS:
            output.append(part)
            continue
        matches = [rule for rule in RULES if rule.pattern.search(part)]
        if not matches:
            output.append(part)
            continue
        use_english = _HAN_RE.search(part) is None
        replacements: list[str] = []
        for rule in matches:
            replacement = rule.abstract_en if use_english else rule.abstract_zh
            if replacement not in replacements:
                replacements.append(replacement)
            if rule.tag not in applied:
                applied.append(rule.tag)
        output.append("\n".join(replacements))

    result = "".join(output)
    result = re.sub(r"(?:\n[ \t]*){3,}", "\n\n", result).strip()
    return result, tuple(applied)


def semantic_abstraction_is_complete(text: str) -> bool:
    """True when no raw semantic-risk pattern remains in public prose."""
    return not semantic_risk_tags(text)
