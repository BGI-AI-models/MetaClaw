# microbiome-profile-merge — Usage Guide

## What this skill does
Upstream MetaPhlAn4 runs once per sample and emits one profile file per sample.
Each profile lists only the clades detected in *that* sample, so the profiles
are not directly comparable. This skill joins them into one rectangular matrix
(samples as columns, clades as rows, zeros where a taxon is absent) — the input
format that `microbiome-diversity-analysis`, `microbiome-differential-abundance`,
and the figure/report skills expect.

It is a faithful re-implementation of biobakery's `merge_metaphlan_tables.py`
(vendored at `scripts/merge_metaphlan_tables.py`), with two job-friendly
additions: sample columns are named by the per-sample stage sub-directory (the
run id) instead of ambiguous output filenames, and a species-level table is
split out for convenience.

## MetaPhlAn profile format
A profile is a TSV with `#`-prefixed header lines, e.g.:

```
#mpa_vJun23_CHOCOPhlAnSGB_202403
#/path/to/metaphlan ... 
#clade_name	NCBI_tax_id	relative_abundance	additional_species
k__Bacteria	2	100.0	
k__Bacteria|p__Firmicutes	2|1239	61.42	
...
k__Bacteria|...|s__Escherichia_coli	...	3.71	
```

- **First header line** = the MetaPhlAn version. All merged profiles must match.
- **Last header line** = the column names.
- **Column 0** `clade_name` = the full pipe-delimited lineage; used as the row key.
- **Column 2** `relative_abundance` = percentage (0–100), summing to 100 within
  each taxonomic rank. This is the value the merge keeps.

## Column semantics (do not change)
The merge keeps `clade_name` + `relative_abundance` (`usecols=[0, 2]`), exactly
like the upstream tool. For **GTDB-based** profiles (`--gtdb_profiles` /
`PARAMS["gtdb_profiles"] = True`) only the first two columns exist, so the merge
keeps `range(2)` instead. Do not switch to estimated read counts or the
`additional_species` column.

## Taxonomic ranks
`clade_name` encodes the full lineage with `|` separators and rank prefixes:
`k__` kingdom, `p__` phylum, `c__` class, `o__` order, `f__` family,
`g__` genus, `s__` species, `t__` SGB (sub-species genome bin, MetaPhlAn4).

The full merged table keeps **all** ranks. To get a single rank, filter the
index by the last segment's prefix:

```python
species = merged.loc[merged.index.to_series().apply(
    lambda c: c.split("|")[-1].startswith("s__") and "t__" not in c)]
genus   = merged.loc[merged.index.to_series().str.split("|").str[-1].str.startswith("g__")]
```

The skill emits the species split (`merged_abundance_species.tsv`) by default;
derive other ranks in the consuming skill rather than here.

## Relative abundance caveats
- Values are **compositional** relative abundances, not counts. Diversity and
  differential-abundance methods that assume counts (e.g. rarefaction, ALDEx2 on
  raw counts) need the appropriate transform — that is the consuming skill's
  responsibility, not this one's.
- Do **not** renormalize the merged table here. Mixing ranks in one matrix means
  columns do not sum to 100; that is expected for an all-rank table. Slice to one
  rank before any sum-to-1 assumption.
- Absent taxa are `0`, not missing — that is the correct compositional zero for a
  taxon MetaPhlAn did not detect in that sample.

## CLI fallback
The vendored official tool is available offline for a quick all-rank merge:

```bash
# Path of the category folder varies — locate the profiles first, then merge.
find /job/stage -name '*.txt' | xargs grep -l '#clade_name' > paths.txt
python scripts/merge_metaphlan_tables.py -l paths.txt -o merged.txt
# GTDB profiles:
python scripts/merge_metaphlan_tables.py --gtdb_profiles -l paths.txt -o merged.txt
```

Prefer the two-stage reference wrapper for real jobs: it names columns by run id,
emits the species split, and writes `*_meta.json` for reproducibility.

## Where profiles live
Discovery is by content, not a fixed path: the skill scans everything under
`/job/stage/` and keeps the files whose headers look like MetaPhlAn profiles.
The category folder name varies (`stage/profile/`, `stage/metaphlan/`,
`stage/metaphlan4/`, a manual `stage/microbiome-profile-merge/`, ...) and the
layout may be flat (`<category>/sampleA_profile.txt`) or per-sample
(`<category>/<sample-id>/profile.txt`) — both work. To pin a specific
directory, set `STAGE_OVERRIDE` in the generated copy.

## Common failure modes
- **No profiles found under `/job/stage/`** → upstream `finalize` did not run.
  Fix the upstream phase first; do not hand-fabricate a table. (Do not assume
  the path is `stage/profile/` — the category folder may be named differently.)
- **Version mismatch** → some samples were profiled with a different MetaPhlAn /
  database version. Re-profile them consistently, then merge.
- **Duplicate sample names** → two profiles resolve to the same id (e.g. flat
  layout with identical filenames). Stage them in per-sample sub-dirs so the run
  id disambiguates the columns.
