# Parameters

The reference script supports the following CLI flags.

| Flag | Purpose | Default |
|---|---|---|
| `--input` | Wide feature × sample CSV file with the feature ID in column 0. | required unless `--demo` |
| `--output` | Output directory for the analysis bundle. | required |
| `--demo` | Generate a bundled demo matrix and run the offline workflow. | off |
| `--method` | Univariate test to apply. | `ttest` |
| `--alpha` | FDR significance threshold used to define the significant subset. | 0.05 |
| `--group1-prefix` | Optional prefix for the first group of sample columns. | midpoint fallback if omitted |
| `--group2-prefix` | Optional prefix for the second group of sample columns. | midpoint fallback if omitted |

## Notes
- `--input` is required unless `--demo` is set.
- `--output` should point at the staged analysis directory for the current job.
- Any optional hints in `options.yaml` or `notes.txt` are advisory only; `manifest.json` takes priority when present.
