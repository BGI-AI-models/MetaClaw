# Output Contract

All outputs are written underneath `/job/analysis/metabolomics-de/`, with reproducibility artifacts under `/job/reproducibility/`.

## Analysis outputs
- `tables/differential_features.csv`
- `tables/significant_features.csv`
- `figures/pca_scores.png`
- `report.md`
- `metabolomics-de_summary.json`

## Reproducibility artifacts
- `generated_scripts/metabolomics-de_<YYYYMMDD-HHMMSS>.py`
- `logs/metabolomics-de.log`
- `metabolomics-de_summary.json`

## Notes
- The report and JSON summary are written by the local reference script and its helper utilities.
- The repository keeps the reference implementation under `scripts/reference_metabolomics-de.py`; the harness runs a generated copy.
