---
name: classification-pipeline
description: |
  从已暂存的表格数据集构建、调优、评估并可选地应用分类模型。用户请求分类、
  疾病预测、二分类或多分类建模时触发。读取 /job/stage/classification/ 下的
  训练数据，将所有结果、生成代码和运行元数据写到 /job/analysis/classification-pipeline/
  和 /job/reproducibility/generated_scripts/。仅在 openclaw/downstream:1.1.0 容器内运行。
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
compatibility: |
  Requires Python 3.9+, pandas, scikit-learn, scipy, matplotlib, seaborn, joblib, pyyaml
---

# Classification Pipeline Skill

你在 `openclaw/downstream:1.1.0` 容器内运行。容器挂载：

| 路径 | 权限 | 内容 |
|---|---|---|
| `/job/stage/` | ro | 上游产物（训练数据从这里读） |
| `/job/analysis/` | rw | 分析结果写到这里 |
| `/job/reproducibility/` | rw | 生成脚本、日志、元数据 |
| `/pipeline/scripts/` | ro | 参考脚本 |

无网络访问（`--network none`）。

---

## 职责

此 skill 对已暂存的表格数据集构建并评估有监督分类模型。从 `/job/stage/classification/` 读取单个训练数据集，可选读取预测数据集，使用 `/job/stage/metadata.tsv`（若存在）做样本级过滤或报告。将预处理、模型训练、调优、评估和可选预测整合为一个可复现的工作流。

**不捏造标签、不推断缺失文件、不在必要输入缺失或矛盾时静默继续。**

---

## 伴随文档

- `assets/supplementary_info.md` — 使用细节与构建假设；调用前先读。

若伴随文档与此 `SKILL.md` 冲突，以 `SKILL.md` 为准并报告不一致。

---

## 输入规范

```
/job/stage/
  classification/
    train.csv          # 或 train.tsv / train.parquet；必需
    predict.csv        # 或 predict.tsv / predict.parquet；可选
    columns.yaml       # 目标列/特征列/分类列提示；可选
  metadata.tsv         # 可选，存在则读取
```

**必要检查（缺失则停止并报告）：**
- `/job/stage/classification/` 下恰好有一个训练数据集
- 训练集包含目标列
- `columns.yaml`（若存在）声明的列名与数据集匹配
- `predict.*`（若存在）特征列可与训练预处理管道对齐

---

## 输出规范

```
/job/analysis/classification-pipeline/
  preprocessing/
    train_processed.csv
    test_processed.csv
    preprocessing_summary.md
  models/
    best_model.joblib
    training_summary.csv
    best_model_params.json
  evaluation/
    metrics_comparison.csv
    confusion_matrix_<model>.png
    roc_curves.png
    feature_importance.csv
    evaluation_summary.md
  predictions/
    predictions.csv
    prediction_summary.md
  classification-pipeline_meta.json

/job/reproducibility/generated_scripts/
  classification_pipeline_<timestamp>.py
```

`classification-pipeline_meta.json` 必须记录：包版本、输入路径、输出路径、参数、随机种子、模型列表、划分策略、评分指标、是否为探索性分析，以及关键预处理和模型选择决策说明。

---

## 工作流

### Step 1 — 读取数据

从 `/job/stage/classification/` 读取训练数据集（CSV/TSV/Parquet）。若 `metadata.tsv` 存在，读取并报告是否并入分析。若 `columns.yaml` 存在，在预处理前验证目标列和特征列声明。

报告所有数据异常：缺失目标值、重复行、不可能的类别标签、全空列、严重类别不均衡、train/predict 模式不匹配。

随机种子：从用户明确提供的 override 或 `columns.yaml` 中的 `random_seed` 字段获取；若未指定，使用固定值 `42` 并在元数据中记录。

### Step 2 — 分析

四个子阶段：预处理 → 训练/调优 → 评估 → 可选预测。

**预处理**：列选择、训练/测试划分或交叉验证设置、缺失值处理、one-hot 编码、数值缩放。

**模型**：默认使用 scikit-learn 支持的分类器（逻辑回归、随机森林、支持向量机、梯度提升）。超参数调优用交叉验证，调优指标与最终评估指标要明确区分。

**评估**：混淆矩阵、ROC 曲线（二分类）、每模型指标（accuracy、precision、recall、f1、roc_auc）、特征重要性（树模型）或系数摘要（线性模型）。

若样本量 < 30（或用户指定的探索性阈值），在报告和元数据中明确标注为**探索性分析**。

若 `predict.*` 存在，应用已保存预处理管道和最佳模型，输出类别预测和概率。

模型间推断性比较须报告效应量和置信区间，不仅仅报告 p 值。

### Step 3 — 归档

每次运行必须：
1. 将生成的分析脚本保存到 `/job/reproducibility/generated_scripts/classification_pipeline_<timestamp>.py`
2. 将 `classification-pipeline_meta.json` 写到 `/job/analysis/classification-pipeline/`

若因文件缺失、模式冲突或规范违反而停止，元数据文件仍须尽可能写入并记录终止原因。

---

## 严格规则

1. 数据异常（NaN、缺失目标值、重复样本、类别不均衡、模式漂移）不可静默跳过——必须显式报告。
2. 模型间推断性比较必须报告效应量和置信区间，不仅仅是 p 值。
3. 样本量低于探索性阈值时，分析必须在报告和 `classification-pipeline_meta.json` 中标注为探索性。
4. 所有随机过程（划分、洗牌交叉验证、随机搜索、Bootstrap、有种子估计器）必须使用固定随机种子。

---

## 调用示例

- "对 /job/stage/classification/ 中的暂存数据集构建分类器。"
- "对暂存训练文件调优随机森林和逻辑回归，并进行比较。"
- "使用分层交叉验证，以 F1 为优化目标，并为 /job/stage/classification/predict.csv 保存预测结果。"


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
