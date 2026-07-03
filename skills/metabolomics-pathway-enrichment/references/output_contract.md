# Output Contract

All outputs are written underneath `/job/analysis/metabolomics-pathway-enrichment/`, with reproducibility artifacts under `/job/reproducibility/`.

## Analysis outputs
- `tables/pathway_enrichment.csv`
- `report.md`
- `metabolomics-pathway-enrichment_summary.json`

## Reproducibility artifacts
- `generated_scripts/metabolomics-pathway-enrichment_<YYYYMMDD-HHMMSS>.py`
- `logs/metabolomics-pathway-enrichment.log`
- `metabolomics-pathway-enrichment_summary.json`

## Notes
- The report and JSON summary are written by the local reference script and its helper utilities.
- The repository keeps the reference implementation under `scripts/reference_metabolomics-pathway-enrichment.py`; the harness runs a generated copy.
