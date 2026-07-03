# Output Contract

All outputs are written underneath `/job/analysis/metabolomics-xcms-preprocessing/`, with reproducibility artifacts under `/job/reproducibility/`.

## Analysis outputs
- `tables/peak_table.csv`
- `report.md`
- `metabolomics-xcms-preprocessing_summary.json`

## Reproducibility artifacts
- `generated_scripts/metabolomics-xcms-preprocessing_<YYYYMMDD-HHMMSS>.py`
- `logs/metabolomics-xcms-preprocessing.log`
- `metabolomics-xcms-preprocessing_summary.json`

## Notes
- The report and JSON summary are written by the local reference script and its helper utilities.
- The repository keeps the reference implementation under `scripts/reference_metabolomics-xcms-preprocessing.py`; the harness runs a generated copy.
