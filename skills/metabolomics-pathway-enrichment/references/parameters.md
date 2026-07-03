# Parameters

The reference script supports the following CLI flags.

| Flag | Purpose | Default |
|---|---|---|
| `--input` | CSV file containing a metabolite list. | required unless `--demo` |
| `--output` | Output directory for the analysis bundle. | required |
| `--demo` | Generate a bundled demo metabolite list and run the offline workflow. | off |
| `--method` | Method label recorded in the summary metadata. | `ora` |

## Notes
- `--input` is required unless `--demo` is set.
- `--output` should point at the staged analysis directory for the current job.
- Any optional hints in `options.yaml` or `notes.txt` are advisory only; `manifest.json` takes priority when present.
