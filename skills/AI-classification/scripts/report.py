#!/usr/bin/env python3
"""
Report generation module.
Creates comprehensive markdown and HTML reports.
"""

import pandas as pd
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime


def generate_summary_report(
    output_dir: Path,
    config: Optional[Dict[str, Any]] = None,
    verbose: bool = True
) -> Path:
    """
    Generate executive summary report.

    Args:
        output_dir: Root output directory
        config: Configuration used (optional)
        verbose: Print progress?

    Returns:
        Path to generated report
    """
    output_dir = Path(output_dir)

    # Read metrics if available
    metrics_path = output_dir / "evaluation" / "metrics_comparison.csv"
    metrics_text = ""
    best_model_info = ""

    if metrics_path.exists():
        metrics_df = pd.read_csv(metrics_path)
        metrics_text = metrics_df.to_markdown(index=False)

        if len(metrics_df) > 0:
            best_idx = metrics_df["accuracy"].idxmax()
            best_model = metrics_df.loc[best_idx, "model"]
            best_acc = metrics_df.loc[best_idx, "accuracy"]
            best_model_info = f"""
## 🏆 Best Model

**Model**: `{best_model.upper()}`
**Accuracy**: {best_acc:.4f}
"""

    # Read training info
    training_summary = ""
    if config and "training" in config:
        training_summary = f"""
## ⚙️ Training Configuration

- Models trained: {', '.join(config['training'].get('models', []))}
- CV folds: {config['training'].get('cv_folds', 'N/A')}
- Scoring metric: {config['training'].get('scoring', 'accuracy')}
- Search strategy: {config['training'].get('search_strategy', 'grid')}
"""

    # Read preprocessing info
    preprocessing_summary = ""
    if config and "preprocessing" in config:
        prep = config["preprocessing"]
        preprocessing_summary = f"""
## 📊 Data Preprocessing

- **Input file**: {prep.get('data_path', 'N/A')}
- **Target column**: {prep.get('target_column', 'N/A')}
- **Imputation method**: {prep.get('imputation_method', 'mean')}
- **Feature scaling**: {'Yes' if prep.get('scale_features', False) else 'No'}
- **Split strategy**: {prep.get('split_strategy', 'N/A')}
- **Train/test ratio**: {prep.get('test_size', 0.2)}
"""

    # Build report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"""# Classification Pipeline Report

*Generated on {timestamp}*

---

## Executive Summary

This report summarizes the end-to-end classification pipeline:
1. **Preprocessing**: Data loading, cleaning, encoding, scaling, and splitting
2. **Training**: Model selection and hyperparameter tuning via cross-validation
3. **Evaluation**: Performance metrics, confusion matrices, and feature importance
4. **Results**: All outputs organized in a single directory for easy access

---

{best_model_info}

{preprocessing_summary}

{training_summary}

---

## 📈 Model Performance Metrics

{metrics_text}

---

## 📁 Output Structure

```
classification_results_<TIMESTAMP>/
├── README.md (this file)
├── config_used.json (configuration snapshot)
├── preprocessing/
│   ├── train_processed.csv
│   ├── test_processed.csv
│   └── preprocessing_summary.md
├── models/
│   ├── <model_name>.joblib (trained models)
│   └── training_summary.csv
├── evaluation/
│   ├── confusion_matrix_*.png
│   ├── roc_curves.png
│   ├── metrics_comparison.csv
│   ├── feature_importance.csv
│   └── evaluation_summary.md
└── predictions/ (if predictions made)
    ├── predictions.csv
    └── prediction_summary.md
```

---

## 🔑 Key Findings

- **Number of features**: Determined during preprocessing
- **Data split**: Stratified K-fold cross-validation for robust evaluation
- **Best performing model**: See "Best Model" section above
- **Model comparison**: See `evaluation/metrics_comparison.csv` for detailed metrics
- **Feature importance**: See `evaluation/feature_importance.csv` (if applicable)

---

## 💡 Recommendations

1. **Model Deployment**: The best model has been saved as `models/<best_model>.joblib`
2. **Reproducibility**: All configurations saved in `config_used.json`
3. **Predictions**: To make predictions on new data, load the model and apply the same preprocessing
4. **Further Tuning**: Adjust hyperparameter grids if you want to explore further

---

## 📚 Next Steps

- **Review visualizations**: Check confusion matrices and ROC curves in `evaluation/`
- **Inspect feature importance**: Understand which features drive predictions
- **Tune hyperparameters**: Modify parameter grids and re-run if desired
- **Make predictions**: Use the saved model on new data

---

*For more details, consult the individual CSV files and markdown reports in each subdirectory.*
"""

    # Save report
    report_path = output_dir / "README.md"
    with open(report_path, "w") as f:
        f.write(report)

    if verbose:
        print(f"   Generated summary report: {report_path.name}")

    return report_path


def generate_prediction_report(
    predictions: pd.DataFrame,
    output_dir: Path,
    verbose: bool = True
) -> Path:
    """Generate prediction summary report."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Count predictions
    pred_counts = predictions["prediction"].value_counts()
    pred_summary = "\n".join([f"- Class {k}: {v} samples" for k, v in pred_counts.items()])

    report = f"""# Prediction Summary

Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

- **Total predictions**: {len(predictions)}
- **Unique classes**: {predictions['prediction'].nunique()}

## Predictions by Class

{pred_summary}

## Output

Full predictions saved to `predictions.csv`

"""

    path = output_dir / "prediction_summary.md"
    with open(path, "w") as f:
        f.write(report)

    if verbose:
        print(f"         Saved prediction report: {path.name}")

    return path
