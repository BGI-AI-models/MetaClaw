"""
reference_regression-analysis.py — TEMPLATE (read-only at /pipeline/scripts/ inside the
downstream container). DO NOT run this directly for real analyses: copy it to
/job/reproducibility/generated_scripts/regression-analysis_<YYYYMMDD-HHMMSS>.py, customize
for your dataset, then invoke:

    bash gateway/run_downstream.sh <job-id> --skills regression-analysis

Supervised regression on a staged tabular dataset.

Contract:
    --job-dir <path>   (default: /job)
    Reads    : <job-dir>/stage/regression
    Writes   : <job-dir>/analysis/regression-analysis/
    Meta     : <job-dir>/analysis/regression-analysis/regression-analysis_meta.json
"""
from __future__ import annotations
import argparse, datetime as _dt, json, os, sys, traceback
from pathlib import Path

SKILL = "regression-analysis"
ANALYSIS_SUBDIR = "regression-analysis"
STAGE_SUBDIR = "regression"  # may be None


def _now() -> str:
    return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _args():
    p = argparse.ArgumentParser(description="Reference template for " + SKILL)
    p.add_argument("--job-dir", default=os.environ.get("JOB_DIR", "/job"))
    p.add_argument("--random-seed", type=int, default=42)
    return p.parse_args()


def _resolve_stage(job_dir: Path) -> Path:
    if not STAGE_SUBDIR:
        return job_dir / "stage"
    return job_dir / "stage" / STAGE_SUBDIR


def _write_meta(analysis_dir: Path, status: str, notes: str, **extra) -> None:
    meta = {
        "skill": SKILL,
        "status": status,
        "timestamp": _now(),
        "notes": notes,
        "exploratory": extra.pop("exploratory", None),
        "random_seed": extra.pop("random_seed", None),
        "inputs": extra.pop("inputs", []),
        "outputs": extra.pop("outputs", []),
        "script": __file__,
        "is_reference_template": True,
    }
    meta.update(extra)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    (analysis_dir / f"{SKILL}_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False)
    )


def run(job_dir: Path, random_seed: int) -> int:
    stage_dir = _resolve_stage(job_dir)
    analysis_dir = job_dir / "analysis" / ANALYSIS_SUBDIR
    analysis_dir.mkdir(parents=True, exist_ok=True)

    if not stage_dir.exists():
        _write_meta(analysis_dir, "aborted",
                    f"Stage dir missing: {stage_dir}",
                    random_seed=random_seed)
        print(f"[{SKILL}] Stage dir missing: {stage_dir}", file=sys.stderr)
        return 2

    # -----------------------------------------------------------------
    # TEMPLATE BODY — replace in the customized copy. Kept intentionally
    # minimal so a LLM-generated copy has a clear starting shape. The
    # reference MUST NOT fabricate results on real data.
    # -----------------------------------------------------------------
    inputs = sorted(str(p.relative_to(job_dir)) for p in stage_dir.rglob("*") if p.is_file())
    _write_meta(
        analysis_dir,
        status="template-noop",
        notes=("This reference template did not perform analysis. Copy it to "
               "/job/reproducibility/generated_scripts/ and customize for the dataset."),
        random_seed=random_seed,
        inputs=inputs,
        outputs=[],
    )
    print(f"[{SKILL}] Template executed in no-op mode. "
          f"Customize a copy under /job/reproducibility/generated_scripts/.")
    return 0


def main() -> int:
    a = _args()
    job_dir = Path(a.job_dir)
    try:
        return run(job_dir, a.random_seed)
    except Exception:
        analysis_dir = job_dir / "analysis" / ANALYSIS_SUBDIR
        analysis_dir.mkdir(parents=True, exist_ok=True)
        _write_meta(analysis_dir, "error", traceback.format_exc()[:4000],
                    random_seed=a.random_seed)
        raise


if __name__ == "__main__":
    sys.exit(main())
