---
name: pipeline-runner
description: >
  在 OpenClaw Gateway 启动宏基因组分析 pipeline。读取 registry/pipelines.yaml
  选择合适的 pipeline，向用户确认后通过 gateway.sh 启动，监控执行并汇报结果。
  用户说"分析数据"、"跑 pipeline"、"处理样本"时触发。
allowed-tools: Bash(bash *) Bash(python3 *) Read Write
disable-model-invocation: false
---

# Pipeline Runner Skill

你在 OpenClaw Gateway（host 进程）内运行，**不在任何容器内**。

---

## 工作流

### Step 1 — 确认数据目录

询问或推断用户的 FASTQ 数据目录（默认 `./data/`）。检查目录是否存在并包含 FASTQ 文件。

### Step 2 — 读取可用 pipeline 列表

```bash
python3 -c "
import yaml
p = yaml.safe_load(open('registry/pipelines.yaml'))['pipelines']
for name, cfg in p.items():
    print(f'{name}: {cfg[\"description\"]}')
"
```

### Step 3 — 匹配并选择 pipeline

根据用户目标从 `registry/pipelines.yaml` 里选最合适的 pipeline。若有多个候选，列出前两个让用户选择。

向用户展示执行计划：
- Pipeline 名称与描述
- 上游：FlowHub flow keyword（`upstream.fkit_flow_keyword`），不再有本地 DAG
- 下游 skill 列表
- 默认参数（`upstream.default_params` + `downstream.default_params`）
- 预计时间（pipeline `timeout_minutes`）

### Step 4 — 收集参数 override

询问用户是否有参数修改（常见：`fastp.min_length`、`kraken2.confidence`）。

将 override 写到 job 目录（**不修改 registry/pipelines.yaml**）：
```yaml
# 写到 /data/output/<job-id>/reproducibility/params_override.yaml
fastp:
  min_length: 75
```

### Step 5 — 用户确认后启动

收到明确"是"后执行：

```bash
bash gateway/gateway.sh <pipeline-name> <data-dir> [params_override.yaml]
```

带 upstream 段的 pipeline：`gateway.sh` 提交 FlowHub 任务后立即返回（`/data/output/<id>/.pipeline_id`）。
仅下游的 pipeline：直接进入 `prepare_downstream.sh`。

### Step 6 — 监控执行

**上游（FlowHub）**——每 10 分钟轮询一次（详见 AGENTS.md W1 step 8）：

```bash
bash skills/upstream-pipeline-fkit/scripts/run.sh poll <job-id>
```

`STATUS=2` 时跑 `... finalize <id> <pipeline>`，结果落到 `/data/output/<id>/stage/`。

**下游（本地容器）**：

```bash
docker ps --filter name=openclaw-down- --format "table {{.Names}}\t{{.Status}}"
tail -20 /data/output/<job-id>/reproducibility/logs/downstream_*.log
```

任何上游/下游错误退出立即停止并报告（参考 AGENTS.md W2）。

### Step 7 — 汇报结果

分析完成后：

```bash
# 读取报告并汇总
python3 -c "
import json
manifest = json.load(open('/data/output/<job-id>/tool_manifest.json'))
# 统计：工具调用次数、成功/失败、总耗时
"
```

向用户报告：
- 分析了什么、用了哪个 pipeline
- 关键发现（读 `analysis/report.html` 或 `analysis/stats/stats_summary.json`）
- 结果路径：`/data/output/<job-id>/analysis/`
- 复现包路径：`/data/output/<job-id>/reproducibility/`

---

## 规则

- **上游只在 FlowHub 跑**——通过 `fkit`，不在本地起任何上游 Docker 容器。
- **永远通过 `gateway.sh` 启动**，不直接调 `docker run`，不直接调 `fkit pipeline create`。
- **不修改 registry/**——参数 override 只写到当前 job 目录。
- **启动前必须确认**，不自动静默启动。
- **轮询 FlowHub 用 `skills/upstream-pipeline-fkit/scripts/run.sh poll`**，不要 `sleep` 阻塞。
- 若没有 pipeline 匹配用户需求，说明现有 pipeline 的覆盖范围，并引导用户参考 AGENTS.md W5。
