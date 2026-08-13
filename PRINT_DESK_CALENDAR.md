# 《授时》实体台历生成手册

这份文档是《授时非人时间表》210 × 140 mm 实体台历的仓库内唯一复现入口。版式参数不再依赖某次对话或仓库外的技能说明；生成器和 QA 都读取同一份版本化 JSON 预设，并把预设路径与 SHA-256 写入 manifest。

## 当前版本

- 版本：`desk-calendar-v1`
- 预设：`config/print-desk-calendar-v1.json`
- 纸张：210 × 140 mm，横向，一天一页，默认含单独封面
- 日期：默认从首个公开 civil day 到数据里的最新公开日；缺席日保留缺席信标，不补造作品
- 风格：暖白底、黑字、彩色事件层与作品图；顶部保留 10 mm 台历装订带
- 作品图：本地静帧优先，中心裁切为 16:9，缓存为 1200 px 宽、quality 86 的 JPEG
- 信息优先级：日期与标题 → 自主作品/缺席信标 → 24 小时时间地层 → 协作与提醒卡 → 例行汇总 → 当天二维码
- 二维码：纠错等级 Q、4 modules 边框，跳转 `https://granted-hours.hyperint.net/timetable/?date=YYYY-MM-DD`
- PDF、manifest、QA 报告与渲染图属于本地构建产物，默认被 `.gitignore` 排除；脚本、参数、依赖和本文档进入 Git。

## 仓库内的正式组成

| 文件 | 作用 |
| --- | --- |
| `config/print-desk-calendar-v1.json` | 尺寸、网格、配色、内容限额、二维码、校样日期、QA 与输出命名的机器可读真源 |
| `scripts/print_calendar_preset.py` | 预设定位、验证和哈希的共享实现 |
| `scripts/build_print_desk_calendar.py` | 从 `src/timetable/timetable-data.js` 生成封面、逐日内页和 manifest |
| `scripts/qa_print_desk_calendar.py` | 校验页数、MediaBox、文本、链接、渲染、空白页和逐日二维码，并生成 contact sheet |
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

代码与参数的回滚单位是 Git commit；PDF 构建产物不进 Git。回滚某次调版时，优先恢复对应预设和脚本版本，再重新生成 PDF。manifest 保存了当次预设 SHA-256，因此可以判断某份 PDF 是否真的由当前规则生成。

如果只想恢复视觉参数而保留后续日程数据，不要回滚 `src/timetable/timetable-data.js`；只恢复 `config/print-desk-calendar-*.json` 和打印脚本后重新构建即可。
