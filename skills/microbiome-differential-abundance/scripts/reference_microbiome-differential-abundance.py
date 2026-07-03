#!/usr/bin/env python3
"""
reference_microbiome-differential-abundance.py — TEMPLATE.

⚠️  Do NOT execute this file directly via run_downstream.sh on a real job.
    Per AGENTS.md §W3 and contributor_guide.md §1, the Planner LLM MUST first
    copy this file into /job/reproducibility/generated_scripts/<skill>_<ts>.py
    and customize it for the job (method choice, filtering thresholds,
    covariates, FDR target).

Purpose
-------
Compositional differential abundance testing across groups for an ASV/OTU
abundance table. Default method: ALDEx2 (Wilcoxon on CLR-transformed Dirichlet
Monte-Carlo samples). The companion `aldex2_analysis.R` (snapshotted to
`/job/reproducibility/skill_snapshots/microbiome-differential-abundance/scripts/`)
is a richer reference; this wrapper inlines the minimal repro driver.

ALDEx2 is the only differential-abundance method installed in
openclaw/downstream:1.1.1. ANCOM-BC2, MaAsLin2, DESeq2, and phyloseq-based
workflows are NOT bundled — requesting them halts with a clear error
rather than silently substituting another method. See the Dockerfile
CHANGELOG for the recipe to re-enable them.

Inputs  (under STAGE_DIR; missing required input → exit 1)
---------------------------------------------------------
  abundance.tsv  — required; samples × taxa raw counts (NOT relative abundance)
  metadata.tsv   — required; samples × covariates; group column = "Group"
                   (falls back to /job/stage/metadata.tsv if absent here)

Outputs (under ANALYSIS_DIR)
----------------------------
  differential_abundance_results.tsv  — taxa × {effect, p, q, win.es, ...}
  filtered_features.tsv               — taxa kept after prevalence/abundance filters
  microbiome-differential-abundance_meta.json
"""
from __future__ import annotations
import json
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

SKILL_NAME    = "microbiome-differential-abundance"
STAGE_DIR     = Path(f"/job/stage/{SKILL_NAME}")
ANALYSIS_DIR  = Path(f"/job/analysis/{SKILL_NAME}")
GENERATED_DIR = Path("/job/reproducibility/generated_scripts")
LOG_DIR       = Path("/job/reproducibility/logs")
RANDOM_SEED   = 42

# Sibling skill that emits MetaPhlAn4 merged tables (relative abundance AND
# synthetic integer counts). Same lookup convention as the diversity skill.
PROFILE_MERGE_ANALYSIS = Path("/job/analysis/microbiome-profile-merge")
COUNT_SIDECARS    = ("merged_count_species.tsv", "merged_count_table.tsv")
RELABUND_SIDECARS = ("merged_abundance_species.tsv", "merged_abundance_table.tsv")

REQUIRED_IN_STAGE = ["abundance.tsv"]   # not required when profile-merge ran


def fail(msg: str, code: int = 1) -> None:
    print(f"[{SKILL_NAME}] FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def resolve_metadata() -> Path:
    for cand in (STAGE_DIR / "metadata.tsv", Path("/job/stage/metadata.tsv")):
        if cand.is_file():
            return cand
    fail("metadata.tsv missing — required (with a Group column) for group testing")


def _read_table_skipping_comments(path: Path):
    import pandas as pd
    with path.open() as fh:
        skip = sum(1 for line in fh if line.startswith("#"))
    # The above consumes the file; re-open to actually read. Cheap on profile-merge
    # outputs (<50 MB even on large cohorts).
    return pd.read_csv(path, sep="\t", skiprows=skip, index_col=0)


def _looks_like_relative_abundance(path: Path) -> bool:
    try:
        df = _read_table_skipping_comments(path)
    except Exception:
        return False
    if df.empty:
        return False
    try:
        if (df.fillna(0).to_numpy() % 1 == 0).all():
            return False
    except Exception:
        return False
    sums = df.sum(axis=0)
    near_100 = ((sums > 50) & (sums < 200)).mean()
    near_1   = ((sums > 0.5) & (sums < 2)).mean()
    return near_100 > 0.5 or near_1 > 0.5


def resolve_abundance() -> tuple[Path, str]:
    """ALDEx2 and ANCOM-BC2 both require integer counts. Mirror the diversity
    skill's resolution policy: count side-car > legacy STAGE_DIR > refuse relabund."""
    for name in COUNT_SIDECARS:
        cand = PROFILE_MERGE_ANALYSIS / name
        if cand.is_file():
            print(f"[{SKILL_NAME}] using profile-merge count side-car: {cand}")
            return cand, "counts"
    legacy = STAGE_DIR / "abundance.tsv"
    if legacy.is_file():
        if _looks_like_relative_abundance(legacy):
            fail(
                f"{legacy} appears to be RELATIVE ABUNDANCE. ALDEx2 and ANCOM-BC2 "
                f"both require integer counts. Re-run `microbiome-profile-merge` "
                f"and consume its merged_count_table.tsv / merged_count_species.tsv "
                f"side-car."
            )
        return legacy, "counts_legacy"
    for name in RELABUND_SIDECARS:
        cand = PROFILE_MERGE_ANALYSIS / name
        if cand.is_file():
            fail(
                f"profile-merge wrote only the relative-abundance table ({cand}) — "
                f"re-run microbiome-profile-merge with PARAMS['emit_counts']=True "
                f"(the new default)."
            )
    fail("no abundance table available — expected the count side-car from "
         "microbiome-profile-merge or a counts-encoded STAGE_DIR/abundance.tsv.")


def main() -> None:
    for d in (ANALYSIS_DIR, GENERATED_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # Input-contract resolution (2026-06-09): no silent retries on relabund.
    abundance_path, abundance_kind = resolve_abundance()
    metadata_path = resolve_metadata()

    parameters = {
        # ALDEx2 is the only differential-abundance method installed in
        # openclaw/downstream:1.1.1. MaAsLin2 / DESeq2 / phyloseq / ANCOMBC
        # are NOT bundled (see images/downstream/Dockerfile CHANGELOG).
        "method":          "ALDEx2",
        "abundance":       str(abundance_path),
        "abundance_kind":  abundance_kind,
        "metadata":        str(metadata_path),
        "group_column":    "Group",              # TODO LLM: actual metadata column
        "min_prevalence":  0.10,                 # taxon must be in ≥10% of samples
        "min_mean_count":  10,                   # taxon mean count ≥ 10
        "mc_samples":      128,                  # Monte-Carlo samples (publication: 256+)
        "fdr_threshold":   0.05,                 # BH-FDR cutoff
        "random_seed":     RANDOM_SEED,
    }

    if parameters["method"].upper() != "ALDEX2":
        fail(
            f"method={parameters['method']!r} is not installed in "
            f"openclaw/downstream:1.1.1. Only ALDEx2 is available. To add "
            f"ANCOMBC / MaAsLin2 / DESeq2 / phyloseq workflows, update "
            f"images/downstream/Dockerfile and the skill's requirements_r.txt.",
            code=2,
        )

    r_script_path = ANALYSIS_DIR / "_run_aldex2.R"
    r_script_path.write_text(_render_aldex2_script(parameters), encoding="utf-8")

    # Log policy (2026-06-09 fix): timestamp every attempt + keep a `latest`
    # symlink. The legacy `open("w")` truncated the log on each retry, so the
    # first-attempt diagnostic was wiped before the user could read it. A
    # 0-byte log from one run could be due to genuine early R crashes (input-
    # format mismatch dies before stdout flushes) OR due to a subsequent retry
    # — separating those was impossible. Per-attempt files make it obvious.
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"{SKILL_NAME}_{ts}.log"
    latest = LOG_DIR / f"{SKILL_NAME}.log"
    with log_path.open("w", encoding="utf-8") as logf:
        logf.write(f"# {SKILL_NAME} attempt at {ts} UTC\n")
        logf.write(f"# abundance: {abundance_path} ({abundance_kind})\n")
        logf.write(f"# metadata:  {metadata_path}\n")
        logf.flush()
        proc = subprocess.run(
            ["Rscript", "--vanilla", str(r_script_path)],
            stdout=logf, stderr=subprocess.STDOUT, check=False,
        )
    # Refresh the convenience pointer (symlink if FS supports it, else copy).
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(log_path.name)
    except OSError:
        latest.write_bytes(log_path.read_bytes())

    if proc.returncode != 0:
        # Surface the empty-log case explicitly — almost always means an input
        # contract violation that killed R before it could print.
        size = log_path.stat().st_size
        hint = ""
        if size < 256:
            hint = (" Log is essentially empty — Rscript likely died before "
                    "writing anything. This is usually an input-format mismatch "
                    "(relative abundance vs. integer counts) or a missing R "
                    "package; check that microbiome-profile-merge ran and that "
                    "the openclaw/downstream image really has ALDEx2 installed "
                    "(`R -q -e 'requireNamespace(\"ALDEx2\")'`).")
        fail(f"Rscript exited {proc.returncode}; see {log_path}.{hint}",
             code=proc.returncode)

    decisions = textwrap.dedent("""\
        Method: ALDEx2 (compositional; Dirichlet-MC Wilcoxon).
        Filters: ≥10% prevalence, mean count ≥10 (removes spurious rare taxa).
        128 MC samples (bump to 256+ for publication-grade stability).
        Reports both effect size (win.es) and BH-FDR q-value — never p alone.
        Note: ANCOM-BC2 / MaAsLin2 / DESeq2 are NOT installed in
        openclaw/downstream:1.1.1 — see Dockerfile CHANGELOG for the
        recipe to re-enable them.
    """).strip()
    write_meta(parameters, decisions=decisions)


def _render_aldex2_script(p: dict) -> str:
    return textwrap.dedent(f"""\
        suppressPackageStartupMessages({{
          library(ALDEx2)
        }})
        set.seed({p["random_seed"]})

        # comment.char="#" strips MetaPhlAn-style provenance headers written
        # by microbiome-profile-merge (version + library_size lines).
        abund <- read.delim("{p["abundance"]}", row.names = 1,
                            check.names = FALSE, comment.char = "#")
        meta  <- read.delim("{p["metadata"]}",  row.names = 1, check.names = FALSE)

        # Orient samples-as-columns (ALDEx2 expects features × samples).
        if (!all(rownames(meta) %in% colnames(abund))) abund <- t(abund)

        # ── input-contract guard ──────────────────────────────────────────
        # ALDEx2 expects raw integer counts; relative abundance would silently
        # zero out under the Dirichlet-Monte-Carlo and produce nonsense. We
        # check here even though the wrapper already vetted abundance_kind,
        # because the LLM-customized copy can swap files and skip the wrapper.
        abund_mat <- as.matrix(abund)
        if (!all(abund_mat == floor(abund_mat), na.rm = TRUE) ||
            min(abund_mat, na.rm = TRUE) < 0) {{
          stop("abundance table is not non-negative integers — ALDEx2 requires counts. ",
               "Use microbiome-profile-merge merged_count_table.tsv.")
        }}
        sample_totals <- colSums(abund_mat)
        if (all(abs(sample_totals - 100) < 5, na.rm = TRUE) ||
            all(abs(sample_totals - 1)   < 0.05, na.rm = TRUE)) {{
          stop("Sample sums look like relative abundance (≈100 or ≈1 per sample). ",
               "Use microbiome-profile-merge merged_count_table.tsv.")
        }}
        common <- intersect(colnames(abund), rownames(meta))
        if (length(common) < 4) stop("fewer than 4 shared samples — cannot test")
        abund <- abund[, common, drop = FALSE]
        meta  <- meta[common, , drop = FALSE]

        if (!"{p["group_column"]}" %in% colnames(meta))
          stop(sprintf("group column '%s' missing in metadata", "{p["group_column"]}"))

        grp <- factor(meta[["{p["group_column"]}"]])
        if (nlevels(grp) != 2)
          stop(sprintf("ALDEx2 expects exactly 2 groups; got %d (%s)",
                        nlevels(grp), paste(levels(grp), collapse = ", ")))

        # ── Filter low-abundance / low-prevalence taxa ─────────────────────
        n        <- ncol(abund)
        prev     <- rowSums(abund > 0) / n
        meanab   <- rowMeans(abund)
        keep     <- prev >= {p["min_prevalence"]} & meanab >= {p["min_mean_count"]}
        cat(sprintf("Taxa kept after filter: %d / %d\\n", sum(keep), length(keep)))
        kept_df  <- data.frame(feature = rownames(abund)[keep],
                               prevalence = prev[keep],
                               mean_count = meanab[keep])
        write.table(kept_df, "{ANALYSIS_DIR}/filtered_features.tsv",
                    sep = "\\t", quote = FALSE, row.names = FALSE)
        abund    <- abund[keep, , drop = FALSE]

        # ── ALDEx2 ─────────────────────────────────────────────────────────
        ax  <- ALDEx2::aldex(abund, conditions = as.character(grp),
                             mc.samples = {p["mc_samples"]},
                             test = "t", effect = TRUE,
                             include.sample.summary = FALSE,
                             denom = "all", verbose = FALSE)
        ax$feature  <- rownames(ax)
        ax$significant <- ax$wi.eBH < {p["fdr_threshold"]}
        ax <- ax[, c("feature", "effect", "diff.btw", "diff.win",
                     "wi.ep", "wi.eBH", "we.ep", "we.eBH",
                     "rab.all", "significant")]
        write.table(ax, "{ANALYSIS_DIR}/differential_abundance_results.tsv",
                    sep = "\\t", quote = FALSE, row.names = FALSE)

        cat(sprintf("Significant taxa at FDR < %g: %d\\n",
                    {p["fdr_threshold"]}, sum(ax$significant, na.rm = TRUE)))
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
            ["Rscript", "-e",
             'cat(as.character(getRversion()), "|", '
             'as.character(packageVersion("ALDEx2")))'],
            capture_output=True, text=True, check=True).stdout.strip()
        rv, av = (s.strip() for s in r_v.split("|"))
        pkgs["R"] = rv
        pkgs["ALDEx2"] = av
    except Exception:
        pkgs["R"] = pkgs["ALDEx2"] = "missing"
    return pkgs


if __name__ == "__main__":
    main()
