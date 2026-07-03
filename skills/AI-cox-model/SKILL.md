---
name: cox-survival-analysis
description: |
  从已暂存的表格生存数据集构建、优化并验证 Cox 比例风险生存分析工作流。用户请求
  生存分析、时间到事件分析、Kaplan-Meier 曲线、风险分层或 LASSO-Cox 模型时触发。
  读取 /job/stage/coxsurvival/ 下的数据集，将结果、生成代码和运行元数据写到
  /job/analysis/cox-survival-analysis/ 和 /job/reproducibility/generated_scripts/。
  仅在 openclaw/downstream:1.1.0 容器内运行。
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
compatibility: |
  Requires Python 3.9+, pandas, numpy, lifelines, scikit-learn, matplotlib, seaborn, reportlab, pyyaml
---

# Cox Survival Analysis Skill

你在 `openclaw/downstream:1.1.0` 容器内运行。容器挂载：

| 路径 | 权限 | 内容 |
|---|---|---|
| `/job/stage/` | ro | 上游产物（生存数据从这里读） |
| `/job/analysis/` | rw | 分析结果写到这里 |
| `/job/reproducibility/` | rw | 生成脚本、日志、元数据 |
| `/pipeline/scripts/` | ro | 参考脚本 |

无网络访问（`--network none`）。

---

## 职责

此 skill 对已暂存的生存数据集执行端到端 Cox 比例风险生存分析。从 `/job/stage/coxsurvival/` 读取主要生存数据集，可使用 `/job/stage/metadata.tsv`（若存在），并在存在暂存配置时使用配置输入。将数据验证、预处理、模型拟合、诊断、风险分层和报告整合为一个可复现的工作流。

**不捏造生存时间、事件指示符、缺失文件或统计结果。不处理分类、普通回归或竞争风险分析（除非明确支持）。**

---

## 伴随文档

- `assets/supplementary_info.md` — 工作流概述、具体示例和构建假设；调用前先读。
- `assets/quick_start.md` — 工作流和命令的补充参考。

若伴随文档与此 `SKILL.md` 冲突，以 `SKILL.md` 为准并报告不一致。

---

## 输入规范

```
/job/stage/
  coxsurvival/
    data.csv           # 或 data.tsv / data.parquet；必需
    config.yaml        # 可选分析配置（列名、特征选择、输出设置）
    predict.csv        # 可选，用于评分或风险预测
  metadata.tsv         # 可选，存在则读取
```

**必要检查（缺失则停止并报告）：**
- `/job/stage/coxsurvival/` 下恰好有一个主要生存数据集
- 数据集包含时间到事件和事件指示符信息（直接包含或通过 config.yaml 验证）
- `config.yaml`（若存在）声明的列名和特征选择与暂存数据集匹配
- `predict.*`（若存在）特征列可与训练预处理管道对齐

随机种子：从 `config.yaml` 的 `random_seed` 字段获取；未指定则使用 `42` 并在元数据中记录。

---

## 输出规范

```
/job/analysis/cox-survival-analysis/
  tables/
    lasso_selected_variables.tsv
    lasso_cv_results.tsv
    risk_group_summary.tsv
    ph_test_results.tsv
    univariate_cox_results.tsv
  figures/
    km_risk_stratified.png
    forest_plot.png
  report/
    survival_analysis_report.pdf
    pipeline_config_summary.json
  cox-survival-analysis_meta.json

/job/reproducibility/generated_scripts/
  cox_pipeline_<timestamp>.py
```

`cox-survival-analysis_meta.json` 必须记录：包版本、输入路径、输出路径、参数、随机种子、模型设置、风险分层选择、是否为探索性分析，以及关键预处理和模型选择决策说明。

---

## 工作流

### Step 1 — 读取数据

从 `/job/stage/coxsurvival/` 读取生存数据集。若 `metadata.tsv` 存在，读取并报告是否并入分析。若 `config.yaml` 存在，在预处理前验证列声明、特征选择和输出设置。

报告所有数据异常：缺失列、无效事件值、重复行、不可能的生存时间、过度缺失、模式不匹配。

### Step 2 — 分析

四个子阶段：预处理 → 模型拟合 → 诊断 → 报告。

**预处理**：列选择、缺失值处理、分类变量 one-hot 编码、数值缩放。

**模型**：默认 Cox 比例风险模型配合 LASSO 或 Elastic-Net 正则化，使用交叉验证选择惩罚因子。

所有随机步骤（洗牌划分、Bootstrap 区间、有种子模型组件）使用固定随机种子。

**诊断**：比例风险检验（若启用）、C 指数、风险组分离、Kaplan-Meier 曲线、森林图（数据支持时）。

推断性比较须报告效应量和置信区间，不仅仅是 p 值。

若样本量低于探索性阈值（< 50 事件或用户指定），在报告和元数据中标注为**探索性分析**。

若 `predict.*` 存在，应用已保存预处理管道和模型输出风险分数或风险组分配。

### Step 3 — 归档

每次运行必须：
1. 将生成脚本保存到 `/job/reproducibility/generated_scripts/cox_pipeline_<timestamp>.py`
2. 将 `cox-survival-analysis_meta.json` 写到 `/job/analysis/cox-survival-analysis/`

若因文件缺失、模式冲突或规范违反而停止，元数据文件仍须尽可能写入并记录终止原因。

---

## 严格规则

1. 数据异常（缺失列、无效事件值、不可能生存时间、重复行、模式漂移）不可静默跳过——必须显式报告。
2. 任何推断性比较必须报告效应量和置信区间，不仅仅是 p 值。
3. 样本量低于探索性阈值时，分析必须在报告和 `cox-survival-analysis_meta.json` 中标注为探索性。
4. 所有随机过程（Bootstrap 区间、洗牌划分、有种子估计器）必须使用固定随机种子。

---

## 调用示例

- "对 /job/stage/coxsurvival/ 中的暂存数据集运行 Cox 生存分析。"
- "拟合 LASSO-Cox 模型，生成诊断图，将报告保存到 /job/analysis/cox-survival-analysis/。"
- "使用暂存生存文件，按风险组生成 Kaplan-Meier 曲线。"
- "将生存模型应用到 /job/stage/coxsurvival/predict.csv 并保存风险评分。"


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
