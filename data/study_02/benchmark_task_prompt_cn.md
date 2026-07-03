# 你的任务

**对 20 个唾液样本进行物种级别分类分析与代谢组学分析，鉴定 RRMS 患者与健康对照之间差异丰度的微生物物种和代谢物。特别检验亚牛磺酸（hypotaurine）在 RRMS 中是否显著降低。**

## 背景

本分析基于 Bousquet 等人（Microbiome, 2025）的研究。该研究发现 RRMS 患者中早期定植菌（链球菌属）减少、亚牛磺酸水平降低。你将使用 20 个样本（10 HC + 10 RRMS），每个样本均同时具备宏基因组和 LC-MS 代谢组学（峰面积）数据。

## 输入文件

所有文件位于本地 `data/study_02/` 目录下：

| 文件 | 说明 |
|------|------|
| `sampling_rationale.md` | 从原文全部样本集中选取20个样本的方法 |
| `selected_samples.tsv` | 20 个选定样本及其分组、药物亚组标签 |
| `metabolite_abundance.tsv` | LC-MS 峰面积矩阵（964 代谢物 × 20 样本） |
| `metabolite_annotation.tsv` | 代谢物 ID → 名称、通路、HMDB/KEGG 映射 |

**数据位置：** 
1. 双端 FASTQ 文件已预先下载，存放于FlowHub文件系统根目录下的 `/data/微生物数据/study_02/` 目录中，按样本ID分为子文件夹（例如 `/data/微生物数据/study_02/{SRR_ID}/{SRR_ID}_1.fastq.gz`）。
   SRR_ID的格式为 `SRR284*`，所有20个样本的SRR_ID可以在本地的 `data/study_02/selected_samples.tsv` 中查看。
2. 用于去宿主处理的参考基因组文件位于FlowHub文件系统根目录下的 `/data/GCF_000001405.40_GRCh38.p14_genomic.fna`。 

**SRA 项目编号：** 所有样本来自 BioProject **PRJNA1090491**（SRA Study SRP497009）。

**样本类型：** 双端宏基因组鸟枪法测序，DNBSEQ-G400，唾液。

## 样本选择

### 分组变量

- **主要分组：** Group（HC = 健康对照，RRMS = 复发缓解型多发性硬化）
- **次要分组：** Drug_Group（MS 疾病修正治疗药物或健康对照）

### 选定样本（N=20）

| 组别 | 亚组 | N |
|------|------|---|
| **HC** | 健康对照 | 10 |
| **RRMS** | Ocrevus（抗CD20） | 4 |
| | Copaxone（免疫调节剂） | 2 |
| | None（未治疗） | 2 |
| | Tecfidera（Nrf2激活剂） | 1 |
| | Avonex（IFN-β） | 1 |
| **合计** | | **20** |

样本选择对主要比较进行 10 vs 10 平衡，并比例性地代表药物亚组。详见 `selected_samples.tsv` 和 `sampling_rationale.md`。

## 允许使用的上游工具

只能使用以下工具进行上游宏基因组处理：

| 工具 | 版本 | 本任务中的用途 |
|------|------|--------------|
| **SOAPnuke** | 2.1.9 | 读段质控与过滤（必须） |
| **Bowtie2** | — | 宿主（人类）读段去除（必须） |
| **MetaPhlAn** | 4.2.4 | 分类组成分析（必须） |

**重要提示：** 禁止使用任何其他上游宏基因组工具（如 Kraken2、Bracken、HUMAnN、fastp、Trimmomatic、BWA、kneaddata）。仅允许使用 SOAPnuke、Bowtie2 和 MetaPhlAn。


## 你必须完成的任务

1. 对 20 个唾液宏基因组样本进行质控（FASTQ 文件位于FlowHub文件系统）
2. 使用 Bowtie2 去除人类宿主读段（预计 >90% 宿主 DNA——这是唾液样本的正常现象）
3. 对非宿主读段运行 MetaPhlAn 4 分类组成分析
4. 比较 HC 和 RRMS 之间的 Alpha 和 Beta 多样性
5. 鉴定差异丰度微生物物种
6. 执行差异代谢物分析：鉴定 HC 与 RRMS 之间丰度显著不同的代谢物
7. 特别检验亚牛磺酸（CHEM_ID=358）在 RRMS 中是否显著降低
8. 执行 RRMS 药物亚组效应的次要探索性分析
9. 将你的发现与原论文结果进行对比

## 你的工作流程

### 阶段 1：质量质控（SOAPnuke 2.1.9）

> **说明：** 原始 FASTQ 文件已由用户预先下载，存放于FlowHub文件系统（见前文）。跳过下载步骤，从此处开始。

```
1.1 对每个样本运行 SOAPnuke：
    - 去除接头序列
    - 修剪低质量碱基（Q < 20）
    - 去除修剪后长度 < 50 bp 的读段
1.2 生成质控汇总：
    - 原始读段数、清洁读段数、保留百分比、平均质量得分
    - 写入 qc_summary.tsv
```

### 阶段 2：宿主去除（Bowtie2）

```
2.1 下载人类参考基因组（GRCh38 主组装）
2.2 构建 Bowtie2 索引
2.3 使用 Bowtie2 将清洁读段比对到人类参考基因组
2.4 提取非宿主读段
2.5 报告每个样本的宿主读段百分比（预计 >90%）
    - 写入 host_reads_summary.tsv
    - 注意：保留读段比例非常低是唾液的正常现象
```

### 阶段 3：分类组成分析（MetaPhlAn 4.2.4）

```
3.1 对所有 20 个非宿主读段集运行 MetaPhlAn 4.2.4
    - 每个样本输出一个谱系文件：{sample}_profile.tsv
3.2 合并谱系为统一的物种级别丰度表：
    - 使用 merge_metaphlan_tables.py（MetaPhlAn 自带）
    - 行：物种，列：样本
    - 写入 metaphlan_merged_species.tsv
```

### 阶段 4：下游分析 — 多样性（Python 或 R）

```
4.1 Alpha 多样性
    - 计算 Shannon、Simpson 和 Observed species 丰富度
    - 使用 Wilcoxon 秩和检验比较 HC vs RRMS
    - 创建带 p 值标注的箱线图
    - 输出：alpha_diversity.tsv、alpha_diversity_boxplot.pdf

4.2 Beta 多样性
    - 从物种丰度计算 Bray-Curtis 相异度矩阵
    - 执行 PCoA 排序
    - PERMANOVA（adonis/vegan）：检验 Group（HC vs RRMS）的效应
    - 创建带 95% 置信椭圆的 PCoA 图
    - 输出：bray_curtis_pcoa.pdf

4.3 （可选）药物亚组 Beta 多样性
    - 按 Drug_Group 着色 PCoA 点，可视化治疗效应
    - 警告：亚组样本量较小，解读需谨慎
```

### 阶段 5：下游分析 — 差异丰度

```
5.1 数据预处理
    - 过滤在 <20% 样本中存在的物种（即少于 4 个样本）
    - 应用中心对数比（CLR）变换或使用相对丰度

5.2 HC vs RRMS 比较
    - 每个物种：Wilcoxon 秩和检验
    - 计算 log2 倍数变化（HC / RRMS，伪计数 1e-5）
    - 应用 Benjamini-Hochberg FDR 校正
    - 鉴定 FDR < 0.1 的物种
    - 输出：diff_abundance.tsv（species, mean_HC, mean_RRMS, log2FC, p_value, FDR）

5.3 可视化
    - 火山图：log2FC vs -log10(FDR)
    - 高亮 FDR < 0.1 的物种
    - 标注前 10 个最显著的物种
    - 输出：volcano_plot.pdf

5.4 热图
    - 选择平均丰度前 30 的物种
    - 跨样本进行 Z-score 标准化
    - 创建带 Group 和 Drug_Group 标注的热图
    - 输出：heatmap_top30.pdf
```

### 阶段 6：下游分析 — 代谢组学（Python 或 R）

```
6.1 数据预处理
    - 加载 metabolite_abundance.tsv
    - 对峰面积进行 log10 变换
    - 过滤缺失值 >30% 的代谢物（NA）
    - 用每个代谢物的半最小值填补剩余缺失值

6.2 差异代谢物分析
    - HC vs RRMS：每个代谢物 Wilcoxon 秩和检验
    - 计算 log2 倍数变化
    - 应用 Benjamini-Hochberg FDR 校正
    - 输出：diff_metabolites.tsv（CHEM_ID, chemical_name, super_pathway, mean_HC, mean_RRMS, log2FC, p_value, FDR）

6.3 亚牛磺酸专项分析
    - 提取亚牛磺酸（CHEM_ID=358）和牛磺酸（CHEM_ID=512）
    - 绘制 HC vs RRMS 箱线图并标注 Wilcoxon p 值
    - 输出：hypotaurine_boxplot.pdf

6.4 代谢物可视化
    - 所有代谢物火山图（log2FC vs -log10(FDR)）
    - 高亮亚牛磺酸和前几位显著代谢物
    - 输出：metabolite_volcano.pdf

6.5 多组学整合（可选）
    - 前 20 差异物种与前 20 差异代谢物的成对 Spearman 相关
    - 相关矩阵热图
    - 输出：species_metabolite_correlation_heatmap.pdf
```

### 阶段 7：报告

```
7.1 撰写 analysis_report.md，包含：
    - 质控摘要（读段保留率、宿主比例）
    - Alpha/Beta 多样性结果及统计量
    - 差异丰度最高的物种
    - 差异丰度最高的代谢物，含通路背景
    - 亚牛磺酸结果：在 RRMS 中是否显著降低？（与原始论文对比）
    - （可选）物种-代谢物关联
    - 药物亚组观察（描述性）
    - 局限性：
      * 小样本基准子集（20/99 样本）
      * 药物亚组统计效力不足
```

## 预期输出

```
所有分析结果必须输出到 Linux 系统本地路径：

/data/output/<job-id>/study_02_output/

其中：
-<job-id> 为本次任务运行时的唯一任务 ID。
-study_02_output/ 为本研究的固定输出目录名，不得更改。
-所有结果文件、脚本和报告必须位于该目录或其子目录下。
-不得将结果输出到当前工作目录、用户家目录、临时目录或其他非指定路径。
-如果目标目录不存在，流程应自动创建。
-如果同名文件已存在，应覆盖或重新生成，确保最终结果与本次运行一致。
-文件路径中不得包含空格、中文字符或未转义的特殊字符。
-样本相关文件中的 {sample} 必须与输入样本 ID 完全一致。

最终输出目录结构：
/data/output/<job-id>/study_02_output/
├── qc/
│   ├── qc_summary.tsv
│   └── {sample}_clean_{1,2}.fq.gz
├── host_removal/
│   ├── host_reads_summary.tsv
│   └── {sample}_nonhost_{1,2}.fq.gz
├── metaphlan/
│   ├── {sample}_profile.tsv
│   └── metaphlan_merged_species.tsv
├── diversity/
│   ├── alpha_diversity.tsv
│   ├── alpha_diversity_stats.tsv
│   ├── beta_diversity_stats.tsv
│   ├── alpha_diversity_boxplot.pdf
│   └── bray_curtis_pcoa.pdf
├── diff_abundance/
│   ├── diff_abundance.tsv
│   ├── volcano_plot.pdf
│   └── heatmap_top30.pdf
├── metabolomics/
│   ├── diff_metabolites.tsv
│   ├── hypotaurine_test.tsv
│   ├── metabolite_volcano.pdf
│   └── hypotaurine_boxplot.pdf
├── drug_subgroup/
│   ├── rrms_drug_subgroup_metadata.tsv
│   ├── rrms_drug_subgroup_microbiome.tsv
│   ├── rrms_drug_subgroup_metabolomics.tsv
│   └── rrms_drug_subgroup_summary.pdf
├── paper_comparison/
│   ├── paper_comparison_table.tsv
│   └── paper_comparison_summary.md
├── scripts/
│   ├── 01_qc.sh
│   ├── 02_host_removal.sh
│   ├── 03_metaphlan.sh
│   ├── 04_diversity_analysis.R
│   ├── 05_diff_abundance.R
│   ├── 06_metabolomics.R
│   ├── 07_drug_subgroup_analysis.R
│   ├── 08_paper_comparison.R
│   └── 09_visualization.R
└── analysis_report.md
```

## 注意事项

- 唾液宏基因组 >90% 为人类 DNA，宿主去除后微生物读段极少属正常现象。
- 药物亚组分析仅为描述性，不要对 n<3 的组进行统计检验。
- 亚牛磺酸为 CHEM_ID=358，牛磺酸为 CHEM_ID=512。使用 metabolite_annotation.tsv 进行 ID 查询。
- 代谢物峰面积在统计检验前需进行 log10 变换。
