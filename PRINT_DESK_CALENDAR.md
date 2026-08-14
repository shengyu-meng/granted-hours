# 《授时》实体台历生成手册

这份文档是《授时非人时间表》210 × 140 mm 实体台历的仓库内唯一复现入口。版式参数不再依赖某次对话或仓库外的技能说明；生成器和 QA 都读取同一份版本化 JSON 预设，并把预设路径与 SHA-256 写入 manifest。

## 当前版本

### v3：内容完整版暗色来源日配对版（当前交付规范）

- 两个新增且独立的预设，不覆盖任何 v1/v2 版本：
  - `config/print-desk-calendar-source-aligned-dark-landscape-v3.json`
  - `config/print-desk-calendar-source-aligned-dark-portrait-v3.json`
- 延续 v2 的 Source Day 配对：纸页日期、时间地层、事件卡与二维码都属于 Source Day；作品来自唯一满足 `source_date == 页日期` 的后续公开结晶日，并在页面上同时印出两个日期。
- 横版和竖版都完整印出四段规范作品文字，顺序固定为中文 Summary、中文 Brief、英文 Summary、英文 Brief。作品文字不得省略号截断；若声明区域在最低字号仍放不下，构建必须失败。
- 缺席页不补造作品或文字：只将公开缺席说明与缺席陈述分别放入 Summary/Brief 位置。
- 信息卡先保留真实的协作事件与第一人称晨间/晚间提醒，再用当天真实发生的 A/H 市场、美股市场、后台/系统/日报三个例行族群填充剩余槽位，最多四张卡。例行卡可以汇总，时间地层仍保留每个原始足迹。
- 竖版不是横版旋转：它有独立的 Summary + Brief、16:9 作品图、时间地层与四卡布局；二维码固定为右下角黑底白码。
- 以 2026-08-13 的当前公开数据为准，成册为封面 + 99 个 Source Day（2026-05-06 至 2026-08-12），配对 93 件作品与 6 个公开缺席结晶（2026-05-07 至 2026-08-13）。最新未配对 Source Day 继续省略。

### v2：来源日配对版（回滚保留）

- 四个独立预设：
  - `config/print-desk-calendar-source-aligned-light-landscape-v2.json`
  - `config/print-desk-calendar-source-aligned-dark-landscape-v2.json`
  - `config/print-desk-calendar-source-aligned-light-portrait-v2.json`
  - `config/print-desk-calendar-source-aligned-dark-portrait-v2.json`
- 纸页日期是 Source Day。该页的时间地层、协作/提醒卡与二维码都来自并指向 Source Day；标题、自由变量、说明和作品图来自唯一满足 `source_date == 页日期` 的后续结晶日。
- 页面明确印出 `SOURCE DAY YYYY-MM-DD -> CRYSTALLIZATION YYYY-MM-DD`；不能把编辑配对冒充成电子版发生时间。
- Source Day 自己的凌晨自主/缺席足迹属于上一轮来源关系，因此从 v2 纸页的信号地层排除；协作、提醒、例行的时间足迹不变。
- 首个来源页为 2026-05-06，配对 2026-05-07 的《白夜罗盘》。电子版 2026-05-06 仍如实显示它自己的缺席信标，并通过 `forward_artwork_seeds` 指向第一件作品。
- 最新一个尚未等到后续公开结晶记录的来源日不进入本次成册。以当前数据为准，来源页为 2026-05-06 至 2026-08-12，共 99 页；作品结晶为 2026-05-07 至 2026-08-13。
- v2 静帧缓存为 1100 px、quality 84：在当前印刷尺寸上保留足够像素，同时控制四份邮件附件体积。

### v1：结晶日版（回滚保留）

- 横版：`desk-calendar-v1`，预设 `config/print-desk-calendar-v1.json`，MediaBox 210 × 140 mm
- 竖版：`desk-calendar-portrait-v1`，预设 `config/print-desk-calendar-portrait-v1.json`，MediaBox 140 × 210 mm
- 暗色横版：`desk-calendar-dark-v1`，预设 `config/print-desk-calendar-dark-v1.json`
- 暗色竖版：`desk-calendar-portrait-dark-v1`，预设 `config/print-desk-calendar-portrait-dark-v1.json`
- 两版使用同一张 210 × 140 mm 物理纸张，只改变方向；一天一页，默认含单独封面
- 日期：默认从首个公开 civil day 到数据里的最新公开日；缺席日保留缺席信标，不补造作品
- 风格：暖白底、黑字、彩色事件层与作品图；顶部保留 10 mm 台历装订带
- 作品图：本地静帧优先，中心裁切为 16:9，缓存为 1200 px 宽、quality 86 的 JPEG
- 信息优先级：日期与标题 → 自主作品/缺席信标 → 24 小时时间地层 → 协作与提醒卡 → 例行汇总 → 当天二维码
- 二维码：纠错等级 Q、4 modules 边框，跳转 `https://granted-hours.hyperint.net/timetable/?date=YYYY-MM-DD`
- 竖版二维码：固定在右下角，黑底白码，纠错等级 H、4 modules quiet zone；正式 QA 必须逐页真实解码
- PDF、manifest、QA 报告与渲染图属于本地构建产物，默认被 `.gitignore` 排除；脚本、参数、依赖和本文档进入 Git。

## 仓库内的正式组成

| 文件 | 作用 |
| --- | --- |
| `config/print-desk-calendar-source-aligned-dark-*-v3.json` | 暗色横/竖内容完整版真源；锁定完整 Summary + Brief、来源日事件归属、例行族群补位与黑底白码 |
| `config/print-desk-calendar-source-aligned-*-v2.json` | 四份来源日配对版真源；分别控制亮/暗、横/竖，不覆盖 v1 |
| `config/print-desk-calendar-v1.json` | 尺寸、网格、配色、内容限额、二维码、校样日期、QA 与输出命名的机器可读真源 |
| `config/print-desk-calendar-portrait-v1.json` | 独立竖版真源；保留横版不动，定义 140 × 210 mm 布局、三张纵向信息卡与反相二维码 |
| `config/print-desk-calendar-dark-v1.json` | 暗色横版真源；石墨黑蓝纸面、骨白字、深色矿物卡和反相二维码 |
| `config/print-desk-calendar-portrait-dark-v1.json` | 暗色竖版真源；与暗色横版共享材料语言，保留独立竖版布局 |
| `scripts/print_calendar_preset.py` | 预设定位、验证和哈希的共享实现 |
| `scripts/build_print_desk_calendar.py` | 从 `src/timetable/timetable-data.js` 生成封面、逐日内页和 manifest |
| `scripts/qa_print_desk_calendar.py` | 校验页数、MediaBox、文本、链接、渲染、空白页和逐日二维码，并生成 contact sheet |
| `scripts/test_print_calendar_projection.py` | 锁定电子首日缺席、首个来源日配对、来源日事件归属、末尾未配对日省略规则 |
| `scripts/test_print_calendar_content.py` | 遍历全部可配对 Source Day，锁定四段作品文字、事件同日关系与真实例行补位规则 |
| `requirements/print-calendar.txt` | v1 已验证的 Python 依赖版本 |

## 环境

需要 Python 3.11+、上面的 Python 包、Poppler 的 `pdftoppm`，以及 macOS 自带的 STHeiti Light/Medium 字体。Codex 桌面环境应先调用 workspace dependency loader，并使用它返回的 bundled Python；不要假设系统 `python3` 已安装 PDF 依赖。

独立环境可以这样准备：

```bash
python3 -m venv .venv-print-calendar
.venv-print-calendar/bin/python -m pip install -r requirements/print-calendar.txt
brew install poppler
export PRINT_PYTHON="$PWD/.venv-print-calendar/bin/python"
```

在 Codex 当前机器上，`PRINT_PYTHON` 应替换为 workspace dependency loader 返回的 Python 绝对路径。QR 解码包的 import 名是 `zxingcpp`，安装包名是 `zxing-cpp`。

## 固定构建命令

当前两份 v3 暗色内容完整版可以一次生成：

```bash
for preset in config/print-desk-calendar-source-aligned-dark-*-v3.json; do
  "$PRINT_PYTHON" scripts/build_print_desk_calendar.py --preset "$preset"
done
```

需要回滚或重建 v2 四份来源日配对版时：

```bash
for preset in config/print-desk-calendar-source-aligned-*-v2.json; do
  "$PRINT_PYTHON" scripts/build_print_desk_calendar.py --preset "$preset"
done
```

每份都必须把同一预设显式传给 QA：

```bash
PYTHONPATH=tmp/pdfs/python-deps "$PRINT_PYTHON" scripts/qa_print_desk_calendar.py \
  output/pdf/EDITION.pdf \
  --preset config/PRINT-PRESET.json \
  --render-dir tmp/pdfs/EDITION-rendered \
  --require-qr-decode
```

完整构建前先运行投影与内容回归测试：

```bash
"$PRINT_PYTHON" scripts/test_print_calendar_projection.py
"$PRINT_PYTHON" scripts/test_print_calendar_content.py
```

先检查预设能够被读取：

```bash
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py --show-preset
```

生成代表性校样。日期直接来自预设中的 `proof.dates`，当前覆盖早期实作、缺席日、密集信息页、长标题页和 `latest_public_day`（会自动解析成数据里的最新公开日）：

```bash
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py \
  --proof \
  --output tmp/pdfs/desk-calendar-proof-v1.pdf
```

不指定 `--output` 时，校样默认输出到：

```text
tmp/pdfs/granted-hours-desk-calendar-proof-{from_date}-to-{through_date}-v1.pdf
```

对校样执行完整 QA：

```bash
"$PRINT_PYTHON" scripts/qa_print_desk_calendar.py \
  tmp/pdfs/desk-calendar-proof-v1.pdf \
  --render-dir tmp/pdfs/desk-calendar-proof-rendered
```

QA 默认采用预设的 180 DPI 并要求每一个逐日二维码解码成功。只有在本机缺少 `zxingcpp`、且只是临时检查其他项目时，才显式使用 `--no-require-qr-decode`；正式交付不能跳过二维码验收。

生成从首个公开日到最新公开日的完整版本：

```bash
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py
```

默认输出到：

```text
output/pdf/granted-hours-desk-calendar-{from_date}-to-{through_date}-v1.pdf
```

然后对这个 PDF 运行同一 QA 脚本，并将 `--render-dir` 指向一个新的本地目录。

## 竖版对比版本

竖版不是把横版页面图像旋转 90°，而是重新排版同一份规范数据：标题与自由变量在上、完整 16:9 作品图居中、时间地层紧随其后，最多三张高优先级信息卡纵向排列，右下角保留黑底白码。横版预设和产物不受影响。

生成竖版代表性校样：

```bash
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py \
  --preset config/print-desk-calendar-portrait-v1.json \
  --proof \
  --output tmp/pdfs/granted-hours-desk-calendar-portrait-proof-v1.pdf
```

验收竖版校样：

```bash
"$PRINT_PYTHON" scripts/qa_print_desk_calendar.py \
  tmp/pdfs/granted-hours-desk-calendar-portrait-proof-v1.pdf \
  --preset config/print-desk-calendar-portrait-v1.json \
  --render-dir tmp/pdfs/desk-calendar-portrait-proof-rendered
```

生成完整竖版：

```bash
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py \
  --preset config/print-desk-calendar-portrait-v1.json
```

默认输出为 `output/pdf/granted-hours-desk-calendar-portrait-{from_date}-to-{through_date}-v1.pdf`。竖版 QA 除常规页数、物理尺寸、文字与链接外，还会检查每页二维码 quiet zone 确实为黑色、存在足够白色码块，并逐页解码精确 URL。

## 暗色主题版本

暗色版使用独立预设，作品静帧维持原色；纸面为石墨黑蓝，正文为骨白和冷灰，协作/提醒/例行卡分别使用低饱和深青、焦褐和深绿。它不是对浅色 PDF 做像素反相，因此作品、语义色和可读性仍分别受控。

```bash
# 暗色横版
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py \
  --preset config/print-desk-calendar-dark-v1.json

# 暗色竖版
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py \
  --preset config/print-desk-calendar-portrait-dark-v1.json
```

两份暗色预设均使用白码黑底二维码。QA 除逐页解码外，还会从每个日页的无内容页边抽样，确认页面真实使用暗纸面，而不是只把卡片或封面改暗。

当前 v3 暗色横/竖完整版的显式命令是：

```bash
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py \
  --preset config/print-desk-calendar-source-aligned-dark-landscape-v3.json

"$PRINT_PYTHON" scripts/build_print_desk_calendar.py \
  --preset config/print-desk-calendar-source-aligned-dark-portrait-v3.json
```

对两份成品都必须运行带 `--require-qr-decode` 的全量 QA。v3 报告还必须满足 `artwork_copy_complete_pages == 日页数`、`failures == []`，并记录实际渲染的 `routine_cards_rendered`；人工检查 contact sheet 时同时确认中文标签无缺字方框、作品说明无裁切、稀疏页的信息卡紧随时间地层。

## 常用覆盖参数

命令行参数只覆盖本次构建；没有显式覆盖时，以 JSON 预设为准。

```bash
# 指定连续日期范围
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py \
  --from-date 2026-07-01 --through 2026-07-31

# 指定若干非连续日期
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py \
  --dates 2026-05-07,2026-06-23,2026-08-13

# 指定输出、manifest 或临时二维码域名
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py \
  --output tmp/pdfs/custom-proof.pdf \
  --manifest tmp/pdfs/custom-proof.manifest.json \
  --qr-base-url https://example.invalid/timetable/

# 仅本次取消封面
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py --no-cover

# 使用未来的新预设
"$PRINT_PYTHON" scripts/build_print_desk_calendar.py \
  --preset config/print-desk-calendar-v2.json
```

`--proof` 不能和 `--dates`、`--from-date`、`--through` 混用，避免“代表性校样”含义悄悄改变。

## 参数地图

- `source`：规范日程数据路径和作品静帧查找优先级。
- `date_selection`：完整构建的默认起止策略。
- `page`：毫米级纸张、页边距、装订带与封面开关。
- `layout`：主视觉、时间地层、卡片网格的关键毫米坐标。
- `artwork`：裁切比例、缓存尺寸与 JPEG 质量。
- `content`：时间地层行、最多四张信息卡、协作/提醒限额与例行汇总。
- `qr`：公开域名、纠错、quiet zone、封面/逐日尺寸和 QA 裁切余量。
- `palette`：v1 全部命名色；生成器直接读取。
- `proof`：每次版式改动必须覆盖的代表性日期。
- `qa`：渲染 DPI、二维码强制解码与物理尺寸容差。
- `output`：校样/完整版目录和文件名模板。
- `print_contract`：不应在无版本升级时改变的内容真实性和排版优先级。

## 调版和版本规则

1. 小幅调试先修改当前预设或生成器，在 `tmp/pdfs/` 生成校样；不要先覆盖已交付 PDF。
2. 每次改变尺寸、版式几何、信息优先级、二维码位置或配色，都必须运行校样 QA，并人工查看 `contact-sheet.jpg`。
3. 确认成为新规范后，复制预设为 `print-desk-calendar-v2.json`，更新 `schema`/`edition_id`/输出文件名版本，并保留 v1。不要把 v1 原地改成另一种视觉语义。
4. 完整生成后核对 manifest 中的 `preset_sha256`、`output_sha256`、页数、日期范围、缺席日数量和逐页二维码 URL。
5. 交付前仍需执行一次全量 QA；代表性校样通过不等于全量自动通过。

## 回滚

v1/v2 预设都没有被 v3 覆盖。最快的回滚是显式选择任一 v2 来源日预设，或任一 `print-desk-calendar-*-v1.json` 重建结晶日版。代码与参数的长期回滚单位仍是 Git commit；PDF 构建产物不进 Git。manifest 保存了当次预设 SHA-256、版本化内容契约和 `temporal_projection_mode`，因此可以判断某份 PDF 使用的是 civil-day、v2 Source-Day，还是 v3 内容完整版规则。

如果只想恢复视觉参数而保留后续日程数据，不要回滚 `src/timetable/timetable-data.js`；只恢复 `config/print-desk-calendar-*.json` 和打印脚本后重新构建即可。
