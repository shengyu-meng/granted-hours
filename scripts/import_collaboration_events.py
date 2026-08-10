#!/usr/bin/env python3
"""Import owner-initiated Hermes collaboration as privacy-safe foreground events."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from import_agent_events import collect_agent_events
from semantic_public_policy import (
    abstract_sensitive_public_text,
    polish_public_excerpt,
    projection_tags,
    semantic_risk_tags,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DB = Path.home() / ".hermes" / "profiles" / "heizhou" / "state.db"
DEFAULT_DAYS = ROOT / "metadata" / "days.json"
DEFAULT_HISTORY = ROOT / "metadata" / "timetable-history.json"
DEFAULT_ENTITY_DETECTOR = ROOT / "scripts" / "detect_collaboration_entities.swift"
DEFAULT_HOLDINGS_DENYLIST = ROOT / ".private" / "holdings-denylist.json"
DEFAULT_SELF_MEDIA_DENYLIST = ROOT / ".private" / "self-media-denylist.json"
DEFAULT_IDENTITY_DENYLIST = ROOT / ".private" / "identity-denylist.json"
DEFAULT_CONTOURS = ROOT / "metadata" / "timetable-collaboration-contours.json"
TIMEZONE = ZoneInfo("Asia/Shanghai")
HISTORY_SCHEMA = "granted-hours-timetable-history-v4"
LEGACY_HISTORY_SCHEMAS = {"granted-hours-timetable-history-v3"}
COLLABORATION_CONTOURS_SCHEMA = "granted-hours-collaboration-contours-v1"
MASK = "████"
MAX_HISTORY_RESIDUES = 10
MAX_COLLABORATIONS_PER_DAY = 4
MAX_AGENT_EVENTS_PER_DAY = 3
AGENT_EXPANSION_EFFECTIVE_DATE = "2026-08-10"
MAX_OWNER_EXCERPTS_PER_CARD = 2
MAX_OUTCOME_EXCERPTS_PER_CARD = 1
MAX_EXCERPTS_PER_CARD = MAX_OWNER_EXCERPTS_PER_CARD + MAX_OUTCOME_EXCERPTS_PER_CARD
MAX_OUTCOME_CANDIDATES_PER_GROUP = 4
MAX_EXCERPT_CHARS = 260
GENERATED_KINDS = {"collaboration_session", "agent_session"}
TOPIC_GROUPING_EFFECTIVE_DATE = "2026-08-10"
MANUALLY_CURATED_DATES = {"2026-05-06"}

ACK_RE = re.compile(
    r"(?ix)^(?:/\w+(?:\s+\w+)?|好(?:的)?|可以|行|嗯+|哦+|继续|收到|知道了|"
    r"明白|是|否|ok(?:ay)?|yes|no|thanks?|谢谢|重试|再试(?:一次)?|go|开始)[。.!！?？\s]*$"
)
WRAPPER_RE = re.compile(
    r"(?ixs)\[\s*IMPORTANT:\s*Background\ process|\[\s*ASYNC\ DELEGATION|"
    r"\[\s*Your\ active\ task\ list|\[\s*System\ note:|"
    r"(?:tool[-\s]?progress|watch[-\s]?pattern)\s+notice|"
    r"\[The\ user\ sent\ an\ image|I(?:’|')m\ sorry,\ but\ I\ don(?:’|')t\ have\ the\ ability\ to\ view|"
    r"(?:conversation|context)\s+(?:was\s+)?compact(?:ed|ion)\b.{0,80}\bhandoff\b"
)
OUTCOME_CUE_RE = re.compile(
    r"(?ix)\b(?:completed|implemented|created|built|fixed|updated|changed|"
    r"verified|validated|passed|confirmed|found|conclusion|result|kept|removed|"
    r"merged|generated|selected|decided|compared|rejected|delivered)\b|"
    r"(?:已|已经|现已)?(?:完成|实现|创建|构建|修复|更新|调整|改为|改成|核验|"
    r"验证|通过|确认|发现|保留|移除|删除|合并|生成|选择|决定|比较|拒绝|交付)|"
    r"结论|结果"
)
NON_OUTCOME_RE = re.compile(
    r"(?ix)\b(?:will|plan(?:ned)?|next|todo|in[- ]?progress|pending|blocked|"
    r"cannot|unable|failed|could\s+not|not\s+(?:completed|finished|done))\b|"
    r"接下来|下一步|计划|准备|待办|稍后|正在|仍在|尚未|未完成|无法|失败|卡住|"
    r"我会|我将"
)
MARKDOWN_PREFIX_RE = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)、]\s+|>\s*)")
OUTCOME_ALLOWED_CATEGORIES = {
    "research_synthesis",
    "visual_production",
    "document_processing",
    "code_development",
}
OUTCOME_PRIVATE_DOMAIN_RE = re.compile(
    r"(?ix)"
    r"股票|个股|市场|持仓|仓位|买点|买入|卖出|买卖|减仓|加仓|止损|止盈|"
    r"申购|套利|期权|行权|covered\s+call|call\s+spread|strike|"
    r"美\s*股|港\s*股|A\s*股|A/H|ETF|LOF|QDII|BOLL|KDJ|MACD|盘口|券商|账户|"
    r"交易|财报|财务|行情|资金|收益|催化|估值|高开|低走|港元|涨幅|"
    r"利润兑现|预期差|恐慌卖|硬触发|观察逻辑|主观察|discovery\s+signal|"
    r"单股|触发价|强势股|日线|大阴线|站回|卖铲人|模块股|基础设施税|"
    r"标的|池内刷新|低优先提及|低\s*beta|US\.|可执行资产|全局诊断|"
    r"财经日报|盘前|盘中|盘后|alpha|put\s+spread|theta|Stage\s*2|"
    r"\b(?:stock|equity|ticker|holding|position|portfolio|trade|trading|option)\b|"
    r"GitHub|git\b|repo(?:sitory)?|commit|push|branch|release|tag\b|"
    r"deploy|auth|login|callback|endpoint|provider|token|API\b|cron|skill|"
    r"workspace|session|model\s+override|端口|授权|登录|会话记录|"
    r"部署|仓库|分支|提交|推送|远程|本地路径|文件路径|目录|备份|依赖|安装|"
    r"定时任务|监控链路|脚本上下文|漏洞|雷达任务|任务列表|worker|queue|browser|浏览器发布|"
    r"发布链路|只读功能验证|只测了|暂不碰|"
    r"微博|知识星球|公众号|学生|课堂|课程|学校|老师|参赛|"
    r"药物|疾病|症状|身体|情绪|伴侣|孩子|家庭|父职|母职"
)
OUTCOME_PROCESS_RE = re.compile(
    r"(?ix)^(?:请|帮我|把|你愿意|你确认|请确认|收到|规则确认|输出格式)|"
    r"等你|回我|你点|之后再|以后再|下一轮|下一步|接下来|后续再讨论|"
    r"可以改|可改|需要改|建议改|"
    r"目前还没有|暂时没有|尚未|仍未|没有完成|中断|卡死|卡住|"
    r"真实调用|完成后会|会自动回|先做.{0,24}再|"
    r"artifacts?/|untracked|working\s+tree|status\b|"
    r"the document is too large|size could not be verified|"
    r"^[^\n]*[：:]\s*$|[{}]|(?:^|\s)\|(?:\s|$)"
)
OUTCOME_PERSONAL_JUDGMENT_RE = re.compile(
    r"你现在最容易|我们要把你|你的关系|你的直觉|你本人|个人状态|"
    r"心理|情绪|主权层|结果层劫持"
)
OUTCOME_PUBLIC_VALUE_RE = re.compile(
    r"(?ix)结论|核心|关键|差别|变化|意味着|说明|边界|结构|取舍|"
    r"证据|事实|推断|验证|实现|修复|改成|改为|保留|移除|合并|"
    r"创作|作品|叙事|对象|界面|页面|视觉|模型|系统|流程|方法|"
    r"conclusion|result|core|key|difference|change|means|boundary|"
    r"evidence|fact|inference|verified|implemented|fixed|structure|method"
)
CATEGORY_PATTERNS = {
    "research_synthesis": re.compile(r"(?ix)\b(?:research|investigat|analy[sz]|evidence|source|audit|review|verify|fact.?check|synthesi|sector|theme|market|stock|equity)\b|调研|研究|分析|证据|来源|审计|复核|核验|综述|题材|股票|市场|个股|行业"),
    "visual_production": re.compile(r"(?ix)\b(?:visual|image|graphic|poster|thumbnail|illustration|render|layout|design|screenshot)\b|视觉|图像|图片|海报|缩略图|插画|渲染|排版|设计|截图"),
    "document_processing": re.compile(r"(?ix)\b(?:ppt|powerpoint|presentation|slides?|deck|document|docx|writing?|draft|article|copy|editorial|edit)\b|PPT|演示文稿|幻灯片|文档|写稿|写作|起草|文稿|文章|审校|编辑"),
    "code_development": re.compile(r"(?ix)\b(?:code|coding|implement|develop|debug|bug|fix|refactor|test|build|script|api|ui|web|app)\b|编码|开发|实现|调试|修复|重构|测试|脚本|网页|应用"),
    "social_media_organization": re.compile(r"(?ix)\b(?:social|post|publish|weibo|twitter|newsletter|content\s+queue)\b|社交媒体|微博|推文|发布|内容队列"),
    "system_maintenance": re.compile(r"(?ix)\b(?:maintenance|backup|deploy|health|cron|system|config|upgrade|migration|monitor)\b|系统|维护|备份|部署|健康检查|配置|升级|迁移|监控"),
}
CATEGORY_PRIORITY = {
    "research_synthesis": 0, "visual_production": 1, "document_processing": 2,
    "code_development": 3, "social_media_organization": 4,
    "redacted_private": 5, "system_maintenance": 6,
}
EXISTING_PRIORITY = {
    "withheld": -1, "daily_record": 0, "task_card": 1,
    "public_post_archive": 2, "maintenance_record": 4,
}
AGENT_ORDER = ("Hermes", "Codex", "GPT", "Claude", "subagent")
ENTITY_ALLOWLIST = {"Hermes", "Codex", "GPT", "Claude", "AI"}

CATEGORY_PAIR_TITLES = {
    "research_synthesis": ("研究线索与验证", "Research threads and validation"),
    "visual_production": ("视觉创作与修改", "Visual creation and revision"),
    "document_processing": ("写作与文档打磨", "Writing and document refinement"),
    "code_development": ("开发与验证", "Development and validation"),
    "social_media_organization": ("内容组织与发布", "Content organization and publishing"),
    "system_maintenance": ("系统维护与可读性", "System maintenance and readability"),
    "redacted_private": ("讨论、判断与推进", "Discussion, judgment, and advancement"),
}

UNVERIFIED_OUTCOME_PAIR = (
    "当天没有找到可以安全公开、并与这组要求可靠对应的完成记录；不把计划或推断写成已完成。",
    "No public-safe completion record was found that reliably matches this request group; plans and inferences are not presented as completed work.",
)

NO_SAFE_REQUEST_PAIR = (
    "当天对话中的具体指令未通过公开审查，未保留可公开细节。",
    "The specific instruction from that day did not pass the public-disclosure review, so no public detail was retained.",
)

TOPIC_PATTERNS = (
    ("periodic_review", re.compile(r"每周|每7天|周期|回看|复盘|错题|非共识|weekly|periodic|review", re.I)),
    ("source_analysis", re.compile(r"文章|论文|PDF|材料|信源|来源|paper|article|source|evidence", re.I)),
    ("research_screening", re.compile(r"筛选|扫描|观察|机会|标的|公司|股票|行业|screen|scan|candidate|market", re.I)),
    ("multi_agent", re.compile(r"多\s*Agent|Agent|并行|委派|协作|multi.?agent|delegate|parallel", re.I)),
    ("data_connector", re.compile(r"数据|行情|价格|接口|连接器|开放网页|API|connector|data|quote", re.I)),
    ("readability_layer", re.compile(r"JSON|Markdown|Obsidian|可读|阅读层|文档层|readable|reading layer", re.I)),
    ("health_and_backup", re.compile(r"健康检查|备份|失败|守门|监控|恢复|health|backup|watchdog|recovery", re.I)),
    ("visual_control", re.compile(r"视觉生成|随机抽卡|可解释|可复现|构图|层级|版式|留白|visual|layout|composition", re.I)),
    ("video_prototype", re.compile(r"视频|分镜|关键帧|镜头|角色连续|video|storyboard|keyframe|shot", re.I)),
    ("package_and_test", re.compile(r"打包|附件|测试版|回归|可运行产物|依赖|package|attachment|regression|test\s+suite|focused\s+test", re.I)),
    ("copy_and_structure", re.compile(r"文案|措辞|结构|精简|双语|翻译|归档|wiki|copy|wording|structure|translate|archive", re.I)),
)

QUOTED_RE = re.compile(
    r"(?s)```.*?```|`[^`\n]*`|\[[^\]\n]+\]\([^\)\n]+\)|《[^》\n]*》|"
    r"“[^”\n]*”|‘[^’\n]*’|「[^」\n]*」|『[^』\n]*』|\"[^\"\n]*\"|'[^'\n]*'"
)
URL_RE = re.compile(r"(?ix)(?:\b(?:https?|ftp)://|\bwww\.)\S+")
PATH_RE = re.compile(r"(?ix)(?<![A-Za-z0-9])/(?!/)[^\s'\"`]+|file://|(?<![A-Za-z0-9])[A-Z]:[/\\][^\s'\"`]+|(?:~[/\\]|\.\.?[/\\])(?=\S)")
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?:\+?86[- ]?)?1[3-9]\d(?:\d{8}|[- ]\d{4}[- ]\d{4})(?![A-Za-z0-9.])"
    r"|(?<!\w)\+\d(?:[- ]?\d){7,14}(?!\d)"
)
ACCOUNT_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?:\d{4}[- ]?){3}\d{4}(?:[- ]?\d{1,3})?(?![A-Za-z0-9.])"
)
HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{2,}")
SECRET_RE = re.compile(r"(?ix)\b(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{8,}|(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[:：=]\s*\S{6,}")
ID_RE = re.compile(r"(?<!\d)\d{7,}(?!\d)|\b[0-9a-f]{16,}\b")
VERSION_RE = re.compile(r"(?i)\bv?\d+\.\d+(?:\.\d+)?(?:[-_][A-Za-z0-9.]+)?\b")
CN_SCOPE_RE = re.compile(r"(?ix)(项目|课题|研究课题|题材|事件|论文|文章|标题|疾病|病名|诊断|持仓|标的|地点|城市|公司|机构|学校)(?:名|名称|题目)?(?:叫|为|是|[:：])?\s*([^，。；;！？!?\n]{2,48})")
CN_NAMED_SYSTEM_RE = re.compile(r"[\u4e00-\u9fff]{2,12}(?:雷达|系统|计划|工程)(?=不是|是|的|：|:|\s)")
EN_SCOPE_RE = re.compile(r"(?ix)\b(project|research\s+topic|topic|paper|thesis|dissertation|event|disease|diagnosis|holding|position|ticker|company|organization|person|place|location|city)(?:\s+(?:called|named|titled|is))?\s*[:=-]?\s*([A-Za-z0-9][^,.;!?\n]{1,60})")
DISEASE_RE = re.compile(r"[\u4e00-\u9fffA-Za-z]{2,20}(?:综合征|障碍|癌|炎|病|症)")
TITLE_CASE_RE = re.compile(r"(?<![A-Za-z])[A-Z][A-Za-z0-9_-]+(?:\s+[A-Z][A-Za-z0-9_-]+)+(?![A-Za-z])")
COMPOUND_IDENTIFIER_RE = re.compile(r"(?i)\b[A-Z][A-Z0-9]*(?:[-_][A-Z0-9]+)+\b")
SINGLE_PROPER_TOKEN_RE = re.compile(r"(?<![A-Za-z])[A-Z][A-Za-z0-9]{2,}(?![A-Za-z])")
PUBLIC_TECH_TOKENS = {
    "AI", "LLM", "HTML", "CSS", "DOM", "UI", "UX", "GIF", "PNG", "SVG",
    "PDF", "JSON", "XML", "BGM", "QA", "HCI", "Canvas", "JavaScript",
}
CN_PERSON_BEFORE_CUE_RE = re.compile(
    r"(?<![\u4e00-\u9fff])"
    r"([赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    r"戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐"
    r"费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄"
    r"和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁"
    r"杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍"
    r"虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程嵇"
    r"邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗"
    r"山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸"
    r"司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党"
    r"翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄"
    r"晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文"
    r"寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙"
    r"乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公][\u4e00-\u9fff]{1,2})"
    r"(?=\s*(?:是|说|问|提到|提出|回复|发送|老师|同学|教授|博士|先生|女士|的(?:问题|观点|回复)))"
)
CN_PERSON_AFTER_CUE_RE = re.compile(
    r"((?:回复|联系|告诉|请问|找到|让|给|采访|关于)\s*)"
    r"([赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    r"戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐"
    r"费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄"
    r"和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁"
    r"杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍"
    r"虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程嵇"
    r"邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗"
    r"山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸"
    r"司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党"
    r"翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄"
    r"晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文"
    r"寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙"
    r"乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公][\u4e00-\u9fff]{1,2})"
    r"(?![\u4e00-\u9fff])"
)
EDUCATION_TERM_RE = re.compile(
    r"(?ix)\b(?:school|university|college|faculty|department|institute|academy|"
    r"course|curriculum|teacher|instructor|student|degree|undergraduate|graduate|"
    r"bachelor|master|doctoral|dissertation|syllabus)\b"
)
RESIDUAL_PRIVATE_RE = re.compile(
    r"(?ix)\b(?:chat[_ -]?id|thread[_ -]?id|session[_ -]?id|user[_ -]?id)\b"
    r"|\.hermes|state\.db|profiles?[/\\]"
    r"|持仓|仓位|试仓|真实账户|账户敞口|账户权限|头寸|券商头寸|富途证券|证券(?:账户|分组|关注组)"
    r"|\b(?:holdings?|positions?|portfolio\s+(?:allocation|holdings|exposure)|real\s+account|live\s+futu|account\s+exposure)\b"
    r"|本科|硕士|博士|学位|学校|大学|学院|教师|导师|课程|课件|教材|教学|教案|毕业设计|配偶|妻子|丈夫"
)


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> bool:
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == serialized:
        return False
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(serialized)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return True


def public_dates(path: Path) -> list[str]:
    source = read_json(path)
    if not isinstance(source, list):
        raise ValueError("Public days must be a list")
    values = sorted(str(item.get("date", "")) for item in source if isinstance(item, dict))
    if not values or any(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None for value in values):
        raise ValueError("Invalid public dates")
    for value in values:
        date.fromisoformat(value)
    return values


def origin(value: object) -> dict | None:
    try:
        parsed = json.loads(value) if isinstance(value, str) and value else None
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def valid_current_session(row: sqlite3.Row | dict, owner_id: str) -> bool:
    data = dict(row)
    if data.get("source") != "telegram" or str(data.get("user_id") or "") != owner_id:
        return False
    chat_type, chat_id, key = data.get("chat_type"), data.get("chat_id"), data.get("session_key")
    parsed = origin(data.get("origin_json"))
    if not all(isinstance(v, str) and v for v in (chat_type, chat_id, key)) or parsed is None:
        return False
    if parsed.get("platform") != "telegram" or any(str(parsed.get(f) or "") != str(data.get(f) or "") for f in ("user_id", "chat_id", "chat_type")):
        return False
    if chat_type == "dm":
        if chat_id != owner_id: return False
        tail = ["telegram", "dm", owner_id]
    elif chat_type == "group":
        tail = ["telegram", "group", chat_id, owner_id]
    else:
        return False
    parts = key.split(":")
    return len(parts) == len(tail) + 2 and all(parts[:2]) and parts[2:] == tail


def valid_legacy_session(row: sqlite3.Row | dict, owner_id: str) -> bool:
    data = dict(row)
    return data.get("source") == "telegram" and str(data.get("user_id") or "") == owner_id and all(data.get(field) in (None, "") for field in ("chat_type", "chat_id", "session_key", "origin_json"))


def discover_owner_id(connection: sqlite3.Connection) -> str:
    candidates = set()
    for row in connection.execute("SELECT source,user_id,chat_type,chat_id,session_key,origin_json FROM sessions WHERE source='telegram' AND chat_type='dm'"):
        candidate = str(row["user_id"] or "")
        if candidate and valid_current_session(row, candidate): candidates.add(candidate)
    if len(candidates) != 1:
        raise ValueError("Could not establish one Telegram owner")
    return next(iter(candidates))


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"【[^】]*】", "", str(value or ""))).strip()[:100_000]


def meaningful(value: object) -> str:
    text = normalize(value)
    if not text or WRAPPER_RE.search(text) or ACK_RE.fullmatch(text) or len(re.sub(r"\s+", "", text)) < 6:
        return ""
    return text


def classify(text: str) -> str:
    matches = [(len(pattern.findall(text)), -CATEGORY_PRIORITY[category], category) for category, pattern in CATEGORY_PATTERNS.items() if pattern.search(text)]
    return max(matches)[2] if matches else "redacted_private"


def load_private_terms(paths: tuple[Path, ...]) -> tuple[str, ...]:
    terms = []
    for path in paths:
        if not path.exists():
            raise ValueError("Private denylist unavailable; excerpt projection failed closed")
        source = read_json(path)
        values = source.get("terms") if isinstance(source, dict) else None
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ValueError("Private denylist malformed")
        terms.extend(item.strip() for item in values if item.strip())
    return tuple(dict.fromkeys(terms))


def detect_entities(texts: list[str], detector: Path) -> list[list[str]]:
    if not texts: return []
    environment = os.environ.copy()
    clang_cache = ROOT / ".private" / "swift-cache" / "clang"
    swift_cache = ROOT / ".private" / "swift-cache" / "swift"
    clang_cache.mkdir(parents=True, exist_ok=True)
    swift_cache.mkdir(parents=True, exist_ok=True)
    environment.setdefault("CLANG_MODULE_CACHE_PATH", str(clang_cache))
    environment.setdefault("SWIFT_MODULECACHE_PATH", str(swift_cache))
    if detector.suffix == ".swift":
        compiled_detector = ROOT / ".private" / "swift-cache" / "detect-collaboration-entities"
        if (
            not compiled_detector.exists()
            or compiled_detector.stat().st_mtime < detector.stat().st_mtime
        ):
            compilation = subprocess.run(
                ["/usr/bin/xcrun", "swiftc", str(detector), "-o", str(compiled_detector)],
                capture_output=True,
                text=True,
                timeout=600,
                env=environment,
            )
            if compilation.returncode != 0:
                raise ValueError("Collaboration entity detector compilation failed closed")
            compiled_detector.chmod(0o700)
        command = [str(compiled_detector)]
    else:
        command = [str(detector)] if os.access(detector, os.X_OK) else [sys.executable, str(detector)]
    result = subprocess.run(command, input=json.dumps(texts, ensure_ascii=False), capture_output=True, text=True, timeout=180, env=environment)
    if result.returncode != 0:
        raise ValueError("Collaboration entity detector failed closed")
    try: detections = json.loads(result.stdout)
    except json.JSONDecodeError as error: raise ValueError("Malformed entity output") from error
    if not isinstance(detections, list) or len(detections) != len(texts): raise ValueError("Malformed entity output")
    output = []
    for item in detections:
        terms = item.get("PrivateEntityTerms") if isinstance(item, dict) else None
        if not isinstance(terms, list) or not all(isinstance(term, str) for term in terms): raise ValueError("Malformed entity output")
        output.append(terms)
    return output


def mask_term(text: str, term: str) -> str:
    term = term.strip()
    return text if not term or term in ENTITY_ALLOWLIST else re.sub(re.escape(term), MASK, text, flags=re.IGNORECASE)


def mask_unknown_proper_tokens(text: str) -> str:
    return SINGLE_PROPER_TOKEN_RE.sub(
        lambda match: match.group(0)
        if match.group(0) in PUBLIC_TECH_TOKENS
        else MASK,
        text,
    )


def sanitize_excerpt(text: str, entity_terms: list[str], private_terms: tuple[str, ...]) -> str:
    """Mask identifying spans first, then abstract only whole sentences that
    remain sensitive after masking. Safe masked contours stay readable."""
    value = QUOTED_RE.sub(MASK, normalize(text))
    for term in sorted((*private_terms, *entity_terms), key=len, reverse=True):
        value = mask_term(value, term)
    value = CN_PERSON_AFTER_CUE_RE.sub(lambda match: f"{match.group(1)}{MASK}", value)
    value = CN_PERSON_BEFORE_CUE_RE.sub(MASK, value)
    value = CN_SCOPE_RE.sub(lambda match: f"{match.group(1)}：{MASK}", value)
    value = EN_SCOPE_RE.sub(lambda match: f"{match.group(1)}: {MASK}", value)
    for pattern in (URL_RE, PATH_RE, EMAIL_RE, PHONE_RE, ACCOUNT_RE, HANDLE_RE, SECRET_RE, ID_RE, VERSION_RE, DISEASE_RE, TITLE_CASE_RE, COMPOUND_IDENTIFIER_RE, EDUCATION_TERM_RE):
        value = pattern.sub(MASK, value)
    value = mask_unknown_proper_tokens(value)
    value = CN_NAMED_SYSTEM_RE.sub(MASK, value)
    value = re.sub(r"[*_]{1,3}", "", value)
    value = re.sub(rf"(?:{re.escape(MASK)}[\s,，;；:/\\|-]*){{2,}}", MASK, value)
    value, _semantic_tags = abstract_sensitive_public_text(value)
    value = re.sub(r"\s+", " ", value).strip(" ,，;；")
    if RESIDUAL_PRIVATE_RE.search(value): return ""
    if len(re.sub(r"\s+", "", value.replace(MASK, ""))) < 18: return ""
    return polish_public_excerpt(value, MAX_EXCERPT_CHARS)


def outcome_candidates(value: object) -> list[str]:
    """Extract bounded result statements without publishing progress chatter."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    if not text or WRAPPER_RE.search(text):
        return []
    text = re.sub(r"(?s)```.*?```", " ", text)
    parts = re.split(r"\n+|(?<=[。！？.!?；;])\s+", text)
    candidates: list[str] = []
    for part in parts:
        candidate = MARKDOWN_PREFIX_RE.sub("", part).strip()
        if not candidate or len(candidate) > 1200:
            continue
        candidate = normalize(candidate)
        if (
            len(re.sub(r"\s+", "", candidate)) < 18
            or candidate.endswith(("?", "？"))
            or not OUTCOME_CUE_RE.search(candidate)
            or NON_OUTCOME_RE.search(candidate)
        ):
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def outcome_publication_eligible(text: str, category: str) -> bool:
    """Apply a conservative public-interest gate before entity redaction."""
    return (
        category in OUTCOME_ALLOWED_CATEGORIES
        and OUTCOME_PRIVATE_DOMAIN_RE.search(text) is None
        and OUTCOME_PROCESS_RE.search(text) is None
        and OUTCOME_PERSONAL_JUDGMENT_RE.search(text) is None
        and OUTCOME_PUBLIC_VALUE_RE.search(text) is not None
        and semantic_risk_tags(text) == ()
        and projection_tags(text) == ()
    )


def sanitize_outcome_excerpt(
    text: str,
    entity_terms: list[str],
    private_terms: tuple[str, ...],
) -> str:
    """Publish only non-sensitive collaboration outcomes; risky outcomes fail closed."""
    if semantic_risk_tags(text) or projection_tags(text):
        return ""
    value = sanitize_excerpt(text, entity_terms, private_terms)
    if not value or semantic_risk_tags(value) or projection_tags(value):
        return ""
    if value.count(MASK) > 2 or len(value.replace(MASK, "").strip()) < 28:
        return ""
    return polish_public_excerpt(value, MAX_EXCERPT_CHARS)


def information_score(value: str) -> tuple[int, int, str]:
    reasoning = len(re.findall(r"(?i)因为|所以|但是|如果|需要|希望|应该|why|because|but|if|need|should", value))
    return reasoning, len(value.replace(MASK, "")), value


def outcome_information_score(value: str) -> tuple[int, int, str]:
    specificity = len(
        re.findall(
            r"(?ix)比较|证据|结论|推断|事实|取舍|差异|原因|依据|边界|"
            r"compared?|evidence|conclusion|inference|fact|trade.?off|difference|reason|boundary",
            value,
        )
    )
    return specificity, len(value.replace(MASK, "")), value


def topic_keys(text: str) -> tuple[str, ...]:
    return tuple(key for key, pattern in TOPIC_PATTERNS if pattern.search(text))


def load_collaboration_contours(path: Path) -> dict[str, dict]:
    source = read_json(path)
    if not isinstance(source, dict) or source.get("schema") != COLLABORATION_CONTOURS_SCHEMA:
        raise ValueError("Collaboration contour registry schema mismatch")
    contours = source.get("contours")
    if not isinstance(contours, dict) or not all(
        isinstance(key, str) and isinstance(value, dict)
        for key, value in contours.items()
    ):
        raise ValueError("Collaboration contour registry malformed")
    return contours


def contour_signature(
    day: str,
    category: str,
    request_excerpts: list[str],
    outcome_excerpts: list[str],
    delegated: int,
    returned: int,
) -> str:
    payload = "\x1f".join(
        (
            day,
            category,
            "\x1e".join(request_excerpts),
            "\x1e".join(outcome_excerpts),
            str(delegated),
            str(returned),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_contour(entry: dict, signature: str) -> None:
    required = {
        "request_zh",
        "request_en",
        "outcome_zh",
        "outcome_en",
        "completion_status",
        "pair_provenance",
    }
    if not isinstance(entry, dict) or not required.issubset(entry):
        raise ValueError(f"Collaboration contour {signature[:16]}... is incomplete")
    zh_masks = entry["request_zh"].count(MASK) + entry["outcome_zh"].count(MASK)
    en_masks = entry["request_en"].count(MASK) + entry["outcome_en"].count(MASK)
    if zh_masks != en_masks:
        raise ValueError(
            f"Collaboration contour {signature[:16]}... mask parity failed"
        )
    if not all(
        isinstance(entry[field], str) and entry[field].strip()
        for field in (
            "request_zh",
            "request_en",
            "outcome_zh",
            "outcome_en",
        )
    ):
        raise ValueError(
            f"Collaboration contour {signature[:16]}... has empty bilingual copy"
        )


REQUEST_PREFIX_RE = re.compile(r"^(?:请|麻烦|帮我|你帮我|你帮|你|帮忙|请帮我)\s*")


def request_statement(excerpt: str) -> str:
    value = REQUEST_PREFIX_RE.sub("", excerpt.strip())
    return polish_public_excerpt(value, 220)


def build_request_pair(
    excerpts: list[str],
) -> tuple[str, tuple[str, ...]]:
    """Deterministic fallback request from the masked owner instruction."""
    combined = "\n".join(excerpts)
    topics = topic_keys(combined)
    statements = [request_statement(excerpt) for excerpt in excerpts[:2]]
    statements = [value for value in statements if value]
    if not statements:
        return NO_SAFE_REQUEST_PAIR[0], topics
    zh = "；另外要求".join(statements)
    zh = polish_public_excerpt(zh, 240)
    return zh, topics


def build_outcome_pair(
    outcome_excerpts: list[str],
) -> str:
    """Deterministic fallback outcome from the masked result excerpt."""
    if outcome_excerpts:
        zh = polish_public_excerpt(outcome_excerpts[0], 220)
        return zh
    return UNVERIFIED_OUTCOME_PAIR[0]


def result_match_score(
    collaboration: dict,
    result: dict,
) -> int:
    result_topics = set(
        topic_keys(f"{result.get('zh', '')}\n{result.get('en', '')}")
    )
    request_topics = tuple(collaboration.get("_request_topics", ()))
    primary_topic = request_topics[0] if request_topics else None
    if primary_topic is None or primary_topic not in result_topics:
        return -1
    score = 20
    if result.get("source_kind") == "collaboration_session":
        return score + int(collaboration.get("category") == result.get("category"))
    if collaboration.get("category") == result.get("category"):
        return score + 3
    compatible = {
        ("system_maintenance", "document_processing"),
        ("document_processing", "system_maintenance"),
        ("code_development", "system_maintenance"),
        ("system_maintenance", "code_development"),
        ("visual_production", "document_processing"),
        ("document_processing", "visual_production"),
        ("redacted_private", "code_development"),
    }
    if (collaboration.get("category"), result.get("category")) in compatible:
        return score + 2
    return -1


def evidence_matches(collaboration: dict, preserved: dict) -> bool:
    """True when a freshly collected collaboration is the same evidence as an
    already-committed residue (same day, category, observed window, counts, and
    agents). Identical evidence must reuse the committed public pair so a
    re-import preserves semantic-public-policy transformations instead of
    restoring sensitive contour/source text."""
    return all(
        collaboration.get(field) == preserved.get(field)
        for field in (
            "category",
            "evidence_count",
            "session_count",
            "delegated_agent_count",
            "returned_agent_count",
            "start",
            "end",
        )
    ) and list(collaboration.get("agent_labels", ())) == list(
        preserved.get("agent_labels", ())
    )


def finalize_collaboration_pair(
    collaboration: dict,
    result_candidates: list[tuple[int, dict]],
    used_result_indexes: set[int],
    contours: dict[str, dict],
    missing_contours: list[str],
    preserved: dict | None = None,
) -> dict:
    output = {
        key: value
        for key, value in collaboration.items()
        if not key.startswith("_")
    }
    signature = str(collaboration.get("_contour_signature", ""))
    contour = contours.get(signature) if signature else None
    if contour is not None:
        validate_contour(contour, signature)
        request_zh = polish_public_excerpt(
            str(contour["request_zh"]),
            MAX_EXCERPT_CHARS,
        )
        request_en = polish_public_excerpt(
            str(contour["request_en"]),
            MAX_EXCERPT_CHARS,
        )
        outcome_zh = polish_public_excerpt(
            str(contour["outcome_zh"]),
            MAX_EXCERPT_CHARS,
        )
        outcome_en = polish_public_excerpt(
            str(contour["outcome_en"]),
            MAX_EXCERPT_CHARS,
        )
        completion_status = str(contour["completion_status"])
        pair_provenance = str(contour["pair_provenance"])
    else:
        if signature:
            missing_contours.append(signature)
        ranked = sorted(
            (
                (result_match_score(collaboration, result), index, result)
                for index, result in result_candidates
                if index not in used_result_indexes
            ),
            reverse=True,
            key=lambda item: (item[0], -item[1]),
        )
        matched_index = None
        matched_result = None
        if ranked and ranked[0][0] >= 10:
            _score, matched_index, matched_result = ranked[0]
        if matched_result is not None:
            outcome_zh = polish_public_excerpt(
                str(matched_result["zh"]),
                MAX_EXCERPT_CHARS,
            )
            outcome_en = polish_public_excerpt(
                str(matched_result["en"]),
                MAX_EXCERPT_CHARS,
            )
            if not outcome_zh or not outcome_en:
                matched_result = None
                matched_index = None
        if (
            matched_result is not None
            and matched_result.get("source_kind") == "collaboration_session"
        ):
            used_result_indexes.add(matched_index)
            completion_status = str(matched_result["completion_status"])
            pair_provenance = str(matched_result["pair_provenance"])
        elif matched_result is not None:
            used_result_indexes.add(matched_index)
            completion_status = "completed"
            pair_provenance = "matched_public_result_record"
        elif collaboration.get("_has_safe_assistant_outcome"):
            outcome_zh = str(collaboration["_outcome_zh"])
            outcome_en = ""
            completion_status = "completed"
            pair_provenance = "assistant_result_summary"
        else:
            outcome_zh = UNVERIFIED_OUTCOME_PAIR[0]
            outcome_en = ""
            completion_status = "unverified"
            pair_provenance = "no_public_result_evidence"
        request_zh = str(collaboration["_request_zh"])
        request_en = ""
    if (
        preserved is not None
        and evidence_matches(collaboration, preserved)
        and all(
            isinstance(preserved.get(field), str)
            for field in ("request_zh", "request_en", "outcome_zh", "outcome_en")
        )
    ):
        # The committed residue already carries the semantic-public-policy
        # transformed pair for this exact evidence. Reuse that copy instead of
        # restoring the freshly generated contour/source text, so
        # import -> semantic policy -> import -> semantic policy reaches a
        # zero-change fixed point and sensitive source text is never
        # republished on a re-import.
        request_zh = str(preserved["request_zh"])
        request_en = str(preserved["request_en"])
        outcome_zh = str(preserved["outcome_zh"])
        outcome_en = str(preserved["outcome_en"])
        completion_status = str(
            preserved.get("completion_status", completion_status)
        )
        pair_provenance = str(
            preserved.get("pair_provenance", pair_provenance)
        )
    title_zh, title_en = CATEGORY_PAIR_TITLES[str(collaboration["category"])]
    mask_count_zh = request_zh.count(MASK) + outcome_zh.count(MASK)
    mask_count_en = request_en.count(MASK) + outcome_en.count(MASK)
    if mask_count_zh != mask_count_en:
        outcome_zh = outcome_zh.replace(MASK, "某项未公开内容")
        outcome_en = outcome_en.replace(MASK, "a private item")
        request_zh = request_zh.replace(MASK, "某项未公开内容")
        request_en = request_en.replace(MASK, "a private item")
        mask_count_zh = mask_count_en = 0
    output.update(
        {
            "zh": title_zh,
            "en": title_en,
            "request_zh": request_zh,
            "request_en": request_en,
            "outcome_zh": outcome_zh,
            "outcome_en": outcome_en,
            "completion_status": completion_status,
            "pair_provenance": pair_provenance,
            "redaction_count": mask_count_zh,
            "redaction_status": "partial" if mask_count_zh else "none",
        }
    )
    return output


def clock_window(first: float, last: float) -> tuple[str, str]:
    a, b = datetime.fromtimestamp(first, TIMEZONE), datetime.fromtimestamp(last, TIMEZONE)
    if a.date() != b.date(): raise ValueError("Cross-day collaboration")
    start = a.hour * 60 + a.minute
    end = max(start + 1, min(1440, b.hour * 60 + b.minute + 1))
    return f"{start // 60:02d}:{start % 60:02d}", "24:00" if end == 1440 else f"{end // 60:02d}:{end % 60:02d}"


def positive_return(value: object) -> bool:
    text = normalize(value)
    rejected = re.compile(r"(?ix)\b(?:not\s+(?:completed|finished|done)|could\s+not|cannot|unable|failed|unfinished|in[- ]?progress|blocked)\b|未完成|无法完成|失败|尚未完成|仍在进行|卡住")
    completed = re.compile(r"(?ix)\b(?:completed|implemented|created|built|fixed|finished|done|passed|delivered|generated|verified|validated)\b|(?:已|已经|现已)?(?:完成|实现|修复|通过|交付|生成|核验|验收)")
    return bool(text) and rejected.search(text) is None and completed.search(text) is not None


def summary(category: str, day: str, messages: int, sessions: int, delegated: int, returned: int) -> tuple[str, str]:
    actions = {
        "research_synthesis": ("调研与题材研究", "research and thematic inquiry"),
        "visual_production": ("视觉创作与修改", "visual creation and revision"),
        "document_processing": ("写作与文档打磨", "writing and document refinement"),
        "code_development": ("开发与验证", "development and validation"),
        "social_media_organization": ("内容组织与发布", "content organization and publishing"),
        "system_maintenance": ("系统维护与部署", "system maintenance and deployment"),
        "redacted_private": ("讨论、判断与任务推进", "discussion, judgment, and task advancement"),
    }
    azh, aen = actions[category]
    zh = f"{day}｜{azh} · {messages} 条内容 · {sessions} 个会话"
    en = f"{day} · {aen.title()} · {messages} message(s) · {sessions} session(s)"
    if delegated:
        zh += f" · {delegated} 次 Agent 委派"
        en += f" · {delegated} delegated Agent run(s)"
        if returned:
            zh += f" · {returned} 次完成回传"
            en += f" · {returned} completed return(s)"
    if len(zh) > 90 or len(en) > 300: raise ValueError("Summary bounds")
    return en, zh


def collect(
    state_db: Path,
    dates: list[str],
    detector: Path,
    denylist_paths: tuple[Path, ...],
) -> tuple[dict[str, list[dict]], dict]:
    first = datetime.combine(date.fromisoformat(dates[0]), datetime.min.time(), tzinfo=TIMEZONE).timestamp()
    last = datetime.combine(date.fromisoformat(dates[-1]) + timedelta(days=1), datetime.min.time(), tzinfo=TIMEZONE).timestamp()
    allowed = set(dates)
    private_terms = load_private_terms(denylist_paths)
    connection = sqlite3.connect(f"file:{state_db.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        owner = discover_owner_id(connection)
        sessions = {}
        for row in connection.execute("SELECT id,source,user_id,model,chat_type,chat_id,session_key,origin_json,started_at,ended_at FROM sessions WHERE source='telegram'"):
            if valid_current_session(row, owner) or valid_legacy_session(row, owner): sessions[str(row["id"])] = dict(row)
        session_ids = tuple(sessions)
        if not session_ids:
            raise ValueError("No verified owner sessions")
        session_placeholders = ",".join("?" for _ in session_ids)
        message_query = (
            "SELECT id,session_id,content,timestamp FROM messages "
            "WHERE session_id IN (" + session_placeholders + ") "
            "AND role=? AND COALESCE(active,1)=1 AND timestamp>=? AND timestamp<? "
            "ORDER BY timestamp,id"
        )
        records, seen = [], defaultdict(set)
        for row in connection.execute(message_query, (*session_ids, "user", first, last)):
            session_id = str(row["session_id"])
            if session_id not in sessions: continue
            text = meaningful(row["content"])
            timestamp = float(row["timestamp"])
            if not text or not math.isfinite(timestamp): continue
            day = datetime.fromtimestamp(timestamp, TIMEZONE).date().isoformat()
            signature = re.sub(r"\s+", " ", text).casefold()
            if day not in allowed or signature in seen[day]: continue
            seen[day].add(signature)
            records.append({"session": session_id, "timestamp": timestamp, "date": day, "category": classify(text), "text": text})
        entity_batches = detect_entities([item["text"] for item in records], detector)
        prepared_records = []
        privacy_states: dict[tuple[str, str], set[bool]] = defaultdict(set)
        for item, entities in zip(records, entity_batches):
            excerpt = sanitize_excerpt(item["text"], entities, private_terms)
            request_text = excerpt or ""
            privacy_text = f"{request_text}\n{item['text']}"
            unsafe = bool(
                OUTCOME_PRIVATE_DOMAIN_RE.search(privacy_text)
                or (
                    item["category"] == "code_development"
                    and re.search(r"路径|沙箱|兼容|stdout|delivery", privacy_text, re.I)
                )
                or re.search(
                    r"(?:\x00|data:image/|base64|(?:^|\s)json:\s*[\[{])",
                    privacy_text,
                    re.I,
                )
            )
            prepared_records.append((item, excerpt, unsafe))
            privacy_states[(item["date"], item["category"])].add(unsafe)

        groups, by_session = {}, defaultdict(list)
        for item, excerpt, unsafe in prepared_records:
            base_key = (item["date"], item["category"])
            if item["date"] >= TOPIC_GROUPING_EFFECTIVE_DATE and len(privacy_states[base_key]) > 1:
                topics = topic_keys(excerpt or item["text"])
                topic = "private" if unsafe else (topics[0] if topics else f"session:{item['session']}")
            else:
                topic = "legacy"
            key = (*base_key, topic)
            group = groups.setdefault(key, {"timestamps": [], "sessions": set(), "excerpts": [], "outcomes": [], "delegated": 0, "returned": 0, "agents": {"Hermes"}})
            group["timestamps"].append(item["timestamp"]); group["sessions"].add(item["session"])
            if excerpt and excerpt not in group["excerpts"]: group["excerpts"].append(excerpt)
            by_session[item["session"]].append((item["timestamp"], item["date"], item["category"], key))
        outcome_candidate_groups = defaultdict(list)
        semantic_outcome_rejections = 0
        policy_outcome_rejections = 0
        for row in connection.execute(message_query, (*session_ids, "assistant", first, last)):
            session_id = str(row["session_id"])
            parent_messages = by_session.get(session_id, [])
            if not parent_messages:
                continue
            timestamp = float(row["timestamp"])
            if not math.isfinite(timestamp):
                continue
            day = datetime.fromtimestamp(timestamp, TIMEZONE).date().isoformat()
            prior = [message for message in parent_messages if message[0] <= timestamp and message[1] == day]
            if not prior:
                continue
            _, _, category, group_key = prior[-1]
            for candidate in outcome_candidates(row["content"]):
                if semantic_risk_tags(candidate) or projection_tags(candidate):
                    semantic_outcome_rejections += 1
                    continue
                if not outcome_publication_eligible(candidate, category):
                    policy_outcome_rejections += 1
                    continue
                key = group_key
                if candidate not in outcome_candidate_groups[key]:
                    outcome_candidate_groups[key].append(candidate)
        delegated_total = returned_total = 0
        child_query = """SELECT c.id,c.parent_session_id,c.model,c.started_at,c.ended_at,(SELECT m.content FROM messages m WHERE m.session_id=c.id AND m.role='assistant' AND COALESCE(m.active,1)=1 ORDER BY m.timestamp DESC,m.id DESC LIMIT 1) final_result FROM sessions c WHERE c.source='subagent' AND c.parent_session_id IS NOT NULL AND c.started_at>=? AND c.started_at<? ORDER BY c.started_at,c.id"""
        for child in connection.execute(child_query, (first, last)):
            parent_messages = by_session.get(str(child["parent_session_id"]), [])
            if not parent_messages: continue
            started = float(child["started_at"])
            prior = [message for message in parent_messages if message[0] <= started]
            _, day, category, group_key = prior[-1] if prior else min(parent_messages, key=lambda message: abs(message[0] - started))
            group = groups[group_key]; group["delegated"] += 1; delegated_total += 1
            if child["ended_at"] is not None and positive_return(child["final_result"]):
                group["returned"] += 1; returned_total += 1
                for candidate in outcome_candidates(child["final_result"]):
                    if semantic_risk_tags(candidate) or projection_tags(candidate):
                        semantic_outcome_rejections += 1
                        continue
                    if not outcome_publication_eligible(candidate, category):
                        policy_outcome_rejections += 1
                        continue
                    key = group_key
                    if candidate not in outcome_candidate_groups[key]:
                        outcome_candidate_groups[key].append(candidate)
            model = str(child["model"] or "").casefold()
            if "gpt" in model: group["agents"].add("GPT")
            if "claude" in model: group["agents"].add("Claude")
            group["agents"].add("subagent")
        outcome_records = []
        low_information_outcome_count = 0
        for group_key, candidates in outcome_candidate_groups.items():
            day, category, _topic = group_key
            ranked = sorted(candidates, key=outcome_information_score, reverse=True)
            selected_candidates = ranked[:MAX_OUTCOME_CANDIDATES_PER_GROUP]
            low_information_outcome_count += len(ranked) - len(selected_candidates)
            outcome_records.extend(
                {"date": day, "category": category, "group_key": group_key, "text": candidate}
                for candidate in selected_candidates
            )
        outcome_entity_batches = detect_entities([item["text"] for item in outcome_records], detector)
        safe_outcome_count = 0
        rejected_outcome_count = semantic_outcome_rejections + policy_outcome_rejections
        for item, entities in zip(outcome_records, outcome_entity_batches):
            excerpt = sanitize_outcome_excerpt(item["text"], entities, private_terms)
            if not excerpt:
                rejected_outcome_count += 1
                continue
            group = groups[item["group_key"]]
            if excerpt not in group["outcomes"]:
                group["outcomes"].append(excerpt)
                safe_outcome_count += 1
        events_by_date, excerpt_count = defaultdict(list), 0
        for (day, category, _topic), group in groups.items():
            timestamps = sorted(group["timestamps"]); start, end = clock_window(timestamps[0], timestamps[-1])
            owner_excerpts = sorted(group["excerpts"], key=information_score, reverse=True)[:MAX_OWNER_EXCERPTS_PER_CARD]
            outcome_excerpts = sorted(group["outcomes"], key=outcome_information_score, reverse=True)[:MAX_OUTCOME_EXCERPTS_PER_CARD]
            request_text = "\n".join(owner_excerpts)
            private_operational_request = (
                category == "code_development"
                and re.search(r"路径|沙箱|兼容|stdout|delivery", request_text, re.I) is not None
            )
            malformed_attachment_request = re.search(
                r"(?:\x00|data:image/|base64|(?:^|\s)json:\s*[\[{])",
                request_text,
                re.I,
            ) is not None
            if (
                (category in {"code_development", "social_media_organization", "system_maintenance"} and not outcome_excerpts)
                or OUTCOME_PRIVATE_DOMAIN_RE.search(request_text)
                or private_operational_request
                or malformed_attachment_request
            ):
                # Do not promote private operational requests without a
                # independently publishable result, or attachment wrappers,
                # into an unverified card.
                continue
            excerpts = [*owner_excerpts, *outcome_excerpts]; excerpt_count += len(excerpts)
            en, zh = summary(category, day, len(timestamps), len(group["sessions"]), group["delegated"], group["returned"])
            pair_request_zh, request_topics = build_request_pair(owner_excerpts)
            pair_outcome_zh = build_outcome_pair(outcome_excerpts)
            if pair_request_zh == NO_SAFE_REQUEST_PAIR[0]:
                # A public card needs a readable masked contour. When none
                # survives the disclosure review, omit the event rather than
                # publish a generic redaction/template sentence.
                continue
            pair_signature = contour_signature(
                day,
                category,
                owner_excerpts,
                outcome_excerpts,
                group["delegated"],
                group["returned"],
            )
            events_by_date[day].append({
                "category": category, "en": en, "zh": zh,
                "redaction_status": "none",
                "redaction_count": 0,
                "source_kind": "collaboration_session", "faithfulness": "faithful_summary", "evidence_count": len(timestamps),
                "session_count": len(group["sessions"]), "delegated_agent_count": group["delegated"], "returned_agent_count": group["returned"],
                "agent_labels": [label for label in AGENT_ORDER if label in group["agents"]],
                "start": start, "end": end, "time_provenance": "observed_message_envelope",
                "_request_zh": pair_request_zh,
                "_outcome_zh": pair_outcome_zh,
                "_contour_signature": pair_signature,
                "_request_topics": request_topics,
                "_has_safe_assistant_outcome": bool(outcome_excerpts),
            })
        selected = {}
        for day, events in events_by_date.items():
            events.sort(key=lambda event: (0 if event["category"] == "research_synthesis" else 1, 0 if event["delegated_agent_count"] else 1, -event["evidence_count"], CATEGORY_PRIORITY[event["category"]], event["start"]))
            selected[day] = events[:MAX_COLLABORATIONS_PER_DAY]
        return dict(selected), {"verified_owner_session_count": len(sessions), "meaningful_message_count": len(records), "active_day_count": len(events_by_date), "delegated_agent_count": delegated_total, "returned_agent_count": returned_total, "public_excerpt_count": excerpt_count, "safe_outcome_candidate_count": safe_outcome_count, "rejected_outcome_candidate_count": rejected_outcome_count, "semantic_outcome_rejection_count": semantic_outcome_rejections, "policy_outcome_rejection_count": policy_outcome_rejections, "discarded_low_information_outcome_count": low_information_outcome_count}
    finally:
        connection.close()


def merge_history(
    history: dict,
    collaborations: dict[str, list[dict]],
    agents: dict[str, list[dict]],
    public_dates: list[str] | None = None,
    contours: dict[str, dict] | None = None,
    missing_contours: list[str] | None = None,
) -> dict:
    if (
        history.get("schema") not in {HISTORY_SCHEMA, *LEGACY_HISTORY_SCHEMAS}
        or not isinstance(history.get("days"), list)
    ):
        raise ValueError("Invalid history")
    history_by_date = {str(entry["date"]): entry for entry in history["days"]}
    ordered_dates = sorted(set(history_by_date) | set(public_dates or ()))
    output = []
    for day in ordered_dates:
        entry = history_by_date.get(day)
        raw_collaborations = collaborations.get(day, [])
        previous_agent_count = sum(
            1
            for item in (entry or {}).get("assigned_residues", [])
            if item.get("source_kind") == "agent_session"
        )
        agent_limit = (
            MAX_AGENT_EVENTS_PER_DAY
            if day >= AGENT_EXPANSION_EFFECTIVE_DATE
            else min(MAX_AGENT_EVENTS_PER_DAY, previous_agent_count)
        )
        foreground = [*raw_collaborations, *agents.get(day, [])[:agent_limit]]
        if entry is None:
            # A newly imported artwork can precede its first dialogue sync. Admit
            # only evidence-backed foreground here; dates with no evidence keep
            # using the builder's inferred fallback until a later refresh.
            if not foreground:
                continue
            entry = {
                "date": day,
                "provenance": "dialogue_based" if collaborations.get(day) else "record_based",
                "assigned_residues": [],
            }
        previous_generated = [
            item for item in entry["assigned_residues"]
            if item.get("source_kind") in GENERATED_KINDS
        ]
        previous_collaborations = [
            item
            for item in previous_generated
            if item.get("source_kind") == "collaboration_session"
            and isinstance(item.get("request_zh"), str)
            and isinstance(item.get("outcome_zh"), str)
            and isinstance(item.get("outcome_en"), str)
        ]
        used_preserved_indexes: set[int] = set()

        def matching_preserved(collaboration: dict) -> dict | None:
            for index, preserved in enumerate(previous_collaborations):
                if index in used_preserved_indexes:
                    continue
                if evidence_matches(collaboration, preserved):
                    used_preserved_indexes.add(index)
                    return preserved
            return None
        existing = [item for item in entry["assigned_residues"] if item.get("source_kind") not in GENERATED_KINDS]
        result_candidates = [
            (index, item)
            for index, item in enumerate(existing)
            if item.get("source_kind")
            in {
                "daily_record",
                "maintenance_record",
                "task_card",
                "public_post_archive",
            }
            and isinstance(item.get("zh"), str)
            and isinstance(item.get("en"), str)
        ]
        result_candidates.extend(
            (
                -(index + 1),
                {
                    "source_kind": "collaboration_session",
                    "category": item.get("category"),
                    "request_zh": item.get("request_zh"),
                    "zh": item.get("outcome_zh"),
                    "en": item.get("outcome_en"),
                    "completion_status": item.get("completion_status"),
                    "pair_provenance": item.get("pair_provenance"),
                },
            )
            for index, item in enumerate(previous_collaborations)
        )
        used_result_indexes: set[int] = set()
        if raw_collaborations:
            finalized_collaborations = []
            for collaboration in raw_collaborations:
                finalized_collaborations.append(finalize_collaboration_pair(
                    collaboration,
                    result_candidates,
                    used_result_indexes,
                    contours or {},
                    missing_contours if missing_contours is not None else [],
                    matching_preserved(collaboration),
                ))
            registered_contours = list((contours or {}).values())
            ordered_collaborations = []
            used_finalized_indexes: set[int] = set()
            for index, preserved in enumerate(previous_collaborations):
                matching_finalized_index = next(
                    (
                        candidate_index
                        for candidate_index, candidate in enumerate(finalized_collaborations)
                        if candidate_index not in used_finalized_indexes
                        and evidence_matches(candidate, preserved)
                    ),
                    None,
                )
                if matching_finalized_index is not None:
                    used_finalized_indexes.add(matching_finalized_index)
                    ordered_collaborations.append(
                        finalized_collaborations[matching_finalized_index]
                    )
                elif any(
                    contour.get("date") == day
                    and contour.get("category") == preserved.get("category")
                    and all(
                        contour.get(field) == preserved.get(field)
                        for field in (
                            "request_zh",
                            "request_en",
                            "outcome_zh",
                            "outcome_en",
                            "completion_status",
                            "pair_provenance",
                        )
                    )
                    for contour in registered_contours
                ):
                    ordered_collaborations.append(preserved)
            ordered_collaborations.extend(
                candidate
                for candidate_index, candidate in enumerate(finalized_collaborations)
                if candidate_index not in used_finalized_indexes
            )
            finalized_collaborations = ordered_collaborations
        else:
            # A date can retain previously validated collaboration cards even
            # when the current bounded source scan has no fresh records for it.
            # Do not turn that absence into an empty history day or erase the
            # prior evidence-backed projection.
            finalized_collaborations = previous_collaborations
        fresh_agents = agents.get(day, [])[:agent_limit]
        foreground = [*finalized_collaborations, *fresh_agents]
        if not raw_collaborations and not fresh_agents:
            foreground = previous_generated
        existing = [
            item for index, item in enumerate(existing)
            if index not in used_result_indexes
        ]
        existing = [item for _, item in sorted(enumerate(existing), key=lambda pair: (EXISTING_PRIORITY.get(pair[1].get("source_kind"), 99), pair[0]))]
        residues = [*foreground, *existing[:max(0, MAX_HISTORY_RESIDUES - len(foreground))]]
        provenance = (
            "withheld"
            if any(item.get("source_kind") == "withheld" for item in residues)
            else "dialogue_based"
            if collaborations.get(day)
            else "record_based"
            if not residues
            else entry["provenance"]
        )
        output.append({**entry, "provenance": provenance, "assigned_residues": residues})
    return {**history, "schema": HISTORY_SCHEMA, "days": output}


def merge_history_scoped(
    history: dict,
    collaborations: dict[str, list[dict]],
    agents: dict[str, list[dict]],
    public_dates: list[str],
    contours: dict[str, dict],
    missing_contours: list[str],
    target_dates: tuple[str, ...] | None = None,
) -> dict:
    if not target_dates:
        return merge_history(
            history,
            collaborations,
            agents,
            public_dates,
            contours,
            missing_contours,
        )
    target_set = set(target_dates)
    scoped_history = {
        **history,
        "days": [entry for entry in history["days"] if entry.get("date") in target_set],
    }
    scoped = merge_history(
        scoped_history,
        collaborations,
        agents,
        sorted(target_set),
        contours,
        missing_contours,
    )
    replacements = {entry["date"]: entry for entry in scoped["days"]}
    merged_days = [
        replacements.pop(entry["date"], entry)
        if entry.get("date") in target_set
        else entry
        for entry in history["days"]
    ]
    merged_days.extend(replacements.values())
    merged_days.sort(key=lambda entry: entry["date"])
    return {**history, "schema": HISTORY_SCHEMA, "days": merged_days}


def import_events(state_db: Path, days_path: Path, history_path: Path, detector: Path, denylists: tuple[Path, ...], dry_run: bool, contours_path: Path = DEFAULT_CONTOURS, target_dates: tuple[str, ...] | None = None) -> dict:
    dates = public_dates(days_path); history = read_json(history_path)
    if target_dates:
        requested = set(target_dates)
        unknown = requested.difference(dates)
        if unknown:
            raise ValueError(f"Requested collaboration dates are not public: {len(unknown)}")
        scan_dates = sorted(requested)
    else:
        scan_dates = dates
    contours = load_collaboration_contours(contours_path)
    collected_dates = [day for day in scan_dates if day not in MANUALLY_CURATED_DATES]
    collaborations, audit = collect(state_db, collected_dates, detector, denylists)
    agents = collect_agent_events(state_db, collected_dates, excluded_parent_sources={"telegram"})
    collaboration_categories = {
        day: {event["category"] for event in events}
        for day, events in collaborations.items()
    }
    agents = {
        day: [
            event for event in events
            if event["category"] not in collaboration_categories.get(day, set())
        ]
        for day, events in agents.items()
    }
    missing_contours: list[str] = []
    merged = merge_history_scoped(
        history,
        collaborations,
        agents,
        scan_dates,
        contours,
        missing_contours,
        target_dates,
    )
    if missing_contours:
        raise ValueError(
            f"Missing {len(missing_contours)} collaboration contours; author "
            f"bilingual contour entries in {contours_path} and rerun"
        )
    report_dates = set(target_dates or dates)
    inserted = [item for day in merged["days"] if day["date"] in report_dates for item in day["assigned_residues"] if item.get("source_kind") == "collaboration_session"]
    changed = json.dumps(merged, ensure_ascii=False, indent=2) + "\n" != history_path.read_text(encoding="utf-8")
    if changed and not dry_run: write_json(history_path, merged)
    return {"changed": changed, "event_count": len(inserted), "event_dates": sorted({day["date"] for day in merged["days"] if day["date"] in report_dates and any(item.get("source_kind") == "collaboration_session" for item in day["assigned_residues"])}), "category_counts": dict(sorted(Counter(item["category"] for item in inserted).items())), "audit": audit, "history": merged}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-db", type=Path, default=DEFAULT_STATE_DB); parser.add_argument("--days", type=Path, default=DEFAULT_DAYS)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY); parser.add_argument("--entity-detector", type=Path, default=DEFAULT_ENTITY_DETECTOR)
    parser.add_argument("--holdings-denylist", type=Path, default=DEFAULT_HOLDINGS_DENYLIST); parser.add_argument("--self-media-denylist", type=Path, default=DEFAULT_SELF_MEDIA_DENYLIST); parser.add_argument("--identity-denylist", type=Path, default=DEFAULT_IDENTITY_DENYLIST)
    parser.add_argument("--contours", type=Path, default=DEFAULT_CONTOURS)
    parser.add_argument("--date", dest="dates", action="append", help="Import only this declared public YYYY-MM-DD date; repeat for multiple dates")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = import_events(args.state_db, args.days, args.history, args.entity_detector, (args.holdings_denylist, args.self_media_denylist, args.identity_denylist), args.dry_run, args.contours, tuple(args.dates) if args.dates else None)
    except (OSError, ValueError, TypeError, OverflowError, sqlite3.Error, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"Collaboration event import failed: {type(error).__name__}", file=sys.stderr); return 1
    audit = result["audit"]
    mode = (
        "would write"
        if args.dry_run and result["changed"]
        else "wrote"
        if not args.dry_run and result["changed"]
        else "already current"
    )
    print(f"Collaboration events {mode}; events={result['event_count']}; dates={len(result['event_dates'])}; meaningful_messages={audit['meaningful_message_count']}; public_pair_sources={audit['public_excerpt_count']}; safe_outcomes={audit['safe_outcome_candidate_count']}; rejected_outcomes={audit['rejected_outcome_candidate_count']}; delegated_agents={audit['delegated_agent_count']}; categories={result['category_counts']}.")
    return 0


if __name__ == "__main__": raise SystemExit(main())
