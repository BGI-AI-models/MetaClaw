# Metabolomics Normalization Methodology

## Implemented behavior
The script supports five normalization modes: median, quantile, total/TIC, PQN, and log2(x+1). It operates on a wide feature × sample table and leaves missing values visible rather than inserting an imputation stage.

`median`, `total`, and `pqn` use per-sample scale factors derived from the table; `quantile` aligns sample distributions; and `log` applies a per-cell log2(x+1) transform.

This skill does not call external normalization services and does not perform any imputation.

## Limitations
This skill stays local and offline; if a requested workflow exceeds the bundled implementation, the run should halt rather than inventing a web-backed substitute.

## Inputs and outputs
See `SKILL.md` for the staged input layout and output contract.
