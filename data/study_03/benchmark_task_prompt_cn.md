# 你的任务

**对 24 个粪便宏基因组样本进行物种级别分类分析，训练机器学习分类器以区分结直肠癌（CRC）患者、腺瘤患者和健康对照。按微生物物种对 CRC 检测的判别能力进行排序。**

## 背景

本分析基于 Zeller 等人（Molecular Systems Biology, 2014）的里程碑研究。该研究证明粪便微生物物种谱可以检测 CRC（AUC > 0.80）。你将使用法国人群（Pop. F）中的 24 个样本（8 Healthy + 8 Adenoma + 8 CRC）。样本分组标签已在 `selected_samples.tsv` 中确认提供，无需额外获取。已报道的 CRC 相关物种（具核梭杆菌、口腔消化链球菌、微小微单胞菌）应出现在你的顶级生物标志物中。

## 输入文件

所有文件位于 `study_03/` 目录：

| 文件 | 说明 |
|------|------|
| `selected_samples.tsv` | 24 个样本及其已确认的 Group、Diagnosis 和临床元数据 |
| `sampling_rationale.md` | 从原文全部样本集中选取24个样本的方法 |

**数据位置：** 双端 FASTQ 文件已预先下载，存放于 `study_03/reads/` 目录。

**表型来源：** 样本分组标签（Healthy/Adenoma/CRC）来源于 Zeller 等人 2014 论文补充表（Pop. F Subject Metadata），并已填入 `selected_samples.tsv`。无需额外获取表型数据。

**重要提示：** Zeller 等人的数据包含已预处理的读段（去接头 + 去人源 hg19）。如果有预处理读段，直接使用它们以跳过宿主去除步骤。

## 样本选择

### 分组变量

- **Group：** Healthy（结肠镜检查正常，n=8）、Adenoma（小腺瘤 + 大腺瘤，n=8）、CRC（癌症，n=8）
- **Diagnosis（详细）：** Normal / Small adenoma / Large adenoma / Cancer
- **临床协变量：** 年龄、性别、BMI、国家（均为法国）

### 选定样本（N=24）

| 组别 | 诊断 | N | 平均年龄 | 性别（男/女） |
|------|------|---|---------|-------------|
| **Healthy** | Normal | 8 | 61.2 | 2/6 |
| **Adenoma** | Small adenoma | 5 | 60.6 | 1/4 |
| | Large adenoma | 3 | 67.3 | 3/0 |
| **CRC** | Cancer | 8 | 65.5 | 4/4 |
| **合计** | | **24** | | |

详见 `selected_samples.tsv` 获取每个样本的完整元数据。

## 允许使用的上游工具

只能使用以下工具进行上游宏基因组处理：

| 工具 | 版本 | 本任务中的用途 |
|------|------|--------------|
| **SOAPnuke** | 2.1.9 | 可选：读段质控（如使用预处理读段则跳过） |
| **Bowtie2** | — | 可选：宿主去除（如使用预处理读段则跳过） |
| **MetaPhlAn** | 4.2.4 | 分类组成分析（必须） |

**重要提示：** 禁止使用任何其他上游宏基因组工具（如 Kraken2、Bracken、HUMAnN、QIIME2、fastp、Trimmomatic、BWA）。仅允许使用上述列出的工具。

**无可用的功能分析工具**（HUMAnN、eggNOG-mapper）。请聚焦于分类组成分析。

## 你必须完成的任务

1. 验证读段质量（如可用，优先使用已去除宿主的预处理读段）
2. 对所有 24 个样本运行 MetaPhlAn 4 分类组成分析
3. 比较 Healthy、Adenoma 和 CRC 三组之间的分类组成
4. 训练机器学习分类器：CRC vs 非CRC、CRC vs Adenoma
5. 按物种对 CRC 检测的判别能力进行排序
6. 将你的顶级生物标志物与已知 CRC 相关物种进行对比

## 你的工作流程

### 阶段 1：质量质控（如需要）

> **说明：** 如有预处理读段（元数据中 submitted_ftp 列），请优先使用。这些读段已完成去接头和去人源 hg19 处理。

```
1.1 检查是否有预处理读段：
    - 预处理：去接头 + 去人源 hg19（推荐，跳过至阶段 2）
    - 原始：如无预处理读段，使用 fastq_ftp 中的原始读段
1.2 如使用原始读段，运行 SOAPnuke：
    - 去接头，Q<20 修剪，<50bp 过滤
1.3 记录读段计数和质控状态
```

### 阶段 2：分类组成分析（MetaPhlAn 4.2.4）

```
2.1 对所有 24 个样本运行 MetaPhlAn 4.2.4
    - 如可用，使用预处理的非宿主读段
    - 每个样本输出：{sample}_profile.tsv
2.2 合并谱系为物种级别丰度表
    - 使用 merge_metaphlan_tables.py
    - 写入 metaphlan_merged_species.tsv
```

### 阶段 3：下游分析 — 比较分析

```
3.1 按疾病分组的 Alpha 多样性
    - Shannon、Simpson、Observed species
    - 三组间的 Kruskal-Wallis 检验
    - 两两 Wilcoxon 检验 + FDR 校正
    - 带 p 值标注的箱线图
    - 输出：alpha_diversity.tsv、alpha_diversity_boxplot.pdf

3.2 Beta 多样性
    - Bray-Curtis 相异度
    - PCoA 排序
    - PERMANOVA：Group
    - 带 95% 椭圆的 PCoA 图
    - 输出：bray_curtis_pcoa.pdf

3.3 差异丰度
    - CRC vs 非CRC（Healthy+Adenoma）
    - CRC vs Adenoma（关键临床问题）
    - Adenoma vs Healthy
    - 每个物种 Wilcoxon 检验，FDR 校正
    - 输出：diff_abundance_crc_vs_non.tsv、diff_abundance_crc_vs_adenoma.tsv
```

### 阶段 4：机器学习分类器

```
4.1 数据准备
    - 过滤在 <20% 样本中存在的物种
    - CLR 变换物种丰度
    - 定义目标：CRC vs 非CRC（二分类）；CRC vs Adenoma（二分类）

4.2 模型训练（推荐随机森林）
    - 嵌套交叉验证（外层 5 折，内层 3 折用于超参数调优）
    - 替代方案：LASSO 逻辑回归
    - 报告：AUC-ROC、灵敏度、特异性、PPV、NPV
    - 绘图：带 95% CI 的 ROC 曲线
    - 输出：classifier_metrics.tsv、classifier_roc.pdf

4.3 特征重要性
    - 随机森林：平均 Gini 不纯度减少
    - LASSO：非零系数
    - 按判别能力对物种排序
    - 输出：biomarker_ranking.tsv、biomarker_barplot.pdf

4.4 与已知 CRC 标志物对比验证
    - 将顶级生物标志物与文献进行比较：
      * 具核梭杆菌（Fusobacterium nucleatum）
      * 口腔消化链球菌（Peptostreptococcus stomatis）
      * 微小微单胞菌（Parvimonas micra）
      * Gemella morbillorum
      * 非解糖卟啉单胞菌（Porphyromonas asaccharolytica）
    - 报告重叠情况和任何新候选标志物
```

### 阶段 5：解读与报告

```
5.1 撰写 analysis_report.md，包含：
    - 质控和分类分析摘要
    - Alpha/Beta 多样性发现
    - CRC 中差异丰度最高的物种
    - 分类器性能（AUC、灵敏度、特异性）
    - 前 10 个生物标志物物种及重要性得分
    - 与 Zeller 等人报道标志物的比较
    - 局限性：
      * 小样本基准子集（24/156 样本）
      * 无功能基因分析
      * 临床协变量（年龄、性别、BMI）可用但未纳入主分类器
```

## 预期输出

```
study_03_output/
├── metaphlan/
│   ├── {sample}_profile.tsv
│   └── metaphlan_merged_species.tsv
├── diversity/
│   ├── alpha_diversity.tsv
│   ├── alpha_diversity_boxplot.pdf
│   └── bray_curtis_pcoa.pdf
├── diff_abundance/
│   ├── diff_abundance_crc_vs_non.tsv
│   ├── diff_abundance_crc_vs_adenoma.tsv
│   └── volcano_plot.pdf
├── classifier/
│   ├── classifier_metrics.tsv
│   ├── classifier_roc.pdf
│   ├── biomarker_ranking.tsv
│   └── biomarker_barplot.pdf
├── scripts/
│   ├── 01_qc.sh （可选）
│   ├── 02_metaphlan.sh
│   ├── 03_diversity_analysis.R （或 .py）
│   ├── 04_diff_abundance.R （或 .py）
│   ├── 05_classifier.R （或 .py）
│   └── 06_visualization.R （或 .py）
└── analysis_report.md
```

## 注意事项

- 使用预处理读段（已去人源 hg19）直接运行 MetaPhlAn，无需宿主去除。
- 每组仅 8 个样本，分类器 AUC 可能中等，优先关注生物可解释性。
- 基因水平和 KEGG 通路分析无法用允许工具复现，仅聚焦分类标志物。
