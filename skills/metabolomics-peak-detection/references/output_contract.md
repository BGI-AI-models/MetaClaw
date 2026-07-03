# Output Contract

All outputs are written underneath `/job/analysis/metabolomics-peak-detection/`, with reproducibility artifacts under `/job/reproducibility/`.

## Analysis outputs
- `tables/detected_peaks.csv`
- `report.md`
- `metabolomics-peak-detection_summary.json`

## Reproducibility artifacts
- `generated_scripts/metabolomics-peak-detection_<YYYYMMDD-HHMMSS>.py`
- `logs/metabolomics-peak-detection.log`
- `metabolomics-peak-detection_summary.json`

## Notes
- The report and JSON summary are written by the local reference script and its helper utilities.
- The repository keeps the reference implementation under `scripts/reference_metabolomics-peak-detection.py`; the harness runs a generated copy.
