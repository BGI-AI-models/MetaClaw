# Metabolomics Statistics Methodology

## Implemented behavior
The script reads a wide feature × sample table, selects the sample columns either by prefix or by midpoint fallback, and applies the requested univariate test feature-by-feature. The supported tests are Welch t-test, Mann-Whitney U, one-way ANOVA in the two-group case, and Kruskal-Wallis.

Group means, fold change, log2 fold change, and BH-FDR are written to the output table. This skill is intentionally offline and does not implement clustering, t-SNE, UMAP, or other multivariate workflows.

## Limitations
This skill stays local and offline; if a requested workflow exceeds the bundled implementation, the run should halt rather than inventing a web-backed substitute.

## Inputs and outputs
See `SKILL.md` for the staged input layout and output contract.
