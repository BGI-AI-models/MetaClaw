# Parameters

The reference script supports the following CLI flags.

| Flag | Purpose | Default |
|---|---|---|
| `--input` | Wide feature × sample CSV file. | required unless `--demo` |
| `--output` | Output directory for the analysis bundle. | required |
| `--demo` | Generate a bundled demo table and run the offline workflow. | off |
| `--group-a-prefix` | Prefix used to select the first group of sample columns. | `ctrl` |
| `--group-b-prefix` | Prefix used to select the second group of sample columns. | `treat` |

## Notes
- `--input` is required unless `--demo` is set.
- `--output` should point at the staged analysis directory for the current job.
- Any optional hints in `options.yaml` or `notes.txt` are advisory only; `manifest.json` takes priority when present.
