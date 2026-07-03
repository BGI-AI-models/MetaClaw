# Output Contract

All outputs are written underneath `/job/analysis/metabolomics-annotation/`, with reproducibility artifacts under `/job/reproducibility/`.

## Analysis outputs
- `tables/annotations.csv`
- `report.md`
- `metabolomics-annotation_summary.json`

## Reproducibility artifacts
- `generated_scripts/metabolomics-annotation_<YYYYMMDD-HHMMSS>.py`
- `logs/metabolomics-annotation.log`
- `metabolomics-annotation_summary.json`

## Notes
- The report and JSON summary are written by the local reference script and its helper utilities.
- The repository keeps the reference implementation under `scripts/reference_metabolomics-annotation.py`; the harness runs a generated copy.
