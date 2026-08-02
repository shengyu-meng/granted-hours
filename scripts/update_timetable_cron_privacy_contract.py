#!/usr/bin/env python3
"""Install the timetable semantic-privacy contract in the two live jobs."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


TARGET_JOB_IDS = {
    "bb2eeb6f4e4f",
    "4ad8b289d364",
}
MARKER = "[授时公开语义隐私契约 v3]"
CONTRACT = """

[授时公开语义隐私契约 v3]
- 公开文本的处理优先级固定为：先改写为可读的抽象表达，再对仍有辨识风险的实体打码；只有连抽象意义都会泄露私人事实时才删除整条。不得把“删除整条”当作默认方案。
- 家庭梦境、亲密关系、照护与父母子女角色，只能保留为“私人经验中的关系/责任/照护平衡”等抽象协作主题；不得公开具体人物、情节、冲突或家庭结构。
- 身体、药物、疾病、症状、低能量和情绪状态，只能保留为“个人恢复安排”等抽象主题；不得公开具体名称、表现或时间线。
- 未公开品牌、产品、媒体、采购、活动和合作 Brief，只能保留文案结构、协作流程、发布节奏等工作方法；不得公开主体、产品、活动、身份、账户或合作语境。
- 密钥、Token、部署平台、量化终端、数据链路和账户状态，只能保留为“核对外部服务权限、部署与数据链路可用性”；不得公开平台名、凭据、故障细节或运行状态。
- 生成或导入日历后，必须先运行 `python3 scripts/apply_semantic_public_policy.py --write`，再运行 `python3 scripts/test_semantic_public_policy.py` 与 `python3 scripts/check_public_safety.py`。任一门禁失败时停止构建、提交、推送和部署，且日志不得回显命中的原文。
- `npm run build:timetable` 已内置同一语义清洗步骤；不得绕开它直接发布旧的 timetable 数据或静态产物。
""".rstrip()


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
    matched = set()
    changed = 0
    for job in jobs:
        job_id = job.get("id")
        if job_id not in TARGET_JOB_IDS:
            continue
        matched.add(job_id)
        prompt = job.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise SystemExit(f"Target cron job {job_id} has no prompt")
        if prompt.count(MARKER) > 1:
            raise SystemExit(f"Target cron job {job_id} has duplicate privacy contracts")
        if MARKER in prompt:
            continue
        job["prompt"] = f"{prompt.rstrip()}\n{CONTRACT}\n"
        changed += 1
    missing = TARGET_JOB_IDS - matched
    if missing:
        raise SystemExit("Required timetable cron jobs were not found")
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
        f"targets={len(matched)}; changed={changed}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
