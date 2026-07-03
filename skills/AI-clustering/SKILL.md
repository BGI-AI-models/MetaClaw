---
name: clustering
description: |
  对已暂存的表格数据集进行无监督聚类分析，发现未标注的结构。用户请求聚类、
  样本分群、异常检测或无监督模式发现时触发。读取 /job/stage/clustering/ 下的
  数据集，将可复现的聚类结果、生成代码和运行元数据写到 /job/analysis/clustering/
  和 /job/reproducibility/generated_scripts/。仅在 openclaw/downstream:1.1.0 容器内运行。
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
compatibility: |
  Requires Python 3.9+, pandas, scikit-learn, scipy, matplotlib, seaborn, joblib, pyyaml
---

# Clustering Skill

你在 `openclaw/downstream:1.1.0` 容器内运行。容器挂载：

| 路径 | 权限 | 内容 |
|---|---|---|
| `/job/stage/` | ro | 上游产物（数据从这里读） |
| `/job/analysis/` | rw | 分析结果写到这里 |
| `/job/reproducibility/` | rw | 生成脚本、日志、元数据 |
| `/pipeline/scripts/` | ro | 参考脚本 |

无网络访问（`--network none`）。

---

## 职责

此 skill 对已暂存的表格数据集执行无监督聚类分析。从 `/job/stage/clustering/` 读取单个聚类数据集，可使用 `/job/stage/metadata.tsv`（若存在）做注释或报告，产出可复现的分群、轮廓评估和聚类画像。

**不捏造聚类、不推断缺失文件、不将无标注聚类视为分类、不静默忽略无效输入。**

---

## 伴随文档

- `assets/supplementary_info.md` — 命令示例、配置格式和工作流说明；调用前先读。
- `assets/config_template.yaml` — 聚类配置示例。
- `scripts/clustering_models_unit_test.py` — 当前工作流和模型检查（若存在）。

若伴随文档与此 `SKILL.md` 冲突，以 `SKILL.md` 为准并报告不一致。

---

## 输入规范

```
/job/stage/
  clustering/
    data.csv           # 或 data.tsv / data.parquet；必需
    columns.yaml       # 特征列/分类列/忽略列/标识符列提示；可选
  metadata.tsv         # 可选，存在则读取
```

**必要检查（缺失则停止并报告）：**
- `/job/stage/clustering/` 下恰好有一个聚类数据集
- `columns.yaml`（若存在）声明的列名与数据集匹配
- metadata join key 必须明确且经验证

---

## 输出规范

```
/job/analysis/clustering/
  preprocessing/
    clustering_input_processed.csv
    preprocessing_summary.md
  models/
    clustering_model.joblib
    clustering_parameters.json
  evaluation/
    cluster_assignments.csv
    cluster_metrics.csv
    cluster_profiles.csv
    embedding_plot.png
    evaluation_summary.md
  clustering_meta.json

/job/reproducibility/generated_scripts/
  clustering_pipeline_<timestamp>.py
```

`clustering_meta.json` 必须记录：包版本、输入路径、输出路径、参数、随机种子、选定算法、缩放和编码选择、降维方法（若使用）、是否为探索性分析，以及关键预处理和算法选择决策说明。

---

## 工作流

### Step 1 — 读取数据

从 `/job/stage/clustering/` 读取数据集（CSV/TSV/Parquet）。若 `metadata.tsv` 存在，读取并报告是否用于注释。若 `columns.yaml` 存在，在预处理前验证特征列和忽略列声明。

报告所有数据异常：缺失值、重复行、全空列、常数列、混合类型特征列、严重稀疏性、metadata join 不匹配。

随机种子：从用户提供的 override 或 `columns.yaml` 的 `random_seed` 字段获取；未指定则使用 `42` 并在元数据中记录。

### Step 2 — 分析

四个子阶段：预处理 → 算法选择 → 聚类 → 评估/报告。

**预处理**：列选择、缺失值处理、分类变量 one-hot 编码、数值缩放（默认标准化），特征数量多或多重共线性严重时可选 PCA 降维。

**算法选择**：
- **KMeans**：已知或可调候选 k 时；
- **DBSCAN**：任意形状簇或异常点检测重要时；
- **Spectral Clustering**：非凸结构且数据量许可时。

所有随机操作（KMeans 初始化、随机降维、洗牌子采样）使用固定随机种子。

**评估**：轮廓系数（Silhouette）、Davies-Bouldin 分数、Calinski-Harabasz 分数（数学上有效时）、簇计数和大小分布、密度方法的噪声点数、原始特征空间中的简洁聚类画像。

参数设置或算法间的推断性比较须报告效应量和置信区间。

若样本量低于探索性阈值（< 30 或用户指定），在报告和元数据中标注为**探索性分析**。

### Step 3 — 归档

每次运行必须：
1. 将生成脚本保存到 `/job/reproducibility/generated_scripts/clustering_pipeline_<timestamp>.py`
2. 将 `clustering_meta.json` 写到 `/job/analysis/clustering/`

若因文件缺失、模式冲突或规范违反而停止，元数据文件仍须尽可能写入并记录终止原因。

---

## 严格规则

1. 数据异常（NaN、重复行、常数列、稀疏或无效特征、模式漂移）不可静默跳过——必须显式报告。
2. 聚类配置间的推断性比较必须报告效应量和置信区间，不仅仅是 p 值。
3. 样本量低于探索性阈值时，分析必须在报告和 `clustering_meta.json` 中标注为探索性。
4. 所有随机过程必须使用固定随机种子（KMeans 初始化、随机分解、有种子估计器）。

---

## 调用示例

- "对 /job/stage/clustering/ 中的暂存数据集进行聚类，展示自然分组。"
- "对暂存观测值进行分群，比较 KMeans 和 DBSCAN。"
- "运行聚类，报告异常点，将所有结果保存到 /job/analysis/clustering/。"
- "对暂存数据集进行聚类画像，解释哪种算法最合适。"


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
