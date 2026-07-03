#!/usr/bin/env python3
"""
reference_statistical-analysis.py — TEMPLATE.

⚠️  Do NOT execute this file directly via run_downstream.sh on a real job.
    Per AGENTS.md §W3 and contributor_guide.md §1, the Planner LLM MUST first
    copy this file into /job/reproducibility/generated_scripts/<skill>_<ts>.py
    and customize it for the dataset (which test to run, what columns are
    grouping vs outcome, FDR target, effect-size convention).

Purpose
-------
Run an assumption-aware statistical test on a tabular dataset and emit an
APA-style summary the report-generator can pick up. The decision tree, the
assumption checks, the effect-size formulas, and the Bayesian alternatives
are documented under `references/` and the assumption-check helpers live in
`assumption_checks.py` (NOT renamed — it remains an importable module).

Default flow on toy data
------------------------
  1. Load `data.tsv` and (optional) `metadata.tsv`.
  2. Identify outcome + group columns.
  3. Run `assumption_checks` on the outcome (normality, homogeneity, outliers).
  4. Pick a test from the decision matrix:
        2 groups,  parametric OK  → Welch t-test    (+ Cohen's d, 95% CI)
        2 groups,  parametric NO  → Mann-Whitney U  (+ rank-biserial r)
        ≥3 groups, parametric OK  → One-way ANOVA   (+ η²) + Tukey HSD
        ≥3 groups, parametric NO  → Kruskal-Wallis  (+ ε²) + Dunn's post-hoc
  5. Multiple-testing correction: BH-FDR via `statsmodels.stats.multitest`.
  6. Emit `results.tsv`, `apa_summary.md`, and the standard meta JSON.

Inputs  (under STAGE_DIR; missing required input → exit 1)
---------------------------------------------------------
  data.tsv          — required; rows=samples, cols=variables
  metadata.tsv      — optional; falls back to /job/stage/metadata.tsv (hardlinked from DATA_DIR by orchestrator)
  options.yaml      — optional; {outcome, group, paired, test_override}

Outputs (under ANALYSIS_DIR)
----------------------------
  assumption_checks.tsv         — per-variable normality / homogeneity report
  results.tsv                   — test statistic, p, q (BH-FDR), effect size, CI
  apa_summary.md                — narrative summary in APA reporting style
  statistical-analysis_meta.json
"""
from __future__ import annotations
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

SKILL_NAME    = "statistical-analysis"
STAGE_DIR     = Path(f"/job/stage/{SKILL_NAME}")
ANALYSIS_DIR  = Path(f"/job/analysis/{SKILL_NAME}")
GENERATED_DIR = Path("/job/reproducibility/generated_scripts")
LOG_DIR       = Path("/job/reproducibility/logs")
RANDOM_SEED   = 42

# Make the companion assumption_checks module importable from this script
# AND from the customized copy under generated_scripts/. We look first in
# the snapshot copy of this skill (always present), then alongside the
# template (only present when run from /pipeline/scripts/).
_SKILL_SNAPSHOT = Path(f"/job/reproducibility/skill_snapshots/{SKILL_NAME}/scripts")
_TEMPLATE_DIR   = Path(__file__).resolve().parent
for _p in (_SKILL_SNAPSHOT, _TEMPLATE_DIR):
    if (_p / "assumption_checks.py").is_file():
        sys.path.insert(0, str(_p))
        break


def fail(msg: str, code: int = 1) -> None:
    print(f"[{SKILL_NAME}] FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def resolve_metadata() -> Path | None:
    for cand in (STAGE_DIR / "metadata.tsv", Path("/job/stage/metadata.tsv")):
        if cand.is_file():
            return cand
    return None


def load_options() -> dict:
    opt = STAGE_DIR / "options.yaml"
    if not opt.is_file():
        return {}
    import yaml
    try:
        return yaml.safe_load(opt.read_text(encoding="utf-8")) or {}
    except Exception as e:
        fail(f"options.yaml parse error: {e}")


def main() -> None:
    if not STAGE_DIR.is_dir():
        fail(f"required input dir missing: {STAGE_DIR}")
    data_path = STAGE_DIR / "data.tsv"
    if not data_path.is_file():
        fail(f"required input missing: {data_path}")

    for d in (ANALYSIS_DIR, GENERATED_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)

    import numpy as np
    import pandas as pd
    np.random.seed(RANDOM_SEED)

    df = pd.read_csv(data_path, sep="\t")
    md_path = resolve_metadata()
    md = pd.read_csv(md_path, sep="\t") if md_path else None
    opts = load_options()

    # ── pick outcome + group columns ─────────────────────────────────────
    # Resolution order (2026-06-09 fix — previously this skill bailed out when
    # auto-detection couldn't pin down a column, even though the user had a
    # documented default. Two retries, never recovered, until manual override):
    #   1. options.yaml in STAGE_DIR (most specific)
    #   2. user defaults parsed from USER.md (workspace-wide convention)
    #   3. literal-name match in metadata / data (cheap and unambiguous)
    #   4. _first_categorical / _first_numeric heuristic (last resort)
    user_defaults = _load_user_defaults()

    group_col = (
        opts.get("group")
        or user_defaults.get("group")
        or _explicit_column_match(df, md, candidates=("group", "Group", "GROUP"))
        or _first_categorical(df, md)
    )
    outcome_col = (
        opts.get("outcome")
        or user_defaults.get("outcome")
        or _explicit_column_match(df, md, candidates=("outcome", "Outcome", "OUTCOME"))
        or _first_numeric(df, exclude={"id", "sample", group_col or ""})
    )

    if group_col is None:
        fail(
            "could not auto-detect group column. Set options.yaml: group, or "
            "add `Default metadata grouping column: <name>` to USER.md."
        )
    if outcome_col is None:
        # Microbiome abundance tables have dozens of numeric taxa columns and
        # auto-picking the first one is almost always wrong. Better to halt
        # with a structured ask than silently use a meaningless feature.
        cand_numeric = [c for c in df.columns if df[c].dtype.kind in "fiu" and c != group_col]
        n = len(cand_numeric)
        snippet = ", ".join(cand_numeric[:5]) + ("…" if n > 5 else "")
        fail(
            f"could not auto-detect outcome column ({n} numeric candidates "
            f"found: {snippet}). Refusing to guess on a wide table — please "
            f"set options.yaml: outcome (or `Default outcome column:` in "
            f"USER.md)."
        )

    # If group column lives in metadata, join in.
    if md is not None and group_col in md.columns and group_col not in df.columns:
        # Detect a shared id column (first common column name).
        common = next((c for c in df.columns if c in md.columns), None)
        if common is None:
            fail("metadata supplied but cannot find a shared id column with data.tsv")
        df = df.merge(md[[common, group_col]], on=common, how="inner")

    # ── assumption checks ────────────────────────────────────────────────
    try:
        import assumption_checks as ac  # type: ignore
    except ImportError as e:
        fail(f"could not import assumption_checks module: {e}")

    groups = df[group_col].dropna().unique().tolist()
    if len(groups) < 2:
        fail(f"group column '{group_col}' has only {len(groups)} level(s)")

    samples = [df.loc[df[group_col] == g, outcome_col].dropna().to_numpy()
               for g in groups]
    if any(len(s) < 3 for s in samples):
        fail(f"each group needs ≥3 samples; got {[len(s) for s in samples]}")

    assumption_rows = []
    parametric_ok = True
    for g, s in zip(groups, samples):
        norm  = ac.check_normality(s)             # type: ignore[attr-defined]
        out   = ac.check_outliers(s)              # type: ignore[attr-defined]
        ok    = norm.get("is_normal", False)
        parametric_ok &= ok
        assumption_rows.append({
            "group": str(g),
            "n": len(s),
            "shapiro_W":  norm.get("shapiro_W"),
            "shapiro_p":  norm.get("shapiro_p"),
            "is_normal":  ok,
            "outlier_count": out.get("outlier_count", 0),
        })
    homog = ac.check_homogeneity(samples)         # type: ignore[attr-defined]
    parametric_ok &= homog.get("homogeneous", False)
    pd.DataFrame(assumption_rows).to_csv(
        ANALYSIS_DIR / "assumption_checks.tsv", sep="\t", index=False)

    # ── pick & run a test ────────────────────────────────────────────────
    parameters = {
        "data":         str(data_path),
        "metadata":     str(md_path) if md_path else None,
        "outcome":      outcome_col,
        "group":        group_col,
        "n_groups":     len(groups),
        "parametric_assumptions_met": bool(parametric_ok),
        "homoscedasticity_p":         homog.get("p_value"),
        "test_override": opts.get("test_override"),
        "fdr_alpha":    opts.get("fdr_alpha", 0.05),
        "random_seed":  RANDOM_SEED,
    }

    test_name, stats_row, posthoc = _run_test(
        samples, groups, parametric_ok, opts.get("test_override"))
    parameters["test"] = test_name

    results_df = pd.DataFrame([stats_row])
    # BH-FDR on the single test's p-value is a no-op; the pattern is here so
    # that customized copies running many tests across many features get
    # correction for free without restructuring.
    from statsmodels.stats.multitest import multipletests
    _, q, _, _ = multipletests(results_df["p"].to_numpy(), method="fdr_bh")
    results_df["q_bh"] = q
    results_df.to_csv(ANALYSIS_DIR / "results.tsv", sep="\t", index=False)

    if posthoc is not None:
        posthoc.to_csv(ANALYSIS_DIR / "posthoc.tsv", sep="\t", index=False)

    (ANALYSIS_DIR / "apa_summary.md").write_text(
        _render_apa(test_name, stats_row, q[0], groups, samples, outcome_col, group_col),
        encoding="utf-8")

    write_meta(parameters, decisions=textwrap.dedent(f"""\
        Outcome: {outcome_col}; group: {group_col}; n groups: {len(groups)}.
        Assumption checks via assumption_checks.py (Shapiro for normality,
        Levene for homogeneity, IQR-based outlier flag).
        Test chosen: {test_name} (parametric_ok={parametric_ok}).
        Effect size reported alongside p; BH-FDR q given even for single test.
        Customize columns / test choice / FDR in the generated copy.
    """).strip())


def _load_user_defaults() -> dict:
    """Parse the user-level defaults that the agent honours pipeline-wide.

    Looks for ``USER.md`` at the workspace root (where the gateway lives) and
    extracts the documented lines:

        - Default metadata grouping column: group
        - Default outcome column: <name>

    These are conventions used across the agent's skills and were previously
    ignored by this script — leading to the 2026-06-09 incident where the user
    had `group` set in USER.md but the skill bailed out because its own
    heuristic couldn't find a categorical column on a wide microbiome table.
    Returns an empty dict if USER.md is missing or unparseable — callers fall
    through to the heuristic.
    """
    import os
    import re
    # Hardcoded search list — keep this short and explicit.
    candidates = [
        os.environ.get("OPENCLAW_USER_MD"),
        "/openclaw/USER.md",
        "/job/USER.md",
        str(Path(__file__).resolve().parent.parent.parent.parent / "USER.md"),
    ]
    text = ""
    for path in candidates:
        if not path:
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
            break
        except OSError:
            continue
    if not text:
        return {}
    defaults: dict[str, str] = {}
    patterns = {
        "group":   re.compile(r"Default\s+metadata\s+grouping\s+column\s*[:：]\s*[`'\"]?([\w.\-]+)", re.IGNORECASE),
        "outcome": re.compile(r"Default\s+outcome\s+column\s*[:：]\s*[`'\"]?([\w.\-]+)", re.IGNORECASE),
    }
    for key, pat in patterns.items():
        m = pat.search(text)
        if m:
            defaults[key] = m.group(1)
    return defaults


def _explicit_column_match(df, md, *, candidates: tuple[str, ...]) -> str | None:
    """Return the first name in `candidates` that exists in df or md."""
    for name in candidates:
        if df is not None and name in df.columns:
            return name
        if md is not None and name in md.columns:
            return name
    return None


def _first_numeric(df, exclude: set[str] | None = None):
    exclude = {x.lower() for x in (exclude or set())}
    for c in df.columns:
        if c.lower() in exclude:
            continue
        if df[c].dtype.kind in "fiu":
            return c
    return None


def _first_categorical(df, md):
    for src in (df, md):
        if src is None:
            continue
        for c in src.columns:
            s = src[c]
            if s.dtype == object or str(s.dtype).startswith("category"):
                if 2 <= s.dropna().nunique() <= 10:
                    return c
    return None


def _run_test(samples, groups, parametric_ok, override):
    """Return (test_name, {stat, p, effect, effect_name, ci_lo, ci_hi}, posthoc_df_or_None)."""
    from scipy import stats as sp
    import numpy as np
    import pandas as pd

    name = (override or "").lower() or None

    if len(samples) == 2:
        if name == "welch" or (name is None and parametric_ok):
            t, p = sp.ttest_ind(samples[0], samples[1], equal_var=False)
            d, lo, hi = _cohens_d_ci(samples[0], samples[1])
            return "Welch t-test", {
                "test": "welch_t", "statistic": float(t), "p": float(p),
                "effect": d, "effect_name": "cohens_d",
                "ci_lo": lo, "ci_hi": hi,
            }, None
        u, p = sp.mannwhitneyu(samples[0], samples[1], alternative="two-sided")
        n1, n2 = len(samples[0]), len(samples[1])
        r = 1 - (2 * u) / (n1 * n2)   # rank-biserial correlation
        return "Mann-Whitney U", {
            "test": "mannwhitney_u", "statistic": float(u), "p": float(p),
            "effect": float(r), "effect_name": "rank_biserial_r",
            "ci_lo": None, "ci_hi": None,
        }, None

    # ≥3 groups
    if name == "anova" or (name is None and parametric_ok):
        f, p = sp.f_oneway(*samples)
        ss_b = sum(len(s) * (np.mean(s) - np.mean(np.concatenate(samples)))**2 for s in samples)
        ss_t = sum((x - np.mean(np.concatenate(samples)))**2 for s in samples for x in s)
        eta2 = float(ss_b / ss_t) if ss_t else None
        posthoc = None
        try:
            from scipy.stats import tukey_hsd
            res = tukey_hsd(*samples)
            posthoc = pd.DataFrame({
                "comparison": [f"{a} vs {b}" for i, a in enumerate(groups) for b in groups[i+1:]],
                "statistic":  [res.statistic[i][j] for i in range(len(groups)) for j in range(i+1, len(groups))],
                "p":          [res.pvalue[i][j]    for i in range(len(groups)) for j in range(i+1, len(groups))],
            })
        except Exception:
            pass
        return "One-way ANOVA", {
            "test": "anova_oneway", "statistic": float(f), "p": float(p),
            "effect": eta2, "effect_name": "eta_squared",
            "ci_lo": None, "ci_hi": None,
        }, posthoc

    h, p = sp.kruskal(*samples)
    n = sum(len(s) for s in samples)
    eps2 = float((h - len(samples) + 1) / (n - len(samples))) if n > len(samples) else None
    return "Kruskal-Wallis", {
        "test": "kruskal_wallis", "statistic": float(h), "p": float(p),
        "effect": eps2, "effect_name": "epsilon_squared",
        "ci_lo": None, "ci_hi": None,
    }, None


def _cohens_d_ci(a, b, ci=0.95):
    import numpy as np
    from scipy import stats as sp
    n1, n2 = len(a), len(b)
    s2 = ((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2)
    d = float((a.mean() - b.mean()) / (s2 ** 0.5)) if s2 > 0 else float("nan")
    se = float(((n1 + n2) / (n1 * n2) + d**2 / (2 * (n1 + n2))) ** 0.5)
    z = sp.norm.ppf(1 - (1 - ci) / 2)
    return d, float(d - z * se), float(d + z * se)


def _render_apa(test_name, row, q, groups, samples, outcome_col, group_col):
    eff = row.get("effect")
    eff_name = row.get("effect_name")
    p = row.get("p")
    p_str = "< .001" if p is not None and p < 0.001 else f"{p:.3f}".lstrip("0")
    q_str = "< .001" if q is not None and q < 0.001 else f"{q:.3f}".lstrip("0")
    eff_str = f"{eff_name}={eff:.3f}" if eff is not None else "effect=NA"
    ns = ", ".join(f"n_{g}={len(s)}" for g, s in zip(groups, samples))
    return textwrap.dedent(f"""\
        # Statistical analysis — APA-style summary

        Differences in **{outcome_col}** across levels of **{group_col}** were
        evaluated using a {test_name} ({ns}). The test yielded
        {row['test']}({row['statistic']:.3f}), p = {p_str}; BH-FDR q = {q_str}.
        Effect size: {eff_str}.

        Assumption diagnostics (normality, homogeneity, outliers) are in
        `assumption_checks.tsv`. When the parametric assumptions are violated,
        the wrapper falls back to the rank-based alternative automatically.
    """).strip() + "\n"


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
    out = {}
    for name in ("pandas", "numpy", "scipy", "statsmodels"):
        try:
            out[name] = __import__(name).__version__
        except ImportError:
            out[name] = "missing"
    return out


if __name__ == "__main__":
    main()
