# Cox Survival Analysis Supplementary Information

---

## README

# Cox Survival Analysis Skill

A comprehensive survival analysis skill for clinical professionals, built on the Cox proportional hazards framework.

## Overview

This skill automates end-to-end Cox survival analysis workflows, from raw data to publication-ready results. It's designed for clinical researchers and clinicians who want robust statistical analysis without manual pipeline engineering.

## Key Features

✓ **Flexible Data Input**: Handles longitudinal (repeated visits) or single-row (pre-computed survival) data
✓ **Automatic Setup**: Installs dependencies and creates configuration interactively
✓ **Smart Defaults**: Runs conservative, well-tested settings on first pass
✓ **LASSO-Cox Optimization**: Automatic variable selection via cross-validated penalizer tuning
✓ **Comprehensive Diagnostics**: Proportional hazards tests, bootstrap C-index CI, univariate analysis
✓ **Publication-Ready Output**: CSV statistical tables, high-resolution plots, and PDF summary report
✓ **Intelligent Suggestions**: Recommends next steps based on model performance

## Installation

The skill is standalone and self-contained. No setup required beyond Claude Code.

## Usage

### Quick Start (Conversational)

Simply tell Claude:
> "I have a CSV file with patient survival data. Can you run Cox analysis on it?"

Claude will:
1. Check/install dependencies automatically
2. Ask clarifying questions about your data
3. Create a configuration file
4. Run the full pipeline
5. Show you results and suggest next steps

### Command-Line (Direct)

```bash
python scripts/run_cox_pipeline.py path/to/data.csv \
  --mode longitudinal \
  --output-dir my_analysis
```

### Advanced (Custom Config)

```bash
# Create custom config.yaml first, then:
python scripts/run_cox_pipeline.py path/to/data.csv \
  --config my_config.yaml \
  --output-dir my_analysis
```

## Output

All results are organized in **one folder** containing:

### Statistical Tables (CSV format)
- **lasso_selected_variables.tsv** — Selected predictors with HR and 95% CI
- **lasso_cv_results.tsv** — Cross-validation performance per penalizer value
- **risk_group_summary.tsv** — Patient counts and event rates per risk group
- **ph_test_results.tsv** — Proportional hazards assumption test (if enabled)
- **univariate_cox_results.tsv** — Single-variable Cox analysis (if enabled)

### Visualizations (PNG format)
- **km_risk_stratified.png** — Kaplan-Meier curves stratified by risk group
- **forest_plot.png** — Forest plot of selected variables (HR with 95% CI)

### Report & Configuration
- **survival_analysis_report.pdf** — Comprehensive visual summary with interpretation guide
- **config.yaml** — Analysis configuration (for reproducibility)
- **pipeline_config_summary.json** — Run metadata and summary statistics

## Configuration

Configuration is managed via YAML. Key settings:

```yaml
# Data
data_path: "your_data.csv"
mode: "longitudinal"  # or "single_row"

# For longitudinal data
id_col: "patient_id"
time_col: "visit_year"
event_status_col: "disease_status"

# Feature selection
cat_features: ["sex", "stage"]
drop_cols: ["patient_id"]
missing_threshold: 50.0  # Remove features >50% missing

# LASSO-Cox tuning
l1_ratio: 1.0  # 1.0 = LASSO, <1 = Elastic Net
n_folds: 5     # Cross-validation folds

# Optional analyses
run_univariate: false
check_ph_assumptions: true
bootstrap_c_index: false
```

See SKILL.md for detailed configuration options and explanations.

## Understanding Results

### Hazard Ratio (HR)
- **HR = 1**: No effect on survival
- **HR > 1**: Increases risk of event (worse survival)
- **HR < 1**: Decreases risk of event (better survival)

*Example: HR = 2 means 2× the hazard (risk) of the event*

### C-Index (Concordance Index)
Model discrimination metric (0–1 scale):
- **0.5**: Random chance
- **0.7–0.8**: Good
- **>0.8**: Excellent

### Log-Rank Test
Compares survival between risk groups:
- **p < 0.05**: Significant difference
- **p ≥ 0.05**: No significant difference

## Workflow

1. **Setup Phase**
   - Install dependencies (automatic)
   - Create/customize YAML config
   - Validate data and configuration

2. **Analysis Phase**
   - Preprocess (encode, impute, scale)
   - Optional: Run univariate Cox
   - Run LASSO-Cox with cross-validation
   - Test proportional hazards assumption
   - Stratify into risk groups

3. **Output Phase**
   - Save statistical tables
   - Generate plots (KM, forest)
   - Create PDF report
   - Print recommendations

## Scripts

The `scripts/` directory contains modular components:

- **install_dependencies.py** — Check/install required packages
- **config_manager.py** — Create, load, validate, and edit YAML configs
- **data_validator.py** — Validate data before analysis
- **run_cox_pipeline.py** — Main orchestrator (entry point)
- **generate_pdf_report.py** — Create PDF summary reports

## Dependencies

Automatically installed:
- `pandas` (data handling)
- `numpy` (numerical computing)
- `lifelines` (Cox models, KM curves)
- `matplotlib`, `seaborn` (visualization)
- `scikit-learn` (MICE imputation)
- `pyyaml` (config files)
- `reportlab` (PDF generation)
- `AI_toolbox` (Cox pipeline implementation)

## Limitations & Cautions

- **Small samples**: <50 patients or <10 events may yield unstable models
- **Missing data assumptions**: Assumes missing-at-random (not missing-not-at-random)
- **Causality**: Cox models show association, not causation
- **Single outcome**: For competing risks, consult a statistician

## Support & Questions

Refer to SKILL.md for comprehensive documentation and FAQ.

For technical issues, check the generated `pipeline_config_summary.json` for debug information.

## References

- Harrell FE, et al. "Regression models for survival analysis." Statistical Methods in clinical Research. 1996.
- Cox DR. "Regression models and life-tables." Journal of the Royal Statistical Society. 1972.
- Therneau TM, Grambsch PM. "Modeling Survival Data: Extending the Cox Model." Springer. 2000.
- lifelines documentation: https://lifelines.readthedocs.io/

## License

This skill is built on the open-source Cox model implementation in the BGI AI_toolbox project.

---

## Example Usage

# Cox Survival Analysis - Example Usage

## Scenario 1: Longitudinal clinical Data

You have a CSV file `patient_cohort.csv` with multiple years of patient follow-up:

```
patient_id,visit_year,age,sex,blood_pressure,cholesterol,disease_status
1001,2015,45,M,140,220,0
1001,2016,46,M,145,218,0
1001,2017,47,M,150,225,1
1002,2015,52,F,135,200,0
1002,2016,53,F,140,205,0
... (more records)
```

### Using the Skill (Conversational)

**You say:**
```
I have longitudinal patient data in "patient_cohort.csv" with multiple years
of follow-up. Each patient has an ID, visit year, clinical measurements, and
a disease_status column (0 or 1 for whether they developed the outcome).
I want to identify which factors predict disease development. Can you run a
Cox survival analysis?
```

**Claude does:**
1. ✓ Checks and installs required packages
2. ✓ Creates `cox_config.yaml` with sensible defaults:
   - Sets `mode: "longitudinal"`
   - Maps `id_col: "patient_id"`, `time_col: "visit_year"`, etc.
3. ✓ Shows you the config and asks if you want to customize
4. ✓ Validates the data (shape, events, missing values)
5. ✓ Runs full Cox pipeline
6. ✓ Generates plots, CSV tables, and PDF report

**Output folder contains:**
- `km_risk_stratified.png` — Kaplan-Meier curves
- `forest_plot.png` — Effect sizes of selected factors
- `lasso_selected_variables.tsv` — Which factors matter (with HR and CI)
- `risk_group_summary.tsv` — Patient counts per risk group
- `survival_analysis_report.pdf` — Complete summary

---

## Scenario 2: Pre-computed Survival Data

You have a CSV file `survival_data.csv` where survival is already computed:

```
patient_id,age,sex,bmi,smoking,duration,event
P001,45,M,25.5,1,3.2,0
P002,52,F,28.1,0,5.1,1
P003,48,M,24.8,1,2.8,0
... (more records)
```

### Using the Skill (Conversational)

**You say:**
```
I have a CSV file "survival_data.csv" where each row is one patient.
The "duration" column is years of follow-up, and "event" column is 1 if
they had the outcome, 0 if censored. Can you run Cox survival analysis?
```

**Claude does:**
1. ✓ Detects single-row format
2. ✓ Creates config with `mode: "single_row"`
3. ✓ Runs analysis (skips longitudinal survival construction)
4. ✓ Generates same outputs

---

## Scenario 3: Customizing the Analysis

After seeing initial results:

**You say:**
```
The C-index is good but I'd like to see the univariate analysis too,
to understand which factors are individually significant. Can you re-run
with that enabled?
```

**Claude does:**
1. ✓ Updates `config.yaml` to set `run_univariate: true`
2. ✓ Re-runs pipeline
3. ✓ Now shows `univariate_cox_results.tsv` with p-values for each factor

---

## Scenario 4: Fine-tuning Variable Selection

After reviewing results:

**You say:**
```
The model selected only 3 variables, which seems too sparse.
Can you make the variable selection less aggressive and try again?
```

**Claude does:**
1. ✓ Updates `lasso_coef_threshold` (lower = less aggressive)
2. ✓ Or changes `l1_ratio` to use Elastic Net instead of pure LASSO
3. ✓ Re-runs pipeline
4. ✓ Compares results to previous run

---

## Scenario 5: Handling Missing Data

Your data has some missing values:

**You say:**
```
Some patients are missing cholesterol measurements. What should I do?
```

**Claude does:**
1. ✓ Shows missing data summary
2. ✓ Explains: MICE imputation handles this automatically
3. ✓ If >50% missing: removes that feature
4. ✓ Otherwise: imputes values using MICE algorithm
5. ✓ Continues analysis

No manual data cleaning needed!

---

## Scenario 6: Interpreting Results

After analysis completes:

**You say:**
```
I see HR=2.5 for blood pressure in the forest plot. What does this mean?
```

**Claude explains:**
> A hazard ratio (HR) of 2.5 for blood pressure means that for each unit increase
> in blood pressure, the hazard (risk) of the event increases by 2.5×.
> For example, if baseline risk is 10%, a doubling of HR means ~20% risk.
> The 95% CI shows the range we're 95% confident the true HR lies in.
> If the CI includes 1, the effect isn't statistically significant.

---

## Scenario 7: External Validation Recommendation

The analysis completes and shows good results:

**You say:**
```
These results look promising. What should I do next?
```

**Claude recommends:**
> Your model shows excellent discrimination (C-index = 0.82). Next steps:
>
> 1. **External Validation**: Test on an independent cohort to ensure results
>    generalize and aren't just fitting noise in this dataset
>
> 2. **Clinical Validation**: Review selected factors with clinical colleagues
>    to ensure they make biological sense
>
> 3. **Prospective Study**: Consider validating predictions prospectively
>    on new patients before clinical implementation
>
> 4. **Competing Risks**: If patients can have multiple different outcomes,
>    we may need competing risks regression instead of standard Cox

---

## Typical Workflow

```
1. Load data
   ↓
2. Run default analysis
   ↓
3. Review initial results (plots, tables, PDF)
   ↓
4. Customize if needed (univariate, different penalties, etc.)
   ↓
5. Finalize and document findings
```

**Time required**: Minutes (not hours of manual coding)

---

## Common Questions During Analysis

### Q: How many events do I need?
A: Minimum ~10 events for stability, but 20-30+ recommended for robust models.

### Q: What if I have categorical variables?
A: Specify them in `cat_features`. They'll be one-hot encoded automatically.

### Q: How do I know if my model is good?
A: Check the C-index in the PDF report:
- **C < 0.6**: Weak (reconsider approach)
- **0.6-0.7**: Moderate (reasonable)
- **0.7-0.8**: Good (solid)
- **>0.8**: Excellent (strong discrimination)

### Q: What if proportional hazards assumption fails?
A: Your data may have time-varying effects. The skill will warn you. Options:
1. Review which variables violated assumption
2. Consider stratification by that variable
3. Consult a biostatistician for advanced methods

### Q: Can I use this for prediction on new patients?
A: The skill generates risk scores and groups in the output. You can:
1. Apply the same variable selection to new patients
2. Use the model coefficients to compute risk scores
3. Compare new patients to the risk groups

---

## File Organization

After analysis, your output folder looks like:

```
cox_survival_results/
├── km_risk_stratified.png          (Kaplan-Meier curves)
├── forest_plot.png                 (Effect sizes)
├── survival_analysis_report.pdf    (Summary report)
├── lasso_selected_variables.tsv    (Statistical results)
├── lasso_cv_results.tsv            (Model tuning results)
├── risk_group_summary.tsv          (Risk group counts)
├── ph_test_results.tsv             (Assumption test)
├── config.yaml                     (Settings for reproducibility)
└── pipeline_config_summary.json    (Metadata)
```

Everything in one folder. Easy to share, archive, or publish!

---

## Publication-Ready Output

The PDF report includes:
- Executive summary
- Kaplan-Meier curves
- Forest plot
- Statistical tables with HR and 95% CIs
- Interpretation guide

Ready to include in papers, presentations, or share with collaborators.

---

## Questions?

Refer to SKILL.md in the skill directory for comprehensive documentation.
