# Output Contract

All outputs are written underneath `/job/analysis/metabolomics-normalization/`, with reproducibility artifacts under `/job/reproducibility/`.

## Analysis outputs
- `tables/normalized.csv`
- `report.md`
- `metabolomics-normalization_summary.json`

## Reproducibility artifacts
- `generated_scripts/metabolomics-normalization_<YYYYMMDD-HHMMSS>.py`
- `logs/metabolomics-normalization.log`
- `metabolomics-normalization_summary.json`

## Notes
- The report and JSON summary are written by the local reference script and its helper utilities.
- The repository keeps the reference implementation under `scripts/reference_metabolomics-normalization.py`; the harness runs a generated copy.
