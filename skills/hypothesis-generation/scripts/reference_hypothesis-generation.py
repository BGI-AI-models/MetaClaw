#!/usr/bin/env python3
"""
reference_hypothesis-generation.py — TEMPLATE.

⚠️  Do NOT execute this file directly via run_downstream.sh on a real job.
    Per AGENTS.md §W3 and contributor_guide.md §1, the Planner LLM MUST first
    copy this file into /job/reproducibility/generated_scripts/<skill>_<ts>.py
    and WRITE the actual hypotheses + experiments + predictions inline in the
    customized copy — the LLM's reasoning IS the analysis here. This wrapper
    only enforces the I/O contract.

Purpose
-------
Convert an observation/question into 3–5 competing mechanistic hypotheses,
each scored against the quality criteria in
`references/hypothesis_quality_criteria.md` (testability, falsifiability,
parsimony, scope, novelty), with a discriminating experiment and a
falsifiable prediction per hypothesis.

This skill does NOT call the internet. Literature support must be supplied
as a pre-staged JSON file (`literature.json` below) — the gateway's network
is set to `none` and online lookup is out of scope. If the user wants a fresh
literature pull, run that beforehand with a network-enabled tool and stage
the results.

Inputs  (under STAGE_DIR; missing required input → exit 1)
---------------------------------------------------------
  observation.txt   — required; the phenomenon, anomaly, or question
                      (free-form prose, ≤ 4 paragraphs)
  context.yaml      — optional; { domain, target_audience, prior_beliefs[],
                                   constraints[] }
  literature.json   — optional; pre-staged refs:
                      [ { id, title, year, authors, finding, link } ]

Outputs (under ANALYSIS_DIR)
----------------------------
  hypotheses.json                 — structured (schema below)
  hypotheses_report.md            — human-readable rendering
  hypothesis-generation_meta.json
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_NAME    = "hypothesis-generation"
STAGE_DIR     = Path(f"/job/stage/{SKILL_NAME}")
ANALYSIS_DIR  = Path(f"/job/analysis/{SKILL_NAME}")
GENERATED_DIR = Path("/job/reproducibility/generated_scripts")
RANDOM_SEED   = 42

# Structured schema for hypotheses.json — the LLM populates this in the
# customized copy. Keep keys stable so downstream consumers (report-generator,
# tracking spreadsheets) can rely on the shape.
HYPOTHESIS_SCHEMA = {
    "id":            "H1",                           # H1..Hn
    "claim":         "<one-sentence mechanistic claim>",
    "rationale":     "<why this could be true; tie to prior literature ids>",
    "supporting_refs": [],                            # list of literature.json ids
    "quality": {
        "testable":      None,                        # bool
        "falsifiable":   None,                        # bool
        "parsimony":     None,                        # 1..5 (5 = simplest)
        "scope":         None,                        # 1..5 (5 = broadest)
        "novelty":       None,                        # 1..5 (5 = most novel)
        "score_total":   None,
    },
    "discriminating_experiment": {
        "design":        "<minimal experiment that distinguishes from rivals>",
        "controls":      [],
        "sample_size":   None,
        "duration":      None,
    },
    "falsifiable_prediction":
                     "<concrete observation that would refute this hypothesis>",
}


def fail(msg: str, code: int = 1) -> None:
    print(f"[{SKILL_NAME}] FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def main() -> None:
    if not STAGE_DIR.is_dir():
        fail(f"required input dir missing: {STAGE_DIR}")
    obs_path = STAGE_DIR / "observation.txt"
    if not obs_path.is_file():
        fail(f"required input missing: {obs_path}")

    for d in (ANALYSIS_DIR, GENERATED_DIR):
        d.mkdir(parents=True, exist_ok=True)

    observation = obs_path.read_text(encoding="utf-8").strip()
    if not observation:
        fail(f"observation.txt is empty — need ≥1 paragraph")

    context     = _load_yaml(STAGE_DIR / "context.yaml")
    literature  = _load_json(STAGE_DIR / "literature.json", default=[])

    # ── LLM CUSTOMIZATION POINT ─────────────────────────────────────────
    # In the generated copy under /job/reproducibility/generated_scripts/,
    # replace this stub with 3–5 fully-filled HYPOTHESIS_SCHEMA dicts.
    # The placeholder below is intentionally minimal so the template runs
    # end-to-end on toy data — it is NOT a substantive hypothesis.
    hypotheses = [_placeholder_hypothesis()]

    parameters = {
        "observation_path":  str(obs_path),
        "context_path":      str(STAGE_DIR / "context.yaml") if (STAGE_DIR / "context.yaml").is_file() else None,
        "literature_path":   str(STAGE_DIR / "literature.json") if (STAGE_DIR / "literature.json").is_file() else None,
        "num_hypotheses":    len(hypotheses),
        "quality_criteria":  "testable, falsifiable, parsimony, scope, novelty (see references/)",
        "random_seed":       RANDOM_SEED,
    }

    out_json = ANALYSIS_DIR / "hypotheses.json"
    out_json.write_text(json.dumps({
        "observation": observation,
        "context":     context,
        "literature_count": len(literature),
        "hypotheses":  hypotheses,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    out_md = ANALYSIS_DIR / "hypotheses_report.md"
    out_md.write_text(_render_markdown(observation, context, hypotheses), encoding="utf-8")

    write_meta(parameters, outputs=[str(out_json), str(out_md)],
               decisions=("Template stub produced; LLM must replace `hypotheses` "
                          "list in the generated copy with substantive entries "
                          "scored against the quality criteria."))


def _placeholder_hypothesis() -> dict:
    h = dict(HYPOTHESIS_SCHEMA)  # shallow copy is fine — values are immutable scalars
    h["id"]                       = "H1"
    h["claim"]                    = "[PLACEHOLDER — LLM: write your hypothesis here]"
    h["rationale"]                = "[PLACEHOLDER — LLM: tie this to literature ids]"
    h["supporting_refs"]          = []
    h["quality"]                  = dict(h["quality"], score_total=0)
    h["discriminating_experiment"]= dict(h["discriminating_experiment"])
    h["falsifiable_prediction"]   = "[PLACEHOLDER — LLM: state what would refute H1]"
    return h


def _render_markdown(observation: str, context: dict, hypotheses: list) -> str:
    lines = [
        "# Hypothesis generation",
        "",
        "## Observation", "", observation, "",
        "## Context", "",
        "```yaml", json.dumps(context, ensure_ascii=False, indent=2) if context else "(none)", "```",
        "",
        "## Competing hypotheses",
        "",
    ]
    for h in hypotheses:
        lines += [
            f"### {h['id']} — {h['claim']}", "",
            f"**Rationale.** {h['rationale']}", "",
            f"**Supporting refs.** {', '.join(h.get('supporting_refs', [])) or '(none)'}", "",
            f"**Discriminating experiment.** {h['discriminating_experiment'].get('design', '')}", "",
            f"**Falsifiable prediction.** {h['falsifiable_prediction']}", "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    import yaml
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        fail(f"{path.name} parse error: {e}")


def _load_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"{path.name} parse error: {e}")


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
    pkgs = {}
    for name in ("pyyaml",):
        try:
            pkgs[name] = __import__("yaml").__version__
        except ImportError:
            pkgs[name] = "missing"
    return pkgs


if __name__ == "__main__":
    main()
