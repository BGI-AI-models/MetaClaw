# Parameters

The reference script supports the following CLI flags.

| Flag | Purpose | Default |
|---|---|---|
| `--input` | One or more LC-MS file paths or file references. | required unless `--demo` |
| `--output` | Output directory for the analysis bundle. | required |
| `--demo` | Generate a bundled demo input set and run the offline workflow. | off |
| `--ppm` | m/z tolerance in parts per million. | 25.0 |
| `--peakwidth-min` | Minimum chromatographic peak width in seconds. | 10.0 |
| `--peakwidth-max` | Maximum chromatographic peak width in seconds. | 60.0 |

## Notes
- `--input` is required unless `--demo` is set.
- `--output` should point at the staged analysis directory for the current job.
- Any optional hints in `options.yaml` or `notes.txt` are advisory only; `manifest.json` takes priority when present.
