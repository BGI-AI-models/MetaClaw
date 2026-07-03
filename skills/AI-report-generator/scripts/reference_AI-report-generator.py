"""
reference_AI-report-generator.py — TEMPLATE (read-only at /pipeline/scripts/ inside
the downstream container). DO NOT run this directly for production reports:
copy to /job/reproducibility/generated_scripts/AI-report-generator_<YYYYMMDD-HHMMSS>.py,
customize for the dataset (KPIs, captions, narrative), then invoke:

    bash gateway/run_downstream.sh <job-id> --skills AI-report-generator

What this template does
-----------------------
1. Discover analysis products under ``<job-dir>/analysis/`` and stage manifest.
2. Pick the most appropriate Jinja template via ``select_template.select(...)``.
3. Render a single-file HTML report into ``<job-dir>/analysis/report/report.html``.
4. Embed plotly.js and any PNG figures inline so the report works fully offline.

CNS-grade styling (Nature/Cell/Science)
---------------------------------------
- Strict Arial sans-serif typography throughout.
- NPG (Nature Publishing Group) categorical palette + viridis-like sequential.
- Data-ink optimised plotly figures: no gridlines, bold black spines, outside ticks.
  Helpers ``apply_npg_style`` / ``new_figure`` wrap any plotly Figure in seconds.
- Booktabs-style HTML tables with optional "Table 1" baseline characteristics
  layout (``baseline_table_from_df``).
- Reproducibility code appendix: a customised copy can attach the
  ggplot2 / ComplexHeatmap / seaborn snippets the analyst will run locally to
  produce vector PDFs for journal submission. ``default_code_appendix()``
  ships ready-to-paste templates wired to NPG colours and 1.6:1 aspect ratios
  so the output drops into a manuscript Figure panel without further tuning.

The body is deliberately conservative: it never fabricates numbers — every KPI
or table cell that cannot be sourced from a real artefact is rendered as ``—``.
A customised copy is expected to fill in tighter, dataset-specific content.

Contract:
    --job-dir <path>      (default: /job)
    --user-prompt <str>   free-text request from the analyst (drives selection)
    --pipeline <str>      pipeline name override
    --template <name>     force a specific template
    Reads  : <job-dir>/stage/, <job-dir>/analysis/*/
    Writes : <job-dir>/analysis/report/report.html  + report-generator_meta.json
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import json
import os
import sys
import textwrap
import traceback
from pathlib import Path
from typing import Any, Iterable

SKILL = "AI-report-generator"
ANALYSIS_SUBDIR = "report"
STAGE_SUBDIR = ""

THIS_DIR = Path(__file__).resolve().parent
ASSETS_DIR = THIS_DIR.parent / "assets"
TEMPLATES_DIR = ASSETS_DIR / "templates"
PARTIALS_DIR = ASSETS_DIR / "partials"
THEME_CSS = ASSETS_DIR / "theme.css"

# Make ``select_template`` importable both when run from the container
# (/pipeline/scripts/) and when run from a customized copy under
# /job/reproducibility/generated_scripts/.
sys.path.insert(0, str(THIS_DIR))
try:
    from select_template import select as select_template  # type: ignore
except Exception:  # pragma: no cover
    select_template = None  # filled in lazily with a clear error later


# ---------------------------------------------------------------------------
# NPG palette + plotly helpers
# ---------------------------------------------------------------------------

# Nature Publishing Group categorical palette (mirrors ggsci::pal_npg("nrc")).
NPG_PALETTE: list[str] = [
    "#E64B35",  # red
    "#4DBBD5",  # cyan
    "#00A087",  # teal
    "#3C5488",  # dark blue
    "#F39B7F",  # salmon
    "#8491B4",  # gray-blue
    "#91D1C2",  # mint
    "#DC0000",  # bright red
    "#7E6148",  # brown
    "#B09C85",  # warm gray
]

# Sequential / continuous (NPG-tinted, perceptually ordered).
NPG_SEQUENTIAL: list[tuple[float, str]] = [
    (0.00, "#1f2c4d"),
    (0.25, "#3C5488"),
    (0.50, "#4DBBD5"),
    (0.75, "#91D1C2"),
    (1.00, "#f5f5f5"),
]

ARIAL_STACK = "Arial, Helvetica, sans-serif"


def _npg_axis() -> dict:
    """Return a Plotly axis dict with no gridlines and bold black spines."""
    return dict(
        showgrid=False, zeroline=False, showline=True,
        linecolor="#000000", linewidth=1.5, mirror=False,
        ticks="outside", tickcolor="#000000", tickwidth=1,
        tickfont=dict(family=ARIAL_STACK, size=12, color="#000"),
        title=dict(font=dict(family=ARIAL_STACK, size=13, color="#000")),
        automargin=True,
    )


def apply_npg_style(fig: Any) -> Any:
    """In-place restyle a Plotly Figure to NPG / CNS conventions.

    - Arial typography across all text.
    - NPG categorical colourway.
    - White paper + plot background, thin black axis lines, no gridlines.
    - Tick marks point outside the plotting area (CNS preference).
    - Margins tightened so the figure prints close to journal column width.

    Safe to call on any ``plotly.graph_objects.Figure``; returns the same
    object so calls can be chained.
    """
    try:
        fig.update_layout(
            colorway=NPG_PALETTE,
            font=dict(family=ARIAL_STACK, size=12, color="#000"),
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            margin=dict(l=60, r=20, t=40, b=50),
            title=dict(font=dict(family=ARIAL_STACK, size=14, color="#000"),
                       x=0.02, xanchor="left"),
            legend=dict(bgcolor="rgba(255,255,255,0)", bordercolor="#d0d0d0",
                        borderwidth=0, font=dict(family=ARIAL_STACK, size=11)),
        )
        fig.update_xaxes(**_npg_axis())
        fig.update_yaxes(**_npg_axis())
    except Exception:
        pass
    return fig


def new_figure(*args, **kwargs):
    """Shortcut: ``import plotly.graph_objects as go; new_figure(go.Bar(...))``.

    Returns a Figure with NPG / CNS defaults already applied. Falls back to a
    clear error if plotly is unavailable in the runtime.
    """
    import plotly.graph_objects as go  # type: ignore
    fig = go.Figure(*args, **kwargs)
    return apply_npg_style(fig)


def fig_to_html(fig: Any) -> str:
    """Render a Plotly Figure to an HTML fragment suitable for embedding.

    NPG style is applied first; ``include_plotlyjs=False`` keeps the bundle
    inlined exactly once at the document level.
    """
    apply_npg_style(fig)
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False})


# ---------------------------------------------------------------------------
# Argument parsing & meta
# ---------------------------------------------------------------------------

def _now() -> str:
    return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _args():
    p = argparse.ArgumentParser(description="Reference template for " + SKILL)
    p.add_argument("--job-dir", default=os.environ.get("JOB_DIR", "/job"))
    p.add_argument("--user-prompt", default=os.environ.get("OPENCLAW_USER_PROMPT", ""))
    p.add_argument("--pipeline", default="")
    p.add_argument("--template", default="", help="Force a specific template name")
    p.add_argument("--random-seed", type=int, default=42)
    return p.parse_args()


def _write_meta(analysis_dir: Path, status: str, notes: str, **extra) -> None:
    meta = {
        "skill": SKILL,
        "status": status,
        "timestamp": _now(),
        "notes": notes,
        "random_seed": extra.pop("random_seed", None),
        "inputs": extra.pop("inputs", []),
        "outputs": extra.pop("outputs", []),
        "script": __file__,
        "is_reference_template": True,
    }
    meta.update(extra)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    (analysis_dir / f"{SKILL}_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def _read_manifest(job_dir: Path) -> dict[str, Any]:
    m = job_dir / "stage" / "manifest.json"
    if m.is_file():
        try:
            return json.loads(m.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _collect_skill_meta(analysis_root: Path) -> dict[str, dict]:
    """Read every ``*_meta.json`` so the report can describe what really ran."""
    out: dict[str, dict] = {}
    if not analysis_root.is_dir():
        return out
    for meta_path in analysis_root.rglob("*_meta.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        skill = data.get("skill") or meta_path.stem.replace("_meta", "")
        out[skill] = data
    return out


def _png_to_data_uri(p: Path) -> str | None:
    if not p.is_file():
        return None
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def _embed_image(p: Path, alt: str = "") -> str:
    uri = _png_to_data_uri(p)
    if not uri:
        return ""
    return f'<img src="{uri}" alt="{alt}" loading="lazy" />'


# ---------------------------------------------------------------------------
# Plotly bundle — read once, embedded inline so the HTML is self-contained
# ---------------------------------------------------------------------------

def _plotly_bundle() -> str:
    try:
        import plotly.offline as _po  # type: ignore
        return f"<script>{_po.get_plotlyjs()}</script>"
    except Exception:
        return "<script>/* plotly.js unavailable in this env */</script>"


# ---------------------------------------------------------------------------
# Statistical helpers — Table 1 (baseline characteristics)
# ---------------------------------------------------------------------------

def _fmt_p(p: float | None) -> str:
    if p is None:
        return "—"
    if p < 0.001:
        return "< 0.001"
    return f"{p:.3f}"


def baseline_table_from_df(
    df: Any,
    group_col: str,
    variables: Iterable[str | dict],
    overall_label: str = "Overall",
    include_overall: bool = True,
    test_legend: str = ("Cont., two-sided <i>t</i>-test or Wilcoxon; "
                        "Cat., χ² or Fisher exact, as appropriate."),
) -> dict:
    """Build the ``data`` payload accepted by ``ui.baseline_table``.

    ``variables`` items are either:
      - ``"age"`` → continuous (mean ± SD, t-test)
      - ``{"name": "age", "kind": "cont", "dp": 1, "label": "Age, years"}``
      - ``{"name": "sex", "kind": "cat"}``  → n (%), χ² test
      - ``{"name": "subhead", "kind": "subhead", "label": "Demographics"}``

    Tests are basic and meant as a starting point — replace for clinical work.
    """
    import numpy as np
    import pandas as pd
    from scipy import stats  # type: ignore

    groups = sorted(df[group_col].dropna().unique().tolist())
    group_n = {g: int((df[group_col] == g).sum()) for g in groups}

    rows: list[dict] = []
    for v in variables:
        if isinstance(v, str):
            v = {"name": v, "kind": "cont"}
        kind = v.get("kind", "cont")
        if kind == "subhead":
            rows.append({"type": "subhead", "variable": v.get("label") or v["name"]})
            continue
        name = v["name"]
        label = v.get("label", name)
        dp = int(v.get("dp", 2))
        values: dict[str, Any] = {}
        p_val: float | None = None

        if kind == "cont":
            series_by_group = [df.loc[df[group_col] == g, name].dropna() for g in groups]
            if include_overall:
                ov = df[name].dropna()
                values["overall"] = f"{ov.mean():.{dp}f} ± {ov.std(ddof=1):.{dp}f}"
            for g, s in zip(groups, series_by_group):
                if len(s) == 0:
                    values[g] = "—"
                else:
                    values[g] = f"{s.mean():.{dp}f} ± {s.std(ddof=1):.{dp}f}"
            try:
                if len(series_by_group) == 2 and all(len(s) > 1 for s in series_by_group):
                    p_val = float(stats.ttest_ind(series_by_group[0], series_by_group[1],
                                                  equal_var=False, nan_policy="omit").pvalue)
                elif len(series_by_group) > 2:
                    p_val = float(stats.f_oneway(*[s for s in series_by_group if len(s) > 1]).pvalue)
            except Exception:
                p_val = None
            values["p"] = _fmt_p(p_val)
            values["sig"] = bool(p_val is not None and p_val < 0.05)
            rows.append({"type": "row", "variable": label,
                         "values": values, "note": f"mean ± SD"})

        elif kind == "cat":
            # Build a proper contingency table for χ² /Fisher.
            ct = pd.crosstab(df[name], df[group_col])
            categories = ct.index.tolist()
            try:
                if ct.shape == (2, 2):
                    p_val = float(stats.fisher_exact(ct.values)[1])
                else:
                    p_val = float(stats.chi2_contingency(ct.values, correction=False)[1])
            except Exception:
                p_val = None

            for cat in categories:
                values_c: dict[str, Any] = {}
                if include_overall:
                    k = int((df[name] == cat).sum())
                    n = int(df[name].notna().sum())
                    values_c["overall"] = f"{k}/{n} ({100*k/n if n else 0:.1f}%)"
                for g in groups:
                    sub = df.loc[df[group_col] == g, name]
                    n = int(sub.notna().sum())
                    k = int((sub == cat).sum())
                    values_c[g] = f"{k}/{n} ({100*k/n if n else 0:.1f}%)"
                values_c["p"] = _fmt_p(p_val) if cat == categories[0] else ""
                values_c["sig"] = bool(p_val is not None and p_val < 0.05) and cat == categories[0]
                rows.append({"type": "row", "variable": f"{label}: {cat}",
                             "values": values_c, "note": "n (%)"})

    return {
        "groups": [{"label": g, "n": group_n[g]} for g in groups],
        "overall": ({"label": overall_label, "n": int(len(df))} if include_overall else None),
        "rows": rows,
        "test_legend": test_legend,
    }


# ---------------------------------------------------------------------------
# Code appendix — ggplot2 / ComplexHeatmap / seaborn templates
# ---------------------------------------------------------------------------

_NPG_R_VEC = ", ".join(f'"{c}"' for c in NPG_PALETTE)

_CODE_GGPLOT_STRIP = textwrap.dedent(f"""\
    # ---- Figure: Strip chart of a continuous variable by group --------------
    # Run with R >= 4.2; install once: install.packages(c("ggplot2","ggsci","readxl"))
    library(ggplot2); library(ggsci); library(readxl)

    df <- read_excel("data.xlsx", sheet = 1)        # <- swap for your file
    # Expected columns: Group (factor), Value (numeric).

    p <- ggplot(df, aes(x = Group, y = Value, colour = Group)) +
      geom_jitter(width = 0.18, size = 1.8, alpha = 0.85) +
      stat_summary(fun = median, geom = "crossbar",
                   width = 0.45, fatten = 1, colour = "black") +
      scale_colour_npg() +
      labs(x = NULL, y = "Value", title = NULL) +
      theme_classic(base_family = "Arial", base_size = 11) +
      theme(panel.grid = element_blank(),
            axis.line = element_line(colour = "black", linewidth = 0.6),
            axis.ticks = element_line(colour = "black", linewidth = 0.5),
            legend.position = "none")

    ggsave("Fig_strip.pdf", p, width = 3.2, height = 2.8, useDingbats = FALSE)
    """)

_CODE_GGPLOT_STACKED = textwrap.dedent(f"""\
    # ---- Figure: Stacked composition (relative abundance) -------------------
    library(ggplot2); library(ggsci); library(readxl); library(dplyr); library(tidyr)

    df <- read_excel("data.xlsx", sheet = "composition")
    # Expected: SampleID, plus one column per category (relative abundance, sums to 1).

    long <- df %>% pivot_longer(-SampleID, names_to = "Taxon", values_to = "Abundance")

    p <- ggplot(long, aes(x = SampleID, y = Abundance, fill = Taxon)) +
      geom_col(width = 0.85, colour = NA) +
      scale_fill_npg() +
      scale_y_continuous(expand = c(0, 0), labels = scales::percent_format()) +
      labs(x = NULL, y = "Relative abundance", fill = NULL) +
      theme_classic(base_family = "Arial", base_size = 11) +
      theme(panel.grid = element_blank(),
            axis.line = element_line(colour = "black", linewidth = 0.6),
            axis.text.x = element_text(angle = 45, hjust = 1),
            legend.key.size = unit(0.35, "cm"))

    ggsave("Fig_stacked.pdf", p, width = 5.2, height = 3.2, useDingbats = FALSE)
    """)

_CODE_GGPLOT_VOLCANO = textwrap.dedent(f"""\
    # ---- Figure: Volcano plot of differential abundance / expression --------
    library(ggplot2); library(ggsci); library(readxl); library(ggrepel)

    df <- read_excel("data.xlsx", sheet = "differential")
    # Expected columns: feature, log2fc, pvalue, qvalue.

    df$Direction <- with(df, ifelse(qvalue < 0.05 & log2fc >  log2(1.5), "Up",
                              ifelse(qvalue < 0.05 & log2fc < -log2(1.5), "Down", "n.s.")))

    p <- ggplot(df, aes(x = log2fc, y = -log10(pvalue), colour = Direction)) +
      geom_point(size = 1.2, alpha = 0.85) +
      scale_colour_manual(values = c(Up = "#E64B35", Down = "#3C5488", `n.s.` = "#B09C85")) +
      geom_vline(xintercept = c(-log2(1.5), log2(1.5)), linetype = "dashed", colour = "grey40") +
      geom_hline(yintercept = -log10(0.05), linetype = "dashed", colour = "grey40") +
      ggrepel::geom_text_repel(
        data = subset(df, Direction != "n.s."),
        aes(label = feature), size = 2.6, max.overlaps = 12) +
      labs(x = expression(log[2]~"fold change"), y = expression(-log[10](italic(P)))) +
      theme_classic(base_family = "Arial", base_size = 11) +
      theme(panel.grid = element_blank(),
            axis.line = element_line(colour = "black", linewidth = 0.6),
            legend.position = c(0.85, 0.95), legend.title = element_blank())

    ggsave("Fig_volcano.pdf", p, width = 4.0, height = 3.4, useDingbats = FALSE)
    """)

_CODE_COMPLEXHEATMAP = textwrap.dedent(f"""\
    # ---- Figure: Heatmap of top differential features -----------------------
    # install.packages("BiocManager"); BiocManager::install("ComplexHeatmap")
    library(ComplexHeatmap); library(circlize); library(readxl)

    mat <- as.matrix(read_excel("data.xlsx", sheet = "heatmap_matrix",
                                col_names = TRUE) |> tibble::column_to_rownames("feature"))
    meta <- read_excel("data.xlsx", sheet = "heatmap_meta")  # SampleID, Group

    col_fun <- colorRamp2(c(-2, 0, 2), c("#3C5488", "#FFFFFF", "#E64B35"))

    ha <- HeatmapAnnotation(
      Group = meta$Group,
      col = list(Group = setNames(c({_NPG_R_VEC})[seq_along(unique(meta$Group))],
                                  unique(meta$Group))),
      annotation_name_gp = gpar(fontfamily = "Arial", fontsize = 9),
      simple_anno_size = unit(3, "mm"))

    pdf("Fig_heatmap.pdf", width = 5.2, height = 4.8, useDingbats = FALSE)
    Heatmap(mat, name = "z-score", col = col_fun, top_annotation = ha,
            row_names_gp = gpar(fontfamily = "Arial", fontsize = 8),
            column_names_gp = gpar(fontfamily = "Arial", fontsize = 8),
            cluster_columns = TRUE, cluster_rows = TRUE,
            show_column_names = FALSE, border = TRUE,
            heatmap_legend_param = list(direction = "horizontal",
                                        title_position = "topcenter"))
    dev.off()
    """)

_CODE_SEABORN_FREQ = textwrap.dedent(f"""\
    # ---- Figure: Mutation / event frequency bar chart (Python) ---------------
    # pip install pandas matplotlib seaborn openpyxl
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    from matplotlib import rcParams

    NPG = ["#E64B35","#4DBBD5","#00A087","#3C5488","#F39B7F",
           "#8491B4","#91D1C2","#DC0000","#7E6148","#B09C85"]

    rcParams.update({{
        "font.family": "Arial",
        "font.size": 10,
        "axes.linewidth": 1.0,
        "axes.edgecolor": "black",
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.direction": "out", "ytick.direction": "out",
        "xtick.major.size": 3, "ytick.major.size": 3,
        "axes.grid": False,
    }})
    sns.set_palette(NPG)

    df = pd.read_excel("data.xlsx", sheet_name="frequency")  # gene, frequency
    df = df.sort_values("frequency", ascending=False).head(15)

    fig, ax = plt.subplots(figsize=(3.6, 3.2))
    sns.barplot(data=df, y="gene", x="frequency", color=NPG[0], ax=ax)
    ax.set_xlabel("Mutation frequency")
    ax.set_ylabel("")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(width=1.0)

    fig.tight_layout()
    fig.savefig("Fig_freq.pdf", dpi=600, bbox_inches="tight")
    """)

_CODE_SEABORN_BOX = textwrap.dedent(f"""\
    # ---- Figure: Box-and-strip plot grouped by clinical variable -------------
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    from matplotlib import rcParams

    NPG = ["#E64B35","#4DBBD5","#00A087","#3C5488","#F39B7F"]

    rcParams.update({{
        "font.family": "Arial", "font.size": 10,
        "axes.linewidth": 1.0, "axes.edgecolor": "black",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": False,
    }})

    df = pd.read_excel("data.xlsx", sheet_name="biomarker")  # group, value

    fig, ax = plt.subplots(figsize=(3.4, 3.2))
    sns.boxplot(data=df, x="group", y="value", palette=NPG,
                width=0.55, fliersize=0, linewidth=1.0, ax=ax)
    sns.stripplot(data=df, x="group", y="value", color="black",
                  size=2.5, alpha=0.6, jitter=0.18, ax=ax)
    ax.set_xlabel(""); ax.set_ylabel("Biomarker level")
    fig.tight_layout()
    fig.savefig("Fig_box.pdf", dpi=600, bbox_inches="tight")
    """)


def default_code_appendix() -> list[dict]:
    """Return the default ggplot2 / ComplexHeatmap / seaborn snippet bank.

    A customised copy can append more entries (e.g., survival KM curves, ROC)
    or replace these with project-specific code. The renderer will inject
    them into the report under "Reproducibility — Source code for vector
    figures" so the analyst can produce journal-grade PDFs locally.
    """
    return [
        {
            "title": "Strip chart by group (continuous biomarker)",
            "lang": "r", "filename": "Fig_strip.R",
            "depends": ["ggplot2", "ggsci", "readxl"],
            "description": "Reproduces a per-group jitter overlay with median crossbar; outputs 3.2×2.8 in PDF.",
            "code": _CODE_GGPLOT_STRIP,
        },
        {
            "title": "Stacked composition (relative abundance)",
            "lang": "r", "filename": "Fig_stacked.R",
            "depends": ["ggplot2", "ggsci", "dplyr", "tidyr", "readxl"],
            "description": "Per-sample stacked bar with NPG palette; outputs 5.2×3.2 in PDF.",
            "code": _CODE_GGPLOT_STACKED,
        },
        {
            "title": "Volcano plot (differential abundance / expression)",
            "lang": "r", "filename": "Fig_volcano.R",
            "depends": ["ggplot2", "ggsci", "ggrepel", "readxl"],
            "description": "Up/Down/n.s. coloured volcano with q < 0.05 and |log2FC| > log2(1.5) cut-offs.",
            "code": _CODE_GGPLOT_VOLCANO,
        },
        {
            "title": "Heatmap of top features (ComplexHeatmap)",
            "lang": "r", "filename": "Fig_heatmap.R",
            "depends": ["ComplexHeatmap", "circlize", "readxl", "tibble"],
            "description": "Z-scored heatmap with NPG group annotation bar; outputs 5.2×4.8 in PDF.",
            "code": _CODE_COMPLEXHEATMAP,
        },
        {
            "title": "Mutation / event frequency bar chart (Python)",
            "lang": "python", "filename": "Fig_freq.py",
            "depends": ["pandas", "matplotlib", "seaborn", "openpyxl"],
            "description": "Top-15 frequency bars with NPG colours; saves 600 DPI PDF.",
            "code": _CODE_SEABORN_FREQ,
        },
        {
            "title": "Box + strip plot of clinical variable (Python)",
            "lang": "python", "filename": "Fig_box.py",
            "depends": ["pandas", "matplotlib", "seaborn", "openpyxl"],
            "description": "Group-wise box plot with overlaid raw points; 600 DPI PDF.",
            "code": _CODE_SEABORN_BOX,
        },
    ]


# ---------------------------------------------------------------------------
# Default context — minimal, honest. A customized copy should replace these.
# ---------------------------------------------------------------------------

def _default_context(
    job_dir: Path,
    manifest: dict,
    skill_meta: dict[str, dict],
    decision_reason: str,
) -> dict[str, Any]:
    pipeline = manifest.get("pipeline") or "—"
    samples = manifest.get("samples") or []
    n_samples = len(samples) if isinstance(samples, list) else (samples or None)
    groups = manifest.get("groups") or []

    methods_table = []
    for skill, m in sorted(skill_meta.items()):
        methods_table.append({
            "step": skill,
            "status": m.get("status", "—"),
            "notes": (m.get("notes") or "")[:280],
        })

    return {
        "title": f"{pipeline} — analysis report",
        "subtitle": (f"Auto-generated from /job/analysis ({len(skill_meta)} step(s)). "
                     f"Styled to NPG / Nature Publishing Group conventions."),
        "eyebrow": "BioLine v3 · OpenClaw",
        "meta": {
            "job_id": str(job_dir).rstrip("/").split("/")[-1] or "—",
            "pipeline": pipeline if pipeline != "—" else None,
            "samples": n_samples,
            "groups": groups,
            "generated_at": _now(),
            "bioline_version": "3",
            "template": None,  # filled in by _render
        },
        "kpis": [
            {"label": "Pipeline", "value": pipeline, "kind": "accent"},
            {"label": "Samples", "value": n_samples if n_samples is not None else "—"},
            {"label": "Steps run", "value": len(skill_meta)},
            {"label": "Generated", "value": _now().split("T")[0]},
        ],
        "methods_table": methods_table,
        # ── IMRAD prose scaffolding (per reference_skills/scientific-writing).
        # The defaults below are intentionally PLACEHOLDER paragraphs — the
        # customized copy must replace each with substantive prose grounded
        # in the actual dataset, written in full paragraphs (never bullets).
        # See SKILL.md §"IMRAD prose writing" for the conventions the LLM
        # must follow (paragraph length, in-text figure citations, terms
        # defined at first use, reporting-guideline compliance).
        "abstract":          _default_abstract(pipeline, n_samples, skill_meta),
        "introduction":      _default_introduction(pipeline, skill_meta),
        "methods_narrative": _default_methods_narrative(skill_meta),
        "results_intro":     _default_results_intro(skill_meta),
        # `results_figures` / `results_tables` are populated by the
        # customized copy with the actual artefacts produced by upstream
        # skills. Each figure entry: {fig_num, title, body, caption,
        # before, after, anchor?}. Each table entry: {tab_num, rows, cols,
        # caption, before, after, max_rows?}. `before` and `after` are the
        # descriptive paragraphs that frame each artefact in prose.
        "results_figures":   [],
        "results_tables":    [],
        "discussion":        _default_discussion(skill_meta),
        "conclusion":        _default_conclusion(pipeline, skill_meta),
        "refs": [],
        # Code appendix populated with the default snippet bank — a
        # customised copy can replace, extend, or set this to [] to hide it.
        "code_blocks": default_code_appendix(),
        "code_intro": None,
        "exploratory_warning": (
            "This report was rendered by the reference template. Copy "
            "reference_AI-report-generator.py to "
            "/job/reproducibility/generated_scripts/ and customize it (in "
            "particular, replace the placeholder abstract / introduction / "
            "methods_narrative / discussion / conclusion paragraphs with "
            "dataset-specific prose) before treating the content as final."
        ),
    }


# ---------------------------------------------------------------------------
# IMRAD default prose generators
#
# These return PLACEHOLDER paragraphs that get the report past the empty-block
# test on toy data. They explicitly flag themselves as templates so a reader
# can never mistake them for substantive narrative — the customized copy
# under /job/reproducibility/generated_scripts/ is expected to overwrite each
# return value with prose grounded in the actual dataset. Reference for
# style: reference_skills/scientific-writing/references/imrad_structure.md
# ---------------------------------------------------------------------------

def _default_abstract(pipeline: str, n_samples, skill_meta: dict) -> dict:
    """Structured (Nature / JAMA-style) abstract scaffold."""
    n_str = f"{n_samples} samples" if n_samples else "the staged sample set"
    skills = ", ".join(sorted(skill_meta.keys())) or "no downstream skill"
    return {
        "background": ("[PLACEHOLDER — LLM: 1–2 sentences on the biological "
                       "or clinical question this analysis was set up to "
                       "address.]"),
        "objective":  ("[PLACEHOLDER — LLM: state the specific hypothesis or "
                       "objective tested in this run.]"),
        "methods":   (f"We analyzed {n_str} through the <code>{pipeline}</code> "
                      f"pipeline, executing the following downstream steps: "
                      f"{skills}. Detailed per-step parameters are listed in "
                      "the Methods section below."),
        "results":   ("[PLACEHOLDER — LLM: 2–3 sentences quoting the key "
                      "numerical findings from the Results section. Include "
                      "effect sizes and confidence intervals, not just "
                      "p-values.]"),
        "conclusion": ("[PLACEHOLDER — LLM: 1 sentence stating what the data "
                       "support (or fail to support) and what the practical "
                       "implication is.]"),
        "keywords":  ["[PLACEHOLDER]", "[customize per dataset]"],
    }


def _default_introduction(pipeline: str, skill_meta: dict) -> list[str]:
    """Two-to-three paragraphs framing the problem and the gap this analysis fills."""
    return [
        ("[PLACEHOLDER — LLM: opening paragraph that establishes the broader "
         "scientific context. Define any specialised terms at first use, "
         "cite the foundational prior work, and end on the unresolved "
         "question.]"),
        ("[PLACEHOLDER — LLM: middle paragraph narrowing the gap to what "
         "this specific analysis addresses. Reference prior microbiome / "
         "epidemiology / clinical results that motivated the choice of "
         "pipeline and skills.]"),
        (f"In this report we present results from the <code>{pipeline}</code> "
         f"pipeline applied to the staged dataset. The downstream skill "
         f"catalog ({len(skill_meta)} step(s)) was selected to address the "
         "objectives above; specific method choices and parameter overrides "
         "are documented in Methods."),
    ]


def _default_methods_narrative(skill_meta: dict) -> list[str]:
    """Three-paragraph Methods prose. Pairs with the compact methods_table aside."""
    n = len(skill_meta)
    return [
        ("[PLACEHOLDER — LLM: data provenance paragraph. Describe sample "
         "collection, inclusion / exclusion, sequencing platform, batch "
         "structure, and ethics approval where applicable. Cite the "
         "relevant reporting guideline (CONSORT / STROBE / PRISMA / "
         "STARD).]"),
        (f"Downstream analysis used BioLine's two-phase execution model: "
         f"<code>prepare_downstream.sh</code> staged the {n} reference "
         "script(s) into <code>/pipeline/scripts/</code>; the Planner "
         "agent customized each into <code>/job/reproducibility/"
         "generated_scripts/&lt;skill&gt;_&lt;ts&gt;.py</code>, and the "
         "gateway ran them in the <code>openclaw/downstream:1.1.0</code> "
         "container with <code>--network none</code> and a fixed random "
         "seed for reproducibility."),
        ("[PLACEHOLDER — LLM: statistical methods paragraph. Name the "
         "tests used, multiple-testing correction (BH-FDR or otherwise), "
         "effect-size convention (Cohen's d / log2 fold-change / η² etc.), "
         "confidence interval method, and the prevalence / abundance "
         "filters applied before any group comparison.]"),
    ]


def _default_results_intro(skill_meta: dict) -> str:
    return ("The results below summarise the outputs of each downstream "
            f"skill that ran successfully ({len(skill_meta)} in total). "
            "Every numbered figure is followed by a paragraph interpreting "
            "the visible pattern; every numbered table is preceded by one "
            "paragraph stating what it shows and followed by one paragraph "
            "commenting on the magnitudes.")


def _default_discussion(skill_meta: dict) -> list[str]:
    return [
        ("[PLACEHOLDER — LLM: paragraph 1 — summarise the principal finding "
         "in one sentence, then place it in the context of the prior "
         "literature cited in the Introduction. Do not introduce new "
         "results here.]"),
        ("[PLACEHOLDER — LLM: paragraph 2 — strengths and limitations. "
         "Sample size, confounding, batch effects, taxonomic database "
         "version, whether the chosen statistical method is appropriate "
         "for the compositional nature of microbiome data, and any failed "
         "or skipped skills.]"),
        ("[PLACEHOLDER — LLM: paragraph 3 — biological / clinical "
         "interpretation and explicit speculation flagged as such. State "
         "the mechanism the data is most consistent with and the obvious "
         "alternative explanations that cannot be ruled out from this run "
         "alone.]"),
    ]


def _default_conclusion(pipeline: str, skill_meta: dict) -> str:
    return ("[PLACEHOLDER — LLM: one short paragraph stating what the data "
            "support, what they do not, and one concrete next experiment "
            "that would resolve the most important remaining uncertainty.]")


# ---------------------------------------------------------------------------
# Main rendering
# ---------------------------------------------------------------------------

def _render(
    *,
    job_dir: Path,
    user_prompt: str,
    pipeline_override: str,
    template_override: str,
) -> tuple[Path, dict[str, Any]]:
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError as e:
        raise RuntimeError("Jinja2 is required to render the report") from e

    if select_template is None:
        raise RuntimeError("select_template module failed to import")

    manifest = _read_manifest(job_dir)
    pipeline = pipeline_override or manifest.get("pipeline", "")
    skill_meta = _collect_skill_meta(job_dir / "analysis")

    decision = select_template(
        user_prompt=user_prompt,
        pipeline=pipeline,
        analysis_root=job_dir / "analysis",
        explicit=template_override,
    )

    env = Environment(
        loader=FileSystemLoader([str(ASSETS_DIR)]),
        autoescape=select_autoescape(enabled_extensions=("html", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    ctx = _default_context(job_dir, manifest, skill_meta, decision.reason)
    ctx["theme_css"] = THEME_CSS.read_text(encoding="utf-8") if THEME_CSS.is_file() else ""
    ctx["plotlyjs"] = _plotly_bundle()
    ctx["template_name"] = decision.template.name
    ctx["meta"]["template"] = decision.template.name

    # A customized copy should populate template-specific keys (kpis, qc.fastqc,
    # taxonomy.stacked, etc.) before this call. Missing keys render as the
    # neutral "not run" placeholder thanks to the {% if %} guards in templates.
    template = env.get_template(f"templates/{decision.template.file}")
    html = template.render(**ctx)

    out_dir = job_dir / "analysis" / ANALYSIS_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "report.html"
    out.write_text(html, encoding="utf-8")
    return out, {
        "template": decision.template.name,
        "template_file": decision.template.file,
        "selection_reason": decision.reason,
        "selection_score": decision.score,
        "skills_seen": sorted(skill_meta.keys()),
        "report_html": str(out.relative_to(job_dir)),
    }


def run(job_dir: Path, args) -> int:
    analysis_dir = job_dir / "analysis" / ANALYSIS_SUBDIR
    analysis_dir.mkdir(parents=True, exist_ok=True)

    if not (job_dir / "stage").exists() and not (job_dir / "analysis").exists():
        _write_meta(analysis_dir, "aborted",
                    f"Neither stage/ nor analysis/ exists under {job_dir}",
                    random_seed=args.random_seed)
        print(f"[{SKILL}] Nothing to report on under {job_dir}", file=sys.stderr)
        return 2

    out, info = _render(
        job_dir=job_dir,
        user_prompt=args.user_prompt,
        pipeline_override=args.pipeline,
        template_override=args.template,
    )
    _write_meta(
        analysis_dir,
        status="template-noop",
        notes=("Reference template rendered with neutral context. Customize a "
               "copy under /job/reproducibility/generated_scripts/ to populate "
               "real KPIs, figures and narrative."),
        random_seed=args.random_seed,
        inputs=sorted(info["skills_seen"]),
        outputs=[info["report_html"]],
        **info,
    )
    print(f"[{SKILL}] Wrote {out} using template '{info['template']}' "
          f"({info['selection_reason']})")
    return 0


def main() -> int:
    a = _args()
    job_dir = Path(a.job_dir)
    try:
        return run(job_dir, a)
    except Exception:
        analysis_dir = job_dir / "analysis" / ANALYSIS_SUBDIR
        analysis_dir.mkdir(parents=True, exist_ok=True)
        _write_meta(analysis_dir, "error", traceback.format_exc()[:4000],
                    random_seed=a.random_seed)
        raise


if __name__ == "__main__":
    sys.exit(main())
