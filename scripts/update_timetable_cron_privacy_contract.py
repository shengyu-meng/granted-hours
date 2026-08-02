#!/usr/bin/env python3
"""Install the timetable v6 privacy and daily-closure contract in live jobs."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import secrets
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


FREE_ROAM_JOB_NAME = "白夜自由时段 · nightly autonomous roam"
DIALOGUE_JOB_NAME = "授时：前一日工作对话脱敏同步"
CLOSURE_JOB_NAME = "授时：每日自由创作与日历闭环"
TARGET_ROLES = {"free_roam", "dialogue", "closure"}
MARKER = "[授时每日公开闭环契约 v6]"
CONTRACT_BLOCK_RE = re.compile(
    r"(?:\n+)?\[(?:授时公开语义隐私契约|授时每日公开闭环契约) v\d+\]\n"
    r"(?:- [^\n]*(?:\n|$))+\Z"
)
COMMON_CONTRACT = """

[授时每日公开闭环契约 v6]
- 公开文本的处理优先级固定为：先改写为可读的抽象表达，再对仍有辨识风险的实体打码；只有连抽象意义都会泄露私人事实时才删除整条。不得把“删除整条”当作默认方案。
- 家庭梦境、亲密关系、照护与父母子女角色，只能保留为“私人经验中的关系/责任/照护平衡”等抽象协作主题；不得公开具体人物、情节、冲突或家庭结构。
- 身体、药物、疾病、症状、低能量和情绪状态，只能保留为“个人恢复安排”等抽象主题；不得公开具体名称、表现或时间线。
- 未公开品牌、产品、媒体、采购、活动和合作 Brief，只能保留文案结构、协作流程、发布节奏等工作方法；不得公开主体、产品、活动、身份、账户或合作语境。
- 密钥、Token、部署平台、量化终端、数据链路和账户状态，只能保留为“核对外部服务权限、部署与数据链路可用性”；不得公开平台名、凭据、故障细节或运行状态。
- 人名、地名、项目名、事件名、论文名、研究课题名、疾病名、实际持仓名、手机号、银行账号、路径、URL、凭据及技术标识必须先经过私有 denylist、实体识别与格式规则处理；私有 denylist 保持 Git 外 0600，任何值不得进入日志。
- 从 AI 回复补充公开结果时，必须先做独立二次审核；只允许已完成的发现、设计取舍、方法或可验证公开成果。家庭/健康、未公开商业、个人投资与交易、发布运营、教育身份、账户与基础设施、进度闲聊一律不作为新增结果；未知私人语境直接拒绝，不得为了补足卡片编造。
- 用户主动交谈、主动交办，以及主会话有证据委派给 Codex/GPT/Claude/子 Agent 并返回完成结果的工作，都是“人机主动协作”；发布前必须运行 `python3 scripts/import_collaboration_events.py`，不得只运行旧的单日摘要 upsert。
- A/H 与美股例行扫描只提交聚合卡片：保留运行次数、宽泛主题、有限状态和通用新鲜度提示；不得提交标的、持仓、价格、动作建议、终端名、源状态、Workspace 标识或维护路径。
- 运行 `import_timetable_pulses.py` 时必须传入 `--private-redaction-terms .private/identity-denylist.json`，使提醒文本与主动协作使用同一套人名、机构名、项目名和事件名 denylist；不得只依赖通用实体识别。
- 面向读者只显示直接标题和完整内容，不显示“已整理/已核对……具体内容不公开”“结果｜”“脱敏原话”、遮罩计数、source kind、faithfulness 或上下文压缩/交接提示。长对话只能在完整句边界收束；无法形成完整句的片段不展示。措辞整理必须位于语义抽象与实体打码之后，不能借补全文意恢复被遮蔽的细节。
- 生成或导入日历后，必须先运行 `python3 scripts/apply_semantic_public_policy.py --write`，再运行 `python3 scripts/test_semantic_public_policy.py` 与 `python3 scripts/check_public_safety.py`。任一门禁失败时停止构建、提交、推送和部署，且日志不得回显命中的原文。
- `npm run build:timetable` 已内置同一语义清洗步骤；不得绕开它直接发布旧的 timetable 数据或静态产物。
- 每次运行都必须审计积压而不只看昨天或今天：完整自由创作产物存在但尚未进入 `metadata/days.json` 的日期、`waiting_for_public_day`、`blocked` 和 `partial` 日期都进入持久待办，后续按日期从旧到新重试；失败不得吞掉日期或伪报成功。
- 发布状态必须区分 `ok/partial/blocked/waiting_for_public_day/no_change`，记录公开 SHA、最新日期、待办日期与失败阶段；状态和日志只写计数、日期、哈希与错误类别，不写私有原文或命中的敏感值。
""".rstrip()

FREE_ROAM_CONTRACT = COMMON_CONTRACT + """
- 05:00 任务从 v6 起只负责自由创作、私有日志、本地安全验证和原子 ready receipt；不得写 canonical public worktree，不得 commit、push 或 deploy。公开归档统一交给 06:35 闭环任务，避免创作与发布在同一长任务中互相拖死。
- ready receipt 写入 workspace `tmp/granted-hours-free-roam-ready/YYYY-MM-DD.json`，权限 0600，只含 schema、日期、作品文件基名、所需资产是否齐全、验证状态与更新时间，不含作品正文、私有日志、会话或身份信息。
""".rstrip()

DIALOGUE_CONTRACT = COMMON_CONTRACT + """
- 00:20 任务先处理刚结束的前一自然日，再复核持久待办中的所有已公开日期；不存在公开日期时写 `waiting_for_public_day`，由 06:35 闭环在作品入历后补跑，不能永久漏收。
- 严格 owner-route collector 与 `upsert_dialogue_residues.py` 可保留为前一日私有证据审计；随后必须运行 `python3 scripts/import_collaboration_events.py`，以统一纳入主动对话、主会话委派和有证据的 Codex/GPT/Claude/子 Agent 完成结果。
- 如果重新导入后没有公开变化，状态写 `no_change`，不得制造提交；有变化才进入完整测试、显式暂存、推送、部署与公网验收。
""".rstrip()

CLOSURE_CONTRACT = COMMON_CONTRACT + """
- 这是 06:35 的每日自由创作与日历闭环，必须在 05:00 创作任务结束后运行；发现创作仍在运行时只记录 `blocked_upstream_running` 并留待下一次，不并发修改公开仓库。
- 先从 ready receipt 与 `artifacts/free-roam` 交叉验证完整产物，再把所有“已有完整产物但未进入日历”的日期按从旧到新处理；一次可连续补齐多日，不得只处理今天。缺少声明、预览或翻译时修复该日期，不能跳过后清空待办。
- 每个新日期进入 `metadata/days.json` 后，依次运行严格对话补录（适用于已结束日期）、`python3 scripts/import_collaboration_events.py`、真实 Cron pulse 导入、语义清洗、完整句与安全门禁、全量测试和确定性构建。
- 预览必须同时存在 PNG、GIF 与 WebP；三者都要表现作品本身，禁止目录、错误页、加载壳或可被 OCR 读出的界面/路径文字。GIF/WebP 必须有可见运动、固定帧数和有界时长，archive 与 docs 镜像哈希必须一致。
- 动态捕获只允许一次有界尝试，90 秒仍未完成就终止整棵捕获进程，改用已验证 PNG 的无文字视觉区域生成确定性固定帧动画并同步导出 GIF/WebP；不得把无限等待、静态单帧、缺任一格式或旧 WebP 继续沿用当作成功。
- 只允许 canonical worktree；开始和发布后均验证 `HEAD == origin/main == git ls-remote origin refs/heads/main`。工作树不干净或三方失配时 fail closed、保留积压，不 merge/rebase/reset，也不吸收无关改动。
- 只有测试与公开安全门禁全部通过才能显式暂存、提交、推送和 Cloudflare 部署；GitHub 成功而 Cloudflare 失败时状态为 `partial` 且后续继续补部署，不回滚已发布提交。
""".rstrip()

CONTRACT_BY_ROLE = {
    "free_roam": FREE_ROAM_CONTRACT,
    "dialogue": DIALOGUE_CONTRACT,
    "closure": CLOSURE_CONTRACT,
}


def job_role(job: dict) -> str | None:
    name = job.get("name")
    if name == FREE_ROAM_JOB_NAME:
        return "free_roam"
    if name == DIALOGUE_JOB_NAME:
        return "dialogue"
    if name == CLOSURE_JOB_NAME:
        return "closure"
    return None


def make_closure_job(free_roam_job: dict) -> dict:
    workspace_value = free_roam_job.get("workdir")
    if not isinstance(workspace_value, str) or not workspace_value.strip():
        raise SystemExit("The free-roam job has no workspace")
    workspace = Path(workspace_value).resolve()
    artifacts = workspace / "artifacts" / "free-roam"
    receipts = workspace / "tmp" / "granted-hours-free-roam-ready"
    public_worktree = (
        workspace / "art-projects" / "granted-hours-daily-sync"
    )
    public_state = workspace / "tmp" / "granted-hours-daily-closure-state.json"
    prompt = f"""你在执行《授时 / Granted Hours》每日自由创作与日历闭环。任务每天 06:35 Asia/Shanghai 运行，承接 05:00 自由创作，并自动追赶历史积压。不得递归创建或修改 Cron。

固定路径：
- workspace: `{workspace}`
- private artifacts: `{artifacts}`
- private ready receipts: `{receipts}`
- canonical public worktree: `{public_worktree}`
- public state: `{public_state}`

只在 canonical public worktree 完成导入、测试、提交、推送、部署和公网验收。最终只报告日期、计数、公开 SHA、远程仓库/公网部署状态、积压日期和错误类别；不得回显私有对话、私有日志或敏感命中值。
"""
    timezone = ZoneInfo("Asia/Shanghai")
    now = datetime.now(timezone)
    next_run = now.replace(hour=6, minute=35, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return {
        "id": secrets.token_hex(6),
        "name": CLOSURE_JOB_NAME,
        "prompt": prompt,
        "skills": copy.deepcopy(free_roam_job.get("skills", [])),
        "skill": free_roam_job.get("skill"),
        "model": None,
        "provider": None,
        "base_url": None,
        "script": None,
        "context_from": None,
        "schedule": {
            "kind": "cron",
            "expr": "35 6 * * *",
            "display": "35 6 * * *",
        },
        "schedule_display": "35 6 * * *",
        "repeat": {"times": None, "completed": 0},
        "enabled": True,
        "state": "scheduled",
        "paused_at": None,
        "paused_reason": None,
        "created_at": now.isoformat(),
        "next_run_at": next_run.isoformat(),
        "last_run_at": None,
        "last_status": None,
        "last_error": None,
        "last_delivery_error": None,
        "deliver": free_roam_job.get("deliver", "origin"),
        "origin": copy.deepcopy(free_roam_job.get("origin")),
        "enabled_toolsets": [
            "terminal",
            "file",
            "web",
            "session_search",
            "memory",
            "skills",
            "vision",
        ],
        "workdir": str(workspace),
        "fire_claim": None,
    }



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jobs", type=Path)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = json.loads(args.jobs.read_text(encoding="utf-8"))
    jobs = source.get("jobs")
    if not isinstance(jobs, list):
        raise SystemExit("Cron job catalog has no jobs array")
    jobs_by_role: dict[str, dict] = {}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        role = job_role(job)
        if role is None:
            continue
        if role in jobs_by_role:
            raise SystemExit(f"More than one timetable job matched role {role}")
        jobs_by_role[role] = job
    changed = 0
    if "free_roam" not in jobs_by_role or "dialogue" not in jobs_by_role:
        raise SystemExit("Required timetable source jobs were not found")
    if "closure" not in jobs_by_role:
        closure_job = make_closure_job(jobs_by_role["free_roam"])
        jobs.append(closure_job)
        jobs_by_role["closure"] = closure_job
    for role, job in jobs_by_role.items():
        prompt = job.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise SystemExit(f"Target cron role {role} has no prompt")
        if prompt.count(MARKER) > 1:
            raise SystemExit(f"Target cron role {role} has duplicate privacy contracts")
        contract = CONTRACT_BY_ROLE[role]
        if MARKER in prompt and prompt.rstrip().endswith(contract):
            continue
        base = CONTRACT_BLOCK_RE.sub("", prompt).rstrip()
        job["prompt"] = f"{base}\n{contract}\n"
        changed += 1
    missing = TARGET_ROLES - set(jobs_by_role)
    if missing:
        raise SystemExit("Required timetable cron roles were not found")
    if args.write and changed:
        mode = args.jobs.stat().st_mode & 0o777
        descriptor, temporary_name = tempfile.mkstemp(
            dir=args.jobs.parent,
            prefix=f".{args.jobs.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(source, output, ensure_ascii=False, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, args.jobs)
        finally:
            temporary.unlink(missing_ok=True)
    print(
        f"Timetable cron privacy contract mode={'write' if args.write else 'audit'}; "
        f"targets={len(jobs_by_role)}; changed={changed}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
