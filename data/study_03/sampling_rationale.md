# Sample Selection Rationale — Study 03

## Study: CRC Early Detection from Fecal Metagenomes

**Paper:** "Potential of fecal microbiota for early-stage detection of colorectal cancer" (Zeller et al., Molecular Systems Biology, 2014)

**Original dataset:** 156 stool metagenomes from French patients undergoing colonoscopy (Pop. F).

## Experimental Design

The original study used a multi-class case-control design within the French population (Pop. F):
- **CRC (n=53):** Patients with confirmed colorectal carcinoma
- **Adenoma (n=42):** Patients with small adenomas (n=27) and large adenomas (n=15)
- **Healthy controls (n=61):** Patients with normal colonoscopy findings

Phenotype labels were obtained from the paper's Supplementary Table (44320_2014_BFMSB145645_MOESM2_ESM.xlsx, Sheet: Pop. F Subject Metadata), which maps each CCIS sample ID to diagnosis (Normal / Small adenoma / Large adenoma / Cancer), age, gender, BMI, and country.

## Selection Criteria

### 1. Multi-class balanced design

Selected **24 samples (8 per group)** for Healthy, Adenoma, and CRC.

This supports:
- Multi-class taxonomic comparison (Healthy → Adenoma → CRC progression)
- Binary classifier training (CRC vs non-CRC, CRC vs Adenoma)
- Adequate per-class sample size for machine learning with cross-validation

### 2. Adenoma subtype balance

Within the Adenoma group:
- **5 Small adenoma** (< 1 cm, low-risk)
- **3 Large adenoma** (> 1 cm, higher-risk)

This mirrors the original study's composition (27 small : 15 large ≈ 5:3) and ensures both adenoma subtypes are represented.

### 3. Age and sex distribution

| Group | Mean Age (Range) | M/F | Mean BMI |
|-------|-----------------|-----|----------|
| Healthy | 61.2 (53–70) | 2/6 | 25.6 |
| Adenoma | 63.1 (45–76) | 4/4 | 25.0 |
| CRC | 65.5 (48–79) | 4/4 | 27.5 |

CRC patients are slightly older on average, consistent with CRC epidemiology. Age can be used as a covariate in downstream analysis.

### 4. Geographic homogeneity

All 24 selected samples are from **France** (same as the full Pop. F cohort), avoiding confounding by population-specific microbiome variation.

### 5. Why 24 samples (not 20)

The original study's core contribution is a CRC classifier. Machine learning requires:
- Sufficient per-class samples for train/test splitting
- At minimum 6 training samples per class for basic models
- With 8 per group: 6 train + 2 test per class for holdout; or 8 for LOOCV

20 samples (7+7+6) would be borderline for 3-class ML. 24 (8+8+8) provides adequate representation.

## Final Sample Distribution

| Group | Diagnosis | N |
|-------|-----------|----|
| **Healthy** | Normal | 8 |
| **Adenoma** | Small adenoma | 5 |
| | Large adenoma | 3 |
| | *Subtotal* | *8* |
| **CRC** | Cancer | 8 |
| **Total** | | **24** |

## Why These Samples Support Downstream Analysis

| Analysis Goal | How Selection Supports It |
|--------------|--------------------------|
| Taxonomic profiling across CRC spectrum | 24 samples spanning Normal → Adenoma → Cancer |
| Species-level biomarker discovery | 8 per group adequate for rank-based statistical tests |
| CRC classifier training (CRC vs non-CRC) | 8 CRC + 16 non-CRC for binary classification |
| CRC vs Adenoma distinction | 8 CRC + 8 Adenoma, addressing the key clinical challenge |
| Validation of Zeller et al. markers | Can test Fusobacterium nucleatum, Peptostreptococcus stomatis enrichment |
| Adenoma subtype analysis | Small (5) + Large (3) adenomas both represented |
