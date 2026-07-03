# Cox Model (COX 生存分析)

A configurable COX survival analysis module that provides:

- **Two data modes**: longitudinal (build survival from repeated measures) or single-row (data already has `duration` and `event`)
- **Preprocessing**: one-hot encoding, zero-variance / high-missing removal, standardization, imputation (e.g. MICE)
- **Modelling**: optional univariate Cox; LASSO-Cox (or Elastic Net) with cross-validated penalizer selection
- **Diagnostics**: proportional hazards (PH) assumption test (Schoenfeld residuals); optional bootstrap C-index CI
- **Visualization**: risk stratification, Kaplan–Meier curves, log-rank test, forest plot
- **Single entrypoint**: `run_survival_pipeline(config)` runs the full pipeline and writes all outputs to `config.result_dir`

## Setup

Import from AI_toolbox:

```python
from AI_toolbox.Modelling.cox_model import (
    CoxPipelineConfig,
    get_carotid_example_config,
    run_survival_pipeline,
)
```

Or use the pipeline entry (same API):

```python
from AI_toolbox.Pipelines.Survival_Analysis_pipeline import (
    CoxPipelineConfig,
    get_carotid_example_config,
    run_survival_pipeline,
)
```

Dependencies: `pandas`, `numpy`, `matplotlib`, `seaborn`, `lifelines`, and the AI_toolbox Preprocessing modules (Encoding, Feature_selection, Imputation, Scaling).

---

## Quick Start

### 1) Full pipeline (longitudinal data, e.g. carotid)

```python
import pandas as pd
from AI_toolbox.Modelling.cox_model import get_carotid_example_config, run_survival_pipeline

config = get_carotid_example_config(
    data_path="Data/Raw/Gulou_Carotid_data_test.csv",
    result_dir="carotid_hsCRP_result",
)
# Optional: enable univariate Cox, bootstrap C-index CI, or PH LOWESS plots (slow)
config.run_univariate = False
config.bootstrap_c_index = False
config.check_ph_show_plots = False  # True = draw PH diagnostic plots (Bootstrapping lowess lines, slow)

results = run_survival_pipeline(config)
# results["cox_df"], results["final_df"], results["lasso_cph"], results["selected_vars"], results["c_index"], ...
```

### 2) Full pipeline (single-row data: already has duration & event)

```python
from AI_toolbox.Modelling.cox_model import CoxPipelineConfig, run_survival_pipeline

config = CoxPipelineConfig(
    data_path="path/to/survival_data.csv",
    result_dir="my_cox_result",
    mode="single_row",
    duration_col="time_to_event",
    event_col="event",
    drop_cols=["patient_id"],
    cat_features=["sex", "stage"],
    drop_ref_categories=["sex_Female", "stage_I"],
)
results = run_survival_pipeline(config)
```

### 3) Step-by-step (build survival table only, or preprocess only, or LASSO only)

```python
import pandas as pd
from AI_toolbox.Modelling.cox_model import (
    CoxPipelineConfig,
    build_survival_from_longitudinal,
    get_baseline_and_survival,
    preprocess_for_cox,
    run_lasso_cox_cv,
    get_selected_variables,
    plot_km_stratified,
    run_logrank,
    plot_forest,
)

# Example: build survival from longitudinal data
config = CoxPipelineConfig(data_path="Data/Raw/longitudinal.csv", result_dir="out")
data_df = pd.read_csv(config.data_path)
cox_df, baseline_df = get_baseline_and_survival(data_df, config)

# Preprocess
final_df, artifacts = preprocess_for_cox(
    cox_df, config,
    duration_col=config.duration_col,
    event_col=config.event_col,
)

# Fit LASSO-Cox (no univariate / PH / plots if you skip them)
lasso_cph, best_penalizer, cv_df = run_lasso_cox_cv(
    final_df, config,
    duration_col=config.duration_col,
    event_col=config.event_col,
)
selected_vars = get_selected_variables(
    lasso_cph, config.lasso_coef_threshold, config.result_dir,
)
# Then add risk_score, risk_group, and call plot_km_stratified, run_logrank, plot_forest as needed.
```

---

## Config: `CoxPipelineConfig`

Main fields (see `config.py` for full list):

| Category        | Fields |
|-----------------|--------|
| **Data & paths** | `data_path`, `result_dir`, `duration_col`, `event_col` |
| **Longitudinal** | `mode` (`"longitudinal"` \| `"single_row"`), `id_col`, `time_col`, `event_status_col`, `baseline_filter_col`, `baseline_filter_value` |
| **Features**     | `drop_cols`, `cat_features`, `drop_ref_categories`, `exclude_from_features`, `missing_threshold`, `impute_method`, `scale_on_binary` |
| **LASSO-Cox**    | `penalizer_grid`, `l1_ratio` (1.0 = LASSO, &lt;1 = Elastic Net), `n_folds`, `lasso_coef_threshold` |
| **Risk / plot**  | `risk_n_groups`, `risk_group_labels`, `time_unit`, `km_xlabel`, `km_ylabel` |
| **Optional**     | `run_univariate`, `check_ph_assumptions`, `check_ph_show_plots`, `bootstrap_c_index`, `bootstrap_n`, `save_preprocessed`, `verbose` |

- **Longitudinal**: each subject has multiple rows (e.g. by year); survival is built from first row (baseline) to first event or last follow-up. Use `baseline_filter_col` / `baseline_filter_value` to restrict to e.g. baseline event-free.
- **Single-row**: each row is one subject with `duration` and `event` already present; no survival construction.

---

## Pipeline outputs

**Return value** `results` from `run_survival_pipeline(config)`:

- `cox_df`: survival dataset (after baseline merge in longitudinal mode)
- `final_df`: preprocessed data with `duration`, `event`, and (after modelling) `risk_score`, `risk_group`
- `lasso_cph`: fitted `lifelines.CoxPHFitter` (LASSO/Elastic Net)
- `selected_vars`: DataFrame of selected variables (coef, HR, CI)
- `c_index`, `best_penalizer`
- `preprocess_artifacts`, optional `c_index_ci`, `baseline_df` (longitudinal)

**Files written to `config.result_dir`**:

| File | Content |
|------|---------|
| `preprocessed_cox_data.tsv` | Preprocessed table (if `save_preprocessed=True`) |
| `lasso_cv_results.tsv` | CV C-index per penalizer |
| `lasso_c_index.txt` | Best C-index, best penalizer, optional bootstrap CI |
| `lasso_selected_variables.tsv` | Selected variables with HR and 95% CI |
| `ph_test_results.tsv` | PH assumption test (if `check_ph_assumptions=True`) |
| `univariate_cox_results.tsv` | Univariate Cox results (if `run_univariate=True`) |
| `km_risk_stratified.png` | Kaplan–Meier curves by risk group |
| `forest_plot.png` | Forest plot of selected variables |
| `logrank_test.txt` | Log-rank p-value (high vs low risk group) |
| `risk_group_summary.tsv` | Count, events, event rate per risk group |
| `pipeline_config_summary.json` | Run summary (paths, n_samples, n_events, c_index, etc.) |

---

## Module structure

| File | Responsibility |
|------|----------------|
| `config.py` | `CoxPipelineConfig`, `get_carotid_example_config` |
| `survival_data.py` | `build_survival_from_longitudinal`, `get_baseline_and_survival` |
| `preprocessing.py` | `preprocess_for_cox` (encode, filter, scale, impute) |
| `univariate.py` | `run_univariate_cox` |
| `lasso_cox.py` | `run_lasso_cox_cv`, `get_selected_variables`, `bootstrap_c_index_ci` |
| `ph_test.py` | `check_ph_assumptions` (Schoenfeld residuals) |
| `visualization.py` | `add_risk_groups`, `plot_km_stratified`, `run_logrank`, `plot_forest` |
| `run.py` | `run_survival_pipeline` (orchestrator) |
| `__init__.py` | Re-exports public API |

---

## Important notes

- **Data alignment**: In longitudinal mode, data must be sortable by `id_col` and `time_col`; `event_status_col` should be 0/1 (or set `event_positive_value` in `build_survival_from_longitudinal`).
- **Event count**: If `n_events < 10`, a warning is logged; LASSO-Cox may be unstable with few events.
- **PH assumption**: The pipeline runs a proportional hazards test and saves results to `ph_test_results.tsv`; interpret violations (e.g. time-varying effects) before relying on Cox HRs. By default PH diagnostic plots (LOWESS) are **disabled** (`check_ph_show_plots=False`) to avoid slow bootstrapping; set `config.check_ph_show_plots = True` if you need the visual diagnostics.
- **Categoricals**: Use `cat_features` and `drop_ref_categories` to avoid collinearity (e.g. drop one level of sex).
- **External dependency**: `lifelines` is required for CoxPHFitter, KaplanMeierFitter, logrank, and PH test; ensure it is installed.
- **Preprocessing**: The same Preprocessing modules as in Classification (Encoding, Feature_selection, Imputation, Scaling) are used; ensure missing columns are not required for downstream steps after `drop_cols` / `exclude_from_features`.
