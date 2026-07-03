---
name: microbiome-profile-merge
description: >
  Use this skill to merge per-sample MetaPhlAn (MetaPhlAn4) taxonomic profiles into a single sample × clade relative-abundance table — the matrix that diversity, differential-abundance, and figure skills consume. Trigger right after upstream `finalize` populates `stage/profile/`, before any community analysis.
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
metadata:
  version: 1.0.0
---

# MetaPhlAn Profile Merge

## Responsibilities
This skill combines the many per-sample MetaPhlAn4 profile files emitted by the upstream pipeline into one merged abundance matrix (samples as columns, clades as rows). It consumes staged profiles under `/job/stage/profile/` and writes a reproducible merged table to `/job/analysis/microbiome-profile-merge/`, with generated code under `/job/reproducibility/generated_scripts/`.

It exists because every per-sample MetaPhlAn run produces its own profile with a different set of detected clades; downstream community analyses need a single rectangular table with a shared clade index and zeros where a taxon is absent. Use it to produce that table (and a species-level convenience split). Do **not** use it to call taxonomy from reads (that is upstream MetaPhlAn), to renormalize or filter abundances for a specific test (that belongs to the consuming skill), or to merge profiles from different MetaPhlAn versions.

## Companion Documents
- `references/usage-guide.md` — MetaPhlAn profile format, column semantics, rank filtering, the `--gtdb_profiles` flag, and relative-abundance caveats.
- `scripts/merge_metaphlan_tables.py` — faithful vendored copy of biobakery's official merge tool (offline-safe), usable as a CLI fallback.
- `scripts/reference_microbiome-profile-merge.py` — the two-stage reference template for this skill.

If a companion document conflicts with this `SKILL.md`, follow `SKILL.md` and report the inconsistency.

## Runtime Environment / 运行环境
- Container image: openclaw/downstream:1.1.0
- Network access: none (`--network none`, per gateway default) — the merge tool is vendored, so no `pip install` or download is needed.
- Mounted paths:

| Path | Permission | Contents |
|---|---|---|
| `/job/stage/` | ro | upstream artifacts; MetaPhlAn profiles under some category dir (e.g. `stage/profile/...` or `stage/metaphlan/...`, flat or per-sample) — discovered by content |
| `/job/analysis/` | rw | this skill's merged tables |
| `/job/reproducibility/` | rw | generated scripts, logs, *_meta.json |
| `/pipeline/scripts/` | ro | reference scripts (templates) |

If the concrete skill runs outside a container, replace the table with the equivalent runtime layout.

## Input Conventions
Profiles are discovered **by content, not by a fixed path** — the stage category name varies across pipelines and runs, so do not assume `stage/profile/`. Any `*.txt`/`*.tsv` under `/job/stage/` whose header looks like a MetaPhlAn profile is picked up, whatever the category folder is called and whether the layout is flat or per-sample. Common shapes (all supported):

```text
/job/stage/profile/<sample-id>/*.txt      # per-sample sub-dirs (batch mode)
/job/stage/profile/*.txt                  # flat: one file per sample
/job/stage/metaphlan/*_profile.txt        # different category name — also fine
/job/stage/metaphlan4/<sample-id>/*.txt   # nested under another name — also fine
/job/stage/microbiome-profile-merge/**    # manually staged — also fine
```

A MetaPhlAn profile is a TSV whose leading lines start with `#`; the **first** header line records the MetaPhlAn version and the **last** header line names the columns (`clade_name`, `NCBI_tax_id`, `relative_abundance`, ...). The merge keys rows on column 0 (`clade_name`) and keeps column 2 (`relative_abundance`); GTDB-based profiles keep the first two columns instead.

Sample naming is layout-aware: a profile alone in a sample-named sub-directory takes that **folder name** (the SRR/run id); a profile in a flat/collection directory takes its **filename stem** (with `_profile`/`_metaphlan`/etc. stripped). If discovery is wrong or you want a specific directory, set `STAGE_OVERRIDE` in the generated script to scan only that subtree. If **no** profiles are found anywhere under `/job/stage/`, **stop and report** that `finalize` has not materialized them — do not fabricate a table. All inputs must share one MetaPhlAn version; if versions differ, halt.

## Output Conventions
Write all results to `/job/analysis/microbiome-profile-merge/`:

- `merged_abundance_table.tsv` — all clade levels; first line is the MetaPhlAn version header, then samples × clades with absent taxa as `0`.
- `merged_abundance_species.tsv` — species-level rows only (clade ends in `s__`, SGB `t__` rows excluded by default).
- `microbiome-profile-merge_meta.json`

Write reproducibility artifacts to `/job/reproducibility/`:

- `generated_scripts/microbiome-profile-merge_<YYYYMMDD-HHMMSS>.py`
- `logs/microbiome-profile-merge.log`

The metadata file must record the MetaPhlAn version header, package versions, the sample list, input profile paths, output paths, clade count, the `gtdb_profiles` choice, and a note that values are raw relative abundances (not renormalized). If the run halts, write the metadata file when possible and record the blocker.

## Workflow
### Step 1 — Read Data
Confirm `stage/profile/` exists and discover the per-sample profiles. Verify each is a real MetaPhlAn profile (has `#` headers) and that all share one MetaPhlAn version. Resolve a unique sample name per profile; refuse to merge on duplicate names.

### Step 2 — Merge
Read each profile's `clade_name` + `relative_abundance` columns, join horizontally on the clade index, and fill taxa missing from a sample with `0` (faithful to `merge_metaphlan_tables.py`). Optionally split out the species-level rows.

### Step 3 — Archiving
Write the merged full table (with the version header line), the species table, the `_meta.json`, the generated script copy, and the log so the merge is fully reproducible.

## Available Libraries / 可用库
Python: `pandas` `numpy`
Bundled tool: `scripts/merge_metaphlan_tables.py` (biobakery, vendored)

## Strict Rules / 严格规则
1. If no MetaPhlAn profiles are found anywhere under `/job/stage/`, exit non-zero and report — never fabricate a merged table. An empty stage usually means `finalize` did not run. Do not hard-fail just because `stage/profile/` specifically is absent; the category folder may have another name.
2. Never merge profiles from different MetaPhlAn versions; halt and report the mismatch.
3. Keep the official column semantics: row key = `clade_name`, value = `relative_abundance` (col 2), or the first two columns for `--gtdb_profiles`. Do not silently switch to read counts.
4. Fill taxa absent from a sample with `0`; do not drop or impute them otherwise.
5. Do not renormalize, relative-abundance-rescale, or rank-filter the merged table here — emit MetaPhlAn's values as-is. Rescaling per rank is the consuming skill's decision.
6. Refuse to merge when two profiles resolve to the same sample name (ambiguous columns).
7. End by writing `/job/analysis/microbiome-profile-merge/microbiome-profile-merge_meta.json` (contributor_guide.md §5).

## Execution Model (Two-Stage) / 执行模型（两阶段）
This skill follows the two-stage downstream pattern.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_microbiome-profile-merge.py` | ro | repository-published template, mounted ro by `prepare_downstream.sh`; do not modify |
| `/job/reproducibility/generated_scripts/microbiome-profile-merge_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy; `run_downstream.sh` executes the most recent one |

Standard flow:

1. `bash gateway/attach.sh --shell` to enter the already-running container (or `docker exec -it $(cat /data/output/<job-id>/.container_name) bash`).
2. Inspect `/job/stage/profile/` to confirm the per-sample layout, profile count, and MetaPhlAn version.
3. Copy the reference script into `/job/reproducibility/generated_scripts/`.
4. Edit the copy for the current job (`gtdb_profiles`, whether to emit the species table, SGB handling).
5. Run the job-specific script with `python <copy>.py`, archive the log, and confirm the merged table + `_meta.json`.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `skills/microbiome-profile-merge/scripts/`; that directory is for templates, not job artifacts.
