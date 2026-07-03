---
name: __NAME__
description: >
  __DESCRIPTION__
  （由 skill-adapter 自 `__SOURCE__` 改写生成的草稿；触发条件、输入产出请人工补全。）
allowed-tools: Bash(python *) Read Write
disable-model-invocation: true
---

# __NAME__ Skill (draft)

> 本文档由 `skill-adapter` 静态生成。请逐节复核并替换所有 `<TODO>` 占位。

你在 `__IMAGE__` 容器内运行。容器挂载：

| 路径 | 权限 | 内容 |
|---|---|---|
| `/job/stage/__NAME__/` | ro | 上游/用户提供的输入 |
| `/job/analysis/__NAME__/` | rw | 下游分析结果（写这里） |
| `/job/reproducibility/` | rw | 可复现性材料 |
| `/pipeline/scripts/` | ro | `reference___NAME__.py` |

无网络访问（`--network none`）。

---

## 输入

<TODO 列出 `/job/stage/__NAME__/` 期望的文件、格式、命名约定>

## 输出

```
/job/analysis/__NAME__/
├── <TODO 主要产物>
└── __NAME___meta.json
```

## 工作流

**Step 1 — 读数据**：<TODO>

**Step 2 — 分析**：<TODO>

**Step 3 — 归档**：写主要产物 + `__NAME___meta.json`。

## Strict Rules

1. 缺必填输入 → `sys.exit(1)`，不伪造。
2. 不 `pip install`、不联网、不写 `/job/` 之外。
3. 末尾必须写 `/job/analysis/__NAME__/__NAME___meta.json`（contributor_guide.md §5）。

---

## 执行模型（两阶段）

- **Prepare**（`gateway/prepare_downstream.sh <job-id> <pipeline>`）：起 `__IMAGE__`
  容器，stage `reference___NAME__.py` 至 `/pipeline/scripts/`。
- **Customize**：复制 `/pipeline/scripts/reference___NAME__.py` →
  `/job/reproducibility/generated_scripts/__NAME___<ts>.py`，按本 job 改写。
- **Execute**（`gateway/run_downstream.sh <job-id> --skills __NAME__`）：跑定制副本。
