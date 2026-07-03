# Metabolomics XCMS Preprocessing Methodology

## Implemented behavior
The script is a pure-Python surrogate for an XCMS-style preprocessing workflow. It reads the staged raw LC-MS file references, applies the configured ppm and peak-width settings, and emits a synthetic-shaped peak table plus summary report.

This implementation does not call R, XCMS, or CAMERA. It exists as a local offline preprocessing placeholder and is intentionally conservative about what it claims to have processed.

## Limitations
This skill stays local and offline; if a requested workflow exceeds the bundled implementation, the run should halt rather than inventing a web-backed substitute.

## Inputs and outputs
See `SKILL.md` for the staged input layout and output contract.
