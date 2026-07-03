# Differential Abundance — Usage Guide

## Overview

Differential abundance testing identifies taxa whose abundance differs between groups while respecting the compositional nature of microbiome data.

In `openclaw/downstream:1.1.1`, **ALDEx2 is the only differential-abundance method installed**:

| Method | Best for | Companion script |
|---|---|---|
| **ALDEx2** | 2-group compositional comparison (CLR + Dirichlet Monte-Carlo Wilcoxon) | `scripts/aldex2_analysis.R` |

Other methods commonly cited in microbiome papers (`ANCOM-BC2`, `MaAsLin2`, `DESeq2`, `phyloseq`-based workflows, `LEfSe`) are **not installed** in the standard image — the skill will halt with a clear message if asked to use one. See `images/downstream/Dockerfile` CHANGELOG for the recipes to add them (ANCOMBC in particular requires rustup, libgmp-dev/libuv1-dev/libgsl-dev, and a CVXR 1.0-12 pin).

## Prerequisites

ALDEx2 + ggplot2 are already in `openclaw/downstream:1.1.1`. No `BiocManager::install` is needed at runtime:

```r
# Already present in the image:
library(ALDEx2)
library(ggplot2)
```

If you're testing outside the container, install:

```r
BiocManager::install("ALDEx2")
install.packages("ggplot2")
```

## Quick Start

Tell your AI agent what you want:
- "Find differentially abundant taxa between treatment and control" → ALDEx2

## Example Prompts

### Simple 2-group comparison (ALDEx2)
> "Run ALDEx2 to compare species abundance between case and control"

> "Find differentially abundant genera between healthy and IBD samples"

### Filtering and interpretation
> "Drop taxa present in fewer than 10% of samples before testing"

> "Which taxa have |effect| > 1 and q < 0.05?"

## What the Agent Will Do

1. Confirm input is integer counts (refuse relative-abundance silently — use `merged_count_table.tsv` from `microbiome-profile-merge`).
2. Filter low-abundance / low-prevalence taxa (defaults: ≥10% prevalence, mean count ≥ 10).
3. Run ALDEx2 with Dirichlet Monte-Carlo (128 MC samples; 256+ for publication-grade).
4. Apply BH-FDR correction.
5. Filter by effect size and significance threshold.
6. Generate the results table, volcano plot, and audit metadata.

## When ALDEx2 Is NOT Appropriate

ALDEx2 is designed for **2-group, no-covariate** comparisons. The agent should refuse rather than misapply it when:

| Design | Why ALDEx2 isn't appropriate | What would be needed |
|---|---|---|
| Covariates (age, sex, batch) | ALDEx2 has no covariate-adjustment mechanism | ANCOM-BC2 / MaAsLin2 — not installed |
| >2 groups | Pairwise loops are valid but produce dependence; FDR control breaks | ANCOM-BC2 with pairwise contrasts — not installed |
| Longitudinal / paired samples | No random-effects support | MaAsLin2 mixed model — not installed |
| Continuous outcome | ALDEx2 takes categorical conditions only | ANCOM-BC2 with `fix_formula = "continuous_var"` — not installed |

For any of the above, halt and explain — do not silently substitute another method or pretend the question can be answered with ALDEx2.

## Methods NOT Available in 1.1.1

If a user asks for these, halt and report; do not silently substitute.

| Method | Status | Why |
|--------|--------|-----|
| ANCOM-BC2 | Not installed | Build chain (rustup + libgmp/libuv/libgsl + CVXR 1.0-12 pin) was too brittle to maintain. See Dockerfile CHANGELOG for recipe. |
| MaAsLin2 | Not installed | Listed as alternative in 1.1.0 docs but never wired; silent Bioc install failure. |
| DESeq2 | Not installed | Designed for RNA-seq; was never wired in this skill. |
| phyloseq-based pipelines | Not installed | Same install issues as DESeq2/MaAsLin2; not wired into runtime code. |
| LEfSe | Not installed | No FDR control by design; avoid. |
| Simple t-test on relative abundance | Method choice | Ignores compositionality; refuse. |

## Filtering Recommendations

Before testing:
- Remove taxa in <10% of samples (`min_prevalence = 0.10`).
- Require mean count ≥ 10 (`min_mean_count = 10`) — keeps the Dirichlet posterior stable.
- (No automatic library-size cut; ALDEx2 handles low-coverage samples gracefully via the CLR + Monte-Carlo sampling.)

## Effect Size Interpretation

| Output column | Method | Meaningful threshold |
|---|---|---|
| `effect` | ALDEx2 | \|effect\| > 1 |
| `we.eBH` | ALDEx2 | < 0.05 |
| `wi.eBH` | ALDEx2 | < 0.05 |
