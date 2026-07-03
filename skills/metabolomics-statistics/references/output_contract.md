# Output Contract

All outputs are written underneath `/job/analysis/metabolomics-statistics/`, with reproducibility artifacts under `/job/reproducibility/`.

## Analysis outputs
- `tables/statistics.csv`
- `tables/significant.csv`
- `report.md`
- `metabolomics-statistics_summary.json`

## Reproducibility artifacts
- `generated_scripts/metabolomics-statistics_<YYYYMMDD-HHMMSS>.py`
- `logs/metabolomics-statistics.log`
- `metabolomics-statistics_summary.json`

## Notes
- The report and JSON summary are written by the local reference script and its helper utilities.
- The repository keeps the reference implementation under `scripts/reference_metabolomics-statistics.py`; the harness runs a generated copy.
