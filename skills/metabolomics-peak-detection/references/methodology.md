# Metabolomics Peak Detection Methodology

## Implemented behavior
The script auto-detects sample columns from the wide table, then applies scipy.signal.find_peaks independently to each sample trace. Prominence, height, and distance are passed through to SciPy, and the detected peak properties are written as a long-form table.

The `distance` parameter is defined in row-index units, so it depends on the ordering of the input table. This skill is intentionally offline and does not call external peak-picking services.

## Limitations
This skill stays local and offline; if a requested workflow exceeds the bundled implementation, the run should halt rather than inventing a web-backed substitute.

## Inputs and outputs
See `SKILL.md` for the staged input layout and output contract.
