#!/usr/bin/env python3
"""
reference_AI-exploratory-data-analysis.py — TEMPLATE.

⚠️  Do NOT execute this file directly via run_downstream.sh on a real job.
    Per AGENTS.md §W3 and contributor_guide.md §1, the Planner LLM MUST first
    copy this file into /job/reproducibility/generated_scripts/<skill>_<ts>.py
    and customize per dataset (file selection, format-specific knobs, what to
    surface in the report). This template ships defensive defaults so it
    runs end-to-end on the toy data without fabricating findings.

Purpose
-------
Format-aware exploratory data analysis. The real analyzer lives in
`eda_analyzer.py` (NOT renamed — it remains an importable module that knows
200+ scientific file formats: tabular, sequences, microscopy, spectroscopy,
proteomics, etc.). This wrapper:
  1. Validates the staged input dir.
  2. Picks the primary input file (single file or first-by-size if many).
  3. Calls eda_analyzer to produce the format-aware Markdown report.
  4. Stamps the standard *_meta.json the gateway expects.

Inputs  (under STAGE_DIR; missing required input → exit 1)
---------------------------------------------------------
  <one or more data files>   — required; .csv .tsv .parquet .h5 .fasta .fastq
                                .vcf .bam .nc .fits .mzML .tif .dcm and more
                                (see eda_analyzer.detect_file_type for the
                                full list).
  options.yaml               — optional; { primary_file, sheet, separator,
                                            sample_limit, summary_depth }

Outputs (under ANALYSIS_DIR)
----------------------------
  <primary_file>_eda.md                       — Markdown EDA report
  AI-exploratory-data-analysis_meta.json
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_NAME    = "AI-exploratory-data-analysis"
STAGE_DIR     = Path(f"/job/stage/{SKILL_NAME}")
ANALYSIS_DIR  = Path(f"/job/analysis/{SKILL_NAME}")
GENERATED_DIR = Path("/job/reproducibility/generated_scripts")
RANDOM_SEED   = 42

# Make the companion eda_analyzer module importable from this script AND
# from the customized copy under generated_scripts/. We try the snapshot
# (always present at runtime) then the template dir (only present when run
# from /pipeline/scripts/).
_SKILL_SNAPSHOT = Path(f"/job/reproducibility/skill_snapshots/{SKILL_NAME}/scripts")
_TEMPLATE_DIR   = Path(__file__).resolve().parent
for _p in (_SKILL_SNAPSHOT, _TEMPLATE_DIR):
    if (_p / "eda_analyzer.py").is_file():
        sys.path.insert(0, str(_p))
        break


def fail(msg: str, code: int = 1) -> None:
    print(f"[{SKILL_NAME}] FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def load_options() -> dict:
    opt = STAGE_DIR / "options.yaml"
    if not opt.is_file():
        return {}
    import yaml
    try:
        return yaml.safe_load(opt.read_text(encoding="utf-8")) or {}
    except Exception as e:
        fail(f"options.yaml parse error: {e}")


def pick_primary_file(options: dict) -> Path:
    """Choose the file to analyze. options.primary_file wins if provided,
    otherwise pick the single non-options file, otherwise the largest one."""
    explicit = options.get("primary_file")
    if explicit:
        cand = STAGE_DIR / explicit
        if not cand.is_file():
            fail(f"options.primary_file points at non-existent file: {cand}")
        return cand

    candidates = [
        p for p in STAGE_DIR.iterdir()
        if p.is_file() and p.name not in ("options.yaml", ".gitkeep")
    ]
    if not candidates:
        fail(f"no data files under {STAGE_DIR}")
    if len(candidates) == 1:
        return candidates[0]
    # Multiple → pick the largest; surface this decision in the meta JSON.
    return max(candidates, key=lambda p: p.stat().st_size)


def main() -> None:
    if not STAGE_DIR.is_dir():
        fail(f"required input dir missing: {STAGE_DIR}")
    for d in (ANALYSIS_DIR, GENERATED_DIR):
        d.mkdir(parents=True, exist_ok=True)

    options = load_options()
    primary = pick_primary_file(options)

    try:
        import eda_analyzer  # type: ignore
    except ImportError as e:
        fail(f"could not import eda_analyzer module: {e}")

    # eda_analyzer module API (2026-06-09 audit):
    #   * `analyze_file(path)`            → dict   (intermediate — NOT Markdown)
    #   * `generate_markdown_report(d)`   → str    (Markdown — what we want)
    #   * optional `run` / `generate_report` → str (all-in-one in some forks)
    #
    # The previous probe order called `analyze_file` first and handed the
    # resulting dict straight to `Path.write_text`, which TypeErrors. Fix:
    #   1. Try the all-in-one Markdown-returning entry points first.
    #   2. Otherwise call analyze_file → generate_markdown_report.
    #   3. Defensively coerce / verify before writing.
    report_md = None
    for entry in ("run", "generate_report"):
        if hasattr(eda_analyzer, entry):
            try:
                cand = getattr(eda_analyzer, entry)(str(primary))
            except TypeError:
                # Some versions take (path, output_path) — try with our path.
                cand = getattr(eda_analyzer, entry)(str(primary), None)
            if isinstance(cand, str):
                report_md = cand
                break
    if report_md is None and hasattr(eda_analyzer, "analyze_file") \
            and hasattr(eda_analyzer, "generate_markdown_report"):
        analysis = eda_analyzer.analyze_file(str(primary))
        report_md = eda_analyzer.generate_markdown_report(analysis)
    if report_md is None:
        # Last resort: invoke the module as a script with --output captured
        # into our analysis dir. Keeps the wrapper functional even if the
        # module exports nothing programmatically.
        import subprocess
        out = ANALYSIS_DIR / f"{primary.stem}_eda.md"
        proc = subprocess.run(
            [sys.executable, str(_TEMPLATE_DIR / "eda_analyzer.py"),
             str(primary), str(out)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            fail(f"eda_analyzer.py failed: {proc.stderr[:400]}", code=proc.returncode)
        report_md = out.read_text(encoding="utf-8") if out.is_file() else proc.stdout

    # Defensive type check — never pass a non-str to Path.write_text.
    if not isinstance(report_md, str):
        fail(
            f"eda_analyzer entry point returned {type(report_md).__name__}, "
            f"expected Markdown str. This usually means a probe matched an "
            f"intermediate function (e.g. analyze_file) instead of a report "
            f"renderer. Check eda_analyzer.py for a `generate_markdown_report` "
            f"function and ensure it is exported."
        )

    out_path = ANALYSIS_DIR / f"{primary.stem}_eda.md"
    out_path.write_text(report_md, encoding="utf-8")

    parameters = {
        "primary_file":      str(primary),
        "primary_file_size": primary.stat().st_size,
        "primary_format":    _safe_call(eda_analyzer, "detect_file_type", str(primary)),
        "options":           options,
        "candidates_in_stage": [p.name for p in STAGE_DIR.iterdir() if p.is_file()],
        "random_seed":       RANDOM_SEED,
    }
    write_meta(parameters, outputs=[str(out_path)],
               decisions=("eda_analyzer module produced the Markdown report; "
                          "primary file picked by options.primary_file > "
                          "single-file > largest-file heuristic"))


def _safe_call(mod, attr: str, *args):
    try:
        return getattr(mod, attr)(*args) if hasattr(mod, attr) else None
    except Exception:
        return None


def write_meta(parameters: dict, outputs: list[str], decisions: str) -> None:
    meta = {
        "skill": SKILL_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "random_seed": RANDOM_SEED,
        "packages": _package_versions(),
        "parameters": parameters,
        "outputs": outputs,
        "decisions": decisions,
    }
    (ANALYSIS_DIR / f"{SKILL_NAME}_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def _package_versions() -> dict:
    out = {}
    for name in ("pandas", "numpy", "scipy", "pyyaml"):
        try:
            mod = __import__("yaml" if name == "pyyaml" else name)
            out[name] = getattr(mod, "__version__", "?")
        except ImportError:
            out[name] = "missing"
    # Optional bio-format libs — record only if present (won't error).
    for opt in ("biopython", "h5py", "pyarrow"):
        try:
            mod = __import__("Bio" if opt == "biopython" else opt)
            out[opt] = getattr(mod, "__version__", "?")
        except ImportError:
            pass
    return out


if __name__ == "__main__":
    main()
