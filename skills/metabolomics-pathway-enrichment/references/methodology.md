# Metabolomics Pathway Enrichment Methodology

## Implemented behavior
The script lowercases the query metabolite list, intersects it with the bundled pathway members, and computes a one-sided hypergeometric enrichment p-value for each pathway. Benjamini-Hochberg FDR correction is then applied across the tested pathways.

Only the embedded nine-pathway demo dictionary is used at runtime. This is intentionally offline and does not depend on KEGGREST, ReactomePA, MetaboAnalystR, or any other live service.

## Limitations
This skill stays local and offline; if a requested workflow exceeds the bundled implementation, the run should halt rather than inventing a web-backed substitute.

## Inputs and outputs
See `SKILL.md` for the staged input layout and output contract.
