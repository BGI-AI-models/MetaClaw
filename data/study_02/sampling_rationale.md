# Sample Selection Rationale — Study 02

## Study: Multiple Sclerosis Oral Microbiome Dysbiosis

**Paper:** "Multiple sclerosis patients exhibit oral dysbiosis with decreased early colonizers and lower hypotaurine level" (Microbiome, 2025)

**Original dataset:** 99 saliva metagenomes from MS patients and healthy controls.

## Experimental Design

The original study used a case-control design:
- **RRMS (n=49):** Relapsing-remitting multiple sclerosis patients on various disease-modifying therapies
- **HC (n=50):** Healthy controls matched for age, sex, and geography (Iowa, USA)
- **Drug subgroups within RRMS:** Ocrevus (20), Copaxone (9), None/untreated (7), Tecfidera (6), Avonex (3), Kesimpta (2), Vumerity (1), Rebif (1)

## Selection Criteria

### 1. Balanced case-control design

Selected **10 HC + 10 RRMS = 20 samples** to provide balanced comparison:
- Equal group sizes maximize power for rank-based tests
- 10 per group is the minimum recommended for robust Wilcoxon tests

### 2. Drug subgroup representation

RRMS samples include the major drug groups proportionally:
- **Ocrevus (n=4):** Largest drug group in original study, anti-CD20 therapy
- **Copaxone (n=2):** Second most common, immunomodulator
- **None/untreated (n=2):** Important to include to assess disease effect independent of treatment
- **Tecfidera (n=1):** Nrf2 pathway activator
- **Avonex (n=1):** Interferon beta

Drug groups excluded from the 20-sample subset:
- **Kesimpta (n=2 total):** Too few for reliable inference
- **Vumerity (n=1 total):** Single sample
- **Rebif (n=1 total):** Single sample

*Note:* Drug subgroups are provided for covariate analysis but the primary comparison is HC vs RRMS.

### 3. Sample diversity within HC

HC samples were selected across the sample ID range (HC-4 through HC-118) to avoid potential batch effects from sequential sample processing.

### 4. All samples are high-quality

- All 99 samples use the same sequencing platform (DNBSEQ-G400)
- All are paired-end, saliva metagenomes
- No samples with missing metadata were considered
- No technical replicates or quality issues reported

## Sample Count Summary

| Group | Subgroup | N |
|-------|----------|---|
| **HC** | Healthy Control | 10 |
| **RRMS** | Ocrevus | 4 |
| | Copaxone | 2 |
| | None (untreated) | 2 |
| | Tecfidera | 1 |
| | Avonex | 1 |
| | *RRMS subtotal* | *10* |
| **Total** | | **20** |

## Why These Samples Support Downstream Analysis

| Analysis Goal | How Sample Selection Supports It |
|--------------|----------------------------------|
| Taxonomic comparison (HC vs RRMS) | 10 vs 10 provides sufficient power |
| Alpha/beta diversity | Balanced design enables robust PERMANOVA and diversity comparisons |
| Drug effect exploration | Multiple drug groups represented as secondary analysis |
| Biomarker discovery | Adequate for rank-based differential abundance testing |
| Original paper finding validation | Can test for decreased Streptococcus (early colonizers) in RRMS |
