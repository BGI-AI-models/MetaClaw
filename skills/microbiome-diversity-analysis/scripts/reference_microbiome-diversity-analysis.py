#!/usr/bin/env python3
"""
reference_microbiome-diversity-analysis.py — TEMPLATE.

⚠️  Do NOT execute this file directly via run_downstream.sh on a real job.
    Per AGENTS.md §W3 and contributor_guide.md §1, the Planner LLM MUST first
    copy this file into /job/reproducibility/generated_scripts/<skill>_<ts>.py
    and customize it for the job's actual data shape (column names, sample
    grouping, rarefaction depth, metric choice).

Purpose
-------
Compute α / β diversity for a microbiome ASV/OTU abundance table:
  • α: Observed, Chao1, Shannon, Simpson           (vegan / phyloseq)
  • β: Bray-Curtis / weighted UniFrac PCoA         (vegan)
  • PERMANOVA across groups + dispersion check     (vegan::adonis2)

The actual analysis logic lives in R (companion script
`diversity_analysis.R`, snapshotted to
`/job/reproducibility/skill_snapshots/microbiome-diversity-analysis/scripts/`).
This wrapper validates inputs, materialises a parameterised R driver into
GENERATED_DIR, runs it with Rscript, and stamps the required *_meta.json.

Inputs  (under STAGE_DIR; missing required input → exit 1)
---------------------------------------------------------
  abundance.tsv        — required; samples × taxa (or ASV) abundance matrix
  taxonomy.tsv         — optional; ASV → taxonomy lineage table
  tree.nwk             — optional; required ONLY for UniFrac / Faith's PD
  metadata.tsv         — optional; samples × covariates; group column = "Group"
                         (falls back to /job/stage/metadata.tsv if absent here)

Outputs (under ANALYSIS_DIR)
----------------------------
  alpha_diversity.tsv             — per-sample α metrics
  beta_diversity_braycurtis.tsv   — pairwise distance matrix
  pcoa_coords.tsv                 — PC1/PC2 coordinates for plotting
  permanova_results.tsv           — adonis2 + betadisper output
  microbiome-diversity-analysis_meta.json
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

SKILL_NAME    = "microbiome-diversity-analysis"
STAGE_DIR     = Path(f"/job/stage/{SKILL_NAME}")
ANALYSIS_DIR  = Path(f"/job/analysis/{SKILL_NAME}")
GENERATED_DIR = Path("/job/reproducibility/generated_scripts")
LOG_DIR       = Path("/job/reproducibility/logs")
RANDOM_SEED   = 42

# Sibling skill that emits MetaPhlAn4 merged tables (both relative abundance
# AND synthetic integer counts). When the user runs the metagenomics-full
# pipeline, profile-merge runs before this skill and its outputs are the
# *real* input — STAGE_DIR/abundance.tsv is just a backwards-compat path.
PROFILE_MERGE_ANALYSIS = Path("/job/analysis/microbiome-profile-merge")
COUNT_SIDECARS    = ("merged_count_species.tsv", "merged_count_table.tsv")
RELABUND_SIDECARS = ("merged_abundance_species.tsv", "merged_abundance_table.tsv")

REQUIRED = ["abundance.tsv"]   # not required when profile-merge already ran (see resolve_abundance)
OPTIONAL = ["taxonomy.tsv", "tree.nwk", "metadata.tsv"]


def fail(msg: str, code: int = 1) -> None:
    print(f"[{SKILL_NAME}] FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def resolve_metadata() -> Path | None:
    for cand in (STAGE_DIR / "metadata.tsv", Path("/job/stage/metadata.tsv")):
        if cand.is_file():
            return cand
    return None


def _read_table_skipping_comments(path: Path) -> "pd.DataFrame":
    """Read a TSV table written by profile-merge, transparently skipping
    leading `#` comment lines (MetaPhlAn version header + count-table provenance)."""
    import pandas as pd
    with path.open() as fh:
        skip = 0
        for line in fh:
            if line.startswith("#"):
                skip += 1
            else:
                break
    return pd.read_csv(path, sep="\t", skiprows=skip, index_col=0)


def _looks_like_relative_abundance(table_path: Path) -> bool:
    """Heuristic: MetaPhlAn4 relative abundance has float values, no integers,
    and column (sample) sums that are ≈ 100. We check both because some pipelines
    rescale to (0, 1] or to fraction (≈ 1)."""
    try:
        df = _read_table_skipping_comments(table_path)
    except Exception:
        return False
    if df.empty:
        return False
    # All-integer columns ⇒ counts.
    try:
        is_int = (df.fillna(0).to_numpy() % 1 == 0).all()
    except Exception:
        is_int = False
    if is_int:
        return False
    sums = df.sum(axis=0)
    # ≈100 (percent) or ≈1 (fraction) per sample ⇒ relative abundance.
    near_100 = ((sums > 50) & (sums < 200)).mean()
    near_1   = ((sums > 0.5) & (sums < 2)).mean()
    return near_100 > 0.5 or near_1 > 0.5


def resolve_abundance() -> tuple[Path, str]:
    """Locate the abundance table this skill will consume.

    Resolution order (and the rationale):
      1. profile-merge synthetic counts side-car (preferred — vegan::rrarefy
         needs integers and profile-merge has the only sample-level library
         size the pipeline knows about);
      2. STAGE_DIR/abundance.tsv (legacy path; only accepted if it's
         already integer counts);
      3. profile-merge relative-abundance side-car (REJECTED with a clear
         instruction — see the 2026-06-09 retry loop).

    Returns (path, kind) where kind ∈ {"counts", "counts_legacy"} so the
    caller can record provenance.
    """
    for name in COUNT_SIDECARS:
        cand = PROFILE_MERGE_ANALYSIS / name
        if cand.is_file():
            print(f"[{SKILL_NAME}] using profile-merge count side-car: {cand}")
            return cand, "counts"

    legacy = STAGE_DIR / "abundance.tsv"
    if legacy.is_file():
        if _looks_like_relative_abundance(legacy):
            fail(
                f"{legacy} appears to be RELATIVE ABUNDANCE (column sums ≈ 100 "
                f"or ≈ 1, values are non-integer floats). vegan::rrarefy and "
                f"every β-diversity test that assumes counts will silently "
                f"misbehave. Resolution: re-run `microbiome-profile-merge` "
                f"first — its `merged_count_table.tsv` / "
                f"`merged_count_species.tsv` are the count tables this skill "
                f"expects. If you intentionally want CLR / Aitchison on "
                f"relative abundance, customize the generated script to "
                f"skip rarefaction and use vegdist(method='aitchison')."
            )
        print(f"[{SKILL_NAME}] using legacy STAGE_DIR abundance: {legacy}")
        return legacy, "counts_legacy"

    for name in RELABUND_SIDECARS:
        cand = PROFILE_MERGE_ANALYSIS / name
        if cand.is_file():
            fail(
                f"profile-merge produced only the relative-abundance table "
                f"({cand}) and not the count side-car. Re-run "
                f"`microbiome-profile-merge` with PARAMS['emit_counts']=True "
                f"(the new default) so the count table is materialized."
            )

    fail(
        "no abundance table available. Expected either "
        f"{PROFILE_MERGE_ANALYSIS}/merged_count_table.tsv "
        f"(from microbiome-profile-merge) or {STAGE_DIR}/abundance.tsv."
    )


def main() -> None:
    for d in (ANALYSIS_DIR, GENERATED_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # New input-resolution policy (2026-06-09): prefer the count side-car
    # written by microbiome-profile-merge, refuse relative-abundance input
    # outright. STAGE_DIR/abundance.tsv is still accepted if it's counts
    # (the historical ASV/OTU path). Either way, no silent format coercion.
    abundance_path, abundance_kind = resolve_abundance()

    metadata_path = resolve_metadata()
    has_tree     = (STAGE_DIR / "tree.nwk").is_file()
    parameters = {
        "abundance":     str(abundance_path),
        "abundance_kind": abundance_kind,
        "metadata":      str(metadata_path) if metadata_path else None,
        "tree":          str(STAGE_DIR / "tree.nwk") if has_tree else None,
        "group_column": "Group",     # TODO LLM: change to actual metadata column
        "rarefy_depth": "min",       # "min" | int — TODO LLM: pick from data
        "alpha_metrics": ["Observed", "Chao1", "Shannon", "Simpson"],
        "beta_metric":   "bray",     # bray | jaccard | unifrac (needs tree)
        "permanova_permutations": 999,
        "random_seed":   RANDOM_SEED,
    }

    r_script_path = ANALYSIS_DIR / "_run_diversity.R"
    r_script_path.write_text(_render_r_script(parameters), encoding="utf-8")

    log_path = LOG_DIR / f"{SKILL_NAME}.log"
    with log_path.open("w", encoding="utf-8") as logf:
        proc = subprocess.run(
            ["Rscript", "--vanilla", str(r_script_path)],
            stdout=logf, stderr=subprocess.STDOUT, check=False,
        )
    if proc.returncode != 0:
        fail(f"Rscript exited {proc.returncode}; see {log_path}", code=proc.returncode)

    write_meta(parameters, decisions=textwrap.dedent("""\
        Default α metrics: Observed/Chao1/Shannon/Simpson.
        β metric: Bray-Curtis (UniFrac only when tree.nwk is present).
        Rarefied to minimum sample depth with rngseed=42 (reproducible).
        PERMANOVA via adonis2 + dispersion check via betadisper.
        Customize group column / rarefy depth / metric in the generated copy.
    """).strip())


def _render_r_script(p: dict) -> str:
    """Inline R driver. Self-contained — does not depend on /pipeline scripts.

    The companion `diversity_analysis.R` (see SKILL.md Companion Documents)
    is the richer reference; this driver is the minimal repro version.
    """
    md_line = f'metadata <- read.delim("{p["metadata"]}", row.names = 1, check.names = FALSE)' if p["metadata"] else 'metadata <- NULL'
    # ape isn't installed in openclaw/downstream:1.1.1. If a tree was supplied,
    # halt early with a clear message rather than crashing inside an R library() call.
    if p["tree"]:
        tree_line = (
            'stop("tree.nwk was supplied but ape/picante are not installed in '
            'openclaw/downstream:1.1.1 — install them in a custom image, or '
            'remove the tree to use vegan-only metrics.")'
        )
    else:
        tree_line = 'tree <- NULL'
    return textwrap.dedent(f"""\
        suppressPackageStartupMessages({{
          # phyloseq + ape NOT loaded (neither is in openclaw/downstream:1.1.1).
          # All α/β work below uses vegan + base R. Tree-based metrics
          # (UniFrac, Faith's PD) require `ape` + `picante` which are NOT
          # bundled — if a tree is supplied, install them in a custom image
          # or in the generated copy of this script before re-running.
          library(vegan)
        }})
        set.seed({p["random_seed"]})

        # MetaPhlAn-style tables ship with one or more leading '#' comment
        # lines (the version header + count-table provenance from
        # microbiome-profile-merge). read.delim with comment.char="#" strips
        # them so we don't need to know how many there are at script gen time.
        abund <- read.delim("{p["abundance"]}", row.names = 1,
                            check.names = FALSE, comment.char = "#")
        abund <- as.matrix(abund)
        # Orient samples as rows (vegan convention). profile-merge writes
        # samples as columns, so transpose unconditionally when the table
        # has more rows than columns (typical microbiome shape: many taxa,
        # few samples).
        if (nrow(abund) > ncol(abund)) abund <- t(abund)

        # ── input-contract guard ──────────────────────────────────────────
        # vegan::rrarefy + every count-assuming test downstream require
        # non-negative integers. Refuse to coerce silently.
        is_integer_counts <- all(abund == floor(abund), na.rm = TRUE) &&
                             min(abund, na.rm = TRUE) >= 0
        row_sums <- rowSums(abund)
        looks_relabund <- all(abs(row_sums - 100) < 5, na.rm = TRUE) ||
                          all(abs(row_sums - 1)   < 0.05, na.rm = TRUE)
        if (looks_relabund || !is_integer_counts) {{
          stop(paste0(
            "abundance table at {p["abundance"]} is not integer counts ",
            "(row sums look like relative abundance or values are floats). ",
            "Use microbiome-profile-merge's merged_count_table.tsv ",
            "(or merged_count_species.tsv) instead — it carries the ",
            "synthetic counts derived from the MetaPhlAn header library size."
          ))
        }}

        {md_line}
        {tree_line}

        # ── α diversity ────────────────────────────────────────────────────
        depth <- if ("{p["rarefy_depth"]}" == "min") min(rowSums(abund)) else as.integer("{p["rarefy_depth"]}")
        cat("Rarefying to depth:", depth, "\\n")
        if (depth < 100) {{
          warning("Rarefaction depth is < 100 reads; α/β results will be unstable. ",
                  "Consider raising library_size_fallback in microbiome-profile-merge ",
                  "or supplying a metadata.tsv with read-count totals.")
        }}
        rare <- rrarefy(abund, sample = depth)
        alpha <- data.frame(
          Observed = specnumber(rare),
          Chao1    = estimateR(rare)["S.chao1", ],
          Shannon  = diversity(rare, index = "shannon"),
          Simpson  = diversity(rare, index = "simpson")
        )
        write.table(alpha, "{ANALYSIS_DIR}/alpha_diversity.tsv",
                    sep = "\\t", quote = FALSE, col.names = NA)

        # ── β diversity ────────────────────────────────────────────────────
        bray <- vegdist(rare, method = "{p["beta_metric"]}")
        write.table(as.matrix(bray), "{ANALYSIS_DIR}/beta_diversity_braycurtis.tsv",
                    sep = "\\t", quote = FALSE, col.names = NA)
        pcoa <- cmdscale(bray, k = 2, eig = TRUE)
        coords <- data.frame(PC1 = pcoa$points[,1], PC2 = pcoa$points[,2])
        write.table(coords, "{ANALYSIS_DIR}/pcoa_coords.tsv",
                    sep = "\\t", quote = FALSE, col.names = NA)

        # ── PERMANOVA + dispersion ─────────────────────────────────────────
        if (!is.null(metadata) && "{p["group_column"]}" %in% colnames(metadata)) {{
          common <- intersect(rownames(rare), rownames(metadata))
          if (length(common) < 4) stop("fewer than 4 shared samples — cannot test")
          grp <- factor(metadata[common, "{p["group_column"]}"])
          ad  <- vegan::adonis2(bray ~ grp, permutations = {p["permanova_permutations"]})
          # sqrt.dist=TRUE silences the "some squared distances are negative
          # and changed to zero" warning emitted on non-Euclidean Bray–Curtis
          # — that's a known PCoA embedding quirk, not a data problem.
          bd  <- vegan::betadisper(bray, grp, sqrt.dist = TRUE)
          out <- data.frame(
            test        = c("adonis2", "betadisper"),
            statistic   = c(ad$F[1],     mean(bd$distances)),
            p_value     = c(ad$`Pr(>F)`[1], anova(bd)$`Pr(>F)`[1])
          )
          write.table(out, "{ANALYSIS_DIR}/permanova_results.tsv",
                      sep = "\\t", quote = FALSE, row.names = FALSE)
        }} else {{
          cat("metadata or group column not available — skipping PERMANOVA\\n")
        }}
    """)


def write_meta(parameters: dict, decisions: str) -> None:
    meta = {
        "skill": SKILL_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "random_seed": RANDOM_SEED,
        "packages": _package_versions(),
        "parameters": parameters,
        "decisions": decisions,
    }
    (ANALYSIS_DIR / f"{SKILL_NAME}_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def _package_versions() -> dict:
    pkgs = {}
    for name in ("pandas", "numpy", "scipy"):
        try:
            pkgs[name] = __import__(name).__version__
        except ImportError:
            pkgs[name] = "missing"
    try:
        r_v = subprocess.run(
            ["Rscript", "-e", 'cat(as.character(getRversion()))'],
            capture_output=True, text=True, check=True).stdout.strip()
        pkgs["R"] = r_v
    except Exception:
        pkgs["R"] = "missing"
    return pkgs


if __name__ == "__main__":
    main()
