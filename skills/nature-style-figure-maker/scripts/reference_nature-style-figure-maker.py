#!/usr/bin/env python3
"""
reference_nature-style-figure-maker.py — TEMPLATE.

⚠️  Do NOT execute this file directly via run_downstream.sh on a real job.
    Per AGENTS.md §W3 and contributor_guide.md §1, the Planner LLM MUST first
    copy this file into /job/reproducibility/generated_scripts/<skill>_<ts>.py
    and customize the figure spec (which columns become axes, panels,
    color/shape encodings, captions) for the job's actual data.

Purpose
-------
Produce Nature-style multi-panel publication figures from a tidy data table.
Defaults match the conventions enforced by AI-report-generator's CNS theme:
  • Arial-only sans-serif (no decorative fonts)
  • NPG (Nature Publishing Group) palette
  • No gridlines, no zerolines; bold black X/Y axis spines (1.5 px)
  • Outside ticks; tabular-nums for any annotated numbers
  • Output sizes calibrated for journal column widths (single 89 mm,
    double 183 mm) at 600 DPI raster + vector PDF

Backend
-------
This template uses **Python (matplotlib + seaborn)**. To switch to R
(ggplot2 + patchwork + ggsci + ragg), replace the body of `render_figure`
with an Rscript subprocess call — both backends are available in
openclaw/downstream:1.1.0. Do NOT mix backends within one panel.

Inputs  (under STAGE_DIR; missing required input → exit 1)
---------------------------------------------------------
  data.tsv     — required; tidy/long-format table to plot
  spec.yaml    — optional figure spec (panel layout, encodings, captions).
                 If absent, a one-panel scatter from the first two numeric
                 columns is produced as a placeholder.

Outputs (under ANALYSIS_DIR)
----------------------------
  figure.pdf                          — vector, journal-ready
  figure.png                          — 600 DPI raster preview
  nature-style-figure-maker_meta.json
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_NAME    = "nature-style-figure-maker"
STAGE_DIR     = Path(f"/job/stage/{SKILL_NAME}")
ANALYSIS_DIR  = Path(f"/job/analysis/{SKILL_NAME}")
GENERATED_DIR = Path("/job/reproducibility/generated_scripts")
RANDOM_SEED   = 42

# NPG palette — must match ggsci::pal_npg() and the AI-report-generator theme.
NPG_PALETTE = ["#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F",
               "#8491B4", "#91D1C2", "#DC0000", "#7E6148", "#B09C85"]

# Column widths from Nature author guide (mm → inches at 1 in = 25.4 mm).
COL_SINGLE_IN = 89  / 25.4   # 3.50 in
COL_DOUBLE_IN = 183 / 25.4   # 7.20 in


def fail(msg: str, code: int = 1) -> None:
    print(f"[{SKILL_NAME}] FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def main() -> None:
    if not STAGE_DIR.is_dir():
        fail(f"required input dir missing: {STAGE_DIR}")
    data_path = STAGE_DIR / "data.tsv"
    if not data_path.is_file():
        fail(f"required input missing: {data_path}")

    for d in (ANALYSIS_DIR, GENERATED_DIR):
        d.mkdir(parents=True, exist_ok=True)

    spec = load_spec(STAGE_DIR / "spec.yaml")
    parameters = {
        "data":       str(data_path),
        "spec":       str(STAGE_DIR / "spec.yaml") if (STAGE_DIR / "spec.yaml").is_file() else None,
        "backend":    "matplotlib",
        "width_in":   spec.get("width_in",  COL_DOUBLE_IN),
        "height_in":  spec.get("height_in", COL_DOUBLE_IN * 0.6),
        "dpi":        spec.get("dpi",       600),
        "random_seed": RANDOM_SEED,
    }

    out_pdf, out_png = render_figure(data_path, spec, parameters)

    write_meta(parameters, outputs=[str(out_pdf), str(out_png)],
               decisions=("matplotlib backend; NPG palette; Arial; no grid; "
                          "spec.yaml absent → placeholder scatter rendered" if not parameters["spec"]
                          else "matplotlib backend; spec.yaml drove the layout"))


def load_spec(spec_path: Path) -> dict:
    if not spec_path.is_file():
        return {}
    import yaml
    try:
        return yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        fail(f"spec.yaml parse error: {e}")


def render_figure(data_path: Path, spec: dict, params: dict) -> tuple[Path, Path]:
    import pandas as pd
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    import numpy as np

    np.random.seed(RANDOM_SEED)
    df = pd.read_csv(data_path, sep="\t")

    _apply_npg_theme(mpl)

    # ── TODO LLM: replace this placeholder with the panel layout from spec ──
    # Default: one panel, first two numeric columns as a coloured scatter.
    fig, ax = plt.subplots(figsize=(params["width_in"], params["height_in"]),
                           dpi=params["dpi"])
    numeric_cols = df.select_dtypes("number").columns.tolist()
    if len(numeric_cols) < 2:
        fail("need at least two numeric columns in data.tsv for placeholder scatter")
    x_col, y_col = spec.get("x", numeric_cols[0]), spec.get("y", numeric_cols[1])
    group_col    = spec.get("group")
    if group_col and group_col in df.columns:
        for i, (g, sub) in enumerate(df.groupby(group_col)):
            ax.scatter(sub[x_col], sub[y_col], s=22, alpha=0.85,
                       color=NPG_PALETTE[i % len(NPG_PALETTE)],
                       edgecolor="black", linewidth=0.4, label=str(g))
        ax.legend(frameon=False, fontsize=7, loc="best")
    else:
        ax.scatter(df[x_col], df[y_col], s=22, alpha=0.85,
                   color=NPG_PALETTE[0], edgecolor="black", linewidth=0.4)

    ax.set_xlabel(spec.get("xlabel", x_col))
    ax.set_ylabel(spec.get("ylabel", y_col))
    if spec.get("title"):
        ax.set_title(spec["title"], loc="left", weight="bold", pad=8)

    fig.tight_layout()
    out_pdf = ANALYSIS_DIR / "figure.pdf"
    out_png = ANALYSIS_DIR / "figure.png"
    fig.savefig(out_pdf, format="pdf")
    fig.savefig(out_png, format="png", dpi=params["dpi"])
    plt.close(fig)
    return out_pdf, out_png


def _apply_npg_theme(mpl) -> None:
    """Pin matplotlib rcParams to the CNS / NPG look."""
    mpl.rcParams.update({
        "font.family":        "sans-serif",
        "font.sans-serif":    ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size":          8,
        "axes.titlesize":     9,
        "axes.labelsize":     8,
        "axes.linewidth":     1.5,
        "axes.spines.top":    False,
        "axes.spines.right":  False,
        "axes.grid":          False,
        "xtick.direction":    "out",
        "ytick.direction":    "out",
        "xtick.major.width":  1.2,
        "ytick.major.width":  1.2,
        "xtick.major.size":   3.5,
        "ytick.major.size":   3.5,
        "legend.frameon":     False,
        "pdf.fonttype":       42,   # TrueType — fonts embeddable / editable
        "ps.fonttype":        42,
    })


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
    for name in ("pandas", "numpy", "matplotlib", "seaborn", "yaml"):
        try:
            pkgs[name] = __import__(name).__version__
        except ImportError:
            pkgs[name] = "missing"
    return pkgs


if __name__ == "__main__":
    main()
