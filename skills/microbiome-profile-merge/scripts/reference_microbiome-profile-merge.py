#!/usr/bin/env python3
"""
reference_microbiome-profile-merge.py — TEMPLATE.

⚠️  Do NOT execute this file directly via run_downstream.sh on a real job.
    Per AGENTS.md §W0/§W3 and contributor_guide.md §1, the Planner LLM MUST
    first copy this file into
    /job/reproducibility/generated_scripts/microbiome-profile-merge_<ts>.py
    and customize it for the job (profile location, rank to keep, gtdb flag,
    whether to also emit a renormalized species table).

Purpose
-------
Merge the per-sample MetaPhlAn4 taxonomic profiles produced by the upstream
FlowHub pipeline into a single sample × clade relative-abundance matrix —
the table every downstream microbiome step (diversity, differential
abundance, figures) expects. This re-implements the exact column semantics of
biobakery's `merge_metaphlan_tables.py` (vendored alongside as
`merge_metaphlan_tables.py`) but adds:

  * sample naming from the per-sample stage sub-directory (the SRR/run id),
    so merged columns are the real sample ids rather than ambiguous output
    filenames;
  * a species-level convenience table split out from the full merge.

Inputs  (discovered ANYWHERE under /job/stage/; missing → exit 1)
----------------------------------------------------------------
  Profiles are found by content, not by a fixed path — the stage category name
  varies across pipelines/runs (`stage/profile/`, `stage/metaphlan/`,
  `stage/metaphlan4/`, a manual `stage/microbiome-profile-merge/`, ...) and the
  layout may be flat or per-sample. Any `*.txt`/`*.tsv` under `/job/stage/`
  whose header looks like a MetaPhlAn profile is picked up. Common shapes:

    /job/stage/<category>/<sample-id>/*.txt   — per-sample sub-dirs (batch mode)
    /job/stage/<category>/*.txt               — flat, one file per sample

  A MetaPhlAn profile has '#'-prefixed header lines; the last header line names
  the columns (clade_name, NCBI_tax_id, relative_abundance, ...). All inputs
  must share one MetaPhlAn version (first header line); mixed versions abort.
  If discovery picks up the wrong files (or you want a specific dir), set
  STAGE_OVERRIDE below to a directory and only that subtree is scanned.

Outputs (under ANALYSIS_DIR)
----------------------------
  merged_abundance_table.tsv     — all clade levels, samples as columns,
                                   first line = the MetaPhlAn version header.
                                   Values are RELATIVE ABUNDANCES (0–100%) as
                                   emitted by MetaPhlAn4.
  merged_abundance_species.tsv   — species-level rows only (clade ends in s__).
  merged_count_table.tsv         — same shape as merged_abundance_table.tsv but
                                   values are SYNTHETIC INTEGER COUNTS, derived
                                   per sample as
                                       round(rel_abund / 100 * library_size).
                                   library_size per sample comes from (in order
                                   of preference):
                                     1. the MetaPhlAn header
                                        `#estimated_reads_mapped_to_known_clades`
                                     2. the MetaPhlAn header `#... reads processed`
                                     3. PARAMS["library_size_fallback"] (default 1_000_000)
                                   This is what downstream R skills that need
                                   counts (vegan::rrarefy, ALDEx2, ANCOMBC,
                                   DESeq2) consume. Relative abundance and
                                   synthetic counts are always emitted together
                                   so the LLM does not have to re-derive this
                                   per skill (the 2026-06-09 diversity-retry
                                   loop was caused by this gap).
  merged_count_species.tsv       — species-level slice of the count table.
  microbiome-profile-merge_meta.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from itertools import takewhile
from pathlib import Path

import pandas as pd

SKILL_NAME    = "microbiome-profile-merge"
STAGE_ROOT    = Path("/job/stage")                          # profiles found anywhere below
STAGE_OVERRIDE = None                                       # set to a Path to scan only that subtree
ANALYSIS_DIR  = Path(f"/job/analysis/{SKILL_NAME}")
GENERATED_DIR = Path("/job/reproducibility/generated_scripts")
LOG_DIR       = Path("/job/reproducibility/logs")

# Directory names that denote a *category/collection* of profiles rather than a
# per-sample folder — when a profile sits directly in one of these (or the stage
# root), the sample name comes from the filename, not the parent dir.
CATEGORY_DIRNAMES = {"profile", "profiles", "metaphlan", "metaphlan4", "mpa",
                     "mpa4", "taxonomy", "stage", SKILL_NAME}
# Filename suffixes stripped when deriving a sample name from a flat layout.
NAME_SUFFIXES = ("_profile", ".metaphlan", "_metaphlan", "_mpa", ".mpa", "_taxonomy")

# ── Job parameters — the Planner LLM edits these in the generated copy ───────
PARAMS = {
    "gtdb_profiles":  False,   # True only if upstream used GTDB-based profiles
    "abundance_col":  "relative_abundance",  # official keeps col 2; fall back to index 2
    "species_table":  True,    # also emit species-level convenience table
    "drop_sgb":       True,    # exclude t__ (SGB) rows from the species table
    "emit_counts":    True,    # also emit synthetic integer count table(s)
    "library_size_fallback": 1_000_000,  # used when MetaPhlAn header carries no read count
}


def fail(msg: str, code: int = 1) -> None:
    print(f"[{SKILL_NAME}] FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def _clean_stem(f: Path) -> str:
    """Sample name from a filename: stem with known MetaPhlAn-ish suffixes removed."""
    stem = f.stem
    for suf in NAME_SUFFIXES:
        if stem.lower().endswith(suf):
            stem = stem[: -len(suf)]
            break
    return stem or f.stem


def discover_profiles() -> list[tuple[Path, str]]:
    """Return [(profile_path, sample_name), ...] for MetaPhlAn profiles staged
    anywhere under the scan root.

    Discovery is by content (header looks like a MetaPhlAn profile), not by a
    fixed path — the stage category name varies (`profile`, `metaphlan`, ...).
    Sample naming is layout-aware:
      * per-sample sub-dir  (one profile in a folder named like a sample id)
        → use the folder name (e.g. the SRR/run id);
      * flat/collection dir (several profiles share a parent, or the parent is a
        known category dir, or it sits at the stage root)
        → use the filename stem (minus `_profile` etc.).
    """
    root = STAGE_OVERRIDE or STAGE_ROOT
    if not Path(root).is_dir():
        fail(f"scan root {root} does not exist. Did `finalize` run? It materializes "
             "the MetaPhlAn profiles under /job/stage/<category>/.")

    files = sorted(p for p in Path(root).rglob("*")
                   if p.suffix in (".txt", ".tsv") and p.is_file() and _looks_like_profile(p))
    if not files:
        fail(f"found no MetaPhlAn profiles under {root} (looked for #-headered *.txt/*.tsv). "
             "An empty stage usually means `finalize` did not run.")

    # A parent dir holding >1 profile is a collection/flat dir, not a sample dir.
    parent_counts = Counter(f.parent for f in files)
    pairs: list[tuple[Path, str]] = []
    for f in files:
        parent = f.parent
        is_collection = (parent_counts[parent] > 1
                         or parent.name.lower() in CATEGORY_DIRNAMES
                         or parent == Path(root))
        sample = _clean_stem(f) if is_collection else parent.name
        pairs.append((f, sample))

    # Guard against duplicate sample names (would silently collide on concat).
    names = [s for _, s in pairs]
    dups = sorted({n for n in names if names.count(n) > 1})
    if dups:
        # Disambiguate with the parent dir before giving up.
        pairs = [(f, s if s not in dups else f"{f.parent.name}_{s}") for f, s in pairs]
        names = [s for _, s in pairs]
        still = sorted({n for n in names if names.count(n) > 1})
        if still:
            fail(f"duplicate sample names {still} after disambiguation — "
                 "refusing to merge ambiguous columns; set STAGE_OVERRIDE or rename inputs")
    return pairs


def _looks_like_profile(f: Path) -> bool:
    try:
        with f.open() as fh:
            head = [next(fh, "") for _ in range(5)]
    except OSError:
        return False
    return any(line.startswith("#") and ("clade_name" in line or "mpa" in line.lower())
               for line in head)


def _parse_library_size(headers: list[str]) -> int | None:
    """Recover an integer library size from a MetaPhlAn4 header block, or None.

    MetaPhlAn4 typically writes lines like:
        #36795060 reads processed
        #... estimated_reads_mapped_to_known_clades: 24571212
    We prefer the latter (it's what was actually classified) and fall back to
    the former. Both forms vary slightly across versions, so the matcher is
    lenient: any header containing one of the expected phrases followed by
    a non-negative integer wins.
    """
    import re
    patterns = [
        re.compile(r"estimated_reads_mapped_to_known_clades[^0-9]*([0-9]+)", re.IGNORECASE),
        re.compile(r"([0-9]+)\s+reads\s+processed", re.IGNORECASE),
        re.compile(r"nreads[^0-9]*([0-9]+)", re.IGNORECASE),
    ]
    for pat in patterns:
        for h in headers:
            m = pat.search(h)
            if m:
                try:
                    n = int(m.group(1))
                    if n > 0:
                        return n
                except ValueError:
                    pass
    return None


def read_profile(f: Path, sample: str) -> tuple[pd.Series, str, int | None]:
    """Read one profile into a Series keyed by clade_name.

    Returns (series, mpa_version, library_size_or_None). The library size is
    pulled from the MetaPhlAn header so downstream count synthesis is reproducible
    per-sample without re-reading the file.
    """
    with f.open() as fh:
        headers = [x.strip() for x in takewhile(lambda x: x.startswith("#"), fh)]
    if not headers:
        fail(f"{f} has no '#' header lines — not a MetaPhlAn profile")
    mpa_version = headers[0]
    names = headers[-1].split("#")[1].strip().split("\t")
    lib_size = _parse_library_size(headers)

    # Faithful to merge_metaphlan_tables.py: clade_name (col 0) + relative_abundance (col 2);
    # GTDB profiles only have two columns.
    usecols = [0, 2] if not PARAMS["gtdb_profiles"] else list(range(2))
    df = pd.read_csv(f, sep="\t", skiprows=len(headers), names=names,
                     usecols=usecols, index_col=0)
    value_col = PARAMS["abundance_col"] if PARAMS["abundance_col"] in df.columns else df.columns[-1]
    return pd.Series(data=df[value_col], index=df.index, name=sample), mpa_version, lib_size


def main() -> None:
    for d in (ANALYSIS_DIR, GENERATED_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)

    pairs = discover_profiles()
    print(f"[{SKILL_NAME}] merging {len(pairs)} profile(s): {[s for _, s in pairs]}")

    series_list: list[pd.Series] = []
    versions: set[str] = set()
    lib_sizes: dict[str, int] = {}
    lib_size_sources: dict[str, str] = {}
    fallback = int(PARAMS["library_size_fallback"])
    for f, sample in pairs:
        ser, ver, lib = read_profile(f, sample)
        versions.add(ver)
        series_list.append(ser)
        if lib is None:
            lib_sizes[sample] = fallback
            lib_size_sources[sample] = "fallback"
        else:
            lib_sizes[sample] = int(lib)
            lib_size_sources[sample] = "metaphlan_header"

    if len(versions) > 1:
        fail(f"profiles span multiple MetaPhlAn versions {sorted(versions)} — "
             "re-profile all samples with one version before merging")
    mpa_version = next(iter(versions))

    merged = pd.concat(series_list, axis=1).fillna(0)
    merged.index.name = "clade_name"

    full_path = ANALYSIS_DIR / "merged_abundance_table.tsv"
    with full_path.open("w", encoding="utf-8") as out:
        out.write(mpa_version + "\n")
        merged.to_csv(out, sep="\t")
    print(f"[{SKILL_NAME}] wrote {full_path}  ({merged.shape[0]} clades × {merged.shape[1]} samples)")

    species_path = None
    if PARAMS["species_table"]:
        is_species = merged.index.to_series().apply(
            lambda c: c.split("|")[-1].startswith("s__")
            and not (PARAMS["drop_sgb"] and "t__" in c))
        species = merged.loc[is_species]
        species_path = ANALYSIS_DIR / "merged_abundance_species.tsv"
        with species_path.open("w", encoding="utf-8") as out:
            out.write(mpa_version + "\n")
            species.to_csv(out, sep="\t")
        print(f"[{SKILL_NAME}] wrote {species_path}  ({species.shape[0]} species)")

    # ── Synthetic integer count tables ──────────────────────────────────────
    # vegan::rrarefy, ALDEx2, ANCOMBC and DESeq2 all require integer counts,
    # but MetaPhlAn4 emits relative abundance. Downstream skills were
    # previously each re-deriving this conversion (or silently choking on
    # floats — see the 2026-06-09 diversity-retry loop). We do it ONCE here,
    # with a documented `library_size` per sample, and ship the synthetic
    # count table alongside the relative-abundance table. Downstream skills
    # detect the count side-car by name (`merged_count_table.tsv`).
    count_path = None
    count_species_path = None
    if PARAMS["emit_counts"]:
        # Build a per-sample library-size vector aligned with merged.columns,
        # then counts[clade, sample] = round(rel_abund / 100 * library_size).
        import numpy as np
        lib_vec = pd.Series({s: lib_sizes[s] for s in merged.columns})
        counts = (merged.divide(100.0) * lib_vec).round().astype(np.int64)
        # Guard against pathological inputs: a sample whose counts sum to zero
        # is useless downstream and is almost always an indicator that the
        # library_size fallback was used on a profile that ought to have had a
        # header read count. Don't fail — just warn loudly.
        zero_samples = counts.columns[counts.sum(axis=0) == 0].tolist()
        if zero_samples:
            print(f"[{SKILL_NAME}] WARN  {len(zero_samples)} sample(s) have zero total "
                  f"counts after synthesis: {zero_samples[:5]}{'…' if len(zero_samples) > 5 else ''}",
                  file=sys.stderr)

        count_path = ANALYSIS_DIR / "merged_count_table.tsv"
        with count_path.open("w", encoding="utf-8") as out:
            out.write(mpa_version + "\n")
            out.write(f"#synthetic_counts_from=relative_abundance\n")
            out.write(f"#library_size_source={json.dumps(lib_size_sources)}\n")
            out.write(f"#library_size={json.dumps(lib_sizes)}\n")
            counts.to_csv(out, sep="\t")
        print(f"[{SKILL_NAME}] wrote {count_path}  "
              f"({counts.shape[0]} clades × {counts.shape[1]} samples, "
              f"total reads ≈ {int(counts.values.sum()):,})")

        if PARAMS["species_table"]:
            count_species = counts.loc[is_species]
            count_species_path = ANALYSIS_DIR / "merged_count_species.tsv"
            with count_species_path.open("w", encoding="utf-8") as out:
                out.write(mpa_version + "\n")
                out.write(f"#synthetic_counts_from=relative_abundance\n")
                out.write(f"#library_size_source={json.dumps(lib_size_sources)}\n")
                out.write(f"#library_size={json.dumps(lib_sizes)}\n")
                count_species.to_csv(out, sep="\t")
            print(f"[{SKILL_NAME}] wrote {count_species_path}  "
                  f"({count_species.shape[0]} species)")

    outputs = [str(full_path)]
    if species_path: outputs.append(str(species_path))
    if count_path: outputs.append(str(count_path))
    if count_species_path: outputs.append(str(count_species_path))

    write_meta(
        mpa_version=mpa_version,
        samples=[s for _, s in pairs],
        inputs=[str(f) for f, _ in pairs],
        outputs=outputs,
        n_clades=int(merged.shape[0]),
        library_sizes=lib_sizes,
        library_size_sources=lib_size_sources,
    )


def write_meta(*, mpa_version, samples, inputs, outputs, n_clades,
               library_sizes: dict[str, int] | None = None,
               library_size_sources: dict[str, str] | None = None) -> None:
    meta = {
        "skill": SKILL_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": "biobakery merge_metaphlan_tables.py (vendored, in-process)",
        "metaphlan_version_header": mpa_version,
        "packages": {"pandas": pd.__version__},
        "parameters": PARAMS,
        "n_samples": len(samples),
        "samples": samples,
        "inputs": inputs,
        "outputs": outputs,
        "n_clades_merged": n_clades,
        "library_sizes": library_sizes or {},
        "library_size_sources": library_size_sources or {},
        "decisions": (
            "Merged per-sample MetaPhlAn4 profiles into a sample × clade "
            "relative-abundance matrix using the official column semantics "
            "(clade_name + relative_abundance; taxa absent in a sample → 0). "
            "Columns named by the per-sample stage sub-directory (run id). "
            "merged_abundance_table.tsv holds relative abundances (%) as "
            "emitted by MetaPhlAn (NOT renormalized). "
            "merged_count_table.tsv holds SYNTHETIC integer counts derived as "
            "round(rel_abund / 100 * library_size) per sample, with "
            "library_size taken from the MetaPhlAn header "
            "(estimated_reads_mapped_to_known_clades, then 'reads processed', "
            "then nreads) and falling back to PARAMS['library_size_fallback'] "
            "(default 1,000,000). Downstream skills that need counts "
            "(vegan::rrarefy, ALDEx2, ANCOMBC, DESeq2) should consume the "
            "count table — never re-derive this conversion ad hoc."
        ),
    }
    (ANALYSIS_DIR / f"{SKILL_NAME}_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
