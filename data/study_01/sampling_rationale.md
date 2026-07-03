# Sample Selection Rationale — Study 01

## Study: Drought-Induced Rhizosphere Microbiome Dynamics

**Paper:** "Genome-resolved metagenomics reveals role of iron metabolism in drought-induced rhizosphere microbiome dynamics" (Nature Communications, 2021)

**Original dataset:** 47 rhizosphere and bulk soil metagenomes from Sorghum bicolor under drought and watered conditions.

## Experimental Design

The original study used a factorial design:
- **2 treatments:** Drought (no watering) vs Watered (100% evapotranspiration)
- **2 genotypes:** RTx642 vs BTx430
- **2 compartments:** Rhizosphere (Z) vs Bulk Soil (S)
- **6 timepoints:** TP3, TP4, TP8, TP9, TP10, TP11
- **8 combinations total:** 2 × 2 × 2, with 5–6 replicates each

## Selection Criteria

### 1. Balance across core experimental groups

The primary analysis question is: **Does drought alter rhizosphere/soil microbiome composition compared to well-watered conditions?**

We selected 5 samples per group × 4 groups = **20 samples**:
- Drought_Rhizo (n=5): Drought-treated rhizosphere
- Watered_Rhizo (n=5): Watered/control rhizosphere
- Drought_Bulk (n=5): Drought-treated bulk soil
- Watered_Bulk (n=5): Watered/control bulk soil

This enables:
- Drought vs Watered comparison within each compartment (5 vs 5)
- Rhizosphere vs Bulk Soil comparison within each treatment
- Two-way contrasts (compartment effect + treatment effect)

### 2. Genotype coverage

Within each group, both genotypes (RTx642, BTx430) are included:
- 3 RTx642 + 2 BTx430 per group (approximate)
- This allows genotype to be used as a blocking factor or covariate
- Prevents genotype-biased results

### 3. Timepoint selection

Samples span 2–3 timepoints (TP3, TP8, with 1–2 from TP10/TP11) rather than all 6:
- TP3: Early drought response
- TP8: Mid-season response
- Simplifies temporal complexity for the benchmark while retaining biological signal
- Agent is NOT required to perform time-series analysis; timepoint can be treated as batch covariate

### 4. Excluded samples

- No samples excluded — all 47 samples have valid metadata and paired-end sequencing on Illumina NovaSeq 6000
- We selected 20 from 47, leaving 27 for potential validation

## Why These Samples Support Downstream Analysis

| Analysis Goal | How Sample Selection Supports It |
|--------------|----------------------------------|
| Differential abundance (Drought vs Watered) | 10 Drought vs 10 Watered provides adequate power for rank-based tests |
| Compartment comparison (Rhizosphere vs Bulk) | 10 Rhizosphere vs 10 Bulk for compartment-level contrasts |
| Taxonomic profiling (MetaPhlAn) | 20 samples is computationally tractable for benchmarking |
| Optional: MAG assembly (MEGAHIT) | Can be run on a subset of 2–4 representative samples |
| Iron metabolism focus | Both genotypes included to replicate original finding of genotype-specific iron metabolism enrichment |

## Sample Count Summary

| Group | RTx642 | BTx430 | Total |
|-------|--------|--------|-------|
| Drought_Rhizo | 3 | 2 | 5 |
| Watered_Rhizo | 3 | 2 | 5 |
| Drought_Bulk | 3 | 2 | 5 |
| Watered_Bulk | 3 | 2 | 5 |
| **Total** | **12** | **8** | **20** |
