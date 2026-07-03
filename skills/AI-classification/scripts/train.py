#!/usr/bin/env python3
"""
Model training and hyperparameter tuning module.
Supports grid/random search with cross-validation.
"""

import joblib
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
import warnings

warnings.filterwarnings('ignore')


# Model registry with default hyperparameters
MODEL_REGISTRY = {
    "rf": {
        "class": RandomForestClassifier,
        "default_params": {"n_estimators": 100, "max_depth": 10, "random_state": 42},
        "param_grid": {
            "n_estimators": [50, 100, 200],
            "max_depth": [5, 10, 15],
            "min_samples_split": [2, 5]
        }
    },
    "logreg": {
        "class": LogisticRegression,
        "default_params": {"max_iter": 1000, "random_state": 42},
        "param_grid": {
            "C": [0.1, 1.0, 10.0],
            "solver": ["lbfgs", "liblinear"]
        }
    },
    "svm": {
        "class": SVC,
        "default_params": {"kernel": "rbf", "random_state": 42, "probability": True},
        "param_grid": {
            "C": [0.1, 1.0, 10.0],
            "kernel": ["rbf", "linear"]
        }
    },
    "gb": {
        "class": GradientBoostingClassifier,
        "default_params": {"n_estimators": 100, "learning_rate": 0.1, "random_state": 42},
        "param_grid": {
            "n_estimators": [50, 100, 200],
            "learning_rate": [0.01, 0.1],
            "max_depth": [3, 5, 7]
        }
    }
}


def get_model_class(model_name: str):
    """Get model class from registry."""
    if model_name.lower() not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(MODEL_REGISTRY.keys())}")
    return MODEL_REGISTRY[model_name.lower()]


def train_model_with_cv(
    model_name: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: Optional[pd.DataFrame] = None,
    y_test: Optional[pd.Series] = None,
    param_grid: Optional[Dict] = None,
    cv_folds: int = 5,
    scoring: str = "accuracy",
    search_strategy: str = "grid",
    n_jobs: int = -1,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Train a single model with hyperparameter tuning via cross-validation.

    Returns:
        Dictionary with trained model, best params, CV results, and metrics
    """
    model_info = get_model_class(model_name)
    model_class = model_info["class"]
    base_params = model_info["default_params"].copy()

    if param_grid is None:
        param_grid = model_info["param_grid"]

    if verbose:
        print(f"      {model_name.upper()}...")

    # Create base model
    base_model = model_class(**base_params)

    # Grid or Random search
    if search_strategy == "grid":
        searcher = GridSearchCV(
            base_model,
            param_grid=param_grid,
            cv=cv_folds,
            scoring=scoring,
            n_jobs=n_jobs,
            verbose=0 if not verbose else 1
        )
    else:  # random
        searcher = RandomizedSearchCV(
            base_model,
            param_distributions=param_grid,
            n_iter=10,
            cv=cv_folds,
            scoring=scoring,
            n_jobs=n_jobs,
            random_state=42,
            verbose=0 if not verbose else 1
        )

    # Fit searcher
    searcher.fit(X_train, y_train)

    best_model = searcher.best_estimator_
    best_params = searcher.best_params_
    cv_results = pd.DataFrame(searcher.cv_results_)

    # Evaluate on test set if available
    test_score = None
    if X_test is not None and y_test is not None:
        test_score = best_model.score(X_test, y_test)

    if verbose:
        print(f"         Best CV score: {searcher.best_score_:.4f}")
        if test_score is not None:
            print(f"         Test score: {test_score:.4f}")

    return {
        "model_name": model_name,
        "model": best_model,
        "best_params": best_params,
        "best_cv_score": searcher.best_score_,
        "cv_results": cv_results,
        "test_score": test_score,
        "searcher": searcher
    }


def train_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: Optional[pd.DataFrame] = None,
    y_test: Optional[pd.Series] = None,
    models: Optional[List[str]] = None,
    param_grids: Optional[Dict[str, Dict]] = None,
    cv_folds: int = 5,
    scoring: str = "accuracy",
    search_strategy: str = "grid",
    n_jobs: int = -1,
    models_dir: Optional[Path] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Train multiple models with hyperparameter tuning.

    Args:
        X_train, y_train: Training data
        X_test, y_test: Test data (optional)
        models: List of model names to train
        param_grids: Dict of model_name -> param_grid override
        cv_folds: Number of CV folds
        scoring: Metric to optimize
        search_strategy: 'grid' or 'random'
        n_jobs: Parallel jobs
        models_dir: Directory to save trained models
        verbose: Print progress?

    Returns:
        Dictionary with trained models and results
    """
    if models is None:
        models = ["rf", "logreg"]

    if param_grids is None:
        param_grids = {}

    all_results = {}
    trained_models = {}
    all_cv_results = []

    if verbose:
        print(f"   Training {len(models)} model(s) with {cv_folds}-fold CV...")

    for model_name in models:
        param_grid = param_grids.get(model_name)

        result = train_model_with_cv(
            model_name=model_name,
            X_train=X_train,
            y_train=y_train,
            X_test=X_test,
            y_test=y_test,
            param_grid=param_grid,
            cv_folds=cv_folds,
            scoring=scoring,
            search_strategy=search_strategy,
            n_jobs=n_jobs,
            verbose=verbose
        )

        all_results[model_name] = result
        trained_models[model_name] = result["model"]

        # Prepare CV results for output
        cv_df = result["cv_results"].copy()
        cv_df.insert(0, "model", model_name)
        all_cv_results.append(cv_df)

        # Save model to disk
        if models_dir:
            models_dir = Path(models_dir)
            models_dir.mkdir(parents=True, exist_ok=True)
            model_path = models_dir / f"{model_name}.joblib"
            joblib.dump(result["model"], model_path)
            if verbose:
                print(f"         Saved to {model_path}")

    # Aggregate results
    combined_cv_results = pd.concat(all_cv_results, ignore_index=True)

    # Find best model overall
    best_model_name = max(all_results, key=lambda k: all_results[k]["best_cv_score"])
    best_model = trained_models[best_model_name]

    if verbose:
        print(f"   ✅ Best model: {best_model_name} (CV score: {all_results[best_model_name]['best_cv_score']:.4f})")

    return {
        "models": trained_models,
        "best_model": best_model_name,
        "best_model_object": best_model,
        "best_params": all_results[best_model_name]["best_params"],
        "all_results": all_results,
        "cv_results": combined_cv_results,
        "cv_results_by_model": {m: all_results[m]["cv_results"] for m in models}
    }
