# Metabolomics Differential Analysis Methodology

## Implemented behavior
The script reads a wide feature × sample table, splits columns into two groups using the configured prefixes, and computes Welch t-tests feature-by-feature. It then derives group means, log2 fold change, and BH-FDR adjusted p-values.

When there are enough samples to support an ordination, the script performs a best-effort PCA on the sample columns and writes a scores plot. PCA failures are logged and do not stop the differential table from being written.

This skill is intentionally offline and does not implement PLS-DA, OPLS-DA, random forests, or ROC analysis.

## Limitations
This skill stays local and offline; if a requested workflow exceeds the bundled implementation, the run should halt rather than inventing a web-backed substitute.

## Inputs and outputs
See `SKILL.md` for the staged input layout and output contract.
