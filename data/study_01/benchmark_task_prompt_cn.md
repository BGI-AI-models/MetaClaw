# 你的任务

**对 20 个高粱根际和土壤宏基因组样本，执行差异分类组成分析与多样性比较，鉴定与干旱胁迫相关的微生物类群及其群落变化。**

## 背景

本分析基于 Xu 等人（Nature Communications, 2021）的研究。该研究发现干旱会富集高粱根际中的放线菌门和铁代谢相关类群。你将使用该研究中精心筛选的 20 个样本子集。你需要将分析结果与原论文的核心发现进行对比：干旱条件下根际中铁代谢相关微生物是否富集。

## 输入文件

所有文件位于 `study_01/` 目录：

| 文件 | 说明 |
|------|------|
| `sampling_rationale.md` | 从原文全部样本集中选取20个样本的方法 |
| `selected_samples.tsv` | 20 个选定样本及其处理、基因型、部位标签 |

**数据位置：** 双端 FASTQ 文件已预先下载，存放于 `study_01/reads/` 目录中，按样本组织（例如 `study_01/reads/{SRR_ID}/{SRR_ID}_1.fastq.gz`）。

**SRA 项目编号：** 所有样本来自 BioProject **PRJNA657940**（SRA Study SRP133339）。

**样本类型：** 双端宏基因组鸟枪法测序，Illumina NovaSeq 6000。

## 样本选择

### 分组变量

- **处理：** Drought（不浇水）vs Watered（100% 蒸发蒸腾量浇水）
- **部位：** Rhizosphere（根际，Z）vs Bulk Soil（土壤，S）
- **基因型：** RTx642 vs BTx430（高粱品系）
- **时间点：** TP3（早期）、TP8（中期）、TP10/TP11（晚期）

### 选定样本（N=20）

| 组别 | N | 说明 |
|------|---|------|
| Drought_Rhizo | 5 | 干旱处理，根际部位 |
| Watered_Rhizo | 5 | 浇水处理，根际部位 |
| Drought_Bulk | 5 | 干旱处理，土壤部位 |
| Watered_Bulk | 5 | 浇水处理，土壤部位 |

每组内均包含两个高粱基因型。详见 `selected_samples.tsv`。

## 允许使用的上游工具

只能使用以下工具进行上游宏基因组处理：

| 工具 | 版本 | 本任务中的用途 |
|------|------|--------------|
| **SOAPnuke** | 2.1.9 | 读段质控与过滤 |
| **Bowtie2** | — | 宿主（高粱）读段去除 |
| **MetaPhlAn** | 4.2.4 | 分类组成分析（必须） |

**重要提示：** 禁止使用任何其他上游宏基因组工具（如 Kraken2、Bracken、HUMAnN、QIIME2、fastp、Trimmomatic、BWA 等）。仅允许使用上述列出的工具。

## 你必须完成的任务

1. 对 20 个宏基因组样本进行质控（FASTQ 文件已预下载至 `study_01/reads/`）
2. 使用 Bowtie2 去除宿主（高粱）读段
3. 对所有非宿主读段运行 MetaPhlAn 4 分类组成分析
4. 比较干旱 vs 浇水、根际 vs 土壤的分类组成差异
5. 通过统计检验鉴定差异丰度物种
6. 将结果与原论文发现进行对比解读

## 你的工作流程

### 阶段 1：质量质控（SOAPnuke）

> **说明：** 原始 FASTQ 文件已由用户预先下载，存放于 `study_01/reads/` 目录。跳过下载步骤，从此处开始。

```
1.1 对每个样本运行 SOAPnuke：
    - 去除接头序列
    - 修剪低质量碱基（Q < 20）
    - 去除修剪后长度 < 50 bp 的读段
1.2 生成质控报告，汇总：
    - 原始读段数、清洁读段数、保留百分比
    - 写入 qc_summary.tsv
```

### 阶段 2：宿主去除（Bowtie2）

```
2.1 下载高粱参考基因组（NCBI GCF_000003195.3）
2.2 构建 Bowtie2 索引
2.3 使用 Bowtie2 将清洁读段比对到宿主基因组
2.4 提取非宿主读段用于下游分析
2.5 报告每个样本的宿主读段百分比
```

### 阶段 3：分类组成分析（MetaPhlAn）

```
3.1 对所有 20 个非宿主读段集运行 MetaPhlAn 4.2.4
    - 使用 --add_viruses 参数包含病毒分类群
    - 每个样本输出：{sample}_profile.tsv
3.2 合并单个谱系为统一的丰度表：
    - 行：物种，列：样本
    - 写入 metaphlan_merged_species.tsv
```

### 阶段 4：下游分析（Python 或 R）

```
4.1 Alpha 多样性分析
    - 计算 Shannon、Simpson 和 Observed species 指数
    - 使用 Wilcoxon 秩和检验比较组间差异
    - 创建带显著性标注的箱线图
    - 输出：alpha_diversity.tsv、alpha_diversity_boxplot.pdf

4.2 Beta 多样性分析
    - 计算 Bray-Curtis 相异度矩阵
    - 执行 PCoA 排序
    - 使用 PERMANOVA（adonis, 999 次置换）检验组间差异：
      ~ Treatment + Compartment + Genotype
    - 生成带分组椭圆的 PCoA 图
    - 输出：bray_curtis_pcoa.pdf

4.3 差异丰度分析
    - 过滤在 <20% 样本中存在的物种
    - 干旱 vs 浇水（在每个部位内分别比较）：
      - 每个物种执行 Wilcoxon 秩和检验
      - 计算 log2 倍数变化（添加伪计数 1e-5）
      - 应用 Benjamini-Hochberg FDR 校正
    - 鉴定 FDR < 0.1 且 |log2FC| > 1 的物种
    - 输出：diff_abundance_rhizo.tsv、diff_abundance_bulk.tsv

4.4 可视化
    - 差异丰度火山图（FDR vs log2FC）
    - 所有样本中丰度前 30 物种的热图
    - 门水平相对丰度堆叠条形图
    - 输出：volcano_plot.pdf、heatmap_top30.pdf、phylum_barplot.pdf
```

### 阶段 5：解读与报告

```
5.1 撰写 analysis_report.md，包含：
    - 质控和宿主去除结果摘要
    - Alpha 多样性发现：哪些组之间存在显著差异？
    - Beta 多样性：什么因素驱动群落的变异？
    - 差异丰度最高的物种
    - 与原始论文铁代谢发现的关联：
      * 放线菌门在干旱条件下是否富集？（如原文所报道）
      * 变形菌门在干旱条件下是否减少？（如原文所报道）
    - 基准测试的局限性（样本量减少、无 MAG 分析）
```

## 预期输出

```
study_01_output/
├── metaphlan/
│   ├── {sample}_profile.tsv      # 每个样本的 MetaPhlAn 输出
│   └── metaphlan_merged_species.tsv  # 合并的物种表
├── diversity/
│   ├── alpha_diversity.tsv
│   ├── alpha_diversity_boxplot.pdf
│   └── bray_curtis_pcoa.pdf
├── diff_abundance/
│   ├── diff_abundance_rhizo.tsv
│   ├── diff_abundance_bulk.tsv
│   └── volcano_plot.pdf
├── figures/
│   ├── heatmap_top30.pdf
│   └── phylum_barplot.pdf
├── scripts/
│   ├── 01_qc.sh
│   ├── 02_host_removal.sh
│   ├── 03_metaphlan.sh
│   ├── 04_diversity_analysis.R  （或 .py）
│   ├── 05_diff_abundance.R      （或 .py）
│   └── 06_visualization.R       （或 .py）
└── analysis_report.md
```

## 注意事项

- 高粱参考基因组约 730 Mb，Bowtie2 索引构建耗时较长。
- MAG 组装（MEGAHIT + MetaWRAP）为可选项，优先完成分类分析。
- 时间点可作为批次协变量处理，无需做时间序列建模。
