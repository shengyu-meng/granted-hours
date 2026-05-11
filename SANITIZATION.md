# Sanitization Protocol / 脱敏协议

## English

The public repository is a sanitized mirror, not the raw archive.

Before publication, entries should be checked for:

- personal names and relationship chains not intended for publication;
- email addresses, phone numbers, chat IDs, account IDs, and private handles;
- secrets, tokens, cookies, API keys, credentials, and session material;
- local absolute paths and machine-specific configuration;
- private financial, investment, medical, family, or administrative information;
- screenshots containing private UI, browser tabs, local paths, or account clues;
- prompts or source materials that quote private conversations without permission.

Allowed public identifiers include the public repository owner and project title.

The recommended workflow is:

1. Keep raw materials in a private local archive.
2. Generate or copy only redacted material into the public mirror.
3. Run `scripts/check_public_safety.py` before every commit.
4. Review warnings manually.
5. Push only the public mirror.

Preview policy:

- Runnable generative artworks should keep three public forms: live HTML as the primary work, a full-frame PNG still for archival clarity, and a compressed GIF for browsing.
- Preview capture may activate the artwork with mouse movement/clicks, so interactive works are documented in an exhibited state rather than as untouched cold starts.

## 中文

公开仓库是脱敏镜像，不是原始档案。

发布前需要检查：

- 不应公开的人名与关系链；
- 邮箱、电话、聊天 ID、账号 ID、私人 handle；
- 密钥、token、cookie、API key、凭证与 session 信息；
- 本地绝对路径与机器相关配置；
- 私人财务、投资、医疗、家庭或行政信息；
- 截图中的私人界面、浏览器标签、本地路径或账号线索；
- 未经许可引用私人对话的 prompt 或源材料。

允许公开的标识包括公开仓库 owner 与项目标题。

推荐流程：

1. 原始材料只保存在本地私有档案。
2. 只把脱敏后的材料生成或复制到公开镜像。
3. 每次 commit 前运行 `scripts/check_public_safety.py`。
4. 人工复核所有 warning。
5. 只 push 公开镜像。

预览策略：

- 可运行的生成艺术保留三种公开形态：live HTML 是作品本体；全画幅 PNG 用于清晰归档；压缩 GIF 用于浏览入口。
- 预览捕获可以用鼠标移动/点击激活作品，让交互作品以“展出状态”被记录，而不是只记录未触碰的冷启动画面。
