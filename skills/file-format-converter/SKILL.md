---
name: file-format-converter
description: >
  在宏基因组学常用格式之间进行无损互转，支持序列文件、丰度表、特征表和对齐文件。
  转换后自动验证文件完整性并输出转换日志。
  在 openclaw/downstream:1.1.0 容器内运行，使用容器内置工具（seqkit、samtools、
  biom-format、pandas）。用户请求格式转换时触发。
allowed-tools: Bash(python *) Bash(samtools *) Bash(seqkit *) Read Write
disable-model-invocation: false
---

# 文件格式转换 Skill

你在 `openclaw/downstream:1.1.0` 容器内运行。容器挂载：

| 路径 | 权限 | 内容 |
|---|---|---|
| `/job/stage/` | ro | 上游工具产物（转换源文件从这里读） |
| `/job/analysis/` | rw | 转换结果写到这里 |
| `/job/reproducibility/` | rw | 转换日志和元数据 |

无网络访问（`--network none`）。只使用容器内已安装的工具，不拉取外部镜像。

---

## 支持的转换路径

```
序列文件：
  FASTQ  ←→  FASTA            （seqkit）
  BAM    →   FASTQ             （samtools）按名排序后拆分双端
  BAM    →   FASTA             （samtools）
  FASTA  →   单行 FASTA        （seqkit seq -w 0）

丰度表：
  BIOM   ←→  TSV               （biom-format Python 包）
  BIOM   →   JSON              （biom-format Python 包）
  宽格式 ←→  长格式（tidy）    （pandas）

对齐文件：
  SAM    ←→  BAM               （samtools）
  BAM    →   CRAM              （samtools，需参考基因组）

压缩：
  任意文件  →  .gz             （pigz，多线程）
  .gz       →  原格式（解压）
```

---

## 输入

```yaml
input_file:    /job/stage/<subdir>/<file>   # 从 stage/ 读，必需
output_format: string                        # 目标格式，必需
output_file:   /job/analysis/converted/<file>  # 输出路径，默认同名换扩展名
paired_r2:     /job/stage/<subdir>/<r2>     # BAM→FASTQ 双端拆分时提供（可选）
threads:       int                           # 线程数，默认 4
compress:      bool                          # 输出是否 gzip，默认 false
```

输入文件路径必须在 `/job/stage/` 下（只读挂载）。**不可读取 `/job/stage/` 以外的路径。**

---

## 工作流

### Step 1 — 识别格式

检查文件扩展名和 magic bytes，确认实际格式：

```python
import subprocess
# BAM: magic bytes 0x1f 0x8b (gzip) + BAM magic
# BIOM: JSON 或 HDF5 格式
```

### Step 2 — 选择转换后端

| 转换路径 | 后端工具 | 容器内可用 |
|---|---|---|
| FASTQ ↔ FASTA | seqkit | ✓ |
| BAM → FASTQ/FASTA | samtools | ✓ |
| SAM ↔ BAM | samtools | ✓ |
| BIOM ↔ TSV/JSON | biom-format (Python) | ✓ |
| 宽格式 ↔ 长格式 | pandas (Python) | ✓ |
| gzip 压缩/解压 | pigz | ✓ |

### Step 3 — 执行转换

```bash
# 示例：BIOM → TSV
python -c "
import biom
t = biom.load_table('/job/stage/taxonomy/feature-table.biom')
with open('/job/analysis/converted/feature-table.tsv','w') as f:
    t.to_dataframe(dense=True).to_csv(f, sep='\t')
"

# 示例：BAM → FASTQ（按名排序后拆分）
samtools sort -n -@ $THREADS /job/stage/assembly/reads.bam -o /tmp/sorted.bam
samtools fastq -@ $THREADS /tmp/sorted.bam \
  -1 /job/analysis/converted/R1.fastq.gz \
  -2 /job/analysis/converted/R2.fastq.gz
```

### Step 4 — 验证完整性

```python
# 校验行数 / read 数一致
# 计算 MD5 写到 .convert.log
import hashlib
```

### Step 5 — 输出转换日志

写到 `/job/analysis/converted/<output_file>.convert.log`：

```json
{
  "skill": "file-format-converter",
  "input":  {"path": "...", "format": "BAM", "md5": "..."},
  "output": {"path": "...", "format": "FASTQ", "md5": "..."},
  "records": {"input": 1234567, "output": 1234567},
  "timestamp": "2026-04-24T10:00:00Z"
}
```

---

## 注意事项

- BAM → FASTQ 时必须先按名排序（`samtools sort -n`），否则双端 reads 顺序错乱。
- BIOM → TSV 默认输出 observations × samples 宽格式；长格式需指定 `output_format: tsv-long`。
- 超过 50 GB 的文件使用流式处理（`samtools view --threads` 或 `seqkit` 流式模式）。
- CRAM 转换需要参考基因组；若 `/job/stage/` 内无参考，报错并停止。
- 所有产出写到 `/job/analysis/converted/`，不可写到 `/job/stage/`（上游只读）。

---

## 引用

- seqkit：Shen W. et al. PLOS ONE, 2016. doi:10.1371/journal.pone.0163962
- samtools：Danecek P. et al. GigaScience, 2021. doi:10.1093/gigascience/giab008
- biom-format：McDonald D. et al. GigaScience, 2012. doi:10.1186/2047-217X-1-7
