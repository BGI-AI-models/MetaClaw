---
name: exploratory-data-analysis
description: |
  对已暂存的科学数据集和数据文件进行探索性数据分析（EDA）。用户想检查文件结构、
  汇总内容、评估数据质量、识别异常、理解分布或在下游分析前获取格式感知建议时触发。
  读取 /job/stage/eda/ 下的输入文件，将可复现的报告、生成代码和运行元数据写到
  /job/analysis/exploratory-data-analysis/ 和 /job/reproducibility/generated_scripts/。
  仅在 openclaw/downstream:1.1.0 容器内运行。
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
compatibility: |
  Requires Python 3.9+, pandas, numpy, scipy, pyyaml, and format-specific libraries as needed
---

# Exploratory Data Analysis Skill

你在 `openclaw/downstream:1.1.0` 容器内运行。容器挂载：

| 路径 | 权限 | 内容 |
|---|---|---|
| `/job/stage/` | ro | 上游产物（分析文件从这里读） |
| `/job/analysis/` | rw | EDA 结果写到这里 |
| `/job/reproducibility/` | rw | 生成脚本、日志、元数据 |
| `/pipeline/scripts/` | ro | 参考脚本（含 eda_analyzer.py） |

无网络访问（`--network none`）。只使用容器内已安装的库和本地参考文档。

---

## 职责

此 skill 对已暂存的科学数据文件和表格数据集执行探索性数据分析。从 `/job/stage/eda/` 读取一个主要输入文件，可使用 `/job/stage/metadata.tsv`（若存在），并利用此 skill 目录下的本地资产执行格式感知分析并生成结构化报告。

**不捏造文件类型、元数据、缺失输入、质量发现或下游建议。必要文件缺失或矛盾时不静默继续，不声称支持无法映射到真实参考条目的文件类型。**

---

## 伴随文档

- `assets/supplementary_info.md` — 支持的格式、参考条目和构建假设；调用前先读。
- `assets/report_template.md` — 报告结构指南。
- `assets/references/` — 各科学数据类别的格式参考文件。
- `assets/environment.yaml` — 预期 conda 环境。
- `scripts/eda_analyzer.py` — 脚本化分析辅助工具（若存在）。

若伴随文档与此 `SKILL.md` 冲突，以 `SKILL.md` 为准并报告不一致。

---

## 输入规范

```
/job/stage/
  eda/
    <input-file>       # 必需；一个主要科学数据文件或表格
    options.yaml       # 可选分析提示（sheet 名、分隔符、采样限制等）
  metadata.tsv         # 可选，存在则读取
```

本地参考资产（格式感知分析依据）：
- `assets/references/bioinformatics_genomics_formats.md`
- `assets/references/chemistry_molecular_formats.md`
- `assets/references/microscopy_imaging_formats.md`
- `assets/references/spectroscopy_analytical_formats.md`
- `assets/references/proteomics_metabolomics_formats.md`
- `assets/references/general_scientific_formats.md`

**必要检查（缺失则停止并报告）：**
- `/job/stage/eda/` 下恰好有一个主要文件（除非用户明确请求协调多文件分析）
- `options.yaml`（若存在）的设置须与实际文件类型和可用输入匹配
- 若文件类型无法映射到已知参考条目，须明确报告该限制

随机种子：从 `options.yaml` 的 `random_seed` 字段获取；未指定则使用 `42` 并在元数据中记录。

---

## 输出规范

```
/job/analysis/exploratory-data-analysis/
  reports/
    <input-basename>_eda_report.md
  summaries/
    file_inventory.json
    quality_summary.csv
  figures/
    preview_plot.png
  exploratory-data-analysis_meta.json

/job/reproducibility/generated_scripts/
  eda_pipeline_<timestamp>.py
```

`exploratory-data-analysis_meta.json` 必须记录：包版本、输入路径、输出路径、参数、随机种子、检测到的文件类型、查阅的参考文件、是否使用了 `scripts/eda_analyzer.py`、是否为探索性分析，以及关键决策说明（采样、解析器选择、报告范围）。

---

## 工作流

### Step 1 — 读取数据

从 `/job/stage/eda/` 读取主要输入文件，确定其扩展名、存储模式和表观格式。使用 `assets/references/` 下对应的本地参考文件查找该扩展名的格式特定指导。

若 `metadata.tsv` 存在，读取并报告是否并入分析。若 `options.yaml` 存在，验证声明的分隔符、工作表、解析器或采样设置。

报告所有摄取时发现的异常：缺失文件、解析失败、格式错误行、不可读二进制负载、重复标识符、空数据集、不可能的维度、不一致的 metadata、不支持的格式。

### Step 2 — 分析

四个子阶段：文件类型检测 → 格式感知检查 → 定量或结构摘要 → 报告。

**表格文件**：维度、列类型、缺失率、重复值、汇总统计、异常值检查、简单分布摘要。

**序列、图像、数组、光谱、组学或其他科学格式**：使用相关参考指南选择适当的结构、元数据和质量检查。

若 `scripts/eda_analyzer.py` 适合检测到的格式，可以使用，但必须验证其行为与当前暂存输入和规范规则匹配。

任何随机组件（大数据集采样、预览的随机化投影）使用固定随机种子。

统计测试或推断性摘要须报告效应量和置信区间，不仅仅是 p 值。

若样本量低于探索性阈值（< 30 或用户指定），在报告和元数据中标注为**探索性分析**。

报告结构遵循 `assets/report_template.md`（适用时）。

### Step 3 — 归档

每次运行必须：
1. 将生成脚本保存到 `/job/reproducibility/generated_scripts/eda_pipeline_<timestamp>.py`
2. 将 `exploratory-data-analysis_meta.json` 写到 `/job/analysis/exploratory-data-analysis/`

若因文件缺失、不支持的格式、模式冲突或规范违反而停止，元数据文件仍须尽可能写入并记录终止原因。

---

## 严格规则

1. 数据异常（缺失文件、解析错误、格式错误行、缺失值、重复标识符、不支持的扩展名、不一致 metadata）不可静默跳过——必须显式报告。
2. 统计测试或推断性摘要必须报告效应量和置信区间，不仅仅是 p 值。
3. 样本量低于探索性阈值时，分析必须在报告和 `exploratory-data-analysis_meta.json` 中标注为探索性。
4. 所有随机过程（数据集采样、随机化预览、有种子算法）必须使用固定随机种子。

---

## 调用示例

- "分析 /job/stage/eda/ 中的暂存文件，汇总其结构和质量。"
- "对暂存数据集运行 EDA，使用本地参考，将报告写到 /job/analysis/exploratory-data-analysis/。"
- "检查暂存的显微镜或组学文件，告诉我适合哪种下游分析。"
- "使用暂存输入生成格式感知的探索性报告，明确报告所有异常。"


---

## 执行模型（两阶段）

此 skill 由 Gateway 的 `gateway/run_downstream.sh` 在 `openclaw/downstream:1.1.0` 容器内调用,**不由 LLM 自主触发**(`disable-model-invocation: true`)。Planner Agent 在 host 层选 skill 子集并触发。

两条路径严格区分,混用会失败:

| 路径 | 权限 | 作用 |
|---|---|---|
| `/pipeline/scripts/reference_<skill>.py` | ro | 仓库发布的模板,由 `prepare_downstream.sh` 挂载;**不可修改** |
| `/job/reproducibility/generated_scripts/<skill>_<YYYYMMDD-HHMMSS>.py` | rw | 针对本 job 数据定制的副本;`run_downstream.sh` 执行最新那一个 |

标准流程:

1. `bash gateway/attach.sh --shell`(或 `docker exec -it $(cat /data/output/<job-id>/.container_name) bash`)进入已在运行的容器。
2. 先用 pandas 检查 `/job/stage/` 下的实际数据 schema 和样本量。
3. `cp /pipeline/scripts/reference_<skill>.py /job/reproducibility/generated_scripts/<skill>_<ts>.py`。
4. 编辑副本:列名、协变量、random_seed、样本量阈值等按本数据集调整。
5. `bash gateway/run_downstream.sh <job-id> --skills <skill>` 执行,日志和 `downstream_manifest.json` 自动归档。

**禁止**: 直接运行 `/pipeline/scripts/reference_*.py`(会跳过定制与元数据归档);把生成脚本写到 host 的 `skills/<skill>/scripts/`(那是模板区,非本 job 的产物)。
