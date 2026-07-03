# BioLine Skill Contract — quick reference for skill-adapter

Excerpted from `contributor_guide.md`. Keep in sync if the guide changes.

## Naming (4 must match exactly)

1. Folder: `skills/<skill-name>/`
2. SKILL.md frontmatter: `name: <skill-name>`
3. Entry script: `scripts/reference_<skill-name>.py`
4. `registry/pipelines.yaml` entry: `<skill-name>` under `downstream.skills`

`prepare_downstream.sh` looks for `skills/<name>/scripts/reference_<name>.py`
at exactly that path. Any drift triggers a WARNING.

## Required directory layout

```
skills/<skill-name>/
├── SKILL.md                              ← required
├── scripts/
│   ├── reference_<skill-name>.py         ← required (container entry)
│   └── <helper>.py                       ← optional; NOT auto-staged when
│                                            reference_*.py exists — keep
│                                            the entry single-file or read
│                                            helpers from the snapshot at
│                                            /job/reproducibility/skill_snapshots/<name>/
├── assets/                               ← optional: templates, tables
└── references/                           ← optional: docs / examples
```

## SKILL.md frontmatter (4 fields)

```yaml
---
name: <skill-name>
description: > 一句话：触发时机、输入、产出
allowed-tools: Bash(python *) Read Write
disable-model-invocation: true
---
```

Body must include: mounts table, Responsibilities, Input/Output Conventions
(use `/job/stage|analysis/<skill-name>/`), Workflow (Step 1 → 2 → 3),
Strict Rules, "执行模型（两阶段）" section.

## Reference script contract (§5)

```python
STAGE_DIR     = "/job/stage/<skill-name>"            # ro
ANALYSIS_DIR  = "/job/analysis/<skill-name>"         # rw
GENERATED_DIR = "/job/reproducibility/generated_scripts"

# Missing required input → sys.exit(1) (do not fabricate).
# At the end, write:
meta = {"skill": "...", "packages": {...}, "parameters": {...},
        "random_seed": 42, "decisions": "..."}
# to ANALYSIS_DIR / "<skill-name>_meta.json"
```

Non-zero exit ⇒ recorded in `downstream_manifest.json`. **Forbidden:**
`pip install`, network downloads, writes outside `/job/`.

## Container mounts (§6)

| Container | Host | Mode |
|---|---|---|
| `/job/` | `/data/output/<job-id>/` | rw |
| `/job/stage/` | `/data/output/<job-id>/stage/` | **ro** |
| `/job/analysis/` | `/data/output/<job-id>/analysis/` | rw |
| `/job/reproducibility/` | `/data/output/<job-id>/reproducibility/` | rw |
| `/pipeline/scripts/` | `/data/output/<job-id>/.pipeline_scripts/scripts/` | **ro** |

Default runtime: `--network none --cap-drop ALL --memory 16g --cpus 8`
(overridable via the optional `runtime:` block in `pipelines.yaml`).

## Image selection (§7)

- 文本/配置/简单表格 → `openclaw/base:1.0.0` (lightweight, ~150 MB)
- 统计 / ML / R → `openclaw/downstream:1.1.0`
- PyTorch / Transformer → `openclaw/downstream-dl:1.0.0`
- 缺包：编辑 `images/<image>/Dockerfile`，pin 版本，重建并 bump tag，同步
  `pipelines.yaml`。**skill-adapter never edits Dockerfiles itself** — it
  flags missing deps in `dependencies_audit.json` and report.

## Pipeline registration (§8)

Append to `registry/pipelines.yaml` (do not edit existing entries):

```yaml
  <pipeline-name>:
    description: "<input → steps → output>"
    downstream:
      image: "openclaw/<image>:<tag>"
      skills:
        - <skill-name>
    timeout_minutes: <minutes>
```

`downstream.skills` is a CATALOG (not an ordered list); the Planner picks
the subset via `gateway/run_downstream.sh --skills s1,s2,...`.
