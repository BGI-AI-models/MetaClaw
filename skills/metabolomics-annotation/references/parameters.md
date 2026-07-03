# Parameters

The reference script supports the following CLI flags.

| Flag | Purpose | Default |
|---|---|---|
| `--input` | CSV file containing the feature table with an `mz` column. | required unless `--demo` |
| `--output` | Output directory for the analysis bundle. | required |
| `--demo` | Generate the bundled demo input table and annotate it offline. | off |
| `--database` | Select the bundled local reference set (`hmdb`, `kegg`, `lipidmaps`, or `metlin`). | hmdb |
| `--ppm` | Mass tolerance in parts per million. | 10.0 |
| `--adducts` | Space-separated adduct labels to consider during matching. | defaults to `[M+H]+ [M-H]-` |

## Notes
- `--input` is required unless `--demo` is set.
- `--output` should point at the staged analysis directory for the current job.
- Any optional hints in `options.yaml` or `notes.txt` are advisory only; `manifest.json` takes priority when present.
