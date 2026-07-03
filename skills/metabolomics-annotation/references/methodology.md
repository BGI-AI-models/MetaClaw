# Metabolomics Annotation Methodology

## Implemented behavior
The script uses bundled offline reference dictionaries and compares each observed m/z value to the local reference masses within the configured ppm tolerance. Multiple adducts are evaluated locally, and matches are expanded into one row per query/database/adduct hit. The database selector chooses among bundled local reference sets rather than a web service or external API.

Unmatched queries are preserved in the summary metadata so the user can see which features remained unannotated.

This skill is intentionally offline-only and does not call HMDB, KEGG, LipidMaps, METLIN, GNPS, SIRIUS, or MetFrag at runtime.

## Limitations
This skill stays local and offline; if a requested workflow exceeds the bundled implementation, the run should halt rather than inventing a web-backed substitute.

## Inputs and outputs
See `SKILL.md` for the staged input layout and output contract.
