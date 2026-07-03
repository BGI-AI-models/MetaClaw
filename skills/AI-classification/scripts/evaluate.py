#!/usr/bin/env python3
"""
Model evaluation module.
Generates confusion matrices, ROC curves, metrics tables, and feature importance.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Any, Dict, Optional
from sklearn.metrics import (
    confusion_matrix, classification_report, roc_curve, auc, roc_auc_score,
    accuracy_score, precision_score, recall_score, f1_score
)
import warnings

warnings.filterwarnings('ignore')


def compute_metrics(y_true, y_pred, y_pred_proba=None) -> Dict[str, float]:
    """Compute classification metrics."""
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, average="weighted", zero_division=0),
        "recall": recall_score(y_true, y_pred, average="weighted", zero_division=0),
        "f1": f1_score(y_true, y_pred, average="weighted", zero_division=0),
    }

    # ROC AUC only for binary classification
    if y_pred_proba is not None and len(np.unique(y_true)) == 2:
        try:
            metrics["roc_auc"] = roc_auc_score(y_true, y_pred_proba[:, 1])
        except:
            pass

    return metrics


def plot_confusion_matrix(
    y_true,
    y_pred,
    model_name: str,
    output_dir: Path,
    verbose: bool = True
) -> Path:
    """Plot and save confusion matrix."""
    cm = confusion_matrix(y_true, y_pred)
    classes = np.unique(y_true)

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax,
                xticklabels=classes, yticklabels=classes)
    ax.set_ylabel("True Label")
    ax.set_xlabel("Predicted Label")
    ax.set_title(f"Confusion Matrix - {model_name}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"confusion_matrix_{model_name.lower()}.png"
    plt.savefig(path, dpi=100, bbox_inches="tight")
    plt.close()

    if verbose:
        print(f"         Saved confusion matrix: {path.name}")

    return path


def plot_roc_curves(
    models: Dict[str, Any],
    X_test: pd.DataFrame,
    y_test: pd.Series,
    output_dir: Path,
    verbose: bool = True
) -> Optional[Path]:
    """Plot ROC curves for binary classification."""
    if len(np.unique(y_test)) != 2:
        if verbose:
            print(f"         ROC curves only for binary classification; skipping")
        return None

    fig, ax = plt.subplots(figsize=(10, 8))

    for model_name, model in models.items():
        if not hasattr(model, "predict_proba"):
            continue

        y_proba = model.predict_proba(X_test)[:, 1]
        fpr, tpr, _ = roc_curve(y_test, y_proba)
        roc_auc = auc(fpr, tpr)

        ax.plot(fpr, tpr, label=f"{model_name} (AUC={roc_auc:.3f})", lw=2)

    ax.plot([0, 1], [0, 1], "k--", label="Random Classifier", lw=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curves")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "roc_curves.png"
    plt.savefig(path, dpi=100, bbox_inches="tight")
    plt.close()

    if verbose:
        print(f"         Saved ROC curves: {path.name}")

    return path


def extract_feature_importance(
    models: Dict[str, Any],
    feature_names: list,
    output_dir: Path,
    verbose: bool = True
) -> Optional[Path]:
    """Extract feature importance from tree-based models."""
    importances = {}

    for model_name, model in models.items():
        if hasattr(model, "feature_importances_"):
            importances[model_name] = model.feature_importances_

    if not importances:
        if verbose:
            print(f"         No tree-based models; skipping feature importance")
        return None

    # Combine importances
    df_importance = pd.DataFrame(
        {name: importances[name] for name in importances.keys()},
        index=feature_names
    )
    df_importance["mean"] = df_importance.mean(axis=1)
    df_importance = df_importance.sort_values("mean", ascending=False)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "feature_importance.csv"
    df_importance.to_csv(path)

    if verbose:
        print(f"         Saved feature importance: {path.name}")

    return path


def evaluate_models(
    models: Dict[str, Any],
    X_test: pd.DataFrame,
    y_test: pd.Series,
    cv_results: Optional[pd.DataFrame] = None,
    output_dir: Optional[Path] = None,
    feature_names: Optional[list] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Evaluate all trained models.

    Args:
        models: Dict of model_name -> fitted model
        X_test, y_test: Test data
        cv_results: Cross-validation results table
        output_dir: Directory to save outputs
        feature_names: Feature names (for importance)
        verbose: Print progress?

    Returns:
        Dictionary with metrics, predictions, and visualizations
    """
    if output_dir is None:
        output_dir = Path(".")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"   Evaluating {len(models)} model(s)...")

    metrics_list = []

    for model_name, model in models.items():
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test) if hasattr(model, "predict_proba") else None

        metrics = compute_metrics(y_test, y_pred, y_proba)
        metrics["model"] = model_name

        metrics_list.append(metrics)

        # Plot confusion matrix
        plot_confusion_matrix(y_test, y_pred, model_name, output_dir, verbose=verbose)

        if verbose:
            print(f"      {model_name}: Accuracy={metrics['accuracy']:.4f}, F1={metrics['f1']:.4f}")

    # Metrics table
    metrics_df = pd.DataFrame(metrics_list)
    metrics_path = output_dir / "metrics_comparison.csv"
    metrics_df.to_csv(metrics_path, index=False)

    if verbose:
        print(f"         Saved metrics table: {metrics_path.name}")

    # ROC curves
    plot_roc_curves(models, X_test, y_test, output_dir, verbose=verbose)

    # Feature importance
    if feature_names:
        extract_feature_importance(models, feature_names, output_dir, verbose=verbose)

    return {
        "metrics": metrics_df,
        "metrics_path": metrics_path,
        "test_size": len(X_test)
    }


def generate_evaluation_report(
    metrics: pd.DataFrame,
    output_dir: Optional[Path] = None,
    verbose: bool = True
) -> Path:
    """Generate markdown evaluation report."""
    if output_dir is None:
        output_dir = Path(".")
    output_dir = Path(output_dir)

    # Find best model
    best_idx = metrics["accuracy"].idxmax()
    best_model = metrics.loc[best_idx, "model"]
    best_acc = metrics.loc[best_idx, "accuracy"]

    report = f"""# Model Evaluation Report

## Best Model
- **Model**: {best_model.upper()}
- **Accuracy**: {best_acc:.4f}

## Metrics Summary

{metrics.to_markdown(index=False)}

## Visualizations
- Confusion matrices: `confusion_matrix_*.png`
- ROC curves: `roc_curves.png`
- Feature importance: `feature_importance.csv` (if applicable)

"""

    path = output_dir / "evaluation_summary.md"
    with open(path, "w") as f:
        f.write(report)

    if verbose:
        print(f"         Saved evaluation report: {path.name}")

    return path
