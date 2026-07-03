---
name: AI-report-generator
description: >
  汇总 stage/ 与 analysis/ 下的所有产物，渲染成自包含的 HTML 分析报告。
  按 IMRAD（Abstract / Introduction / Methods / Results / Discussion /
  Conclusion）结构以完整段落写成科研论文风格正文，每张 Figure / Table 前后
  各配一段描述性文字，并自动加入 in-text 交叉引用（"Fig. 2A", "Table 1"）。
  内置多套针对宏基因组与生物医学场景的模板（taxonomy/QC/assembly/分类/回归/
  聚类/Cox/EDA/富集/通用），并依据 manifest pipeline、analysis 子目录与
  用户 prompt 自动选择最合适的一个。排版遵循 CNS（Cell/Nature/Science）
  规范：Arial 字体、NPG (Nature Publishing Group) 色板、Data-Ink 优化的
  图表（无网格线、加粗黑色坐标轴）、Booktabs 风格数据表，并自动附带 Table 1
  基线特征表与可下载的 R / Python 矢量图源代码（ggplot2 / ComplexHeatmap /
  seaborn）。所有图表内嵌（plotly.js 离线 + 图片 base64），最终写到
  /job/analysis/report/report.html。
  仅在 openclaw/downstream:1.1.0 或 openclaw/downstream-dl:1.0.0 容器内运行。
allowed-tools: Bash(python *) Read Write
disable-model-invocation: true
---

# Report Generator Skill

你在 `openclaw/downstream:1.1.0` 或 `openclaw/downstream-dl:1.0.0` 容器内运行。容器挂载：

| 路径 | 权限 | 内容 |
|---|---|---|
| `/job/stage/` | ro | 上游工具产物 |
| `/job/analysis/` | rw | 各下游 skill 的分析结果（读+写） |
| `/job/reproducibility/` | rw | 生成脚本、日志、元数据 |
| `/pipeline/scripts/` | ro | 参考脚本（含 `reference_AI-report-generator.py`、`select_template.py`） |
| `/pipeline/scripts/../assets/` | ro | 模板与样式（templates/、partials/、theme.css、template_index.yaml） |

无网络访问（`--network none`）。HTML 报告必须自包含——所有图表内嵌，无 CDN 依赖。

---

## CNS 排版与配色（Nature/Cell/Science 标准）

为了让报告达到投稿原稿的视觉品质，整套样式按医学顶刊审稿人偏好的「极简、可信、可复现」进行了硬编码：

| 维度 | 实现 |
|---|---|
| 字体 | 全局 `Arial / Helvetica / sans-serif`，无衬线、无装饰字体；标题、正文、坐标轴、图注一致。 |
| 配色 | 强制使用 **NPG (Nature Publishing Group) 色板**：经典蓝 `#4DBBD5`、红 `#E64B35`、绿 `#00A087`、深蓝 `#3C5488`、鲑色 `#F39B7F` 等共 10 色（与 R 包 `ggsci::pal_npg` 完全一致）。Plotly 全局 template `npg_cns` 自动注入，无需逐图设置。 |
| 阴影 | 所有 KPI 卡片、表格、Figure 卡片**移除阴影**，改用 1 px 黑/灰边框；网页效果与打印一致。 |
| 图表 Spines | Plotly 默认输出**取消 gridlines / zerolines**，保留并加粗 X/Y 轴黑色 spines（`linewidth=1.5`），刻度向外（`ticks="outside"`）—— Data-Ink 比最大化。 |
| 表格 | Booktabs 风格：仅顶部 / 底部粗横线 + 表头下细横线；无垂直线、无斑马纹；caption 居上、左对齐，自动加 `Table N.` 编号。 |
| 数字排版 | 表格与 KPI 使用 `tabular-nums`，对齐数字位；统计量用专属 class（`.stat-p`、`.stat-ci`、`.stat-mean`）保持斜体 *p / n* 与等宽小数。 |
| 显著性 | `.sig-1 / .sig-2 / .sig-3` 自动渲染 `*` / `**` / `***`，并附带 sig-legend。 |

> 想改回旧风格？保留旧版样式表为 `theme.css.legacy` 后再覆盖即可——本目录下的 `theme.css` 总是 CNS 版。

### 报告新增的标准章节

每个模板均可使用以下复用组件（定义在 `assets/partials/components.html.j2`）：

| 组件 | 何时用 | 渲染效果 |
|---|---|---|
| `ui.graphical_abstract(src, caption)` | 报告首部 | 横向 hero 图，模拟期刊 TOC 的 graphical abstract。 |
| `ui.figure(title, body_html, caption, fig_num=2)` | 任意章节 | 自动加 `Figure N.` 标号，caption 上方有分隔细线。 |
| `ui.table(rows, cols, tab_num=2, caption=...)` | 通用表格 | Booktabs 风格 + `Table N.` 标号，超出 20 行自动折叠。 |
| `ui.baseline_table(data, tab_num=1, caption='Baseline characteristics')` | **Table 1** | 模拟基线特征表：每组 *n*，连续变量 mean ± SD，分类变量 *n* (%)，附 *P* 值列与统计学注脚。 |
| `ui.pvalue(p)` / `ui.mean_sd(m,sd)` / `ui.median_iqr(...)` / `ui.ci(lo,hi)` / `ui.nfrac(k,n)` | 文中行内统计 | 标准 CNS 风格行内统计描述。 |
| `ui.code_appendix(blocks)` | 报告末尾 | 折叠式代码附录（见下）。 |

### 终极发文保障：R / Python 矢量图源代码附录

> 网页前端的 Plotly / PNG 仅用于交互展示；学术界真正需要的是本地运行 R/Python 产出的**矢量 PDF**。

`reference_AI-report-generator.py` 提供：

- `default_code_appendix()`：返回一组**即开即用**的源代码片段，覆盖最常见的发文场景：
  - **ggplot2 + ggsci**：年龄分布**剥离图（Strip chart）**、构成比图（Stacked bar）、Volcano。
  - **ComplexHeatmap**：top features 的 Z-score 热图，含 NPG 分组注释条。
  - **seaborn / matplotlib**：突变发生频率图、临床变量的 Box + Strip 图。
- 所有片段：
  - 已强制 `Arial` 字体、NPG 色板、移除 grid、保留黑色 axis。
  - 输出尺寸（如 3.2 × 2.8 in、5.2 × 3.2 in）和 600 DPI 已校准为 Figure panel 直接可用。
  - 顶部声明 `read_excel("data.xlsx", sheet=...)`：用户只需把您给我的 Excel 与代码在本地一起运行即可。
- `ui.code_appendix(blocks)` 在报告末尾以 `<details>` 折叠块呈现，每段附 `R` / `PYTHON` 标签、依赖列表、用途描述。打印时所有块自动展开，便于审稿打印件留底。

定制副本时可继续追加（例如 KM 生存曲线、ROC、SHAP）：

```python
from reference_report_generator import default_code_appendix
ctx["code_blocks"] = default_code_appendix() + [
    {"title": "Kaplan-Meier survival curve", "lang": "r",
     "filename": "Fig_km.R", "depends": ["survminer", "survival"],
     "code": Path("snippets/km.R").read_text(), "description": "..."},
]
```

### IMRAD prose writing（核心新增 — 每份报告必备）

> 借鉴自 `reference_skills/scientific-writing/` —— 完整科研论文的写作规范在
> `references/imrad_structure.md` / `references/writing_principles.md` /
> `references/figures_tables.md`。本 skill 把这些规范固化到模板里，定制副本
> 只需填充段落文字，结构与排版自动落地。

每份报告**必须**按 IMRAD 顺序组织，并且**所有正文段落只用完整句子写成，不
要用项目符号 / bullet list**。`base.html.j2` 已经为下列五段预留了独立 block，
按出现顺序自动编号：

| Block / Context key                    | 应写内容                                                  |
|----------------------------------------|----------------------------------------------------------|
| `abstract` (dict)                      | 结构化摘要：`background / objective / methods / results / conclusion / keywords` |
| `introduction` (list of str)           | 2–3 段：领域背景 → 具体 gap → 本次分析要回答什么          |
| `methods_narrative` (list of str)      | 3 段：数据来源 + 报告指南 / 计算流程 / 统计方法           |
| `results_intro` (str) + `results_figures` / `results_tables` | 引子段 + 每张图表的 before/after 段落 |
| `discussion` (list of str)             | 3 段：主要发现 / 优劣势 / 生物学解释                      |
| `conclusion` (str or list of str)      | 1 段：数据支持什么、不支持什么、下一步具体实验            |

**Figure / Table 描述规范** —— 每张 Figure 和 Table 在 `results_figures` /
`results_tables` 列表中都必须配 `before` + `after` 两段描述（任一可省略，但
强烈建议都写）：

```python
ctx["results_figures"] = [
    {
        "fig_num": 1,
        "title":   "α diversity across groups",
        "body":    fig_to_html(my_plotly_fig),
        "caption": ("Shannon diversity index by group, n = 24 per group. "
                    "Box plots show median (line), Q1–Q3 (box), 1.5×IQR "
                    "(whiskers); individual samples as dots."),
        "before":  ("Microbial α diversity was first compared across the "
                    "three treatment arms to test whether community richness "
                    "differed at baseline ({{ ui.fig_ref(1) }})."),
        "after":   ("Shannon diversity was significantly lower in the "
                    "antibiotic-treated arm (median 2.3, IQR 1.8–2.7) "
                    "than in controls (median 3.4, IQR 3.0–3.8; "
                    "Wilcoxon W = 412, p = 0.003, rank-biserial r = 0.45). "
                    "The placebo arm did not differ from controls "
                    "(p = 0.41)."),
    },
]
```

**Cross-references in prose** — use the `ui.fig_ref(n, suffix)` and
`ui.tab_ref(n)` Jinja macros so every figure / table mention becomes a
clickable anchor in the rendered HTML:

```jinja
{% raw %}
<p>The taxonomic shift is most pronounced at the genus level
({{ ui.fig_ref(2, 'A') }}), with 18 of 24 differentially abundant
taxa concentrated in the Bacteroidetes phylum
({{ ui.tab_ref(2) }}).</p>
{% endraw %}
```

**Writing rules enforced by review (not by the template)** — copy these into
the customized script as a comment so the LLM customizer follows them:

1. **Full paragraphs, never bullets** in Abstract / Introduction / Methods
   / Results / Discussion / Conclusion. Bulleted KPI cards are fine; body
   prose is not.
2. **Define every specialised term at first use** (e.g. "amplicon sequence
   variant (ASV)", "β diversity (between-sample compositional distance)").
3. **Cite every figure and table** in the corresponding section using
   `ui.fig_ref` / `ui.tab_ref` — orphan figures are not allowed.
4. **Report effect sizes + 95 % CI alongside every p-value.** Significant
   without magnitude is not informative.
5. **Pick a reporting guideline** appropriate to the study design (CONSORT
   for trials, STROBE for observational, PRISMA for reviews, STARD for
   diagnostic accuracy) and reference it in the Methods narrative.

The Markdown / HTML rendered for stub IMRAD content explicitly marks each
PLACEHOLDER paragraph so unreviewed reports never look final by accident.

---

### 自动 Table 1（基线特征）

```python
from reference_report_generator import baseline_table_from_df
ctx["baseline"] = baseline_table_from_df(
    df,
    group_col="Arm",                       # 分组变量
    variables=[
        {"name": "demographics", "kind": "subhead", "label": "Demographics"},
        {"name": "age",  "kind": "cont", "label": "Age, years", "dp": 1},
        {"name": "bmi",  "kind": "cont", "label": "BMI, kg/m²", "dp": 1},
        {"name": "comorbidities", "kind": "subhead", "label": "Comorbidities"},
        {"name": "diabetes", "kind": "cat", "label": "Diabetes"},
        {"name": "hypertension", "kind": "cat", "label": "Hypertension"},
    ],
)
```

模板里调用 `{{ ui.baseline_table(baseline, tab_num=1) }}` 即可输出 Nature 风格 Table 1（每组列头自带 *n*=...，连续 vs. 分类自动选择 *t*-test / Wilcoxon vs. χ² / Fisher）。

---

## 模板系统

模板登记在 `assets/template_index.yaml`，渲染脚本加载它即可获得：

| 模板 | 用途 | 触发信号 |
|---|---|---|
| `metagenomics_full` | 宏基因组完整分析 | pipeline=metagenomics / `analysis/taxonomy`、`differential` |
| `metagenomics_qc` | 仅 QC 概览 | `analysis/qc` |
| `metagenomics_assembly` | 装配 + 注释 | `analysis/assembly`、`gene_prediction` |
| `enrichment` | 通路 / 富集 | `analysis/enrichment`、prompt 含 GSEA/KEGG |
| `classification` | 二/多分类模型 | `analysis/classification` |
| `regression` | 回归模型 | `analysis/regression` |
| `clustering` | 无监督聚类 | `analysis/clustering` |
| `survival` | Cox / 生存 | `analysis/survival` |
| `eda` | 探索性数据分析 | pipeline=eda |
| `generic` | 兜底 | 总能命中 |

选择级联（见 `scripts/select_template.py`）：

```
explicit --template  >  pipeline 名匹配  >  required_dirs 全命中
                     >  any_dirs 任一命中  >  prompt 关键词  >  priority  >  generic
```

CLI 用法：

```bash
python /pipeline/scripts/select_template.py \
       --job-dir /job --user-prompt "我想要差异物种和富集" --json
```

---

## 输入

### 必读
- `/job/stage/manifest.json` — pipeline 名 + 样本列表

### 按需扫描
- `/job/analysis/<skill>/` 任意子目录 — 触发模板选择
- `/job/analysis/<skill>/*_meta.json` — 自动汇入"方法 / 可复现性"
- `/job/analysis/figures/*.html` — Plotly 交互图（`<div>` 内嵌）
- `/job/analysis/**/*.png` — 静态图，base64 内嵌

---

## 工作流（两阶段）

### Step 1 — 进入容器

```bash
bash gateway/attach.sh --shell
# 或 docker exec -it $(cat /data/output/<job-id>/.container_name) bash
```

### Step 2 — 选模板，准备脚本

```bash
python /pipeline/scripts/select_template.py --job-dir /job \
       --user-prompt "$USER_PROMPT" --json | tee /tmp/tpl.json

TS=$(date +%Y%m%d-%H%M%S)
SCRIPT=/job/reproducibility/generated_scripts/AI-report-generator_${TS}.py
cp /pipeline/scripts/reference_AI-report-generator.py "$SCRIPT"
```

### Step 3 — 定制副本

`reference_AI-report-generator.py` 的默认 context 是中性的（pipeline、样本数、各 skill 的 status/notes）。
在副本里要做的事：

1. 用 pandas 读真实表（`/job/stage/`、`/job/analysis/<skill>/*.csv`），算出 KPI、top-N 表格。
2. **图表**：
   - Plotly：用 `apply_npg_style(fig)` 或 `new_figure(...)` 包装，`fig_to_html(fig)` 输出片段，再塞进对应模板键（`taxonomy.stack`、`differential.volcano`…）。
   - PNG → `_embed_image(...)`，避免外链。
3. **Table 1**：`ctx["baseline"] = baseline_table_from_df(df, "group", [...])`，模板里 `{{ ui.baseline_table(baseline, tab_num=1) }}`。
4. **代码附录**：默认已注入 `ctx["code_blocks"] = default_code_appendix()`；按需追加 KM/ROC/Forest 代码块。
5. 调用 `template.render(**ctx)` 前再覆写 `methods_table` / `refs`。

### Step 4 — 执行

```bash
bash gateway/run_downstream.sh <job-id> --skills AI-report-generator
# 输出： /job/analysis/report/report.html
#        /job/analysis/report/AI-report-generator_meta.json
```

### Step 5 — 报告章节（按模板而异）

所有模板共享：标题区 + 右侧 TOC + （可选）Graphical abstract + KPI 卡片网格 + 图卡 + 数据表 +
方法表 + 引用块 + **代码附录** + 打印样式。
缺少数据的章节自动隐藏（`{% if %}` 守卫），不会留下空标题。

---

## 严格规则

1. HTML 必须自包含：plotly.js 离线打包，PNG 必须 base64，禁外部 URL。
2. **CNS 排版规则不可破坏**：
   - 字体只用 Arial 栈；不要在副本里 `update_layout(font_family="...")` 切到衬线或装饰字体。
   - 颜色必须取自 `NPG_PALETTE` / `NPG_SEQUENTIAL`；新增系列从该列表里选，禁止使用 Excel 默认 / Plotly 默认。
   - 不要重新打开 gridlines（`showgrid=True` 会被 base.html.j2 注入的脚本覆盖回 False）。
3. 缺失数据用 "—" 或自动隐藏章节；不要伪造数字。
4. `assets/templates/` 与 `theme.css` 是模板区，**只读**；新增模板请改 `template_index.yaml`，新增样式 token 改 `theme.css` 的 `:root`，**不要**在 Jinja 里 inline-style。
5. 输出固定到 `/job/analysis/report/report.html`，元数据到同目录的 `AI-report-generator_meta.json`。
6. 生成脚本归档到 `/job/reproducibility/generated_scripts/`，否则视为未执行。

---

## 执行模型（两阶段）

此 skill 由 Gateway 的 `gateway/run_downstream.sh` 在 `openclaw/downstream:1.1.0` 或 `openclaw/downstream-dl:1.0.0` 容器内调用，**不由 LLM 自主触发**（`disable-model-invocation: true`）。Planner Agent 在 host 层选 skill 子集并触发。

两条路径严格区分：

| 路径 | 权限 | 作用 |
|---|---|---|
| `/pipeline/scripts/reference_<skill>.py` | ro | 仓库发布的模板，由 `prepare_downstream.sh` 挂载；不可修改 |
| `/job/reproducibility/generated_scripts/<skill>_<YYYYMMDD-HHMMSS>.py` | rw | 针对本 job 数据定制的副本；`run_downstream.sh` 执行最新那一个 |

**禁止**：直接运行 `/pipeline/scripts/reference_*.py`；把生成脚本写到 host 的 `skills/<skill>/scripts/`。
