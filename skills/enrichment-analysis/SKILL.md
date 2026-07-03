---
name: enrichment-analysis
description: >
  对宏基因组上游的功能通路产物（HUMAnN pathabundance）做通路富集分析：
  组间差异通路、GSEA 风格的通路评分、MetaCyc/UniRef 功能注释富集。
  用户请求通路富集、功能差异、代谢通路分析时触发。
  仅在 openclaw/downstream:1.1.0 容器里运行。
allowed-tools: Bash(python *) Bash(Rscript *) Read Write
disable-model-invocation: true
---

# Enrichment Analysis Skill

你在 `openclaw/downstream:1.1.0` 容器内运行。容器挂载：

| 路径 | 权限 | 内容 |
|---|---|---|
| `/job/stage/` | ro | 上游工具产物 |
| `/job/analysis/` | rw | 下游分析结果（写这里） |
| `/job/reproducibility/` | rw | 可复现性材料 |
| `/pipeline/scripts/` | ro | 参考脚本 |

无网络访问（`--network none`）。通路注释数据库只使用已挂载到容器内的本地文件。

---

## 输入

- `/job/stage/manifest.json` — 上游产物索引，**先读这个**
- `/job/stage/functional/*_humann/*_pathabundance.tsv` — HUMAnN3 通路丰度表
- `/job/stage/functional/*_humann/*_genefamilies.tsv` — 基因家族丰度（可选）
- `/job/stage/metadata.tsv` — 样本元数据（由 orchestrator 从 DATA_DIR 硬链接进来；分组信息，无则仅做描述统计）
- `/job/analysis/stats/stats_summary.json` — stats-analysis 产物（若已存在，用于交叉验证）

---

## 工作流

### Step 1 — 读取并聚合通路表

```python
import json, pandas as pd
manifest = json.load(open('/job/stage/manifest.json'))
# 按 manifest['functional'] 定位每个样本的 pathabundance 路径
# 合并为样本 × 通路矩阵
```

报告：通路总数、样本数、零值比例、每样本的总丰度分布。

### Step 2 — 数据预处理

1. **过滤低丰度通路**：在 >X% 样本中丰度为 0 的通路予以过滤（X 由数据驱动决定，默认 80%）。
2. **CLR 变换**（成分数据必做）：`skbio.stats.composition.clr`。
3. **层级化**：保留 stratified（菌种来源）和 unstratified 两种视图分别分析。

### Step 3 — 决定富集方法

| 情形 | 方法 |
|---|---|
| 两组、通路丰度连续 | Wilcoxon + BH-FDR |
| 多组 | Kruskal-Wallis + Dunn 事后 |
| 有连续协变量 / 混杂 | rpy2 调用 MaAsLin2（通路级） |
| 想做通路集整体检验 | GSEA-preranked（用 log2FC 排名） |

### Step 4 — 生成定制脚本

**不要直接运行参考脚本**——基于 `/pipeline/scripts/reference_enrichment.py` 改写定制版本：

```bash
SCRIPT=/job/reproducibility/generated_scripts/enrichment_$(date +%Y%m%d-%H%M%S).py
```

### Step 5 — 执行并捕获日志

```bash
python "$SCRIPT" 2>&1 | tee /job/reproducibility/logs/enrichment.log
```

### Step 6 — 产出（写到 `/job/analysis/enrichment/`）

| 文件 | 内容 |
|---|---|
| `pathway_matrix.csv` | CLR 变换后的样本 × 通路矩阵 |
| `differential_pathways.csv` | p、FDR、effect size、通路名称 |
| `top_pathways_heatmap.html` | Plotly 热图（top 40 差异通路） |
| `enrichment_summary.json` | 结构化摘要，供 report-generator 读取 |

### Step 7 — 写 reproducibility 元数据

```bash
cat > /job/reproducibility/enrichment_meta.json <<EOF
{
  "skill": "enrichment-analysis",
  "generated_script": "generated_scripts/enrichment_<ts>.py",
  "tools": {
    "python": "$(python --version 2>&1)",
    "pandas": "$(python -c 'import pandas; print(pandas.__version__)')",
    "scikit-bio": "$(python -c 'import skbio; print(skbio.__version__)')",
    "R": "$(Rscript -e 'cat(R.version.string)' 2>/dev/null || echo NA)"
  },
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
```

---

## 可用库

Python: `pandas` `numpy` `scipy` `statsmodels` `scikit-bio` `rpy2` `plotly`  
R（通过 rpy2）: `MaAsLin2` `vegan`

---

## 严格规则

1. 多重检验必须 BH-FDR。
2. CLR 变换前必须处理零值（加伪计数 1e-6 或 multiplicative replacement）。
3. Stratified 和 unstratified 通路必须分开分析，不可混合。
4. 生成的脚本归档到 `/job/reproducibility/generated_scripts/`，执行前不可跳过。
5. 所有产出写到 `/job/analysis/enrichment/`，不得写到 stage/。


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
