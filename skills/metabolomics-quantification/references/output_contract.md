# Output Contract

All outputs are written underneath `/job/analysis/metabolomics-quantification/`, with reproducibility artifacts under `/job/reproducibility/`.

## Analysis outputs
- `tables/quantified_features.csv`
- `report.md`
- `metabolomics-quantification_summary.json`

## Reproducibility artifacts
- `generated_scripts/metabolomics-quantification_<YYYYMMDD-HHMMSS>.py`
- `logs/metabolomics-quantification.log`
- `metabolomics-quantification_summary.json`

## Notes
- The report and JSON summary are written by the local reference script and its helper utilities.
- The repository keeps the reference implementation under `scripts/reference_metabolomics-quantification.py`; the harness runs a generated copy.
