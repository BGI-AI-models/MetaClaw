#!/usr/bin/env python3
"""
Main orchestrator for the Classification Pipeline skill.
Guides users through preprocessing, training, evaluation, and prediction.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from preprocess import preprocess_data
from train import train_models
from evaluate import evaluate_models, generate_evaluation_report
from predict import make_predictions
from report import generate_summary_report


class ClassificationPipeline:
    """End-to-end classification pipeline orchestrator."""

    def __init__(self, output_dir: Optional[str] = None):
        """Initialize pipeline with output directory."""
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"classification_results_{timestamp}"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = {}

        # Create subdirectories
        self.preprocessing_dir = self.output_dir / "preprocessing"
        self.models_dir = self.output_dir / "models"
        self.evaluation_dir = self.output_dir / "evaluation"
        self.predictions_dir = self.output_dir / "predictions"

        for d in [self.preprocessing_dir, self.models_dir, self.evaluation_dir, self.predictions_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def preprocess(
        self,
        data_path: str,
        target_column: str,
        exclude_columns: Optional[list] = None,
        categorical_features: Optional[list] = None,
        imputation_method: str = "mean",
        scale_features: bool = True,
        split_strategy: str = "stratified_cv",
        test_size: float = 0.2,
        cv_folds: int = 5,
        random_state: int = 42,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Preprocess data: load, encode, impute, scale, split.

        Args:
            data_path: Path to input CSV/TSV/Parquet file
            target_column: Name of target/label column
            exclude_columns: Columns to drop before preprocessing
            categorical_features: Categorical columns for one-hot encoding
            imputation_method: 'mean', 'median', 'knn', 'mice', 'drop'
            scale_features: Standardize numeric features?
            split_strategy: 'train_test', 'cv', 'stratified_cv', 'full'
            test_size: Fraction for train/test split
            cv_folds: Number of CV folds
            random_state: Random seed
            verbose: Print progress?

        Returns:
            Dictionary with preprocessed data and metadata
        """
        if verbose:
            print(f"\n📊 Phase 1: Preprocessing")
            print(f"   Data: {data_path}")
            print(f"   Target: {target_column}")
            print(f"   Imputation: {imputation_method}")
            print(f"   Split strategy: {split_strategy}")

        result = preprocess_data(
            data_path=data_path,
            target_column=target_column,
            exclude_columns=exclude_columns or [],
            categorical_features=categorical_features or [],
            imputation_method=imputation_method,
            scale_features=scale_features,
            split_strategy=split_strategy,
            test_size=test_size,
            cv_folds=cv_folds,
            random_state=random_state,
            output_dir=self.preprocessing_dir,
            verbose=verbose
        )

        # Save preprocessing config
        self.config["preprocessing"] = {
            "data_path": str(data_path),
            "target_column": target_column,
            "exclude_columns": exclude_columns or [],
            "categorical_features": categorical_features or [],
            "imputation_method": imputation_method,
            "scale_features": scale_features,
            "split_strategy": split_strategy,
            "test_size": test_size,
            "cv_folds": cv_folds,
            "random_state": random_state
        }

        if verbose:
            print(f"   ✅ Preprocessing complete")

        return result

    def train(
        self,
        X_train,
        y_train,
        X_test=None,
        y_test=None,
        models: Optional[list] = None,
        param_grids: Optional[Dict[str, Dict]] = None,
        cv_folds: int = 5,
        scoring: str = "accuracy",
        search_strategy: str = "grid",
        n_jobs: int = -1,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Train and tune models with cross-validation.

        Args:
            X_train, y_train: Training data and labels
            X_test, y_test: Test data and labels (optional)
            models: List of model names ('rf', 'logreg', 'svm', 'xgb', etc.)
            param_grids: Dict of model -> {param: [values]}
            cv_folds: Number of CV folds
            scoring: Metric to optimize ('accuracy', 'f1', 'roc_auc', etc.)
            search_strategy: 'grid' or 'random'
            n_jobs: Parallel jobs (-1 for all cores)
            verbose: Print progress?

        Returns:
            Dictionary with trained models, results, and best params
        """
        if models is None:
            models = ["rf", "logreg"]

        if verbose:
            print(f"\n🎯 Phase 2: Training & Hyperparameter Tuning")
            print(f"   Models: {models}")
            print(f"   CV folds: {cv_folds}")
            print(f"   Scoring metric: {scoring}")
            print(f"   Search strategy: {search_strategy}")

        result = train_models(
            X_train=X_train,
            y_train=y_train,
            X_test=X_test,
            y_test=y_test,
            models=models,
            param_grids=param_grids,
            cv_folds=cv_folds,
            scoring=scoring,
            search_strategy=search_strategy,
            n_jobs=n_jobs,
            models_dir=self.models_dir,
            verbose=verbose
        )

        # Save training config
        self.config["training"] = {
            "models": models,
            "cv_folds": cv_folds,
            "scoring": scoring,
            "search_strategy": search_strategy,
            "best_params": result.get("best_params", {})
        }

        if verbose:
            print(f"   ✅ Training complete. Best model: {result.get('best_model')}")

        return result

    def evaluate(
        self,
        trained_models: Dict[str, Any],
        X_test,
        y_test,
        cv_results: Optional[Dict] = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluate models, generate confusion matrices, ROC curves, metrics tables.

        Args:
            trained_models: Dict of model_name -> fitted model
            X_test, y_test: Test data and labels
            cv_results: Optional cross-validation results from training
            verbose: Print progress?

        Returns:
            Dictionary with evaluation metrics and visualizations
        """
        if verbose:
            print(f"\n📈 Phase 3: Evaluation & Reporting")

        result = evaluate_models(
            models=trained_models,
            X_test=X_test,
            y_test=y_test,
            cv_results=cv_results,
            output_dir=self.evaluation_dir,
            verbose=verbose
        )

        # Generate evaluation report
        generate_evaluation_report(
            metrics=result["metrics"],
            output_dir=self.evaluation_dir,
            verbose=verbose
        )

        if verbose:
            print(f"   ✅ Evaluation complete")

        return result

    def predict(
        self,
        model,
        X_new,
        output_dir: Optional[Path] = None,
        verbose: bool = True
    ) -> Any:
        """
        Make predictions on new data.

        Args:
            model: Trained model object
            X_new: New data to predict on
            output_dir: Where to save predictions
            verbose: Print progress?

        Returns:
            Predictions (and probabilities if available)
        """
        if output_dir is None:
            output_dir = self.predictions_dir

        if verbose:
            print(f"\n🔮 Phase 4: Prediction")

        result = make_predictions(
            model=model,
            X_new=X_new,
            output_dir=output_dir,
            verbose=verbose
        )

        if verbose:
            print(f"   ✅ Predictions saved to {output_dir}")

        return result

    def generate_report(self, verbose: bool = True) -> Path:
        """
        Generate comprehensive summary report.

        Returns:
            Path to generated report
        """
        if verbose:
            print(f"\n📝 Generating Summary Report")

        report_path = generate_summary_report(
            output_dir=self.output_dir,
            config=self.config,
            verbose=verbose
        )

        # Save config snapshot
        config_path = self.output_dir / "config_used.json"
        with open(config_path, "w") as f:
            json.dump(self.config, f, indent=2, default=str)

        if verbose:
            print(f"   ✅ Report saved to {report_path}")
            print(f"\n✨ All results in: {self.output_dir}")

        return report_path

    def run_full_pipeline(
        self,
        data_path: str,
        target_column: str,
        exclude_columns: Optional[list] = None,
        categorical_features: Optional[list] = None,
        imputation_method: str = "mean",
        scale_features: bool = True,
        split_strategy: str = "stratified_cv",
        models: Optional[list] = None,
        param_grids: Optional[Dict] = None,
        cv_folds: int = 5,
        scoring: str = "accuracy",
        search_strategy: str = "grid",
        random_state: int = 42,
        verbose: bool = True
    ) -> Path:
        """
        Run complete pipeline: preprocess → train → evaluate → report.

        Returns:
            Path to output directory
        """
        # Phase 1: Preprocessing
        preproc_result = self.preprocess(
            data_path=data_path,
            target_column=target_column,
            exclude_columns=exclude_columns,
            categorical_features=categorical_features,
            imputation_method=imputation_method,
            scale_features=scale_features,
            split_strategy=split_strategy,
            cv_folds=cv_folds,
            random_state=random_state,
            verbose=verbose
        )

        # Phase 2: Training
        train_result = self.train(
            X_train=preproc_result["X_train"],
            y_train=preproc_result["y_train"],
            X_test=preproc_result.get("X_test"),
            y_test=preproc_result.get("y_test"),
            models=models,
            param_grids=param_grids,
            cv_folds=cv_folds,
            scoring=scoring,
            search_strategy=search_strategy,
            verbose=verbose
        )

        # Phase 3: Evaluation
        if preproc_result.get("X_test") is not None:
            self.evaluate(
                trained_models=train_result["models"],
                X_test=preproc_result["X_test"],
                y_test=preproc_result["y_test"],
                cv_results=train_result.get("cv_results"),
                verbose=verbose
            )

        # Phase 4: Report
        self.generate_report(verbose=verbose)

        return self.output_dir


if __name__ == "__main__":
    # Example usage
    pipeline = ClassificationPipeline()

    # This would be called interactively through the skill
    # For now, just showing the structure
    print("Classification Pipeline initialized. Call methods as needed.")
