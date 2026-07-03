# Parameters

The reference script supports the following CLI flags.

| Flag | Purpose | Default |
|---|---|---|
| `--input` | Wide feature × intensity CSV file. | required unless `--demo` |
| `--output` | Output directory for the analysis bundle. | required |
| `--demo` | Generate a bundled demo matrix and run the offline workflow. | off |
| `--sample-prefix` | Optional prefix used to select sample columns. | auto-detect |
| `--prominence` | Peak prominence threshold. | 1e4 |
| `--height` | Optional minimum peak height. | unset |
| `--distance` | Minimum index spacing between peaks. | 5 |

## Notes
- `--input` is required unless `--demo` is set.
- `--output` should point at the staged analysis directory for the current job.
- Any optional hints in `options.yaml` or `notes.txt` are advisory only; `manifest.json` takes priority when present.
