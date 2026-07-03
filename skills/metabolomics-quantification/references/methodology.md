# Metabolomics Quantification Methodology

## Implemented behavior
The script auto-detects sample columns, imputes missing values with the selected offline method, and then applies the selected normalization method to the imputed matrix. `min`, `median`, and `knn` are the imputation modes; `tic`, `median`, and `log` are the normalization modes.

KNN imputation uses a fixed five-neighbor configuration. This skill is intentionally offline and does not call web services or external preprocessing tools.

## Limitations
This skill stays local and offline; if a requested workflow exceeds the bundled implementation, the run should halt rather than inventing a web-backed substitute.

## Inputs and outputs
See `SKILL.md` for the staged input layout and output contract.
