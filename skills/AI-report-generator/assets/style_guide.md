# Report style guide (CNS-grade)

This document tells customizers of `reference_AI-report-generator.py` how the
template system is laid out and what each piece is responsible for. Read it
before editing a generated copy under
`/job/reproducibility/generated_scripts/`.

The whole system is tuned for **Cell / Nature / Science** (CNS) submission
visuals: Arial typography, NPG palette, no shadows, booktabs tables, data-ink
optimized figures, and a code appendix for vector PDFs.

## Layout

```
assets/
├─ theme.css                  # Design tokens: NPG palette, Arial type stack,
│                               KPI cards (no shadow), booktabs tables,
│                               callouts, code appendix, print rules.
├─ partials/components.html.j2  # Jinja macros:
│                                 kpi/kpi_grid, figure(+fig_num), figure_image,
│                                 graphical_abstract, table(+tab_num),
│                                 baseline_table (Table 1), pvalue/mean_sd/
│                                 median_iqr/ci/nfrac, callout, pill, methods,
│                                 references, code_appendix, provenance, not_run.
├─ templates/
│  ├─ base.html.j2            # Skeleton: <head>, sticky TOC, blocks for
│  │                            graphical_abstract / content / methods /
│  │                            references / code_appendix. Inlines
│  │                            theme_css and plotlyjs once per report,
│  │                            registers a global Plotly NPG template
│  │                            (Arial, no gridlines, bold black spines).
│  ├─ metagenomics_full.html.j2
│  ├─ metagenomics_qc.html.j2
│  ├─ metagenomics_assembly.html.j2
│  ├─ classification.html.j2
│  ├─ regression.html.j2
│  ├─ clustering.html.j2
│  ├─ survival.html.j2
│  ├─ enrichment.html.j2
│  ├─ eda.html.j2
│  └─ generic.html.j2         # Fallback; renders arbitrary `extra_sections`.
└─ template_index.yaml        # Registry consumed by select_template.py
```

## Inheritance

Every template starts with:

```jinja
{% extends "templates/base.html.j2" %}
{% import "partials/components.html.j2" as ui %}

{% block content %} ... {% endblock %}
{% block methods %}{{ ui.methods(methods_table) }}{% endblock %}
{% block references %}{{ ui.references(refs) }}{% endblock %}
```

`base.html.j2` automatically renders the graphical abstract (when
`graphical_abstract_src` is set) and the code appendix (when `code_blocks` is
non-empty), so a typical template only fills in `content` + `methods` +
`references`.

## Context conventions

| Key | Type | Used by |
|---|---|---|
| `title`, `subtitle`, `eyebrow` | str | base header |
| `meta` | dict — keys: `job_id`, `pipeline`, `samples`, `groups`, `generated_at`, `template`, `bioline_version` | base header + footer |
| `kpis` | list of `{label, value, hint?, kind?}` | overview KPI grid |
| `graphical_abstract_src` / `graphical_abstract_caption` | str | hero graphical abstract |
| `baseline` | dict produced by `baseline_table_from_df(...)` | Table 1 |
| `methods_table` | list of `{step, status, notes}` *or* dict | methods block |
| `refs` | list of `str` *or* `{citation, doi?}` | references block |
| `code_blocks` | list of `{title, lang, filename, depends, description, code}` | code appendix |
| `qc.fastqc`, `taxonomy.stack`, `differential.volcano`, … | raw HTML / `<img>` data-URI | per-template figure slots |
| `<group>.table` | `{rows, cols, caption?}` | rendered with `ui.table` |

`rows` is a list of dicts keyed by `cols[i].key`; `cols[i]` is
`{key, label, kind?}` with `kind ∈ {numeric, score, pvalue, pill}`.

## Figures (CNS rules)

- **Always** wrap Plotly figures with `apply_npg_style(fig)` or build them via
  `new_figure(go.Bar(...))`. The base template injects a global Plotly
  template; this helper makes the styling explicit and survivable across
  re-renders.
- Convert to HTML with `fig_to_html(fig)` (= `to_html(full_html=False,
  include_plotlyjs=False)` plus `displaylogo=False`).
- PNGs: `_embed_image(path)`. Never reference external URLs — the container
  runs with `--network none`.
- Use `ui.figure(title, body, caption, fig_num=N)` so each figure prints with
  a `Figure N.` label per journal convention.

## Tables (booktabs)

- Use `ui.table(rows, cols, tab_num=N, caption=...)`. The macro auto-renders
  the table with thick top/bottom rules and a single midrule under the
  header, no zebra, no vertical lines.
- Use `ui.baseline_table(data, tab_num=1)` for the **Table 1** baseline
  characteristics layout. `data` is what `baseline_table_from_df()` returns.
- Numerical columns: set `cols[i].kind = "num"` to align right with
  `tabular-nums`.

## Adding a new template

1. Drop `templates/<name>.html.j2` extending `base.html.j2`.
2. Append an entry to `template_index.yaml` with selection rules.
3. Reuse `ui.*` macros; if styling is missing, extend `theme.css` rather than
   inline-styling inside the template.

## Visual rules

- Tables cap at 20 rows by default — the macro handles overflow.
- Section numbers are hard-coded per template (`<h2>2. …</h2>`); keep them
  monotonic and reflow when adding/removing sections.
- Use the `ui.callout` macro (`info` / `warning` / `danger`) for boxed notes.
- Keep KPI cards under 6 per row; the grid auto-wraps responsively.
- Do **not** inline custom fonts, drop shadows, or non-NPG colours. The
  output must remain print-faithful and consistent with journal style guides.
- Statistics in narrative text must use the helper macros
  (`ui.pvalue`, `ui.mean_sd`, `ui.median_iqr`, `ui.ci`, `ui.nfrac`) so the
  rendered HTML keeps italic *p* / *n* and tabular-aligned decimals.
