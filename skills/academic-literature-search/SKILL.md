---
name: academic-literature-search
description: >
  学术文献检索工具，集成 Semantic Scholar、Crossref、arXiv、PubMed 等数据库，
  提供全面的文献检索、过滤、排序与多格式输出服务。
  用户询问文献、论文、研究背景、引用相关问题时触发。
  在 OpenClaw Gateway（host 进程）运行，需要网络访问，不可在容器内使用。
allowed-tools: Bash(python3 *) Read Write
disable-model-invocation: false
---

# 学术文献检索 Skill

你在 **OpenClaw Gateway（host 进程）** 内运行，**不在任何分析容器内**。此 skill 需要网络访问，容器内（`--network none`）不可使用。

---

## 支持的数据库

| 数据库 | 数据量 | 优势领域 | 速率限制 |
|--------|--------|----------|----------|
| Semantic Scholar | 2.33亿+ | AI、计算机科学、多学科 | 100请求/5分钟 |
| Crossref | 1.4亿+ | 期刊文章、官方DOI | 无限制（礼貌使用） |
| arXiv | 220万+ | 预印本、计算机、物理、数学 | 无限制 |
| PubMed | 3500万+ | 生物医学、生命科学 | 10请求/秒 |

---

## 工作流

### Step 1 — 解析检索意图

理解用户的检索需求：主题、时间范围、数据库偏好、输出格式。

### Step 2 — 构建检索查询

支持：
- 自然语言：`deep learning in medical imaging`
- 布尔运算：`attention mechanism AND transformer NOT BERT`
- 字段限定：`title:metagenomics author:Qin`
- 范围过滤：`year:2020-2024 citations:>50`

### Step 3 — 执行检索

```python
# 调用 agent.py 或直接使用各数据库 API
# 优先使用 Semantic Scholar（多学科覆盖好）
# 宏基因组/生物医学查询追加 PubMed
```

### Step 4 — 结果处理

- **去重**：基于 DOI、标题、作者多维度去重
- **排序**：引用数、年份、相关性（由用户指定，默认相关性）
- **过滤**：期刊类型、开放获取、最小引用数

### Step 5 — 输出结果

默认输出 Markdown 格式（适合对话展示）。用户可指定：

| 格式 | 适用场景 |
|---|---|
| Markdown | 对话阅读 |
| BibTeX / RIS | 文献管理软件 |
| JSON | 程序处理 |
| CSV | 数据分析 |

结果保存到本地文件时，写到 Gateway 工作目录（不写到 job/ 子目录）。

---

## 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| query | string | 必需 | 检索查询 |
| databases | array | `["semantic_scholar"]` | 使用的数据库 |
| max_results | integer | 20 | 最大返回数量（上限 200） |
| year_range | string | — | 如 `"2020-2024"` |
| sort_by | string | `"relevance"` | relevance / citations / year |
| open_access_only | boolean | false | 仅开放获取 |
| min_citations | integer | — | 最小引用数 |
| output_format | string | `"markdown"` | 输出格式 |

---

## 环境配置（可选）

```bash
# API 密钥可提升速率限制，不设置也可运行
SEMANTIC_SCHOLAR_API_KEY="your_key_here"
CROSSREF_API_EMAIL="your_email@example.com"
PUBMED_API_KEY="your_key_here"
```

---

## 错误处理

- **网络错误**：自动重试，提供降级方案（切换数据库）
- **API 限速**：指数退避，提示用户配置 API key
- **无结果**：提供扩展搜索建议（放宽时间范围、换数据库）

---

## 注意事项

- 检索查询会发送到第三方 API（Semantic Scholar、Crossref、PubMed、arXiv）
- 不在分析容器内运行——容器无网络访问
- 检索结果不写入 `/data/output/<job-id>/` 目录，那是分析数据的专属区域
