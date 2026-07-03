#!/usr/bin/env python3
"""
Prediction module for applying trained models to new data.
"""

import pandas as pd
import joblib
from pathlib import Path
from typing import Any, Dict, Optional


def make_predictions(
    model: Any,
    X_new: pd.DataFrame,
    output_dir: Optional[Path] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Make predictions on new data.

    Args:
        model: Trained model object
        X_new: New data to predict on
        output_dir: Directory to save predictions
        verbose: Print progress?

    Returns:
        Dictionary with predictions and metadata
    """
    if output_dir is None:
        output_dir = Path(".")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Make predictions
    y_pred = model.predict(X_new)

    # Get probabilities if available
    y_proba = None
    if hasattr(model, "predict_proba"):
        y_proba = model.predict_proba(X_new)

    # Create results dataframe
    results = pd.DataFrame({
        "index": range(len(X_new)),
        "prediction": y_pred
    })

    if y_proba is not None:
        # Add probability columns
        for i, prob in enumerate(y_proba.T):
            results[f"probability_class_{i}"] = prob

    # Save predictions
    pred_path = output_dir / "predictions.csv"
    results.to_csv(pred_path, index=False)

    if verbose:
        print(f"         Saved {len(results)} predictions to {pred_path.name}")

    return {
        "predictions": results,
        "n_samples": len(results),
        "unique_predictions": len(results["prediction"].unique()),
        "output_path": pred_path
    }


def load_model(model_path: str) -> Any:
    """Load a saved model from disk."""
    return joblib.load(model_path)


def save_model(model: Any, output_path: str) -> None:
    """Save a trained model to disk."""
    joblib.dump(model, output_path)
