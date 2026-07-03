---
name: skill-adapter
description: >
  把外部 Skill（Anthropic Skills、第三方 SKILL.md）静态改写为符合 BioLine 契约
  的下游 Skill 草稿。读 /job/stage/skill-adapter/<external-skill>/，写
  /job/analysis/skill-adapter/<adapted-name>/。AST 静态分析（不执行外部代码）+
  路径改写 + 依赖审计 + 报告。仅在 openclaw/base:1.0.0 容器里运行。
allowed-tools: Bash(python *) Read Write
disable-model-invocation: true
---

# Skill-Adapter Skill

你在 `openclaw/base:1.0.0` 容器内运行（轻量级镜像，只装 pyyaml/jinja2/markdown/pandas/numpy）。
容器挂载：

| 路径 | 权限 | 内容 |
|---|---|---|
| `/job/stage/skill-adapter/<external-skill>/` | ro | 待改写的外部 Skill 源码 |
| `/job/analysis/skill-adapter/` | rw | 改写产物（草稿 Skill + 报告） |
| `/job/reproducibility/` | rw | meta JSON、日志 |
| `/job/reproducibility/skill_snapshots/skill-adapter/` | ro | 本 Skill 的完整快照（含 `assets/`、`references/`） |
| `/pipeline/scripts/` | ro | `reference_skill-adapter.py` |

无网络访问（`--network none`），禁止 `pip install`、`exec`/`eval`、联网下载。

---

## 输入

要求用户在 `/job/stage/skill-adapter/<external-skill>/` 下放置一个完整的外部 Skill
文件夹。期望布局：

```
/job/stage/skill-adapter/<external-skill>/
├── SKILL.md           （或任意 *.md，可选）
└── *.py               （至少一个；多个 .py 时优先 reference_*.py）
```

可选辅助文件：

- `/job/stage/skill-adapter/intent.txt` — 一行说明改写后的目标场景（注入草稿描述）
- `/job/stage/skill-adapter/<external-skill>/columns.yaml` — 数据列契约

## 输出

```
/job/analysis/skill-adapter/<adapted-name>/
├── SKILL.md                                    ← 改写草稿（已套 BioLine 模板）
├── scripts/reference_<adapted-name>.py         ← 改写草稿（路径常量 + meta JSON tail）
├── adaptation_report.md                        ← 人类可读的改动说明 + 下一步清单
├── dependencies_audit.json                     ← 每镜像依赖覆盖度 + 推荐镜像
├── naming_consistency.json                     ← 4 处命名一致性自检
└── unsafe_findings.json                        ← block/warn/info 三级清单

/job/analysis/skill-adapter/skill-adapter_meta.json   ← 本 Skill 自身的契约 meta
```

## 工作流

**Step 1 — 收集**：扫描 `/job/stage/skill-adapter/<external-skill>/`，读取 `SKILL.md`
（若有），列出全部 `*.py`。

**Step 2 — 静态分析**（**仅 ast.parse；绝不 exec/eval/import 外部代码**）：

- imports → 比对 `assets/image_packages.yaml`，对每个候选镜像（`base` / `downstream` / `downstream-dl`）算覆盖度，标记缺包。
- 网络模块导入：`urllib*`/`requests`/`httpx`/`aiohttp`/`socket`/`http.client`/`urllib3`/`ftplib`/`smtplib`/`paramiko` → block。
- 安装/克隆 subprocess：argv0 ∈ `{pip, pip3, conda, mamba, apt, apt-get, curl, wget, git}` → block。
- 交互式 I/O：`input()`/`getpass.getpass`/`click.prompt` → warn。
- 越权写入：字面量路径 `^(/etc|/var|/usr|/root|/home|/opt|~)` 传给 `open(..., "w")`/`Path.write_*`/`shutil.copy*` → block。
- 硬编码相对路径：`./input`、`./output`、`data/`、`output/` → info（自动建议改写为 `STAGE_DIR`/`ANALYSIS_DIR`）。

**Step 3 — 生成草稿**：从 `assets/template_SKILL.md` 与 `assets/template_reference.py`
渲染。外部代码以 *注释块* 嵌入草稿，每条 block 级 finding 上方插入
`# TODO[skill-adapter] ...` 标记，确保 LLM 在 customization 阶段看得到。

**Step 4 — 自检 + 落盘**：4 处命名一致性、依赖审计、推荐镜像（取最轻能容纳全部依赖
的镜像）、`skill-adapter_meta.json`。

## Strict Rules

1. **NEVER** `exec`/`eval`/`compile`/`importlib.import_module` 外部代码。
2. **NEVER** `pip install`、联网、`subprocess` 调用 `pip`/`curl`/`wget`/`git`。
3. **NEVER** 写 `/job/analysis/skill-adapter/` 之外的路径（脚本自带 sandbox 断言）。
4. **NEVER** 覆盖既有 `skills/<adapted-name>/` —— 草稿留在 `analysis/` 下，由人类移动。
5. **NEVER** 自称 "已完成适配"。所有产物都是 *草稿*，必须按 contributor_guide.md §11 端到端验证。
6. 发现外部 Skill 引入的依赖在三镜像下均缺失 → 在 `adaptation_report.md` 的 Next steps
   里指引人类阅读 contributor_guide.md §7（**绝不** 自动改 Dockerfile）。

---

## 执行模型（两阶段）

参见 contributor_guide.md §1。

- **Prepare**（`gateway/prepare_downstream.sh <job-id> skill-adaptation`）：起
  `openclaw/base:1.0.0` 容器，stage `reference_skill-adapter.py` 至 `/pipeline/scripts/`。
- **Customize**：LLM 复制 `/pipeline/scripts/reference_skill-adapter.py` →
  `/job/reproducibility/generated_scripts/skill-adapter_<ts>.py`，按本 job 设置
  `EXTERNAL_NAME`、`ADAPTED_NAME`（顶部两个常量）。
- **Execute**（`gateway/run_downstream.sh <job-id> --skills skill-adapter`）：跑
  定制副本，产物落 `/job/analysis/skill-adapter/<adapted-name>/`。
