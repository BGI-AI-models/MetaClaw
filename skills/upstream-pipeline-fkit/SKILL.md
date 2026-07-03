---
name: upstream-pipeline-fkit
description: >
  唯一的上游执行入口：通过 fkit CLI 把所有宏基因组上游分析提交到 FlowHub 云平台运行
  （本地不再起任何上游 Docker 容器）。**输入数据驻留在 FlowHub 文件系统上**——
  agent 不再上传，submit 阶段直接用 `fkit ls` 在 FlowHub 上发现 fileId。
  负责：根据用户请求挑选合适的 FlowHub flow → 读取
  /data/output/<id>/.input_source 记录的 FlowHub 绝对路径 → `fkit ls` 拿到 fileId →
  生成 spec → `fkit pipeline create` → 每 10 分钟轮询并向用户汇报 → 成功后
  下载结果到 /data/output/<id>/stage/ 并通知下游。
  用户请求 QC / 物种分类 / 功能注释 / 序列组装 / 任何宏基因组上游任务，
  或想"在 FlowHub / 云端跑流程"、"用 fkit 跑分析"时触发。
allowed-tools: Bash(bash *) Bash(fkit *) Bash(jq *) Read Write
disable-model-invocation: false
---

# Upstream Pipeline — FlowHub via fkit

你在 **OpenClaw Gateway（host 进程）** 内运行。**本 skill 不在本地启动任何上游 Docker 容器**——
所有上游容器都跑在 FlowHub 上，本地只用 `fkit` 提交、查询、下载文件。

> 宿主机 jobs 根默认 `/data/output`，用 `OPENCLAW_JOBS_ROOT` 覆盖；本 skill
> 的 `scripts/run.sh` 启动时自动读取。

## 角色定位

本 skill 是 BioLine 上游的**唯一**执行入口与**唯一**事实来源。Gateway 不再封装
fkit 生命周期——`gateway/orchestrator.sh` 只负责创建 `/data/output/<id>/{input,stage,
reproducibility,...}` 等目录后把控制权交还 agent，由 agent 按 SKILL.md 调用本
skill 自带的驱动脚本 `scripts/run.sh`。本 SKILL.md 既是 **agent 的行为契约**
（怎么挑 pipeline、怎么报状态、什么时候触发 finalize），也是 **fkit 调用细节
的归宿**（flow 解析、上传、spec 生成、下载、stage 落地）。

## 工作目录

| 路径 | 用途 |
|---|---|
| `fkit`（系统 PATH 上） | FlowHub CLI，由运维预装；本 skill 不再附带二进制副本。可用 `FKIT=<path>` 显式指定 |
| `skills/upstream-pipeline-fkit/scripts/run.sh` | 三段式 fkit 驱动脚本（`submit` / `poll` / `finalize`），由本 skill 独占 |
| `skills/upstream-pipeline-fkit/scripts/build_spec.py` | 由 `flow inspect` + 上传后的 fileId + pipelines.yaml 生成 spec |
| `skills/upstream-pipeline-fkit/scripts/materialize_stage.py` | FlowHub 下载产物 → `/data/output/<id>/stage/<category>/` + `stage/manifest.json` |
| `/data/output/<job-id>/.input_source` | 单行文本文件，记录用户传入的 **FlowHub 绝对路径**（如 `/Store/cohorts/gut/`、`/personal/<user>/runs/gut/`、`/openclaw/cohorts/gut/`）。**本 skill 直接对该路径调 `fkit ls` 发现 fileId——没有本地副本，也没有上传步骤**。带 upstream 段的 pipeline 强制要求 FlowHub 路径；orchestrator 会拒绝本地路径并提示"先 fkit upload"。|
| `/data/output/<job-id>/.input_source_kind` | 单行文本：`local` 或 `flowhub`。本 skill 跑的 upstream pipeline 该字段必为 `flowhub`（orchestrator 保证）；只有下游-only pipeline 才可能是 `local`，与本 skill 无关。|
| `/data/output/<job-id>/reproducibility/` | spec JSON、轮询快照、flow inspect 等审计文件 |
| `/data/output/<job-id>/stage/` | finalize 后 FlowHub 产物落地处（下游 read-only）；orchestrator 在准备阶段还会 `fkit download` FlowHub DATA_DIR 中的非测序文件（metadata.tsv、sample sheet 等）到这里供下游读取 —— **文件共享** 通道（同样是 FlowHub → 本地的下行链路） |
| `/data/output/<job-id>/stage/manifest.json` | 各 category 下产物索引（schema 见下方）|
| `/data/output/<job-id>/.pipeline_id` | 当前 FlowHub pipelineId（submit 后写入）|
| `/data/output/<job-id>/upstream_state.json` | 机器可读状态快照（poll/finalize 后刷新）|
| `/data/output/<job-id>/.fkit_done` | finalize 完成的时间戳标记 —— 下游唯一启动信号 |

调用 fkit 时使用系统 PATH 上预装的 `fkit`（运维负责安装/升级）。如果环境特殊
（多版本、容器内、非默认安装目录），用环境变量显式指定：

```bash
# 默认：从 PATH 找。登录自检请用非交互探针，**不要**用裸 `fkit project`
# （后者是交互式项目选择器，agent 的非 TTY shell 里会出乱码）
fkit flow list --limit 1 --json   # rc=0 ⇒ 登录正常

# 或显式指定路径（脚本会读取 $FKIT）
FKIT=/opt/flowhub/bin/fkit bash skills/upstream-pipeline-fkit/scripts/run.sh poll <job-id>
```

`scripts/run.sh` 启动时若 `fkit` 不在 PATH 也未通过 `$FKIT` 指向可执行路径，会
直接报错退出——不再回退到仓库内副本。

## Core Rule

**fkit 是唯一事实来源。** 不要编造 flowVersionId、fileId、taskName、portName、paramKey——
全部由 `skills/upstream-pipeline-fkit/scripts/run.sh submit` 在内部通过 `flow list / flow inspect /
file search` 查出，agent 不需要重复这些查询。Gateway 不再封装这套调用——本 skill
（`SKILL.md` + `scripts/`）就是 fkit 调用细节的唯一归宿。

## FlowHub 文件约定（与脚本保持一致）

| 远端路径 | 含义 |
|---|---|
| `<DATA_DIR>`（由用户提供）| 输入数据目录。可以是 `/Store/...`（社区资源订阅，只读）、`/personal/<user>/...`（个人空间）、`/openclaw/...`（项目空间）。**本 skill 只读** —— submit 不上传、不修改这里的任何文件。|
| `/output/openclaw-<job-id>/<task>/...` | 系统输出目录（FlowHub 自动写入；`outputDir` 在 spec 里固定为 `openclaw-<job-id>`）|

> 旧版（≤ 2026.4）把 FASTQ 从本地上传到 `/openclaw/<id>/input/`。该约定已废弃 ——
> 输入文件现在永远来自用户指定的 FlowHub 路径，**没有上传环节**。

## 工作流（agent 视角）

### Step 1 — 选 pipeline

读 `registry/pipelines.yaml`。每个 pipeline 的 `upstream.fkit_flow_keyword` 指向
FlowHub 上的目标 flow。常见映射：

| 用户意图 | pipeline |
|---|---|
| 全套宏基因组（QC + 去宿主 + 分类组成 + 下游统计/预测/可视化）| `metagenomics-full` |
| 仅上游分析（QC + 去宿主 + 分类组成）| `upstream-only` |

如果用户描述无法明确匹配任何 pipeline，按 AGENTS.md W5 处理。

### Step 2 — 展示计划并收集 override

向用户列出：
- pipeline 名 + `fkit_flow_keyword`
- `upstream.default_params` 列表
- 下游 skill 目录（catalog）
- 预估时间（pipeline `timeout_minutes`）

让用户提调参（如 `SOAPnuke.quality`、`kraken2.confidence`）。override 写到
`/data/output/<job-id>/reproducibility/params_override.yaml`：

```yaml
SOAPnuke:
  quality: 0.2
kraken2:
  confidence: 0.3
```

`scripts/build_spec.py` 会在生成 spec 时合并该 override。**绝不**修改 `pipelines.yaml`。

### Step 2.5 — 检查 input_routing 并核对绑定表（必读）

**input_routing**：多端口的 flow（如 `read1` + `read2`）应在 `pipelines.yaml`
`upstream.input_routing` 里写明哪个 glob 进哪个 port。没写时所有端口会回退到启发式
匹配，可能把同一个文件绑到多个端口。常见声明：

```yaml
upstream:
  input_routing:
    - { port: read1,  glob: "*_R1*.f*q*" }
    - { port: read2,  glob: "*_R2*.f*q*" }
    - { port: ref_db, glob: "human_ref*", task: bowtie2 }   # 目录类端口同理

    # ── 用户**主动选择** flow 自带的默认值（即使本地有同名文件）─────────
    - { port: silva_db, use_default: true, task: classify_taxa }
    # use_default: true → 直接跳过 Phase 1/2，强制走 Phase 3（flow 默认）。
    # 用途：DATA_DIR 里偶然有个 silva_xxx 目录，但你要的是 flow 内嵌的
    # 那份精心维护的 SILVA，而不是用户那份。glob 字段可省略。

    # ── 用户**禁止** flow 默认值兜底（生产/受监管流程常用）──────────────
    - { port: ref_genome, glob: "*.fa", default: false, task: bowtie2 }
    # default: false → 跳过 Phase 3 兜底。如果 Phase 1/2 没绑成，required
    # 端口直接报错（不让 flow 偷偷塞默认参考基因组进来）。

    # 字段一览：
    #   task         端口同名时限定到指定 taskName
    #   glob         锚定 fnmatch；use_default:true 时可省
    #   required     默认 true；false 时缺文件只 warn
    #   allow_reuse  默认 false；true 时一个上传可绑多个端口
    #   multi        默认 false；true 时把所有匹配文件全绑给该端口
    #   use_default  默认 false；true → 跳过 Phase 1/2 强制 flow 默认
    #   default      默认 true；false → 跳过 Phase 3 兜底（强制显式绑定）
```

如果 FlowHub DATA_DIR 里的文件命名不匹配（没有 `_R1`/`_R2`、用 `_1`/`_2`、或
`forward`/`reverse`），**先**让用户在 FlowHub 上把文件改名（FlowHub Web UI 或
`fkit` 重命名 API），**或者**让用户在 PR 里改这个 pipeline 的 `input_routing`
glob。**不要**让 agent 偷偷改 `pipelines.yaml`。

**file vs directory**：`scripts/build_spec.py` 会从 `flow inspect.inputs[]` 读取
端口类型（字段名：`inputType`/`type`/`dataType`/`kind`/`acceptType`/`portType` 或
`isDirectory`），区分该端口要的是文件还是目录：

- 文件端口只接受 `fkit ls` 里 `type=file` 的条目；目录端口只接受 `type=folder` 的
  条目——**绝不**会把目录 fileId 喂给文件端口，反之亦然。
- 若上传里同时有匹配的文件和默认值，优先用上传；否则用 flow 自带的 `defaultFiles`
  （文件端口）或 `defaultDirs`（目录端口）。
- 若端口在 flow inspect 里标记 `required: false`（或 `optional: true`），缺绑只产
  WARN；其它端口缺绑会让 submit 以 exit=2 退出且**不写**任何 spec。

**绑定表**：submit 会打印一张人类可读表（示例）：

```
Port → input bindings:
  bowtie2.ref_db   [DIR , required]  ←  human_ref_db          (routing)   [fid-DB]
  fastp.read1      [FILE, required]  ←  sampleA_R1.fastq.gz   (routing)   [fid-A1]
  fastp.read2      [FILE, required]  ←  sampleA_R2.fastq.gz   (routing)   [fid-A2]
  humann.tmp_dir   [DIR , optional]  ←  default_tmp           (default)   [fid-def-tmp]
  kraken2.opts     [FILE, optional]  ←  std_opts.txt          (default)   [fid-def-opts]
```

- `[FILE|DIR , required|optional]` 标签来自 flow inspect。
- `(routing|heuristic|default)` 标识绑定来源。
- agent **必须**把这张表复述给用户、并按下面规则汇报缺失：

| 情况 | 标记 | 处理 |
|---|---|---|
| 所有 open 端口都已绑 | ✅ | 直接告诉用户"5 个 input 都已就绪"，列出每个端口的来源 |
| required 端口未绑 | ❌ submit 已退出 (exit=2) | 转述 `ERRORS:` 行；指出缺哪个端口、是 FILE 还是 DIR；让用户：补传文件 → 调 `input_routing.glob` → 或确认用 `--required false` 软化 |
| optional 端口未绑且无 default | ⚠️ submit 仍成功 | 转述 stderr `WARN:` 行；提醒用户该端口将走 FlowHub 内部 fallback |
| 来源是 `default` | ℹ️ | 告诉用户"该端口用的是 flow 自带默认值（如参考库），不消耗 DATA_DIR 里的文件" |

任一 required 端口绑不到内容，**不要**强行重试 submit；先把缺失列表给用户。

### Step 2.6 — DRY RUN 预览（`plan`，**必做**）

在调 `submit`（会创建真实 FlowHub pipeline 并占用计算配额）之前，**必须**先
跑一次 dry run，把绑定结果交给用户确认：

```bash
bash skills/upstream-pipeline-fkit/scripts/run.sh plan <job-id> <pipeline>
```

`plan` 只调 `fkit flow list` + `fkit flow inspect` + `fkit ls <DATA_DIR>`，
**不调 `pipeline create`**。它会：

1. 读 `/data/output/<id>/.input_source` 拿到 FlowHub DATA_DIR；
2. 调 `fkit ls $DATA_DIR --json`（并对顶层文件夹再递归一层），把所有真实
   fileId 落到 `reproducibility/file_search_plan.json`；
3. 跑 `build_spec.py --dry-run`，打印 **Port → input bindings** 表，并把 spec
   写到 `reproducibility/pipeline_<id>_plan.json`、结构化报告写到
   `reproducibility/bindings_report.json`；
4. 紧接着打印一张 **Flow defaults available** 表，列出每个 open port 的
   `defaultFiles` / `defaultDirs`——这是用户选 `use_default: true` 时能拿到的
   东西。

注意 fileId **都是真的**（不是 `plan:xxx` 占位符），因为输入数据本来就驻留
在 FlowHub 上。`plan` 写出的绑定结果与 `submit` 时一致——除非 `plan` 与
`submit` 之间用户在 FlowHub 上又增删了文件。

**agent 把这两张表完整复述给用户**，按 Step 2.5 的规则汇报缺失/绑定来源，
并主动询问：
- 任何 required 端口绑不到 → 让用户调 `input_routing.glob` 或上传文件，**重新 `plan`**；
- 任何 source 是 `default` 的端口 → 询问"是否接受 flow 自带的默认？还是您要
  自己提供？"（接受就直接进 `submit`；不接受就用 `default: false` 强制显式绑定）；
- 任何 source 是 `heuristic` 的端口 → 提示"这是按名称猜的，确认正确吗？"
  正确就进 submit；不正确就用显式 `input_routing.glob` 锁定。

**只有在用户对绑定表明确点头之后**，才进入 Step 3 调 `submit`。`plan` 可重复
跑多次，每次都覆盖 `bindings_report.json` / `pipeline_<id>_plan.json`，**完全
不创建 FlowHub pipeline、不消耗计算配额**——只读元数据 + `fkit ls` 而已。

### Step 3 — 启动（gateway 调用本 skill 的执行端）

```bash
bash gateway/gateway.sh <pipeline> <flowhub-data-dir> \
  /data/output/<job-id>/reproducibility/params_override.yaml
```

`<flowhub-data-dir>` 是用户给的 **FlowHub 绝对路径**（例如
`/Store/cohorts/gut/`、`/personal/<user>/runs/gut/`）。orchestrator 只做：
把该路径写入 `/data/output/<id>/.input_source`、`fkit download` FlowHub 上的非测序
文件（metadata、sample sheet）到 `/data/output/<id>/stage/` 供下游读取、写
`reproducibility/pipeline.yaml`、pin 下游 Dockerfile，然后把控制权交还 agent。
**输入 FASTQ 永远留在 FlowHub**——本 skill 通过 `fkit ls` 发现 fileId，引用，
然后提交。

```bash
bash skills/upstream-pipeline-fkit/scripts/run.sh submit <job-id> <pipeline>
```

该命令内部完成：读 `/data/output/<id>/.input_source` 拿到 FlowHub DATA_DIR → 解析 flow
（`flow list` + `flow inspect`）→ `fkit ls $DATA_DIR --json` 刷新文件清单（无
上传）→ 生成 spec → `pipeline create` → 把 `pipelineId` 写到
`/data/output/<id>/.pipeline_id`，同时把状态摘要写到 `/data/output/<id>/upstream_state.json`。
**不阻塞**，立即返回。

> 一次性 / CI 场景可设置 `OPENCLAW_AUTO_SUBMIT=1`，让 orchestrator 自动驱动
> `scripts/run.sh submit`；交互式 agent 会话**不要**依赖这个开关。

向用户确认："已提交到 FlowHub，pipelineId=`<...>`，进入运行。下次更新约 10 分钟后。"

### Step 4 — 每 10 分钟轮询并汇报

```bash
bash skills/upstream-pipeline-fkit/scripts/run.sh poll <job-id>
```

输出格式：

```
pipelineId: <...>
status: 1 (total=10 closed=2 success=3 running=2 pending=3 failed=0 stopped=0)
STATUS=1
```

最后一行 `STATUS=<code>` 是机器可读的状态码（见下方映射）。**节奏：每 10 分钟一次**，
节奏由 agent / heartbeat / scheduled wakeup 实现，**不要**用 `sleep 600` 阻塞。

每次轮询后向用户报告（模板）：

```
⏱  FlowHub 进度 — pipelineId=<...>  T+<elapsed>m
   状态：RUNNING (1)
   有效节点 N=<total - closed>：✓<success> ▶<running> …<pending> ✗<failed>
   当前在跑：<jq 出 tasks[]|select(.status==0)|.nodeName>
   下次更新：10 min 后
```

报告时**隐藏** `TaskStatusEnum.CLOSE` (-3) 的节点；用 `summary.total - summary.closed`
作为有效总数，不要只看 `progressPercent`。

每次 poll 的全量响应都留在 `/data/output/<id>/reproducibility/poll_*.json`，可事后审计。

### Step 5 — 终态分支

| `STATUS=` | 含义 | 处理 |
|---|---|---|
| `2` | SUCCESS | 进入 Step 6 |
| `-1` | FAIL | 从最后一个 `poll_*.json` 选 `tasks[]\|select(.status==-1)` 的节点，报 `nodeName + errMsg`；指向 FlowHub Web UI 任务详情；**不要自动重试** |
| `-2`/`-3` | STOP / STOPPING | 报告"已（被）停止"，等用户指示 |

### Step 6 — finalize：下载并落地到 stage/

```bash
bash skills/upstream-pipeline-fkit/scripts/run.sh finalize <job-id> <pipeline-name>
```

脚本会：
1. `fkit download /output/openclaw-<id>/ /data/output/<id>/.fkit_download/ -r`
   （positional 参数 `<SRC> <DEST> [-r]`；`-r` 递归下载远端目录）
2. 按 `pipelines.yaml` 里 `upstream.output_to_stage` 的 glob 把文件硬链接/拷贝到
   `/data/output/<id>/stage/<category>/` —— **文件共享**：下游容器只读挂载这个目录
3. 写 `/data/output/<id>/stage/manifest.json`（schema：`{job_id, pipeline, samples:[...],
   <category>: {<sample>: <relpath>, ...}}`；下游 skills 通过 category 名读对应产物）
4. 写时间戳到 `/data/output/<id>/.fkit_done`、刷新 `/data/output/<id>/upstream_state.json`
   ——**状态共享**：下游 / heartbeat / `prepare_downstream.sh` 都通过 `.fkit_done`
   判断"上游已就绪"

向用户报告："上游完成，产物已落地 `/data/output/<id>/stage/`；现在进入下游。"

### 文件与状态共享契约（与 gateway 解耦）

| 信号 | 写者 | 读者 | 含义 |
|---|---|---|---|
| `/data/output/<id>/.input_source` | gateway/orchestrator.sh | 本 skill 的 `plan`/`submit` | 单行文本：用户的 **FlowHub** 绝对路径。`plan`/`submit` 通过 `fkit ls` 在该路径下发现 fileId——**没有上传，没有本地副本** |
| `/data/output/<id>/reproducibility/bindings_report.json` | `build_spec.py`（plan & submit 都写）| agent + heartbeat | 结构化绑定报告：`{mode: plan\|submit, bindings:[...], defaults_used:[...], missing_required:[...], missing_optional:[...], errors:[...]}`。**agent 必读 `defaults_used` 并向用户汇报**——这是 flow 默认值兜底的唯一审计入口 |
| `/data/output/<id>/reproducibility/pipeline_<id>_plan.json` | 本 skill `plan` | 审计 | DRY RUN 时生成的 spec，与 `submit` 时的真实 spec 结构一致，便于 diff |
| `/data/output/<id>/.pipeline_id` | 本 skill `submit` | agent + heartbeat | FlowHub pipelineId（云端句柄）|
| `/data/output/<id>/upstream_state.json` | 本 skill `poll`/`finalize` | agent + heartbeat | `{status, status_code, summary, last_poll, pipeline_id, updated_at}` |
| `/data/output/<id>/stage/<category>/...` | 本 skill `finalize` | 下游容器 (`/job/stage:ro`) | **文件共享**：上游产物 |
| `/data/output/<id>/stage/manifest.json` | 本 skill `finalize` | 下游 skills | category → sample → relpath 索引 |
| `/data/output/<id>/.fkit_done` | 本 skill `finalize` | `prepare_downstream.sh`, agent, heartbeat | **状态共享**：唯一可信的"上游就绪"信号 |

`prepare_downstream.sh` 在 pipeline 有 upstream 段时**会拒绝**启动容器，直到看到
`.fkit_done` + `stage/manifest.json`。agent 不需要手动同步——只要本 skill 的
`finalize` 跑完，下游就具备启动条件。

### Step 6.5 — Batch (per-sample) 上游

如果 pipeline 在 `upstream.batch.mode: per_sample` 下声明了批量模式，本 skill
会把同一条 flow **fan out 到 N 个 FlowHub pipeline**——每个样本一个，互相隔离
输出，但共用同一参考库/默认文件。**agent 不需要改命令**——`plan` / `submit` /
`poll` / `finalize` 这四个命令照常调，run.sh 在内部检测到 `batch.mode` 后自动
切到 batch 实现（`phase_*_batch`）。

#### 样本检测（`enumerate_samples.py`）

按 `upstream.batch.detect` 顺序尝试以下模式，首个返回 ≥1 样本即用。检测的输入
是 **FlowHub listing**（由 `fkit ls $DATA_DIR --json` + 顶层文件夹递归一层得到
的扁平表），**不是**本地文件系统：

| mode | 样本是什么 | sample_id | shared 文件 |
|---|---|---|---|
| `subdirectories` | FlowHub DATA_DIR 下的每个顶层子目录（`type=folder`）| 子目录名 | DATA_DIR 顶层的非目录文件（ref DB、metadata 等）|
| `paired_by_basename` | 按 `*_R1*` / `*_R2*`（也认 `_1`/`_2`、`forward`/`reverse`）配对的顶层文件组 | 共同前缀 | 顶层不匹配的其它文件 |
| `single_file` | 每个顶层测序文件（`*.fastq*` / `*.fq*` / `*.bam` / `*.cram` / `*.sra`）| 去掉所有后缀的 stem | 顶层非测序文件 |

sample_id 会被清洗到 `[A-Za-z0-9._-]+`——清洗后冲突会显式报错。
samples.json 中的 paths 是**相对 FlowHub DATA_DIR** 的（`sampleA/R1.fq.gz` 或
`metadata.tsv`），与 `file_search.json` 的 `name` 字段一一对应。

#### 命名约定（用户/agent 都要知道）

每个样本的 FlowHub pipeline：

```
name       = openclaw-<job-id>-<sample-id>
outputDir  = openclaw-<job-id>-<sample-id>
（远端输出落在  /output/openclaw-<job-id>-<sample-id>/  ）
```

这是"openclaw-<job-id>"在 batch 模式下的扩展形式——agent 报状态时应该使用
完整带样本后缀的名字，方便用户去 FlowHub Web UI 对照。

#### fileId 解析策略（无上传）

- **shared 文件**：FlowHub 上**已存在**——所有 N 个 per-sample spec 共享同一个
  fileId（参考基因组永远只占一份云端配额，自动）。
- **per-sample 文件**：FlowHub 上**已存在**，每个 fileId 独立。
- `fkit ls` 全局只跑一次（`reproducibility/file_search.json`），每个样本的 spec
  用 `file_search_<sample_id>.json` 视图（= shared basename ∪ 该样本的 basename）
  作为绑定输入——纯文件 ID 子集，无 IO。
- 端口绑定的优先级（routing → heuristic → flow default）与 Step 2.5 一致；
  `per_sample: false` 标志仅用于**自我文档**——是否共享由检测决定。

#### plan 模式（batch）

`plan` 只预览**一个**代表性样本（排序后第一个）的绑定表，并打印 batch 概览：

```
BATCH PLAN: 20 sample(s) detected via paired_by_basename.
  Submission count: 20 (one FlowHub pipeline per sample).
  Naming: spec.name = spec.outputDir = openclaw-<job-id>-<sample-id>
  Sample IDs:
    - sampleA  (2 files)
    - sampleB  (2 files)
    ...
  Shared files (referenced by every sample, NOT re-uploaded — they live on FlowHub):
    - human_ref_db
    - metadata.tsv
```

所有样本走同一 flow + 同一 input_routing + 同一 shared 集合，所以一个样本绑
得对，其它样本也绑得对。agent 把代表样本的 bindings 表 + 上面的 batch 概览
都给用户看，再 `submit`。

#### poll / finalize 行为

- `poll` 调 `fkit pipeline get <pid>` for each sample，写
  `reproducibility/poll_<ts>/<sample-id>.json`。stdout 末行 `STATUS=<code>`
  是**聚合**值：
  | 聚合规则 | code |
  |---|---|
  | 任一 FAIL / submit-time 失败 | -1 |
  | 任一 STOP/STOPPING（且无 FAIL）| -2 / -3 |
  | 任一 RUNNING/WAITING（且无 FAIL/STOP）| 1 |
  | 全部 SUCCESS | 2 |
- `finalize` **拒绝**在任一样本未达 SUCCESS 时执行——确保 `stage/manifest.json`
  完整。按 `output_to_stage` glob 把每个样本的产物落到
  `stage/<category>/<sample-id>/<filename>`（**带 sample 子目录**，避免同名
  冲突），再合并 `stage/.manifest_fragments/<sid>.json` → `stage/manifest.json`。
- **`finalize` 可断点续跑（resumable）。** batch 顺序下载 N 个样本可能耗时
  15–30 分钟；若进程被系统杀掉（TTL / OOM 等），**直接再跑一次 `finalize` 即可**
  ——脚本按样本保存 `.dl_done` 标记和 manifest 分片，已完成的样本会被跳过，只
  补下缺失样本，**绝不**清空 `$SCRATCH` 或已有分片重头再来。若本轮仍有样本下载
  失败，状态记为 `FINALIZE_PARTIAL` 并以 exit 1 退出，再次调用即继续。

新增 / 变化的状态文件：

| 文件 | 写者 | 含义 |
|---|---|---|
| `/data/output/<id>/reproducibility/samples.json` | `submit`/`plan` 调 `enumerate_samples.py` | 从 FlowHub listing 检测出的 samples + shared 列表 + detect_mode（路径是 FlowHub DATA_DIR 内的相对路径）|
| `/data/output/<id>/.batch_state.json` | `phase_submit_batch` | `{mode:batch, samples:[{sample_id, pipeline_id, pipeline_name, output_dir, spec_path, report_path, status, status_code, last_poll}, ...]}` |
| `/data/output/<id>/reproducibility/pipeline_<id>_<sid>_spec.json` | `phase_submit_batch` | 每个样本的 FlowHub spec |
| `/data/output/<id>/reproducibility/bindings_report_<sid>.json` | `build_spec.py --sample-id <sid>` | 每个样本的结构化绑定报告 |
| `/data/output/<id>/reproducibility/file_search_<sid>.json` | `phase_submit_batch` | 每个样本可见的 fileId 子集 |
| `/data/output/<id>/reproducibility/poll_<ts>/<sid>.json` | `phase_poll_batch` | 每个样本每次 poll 的全量快照 |
| `/data/output/<id>/stage/<category>/<sid>/...` | `materialize_stage.py --sample-id <sid>` | 每个样本的产物子目录（避免文件名冲突）|
| `/data/output/<id>/stage/.manifest_fragments/<sid>.json` | `materialize_stage.py --sample-id <sid>` | 合并前的每个样本 manifest 片段 |
| `/data/output/<id>/stage/manifest.json` | `phase_finalize_batch` 合并产生 | `{mode:batch, samples:[...], <category>:{<sid>: relpath, ...}, flowhub:[{sample_id, pipeline_id, output_dir}, ...]}` |

#### Strict Rules（batch 增量）

- batch 的 sample 数由 `enumerate_samples.py` 决定，**不能**手工编辑 sample
  列表——如果检测结果不对，调 `upstream.batch.detect` 或重命名输入文件。
- batch 模式下**禁止**对未完成的 batch 调 `finalize`——会被脚本拒绝。先等
  `STATUS=2`（所有样本 SUCCESS）。
- 单个样本失败**不**自动重试整批；agent 把失败样本列出来让用户决策。
- batch 模式不与 `--required true` 的 single-shot 模式混用——同一个 pipeline
  要么是 batch 要么是 single，由 `upstream.batch:` 块的存在与否决定。

### Step 7 — 触发下游（如 pipeline 有 downstream 段）

调 AGENTS.md W3 的下游两阶段流程：

```bash
bash gateway/prepare_downstream.sh <job-id> <pipeline-name>
# Planner 从 downstream.skills catalog 里挑子集，进容器定制脚本：
bash gateway/attach.sh --shell
# 跑：
bash gateway/run_downstream.sh <job-id> --skills <s1,s2>
```

## Pipeline status 映射

| Code | Enum | 含义 |
| ---: | --- | --- |
| -3 | `STOPING` | 停止中 |
| -2 | `STOP` | 已停止 |
| -1 | `FAIL` | 运行失败 |
|  0 | `WAITING` | 等待 |
|  1 | `RUNNING` | 运行中 |
|  2 | `SUCCESS` | 运行完成 |

## Task / node status 映射

| Code | Enum | 含义 |
| ---: | --- | --- |
| -3 | `CLOSE` | 关闭状态（汇报时隐藏） |
| -2 | `STOP` | 已停止 |
| -1 | `FAIL` | 运行失败 |
|  0 | `RUNNING` | 运行中 |
|  1 | `SUCCESS` | 运行成功 |
|  2 | `PENDING` | 等待运行 |

## Failure Handling

- `Input file corresponding nodes must be in an open state` — `scripts/build_spec.py`
  绑文件到了 `openStatus != 1` 的节点。检查 `reproducibility/flow_inspect.json`，
  对脚本反馈 bug。
- `There is no files in the input port` / `输入port没有传入文件` — open input 端口
  既没有匹配到 FlowHub DATA_DIR 里的文件、又没有 `defaultFiles`。**首查** pipeline
  的 `input_routing` 里该端口的 `glob` 是否真的命中 DATA_DIR 中的文件（看 plan/
  submit 时打印的 `Port → File` 表 + `reproducibility/file_search.json`）。不命中
  就让用户在 FlowHub 上把文件改名 / 添加缺失文件，或在 PR 里改
  `input_routing.glob`；命名规范完全没救时再考虑 pin `fkit_flow_version_id`。
- **同一份文件被绑到所有端口** — pipeline 没声明 `input_routing` 且端口
  `namePattern` 太宽泛（如 `*.fastq.gz` 同时匹配 R1/R2）。在 `pipelines.yaml` 里
  补 `input_routing`（见 Step 2.5），让 R1 与 R2 各走各的 glob。
- **整个目录被当成一个 fileId 绑给端口** — 目录类型条目通过 `is_dir_entry()`
  过滤；如果仍出现，看 `reproducibility/file_search.json` 里 `type/kind/isFolder`
  字段并补到 `_DIR_KIND_VALUES`。
- **`fkit ls` 失败** — submit 在 `fkit ls` 失败时直接退出 1，因为没有 fileId 就
  没法 build_spec。常见原因：
  1. DATA_DIR 路径不存在或拼写错。让用户确认（FlowHub Web UI 直接看一眼）。
  2. 项目对该路径没有读权限。让用户切换到自己有访问权限的路径（常见：
     `/personal/<userid>/...`、`/<project>/...`、`/Store/<community>/...`）。
  3. fkit 凭据过期。让用户 `fkit login -k <AccessKey> -s <AccessSecret>` 再试。
- **`plan` 显示绑定全对，但 `submit` 时少文件** — 用户在 plan 与 submit 之间
  动了 FlowHub 上的文件。直接重跑 `plan` 让用户看新的绑定表，确认无误后再 submit。
- **`fkit pipeline create` 失败但 submit 退出 0** — 看 `reproducibility/pipeline_create.json`
  的 `code` / `msg`；常见 `code=400` 是 `inputs[]` 里 fileId 找不到（DATA_DIR
  里的文件在 plan/submit 之间被删了）→ 重跑 `scripts/run.sh submit` 让
  build_spec.py 重新索引。
- `flow list` 多个候选 — 在 `pipelines.yaml` 给该 pipeline 加 `fkit_flow_version_id`
  显式锁版本，重提交。
- 凭据未登录 — 让用户 `fkit login -k <AccessKey> -s <AccessSecret>`，**不要**把
  凭据写入任何文件。

## Strict Rules

- **必须先 `plan` 再 `submit`。** 不允许直接 `submit`——`submit` 会创建真实的
  FlowHub pipeline 并占用计算配额。`plan` 只查 flow 元数据 + `fkit ls`，完全
  免费。agent 必须把 `plan` 输出的绑定表与 Flow defaults 表交给用户，收到明确
  确认后才能 `submit`。
- **不在本地起任何上游 Docker 容器**——所有上游都跑在 FlowHub。
- **没有上传**。输入数据必须事先存在于 FlowHub 上由用户指定的路径下。如果
  数据还在本地，让用户先用 `fkit upload` 自己传上去，再把 FlowHub 路径告诉 agent。
  agent **不**代为上传——大文件上传是用户的运维操作，不属于 agent 的职责。
- **不**直接调 `docker run`；下游容器由 `prepare_downstream.sh` 统一启动。
- **不**写凭据到磁盘；AccessKey/AccessSecret 仅作 `fkit login` 参数。
- **不**修改 `registry/pipelines.yaml`；调参写 `params_override.yaml`。
- **不**阻塞会话进程做长 `sleep`；10 分钟轮询节奏由外层编排实现。
- spec 必须用文件（`pipeline_<id>_spec.json`），不内联 JSON。
- 失败不自动重试，先报告再等用户决定。
- finalize 之后才允许触发下游；`.fkit_done` 未写出时不要调 `prepare_downstream.sh`。
- **`poll` 返回 `STATUS=2`（SUCCESS）不是终点——必须接着调 `finalize`。** 严禁
  为了"省事"手工 `fkit download` 云端产物、手工 `merge_metaphlan_tables.py`
  绕过 finalize：那样 `stage/` 永远是空的、`stage/manifest.json` / `.fkit_done`
  都不存在，下游无输入、`prepare_downstream.sh` 会拒绝启动。`upstream_state.json`
  的 `status` 必须从 `SUBMITTED`→`SUCCESS`→`FINALIZED` 走完整条链。
- **所有产物只落在 `/data/output/<job-id>/` 下，绝不写到 workspace、cwd、`$HOME`
  或 `/tmp`**（见 AGENTS.md W0）。任务 prompt 里的相对输出路径一律解析为
  job 目录下的绝对路径。

