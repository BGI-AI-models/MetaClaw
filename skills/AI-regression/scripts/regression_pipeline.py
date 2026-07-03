#!/usr/bin/env python
"""
Regression Pipeline for Medical Data Analysis
Handles preprocessing, model training, evaluation, and reporting with advanced visualizations.
"""

import argparse
import json
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer, SimpleImputer
from sklearn.linear_model import Ridge, Lasso
from sklearn.svm import SVR
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

warnings.filterwarnings("ignore")
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 10


class RegressionPipeline:
    """End-to-end regression pipeline for medical data."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.models = {}
        self.results = {}
        self.preprocessor = None
        self.best_model = None
        self.best_model_name = None
        self.cv_results_df = None
        self.feature_names = None

    def load_data(self, input_path: str) -> pd.DataFrame:
        """Load CSV data."""
        try:
            df = pd.read_csv(input_path)
            print(f"[OK] Loaded {input_path}: {df.shape[0]} rows, {df.shape[1]} columns")
            return df
        except Exception as e:
            print(f"[ERROR] Error loading {input_path}: {e}")
            sys.exit(1)

    def analyze_data(self, df: pd.DataFrame) -> Tuple[List[str], List[str]]:
        """Analyze data to detect numeric and categorical columns."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        return numeric_cols, categorical_cols

    def preprocess_data(self, df: pd.DataFrame, target_col: str) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Preprocess data: imputation, encoding, scaling.
        """
        df = df.copy()

        # Separate target
        if target_col not in df.columns:
            print(f"[ERROR] Target column '{target_col}' not found in data")
            print(f"Available columns: {df.columns.tolist()}")
            sys.exit(1)

        y = df[target_col]
        X = df.drop(columns=[target_col])

        # Check for missing target
        if y.isna().sum() > 0:
            print(f"[ERROR] Target column has {y.isna().sum()} missing values. Please clean data.")
            sys.exit(1)

        numeric_cols, categorical_cols = self.analyze_data(X)

        print(f"[OK] Detected {len(numeric_cols)} numeric, {len(categorical_cols)} categorical features")
        print(f"[OK] Target: {target_col} (min={y.min():.2f}, max={y.max():.2f}, mean={y.mean():.2f})")

        # Imputation
        impute_method = self.config.get("preprocessing", {}).get("imputation_method", "mice")
        print(f"[OK] Imputation method: {impute_method}")

        if impute_method == "mice":
            imputer = IterativeImputer(max_iter=10, random_state=42)
        elif impute_method == "mean":
            imputer = SimpleImputer(strategy="mean")
        elif impute_method == "median":
            imputer = SimpleImputer(strategy="median")
        elif impute_method == "none":
            imputer = None
        else:
            imputer = IterativeImputer(max_iter=10, random_state=42)

        # Apply imputation to numeric features
        if imputer and len(numeric_cols) > 0:
            X[numeric_cols] = imputer.fit_transform(X[numeric_cols])

        # One-hot encode categorical features
        if len(categorical_cols) > 0:
            X = pd.get_dummies(X, columns=categorical_cols, drop_first=True)
            print(f"[OK] One-hot encoded categorical features -> {X.shape[1]} total features")

        # Handle any remaining NaN
        X = X.fillna(X.mean())

        # Train/test split
        test_split = self.config.get("preprocessing", {}).get("test_split_ratio", 0.2)
        random_state = self.config.get("preprocessing", {}).get("random_state", 42)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_split, random_state=random_state
        )

        print(f"[OK] Split: {X_train.shape[0]} train, {X_test.shape[0]} test ({test_split*100:.0f}%)")

        # Scaling
        scaler = StandardScaler()
        X_train = pd.DataFrame(
            scaler.fit_transform(X_train),
            columns=X_train.columns,
            index=X_train.index
        )
        X_test = pd.DataFrame(
            scaler.transform(X_test),
            columns=X_test.columns,
            index=X_test.index
        )

        self.feature_names = X_train.columns.tolist()
        print(f"[OK] Features standardized (StandardScaler)")

        return X_train, X_test, y_train, y_test, X.columns.tolist()

    def train_models(self, X_train: pd.DataFrame, y_train: pd.Series) -> Dict[str, Any]:
        """Train and tune models via grid search + cross-validation."""
        models_to_train = self.config.get("training", {}).get("models", ["ridge", "rf", "gb"])
        cv = self.config.get("training", {}).get("cv", 5)
        n_jobs = self.config.get("training", {}).get("n_jobs", -1)
        param_grids = self.config.get("training", {}).get("param_grids", {})

        print(f"\n[INFO] Training Models ({cv}-fold CV):")

        results = {}

        # Ridge
        if "ridge" in models_to_train:
            print(f"\n  Ridge Regression:")
            ridge_params = param_grids.get("ridge", {"alpha": [0.01, 0.1, 1.0, 10.0, 100.0]})
            ridge = GridSearchCV(
                Ridge(),
                ridge_params,
                cv=cv,
                scoring="r2",
                n_jobs=n_jobs
            )
            ridge.fit(X_train, y_train)
            self.models["ridge"] = ridge.best_estimator_
            results["ridge"] = {
                "best_params": ridge.best_params_,
                "best_cv_score": ridge.best_score_,
                "cv_results": ridge.cv_results_
            }
            print(f"    [OK] Best params: {ridge.best_params_}")
            print(f"    [OK] CV R2 score: {ridge.best_score_:.4f}")

        # Lasso
        if "lasso" in models_to_train:
            print(f"\n  Lasso Regression:")
            lasso_params = param_grids.get("lasso", {"alpha": [0.001, 0.01, 0.1, 1.0, 10.0]})
            lasso = GridSearchCV(
                Lasso(max_iter=5000),
                lasso_params,
                cv=cv,
                scoring="r2",
                n_jobs=n_jobs
            )
            lasso.fit(X_train, y_train)
            self.models["lasso"] = lasso.best_estimator_
            results["lasso"] = {
                "best_params": lasso.best_params_,
                "best_cv_score": lasso.best_score_,
                "cv_results": lasso.cv_results_
            }
            print(f"    [OK] Best params: {lasso.best_params_}")
            print(f"    [OK] CV R2 score: {lasso.best_score_:.4f}")

        # Random Forest
        if "rf" in models_to_train:
            print(f"\n  Random Forest:")
            rf_params = param_grids.get("rf", {
                "n_estimators": [100, 200, 500],
                "max_depth": [5, 10, None]
            })
            rf = GridSearchCV(
                RandomForestRegressor(random_state=42),
                rf_params,
                cv=cv,
                scoring="r2",
                n_jobs=n_jobs
            )
            rf.fit(X_train, y_train)
            self.models["rf"] = rf.best_estimator_
            results["rf"] = {
                "best_params": rf.best_params_,
                "best_cv_score": rf.best_score_,
                "cv_results": rf.cv_results_
            }
            print(f"    [OK] Best params: {rf.best_params_}")
            print(f"    [OK] CV R2 score: {rf.best_score_:.4f}")

        # Gradient Boosting
        if "gb" in models_to_train:
            print(f"\n  Gradient Boosting:")
            gb_params = param_grids.get("gb", {
                "n_estimators": [100, 200],
                "learning_rate": [0.01, 0.1]
            })
            gb = GridSearchCV(
                GradientBoostingRegressor(random_state=42),
                gb_params,
                cv=cv,
                scoring="r2",
                n_jobs=n_jobs
            )
            gb.fit(X_train, y_train)
            self.models["gb"] = gb.best_estimator_
            results["gb"] = {
                "best_params": gb.best_params_,
                "best_cv_score": gb.best_score_,
                "cv_results": gb.cv_results_
            }
            print(f"    [OK] Best params: {gb.best_params_}")
            print(f"    [OK] CV R2 score: {gb.best_score_:.4f}")

        # SVM
        if "svr" in models_to_train:
            print(f"\n  Support Vector Regression:")
            svr_params = param_grids.get("svr", {
                "C": [0.1, 1.0, 10.0],
                "kernel": ["linear", "rbf"]
            })
            svr = GridSearchCV(
                SVR(),
                svr_params,
                cv=cv,
                scoring="r2",
                n_jobs=n_jobs
            )
            svr.fit(X_train, y_train)
            self.models["svr"] = svr.best_estimator_
            results["svr"] = {
                "best_params": svr.best_params_,
                "best_cv_score": svr.best_score_,
                "cv_results": svr.cv_results_
            }
            print(f"    [OK] Best params: {svr.best_params_}")
            print(f"    [OK] CV R2 score: {svr.best_score_:.4f}")

        return results

    def evaluate_models(
        self, X_test: pd.DataFrame, y_test: pd.Series
    ) -> pd.DataFrame:
        """Evaluate all trained models on test set."""
        print(f"\n[INFO] Model Evaluation (Test Set):")

        eval_results = []
        best_score = -np.inf
        best_model_name = None

        for model_name, model in self.models.items():
            y_pred = model.predict(X_test)

            r2 = r2_score(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)

            eval_results.append({
                "Model": model_name.upper(),
                "R2": r2,
                "RMSE": rmse,
                "MAE": mae
            })

            print(f"  {model_name.upper()}:")
            print(f"    R2 = {r2:.4f}")
            print(f"    RMSE = {rmse:.4f}")
            print(f"    MAE = {mae:.4f}")

            if r2 > best_score:
                best_score = r2
                best_model_name = model_name

        self.best_model_name = best_model_name
        self.best_model = self.models[best_model_name]
        print(f"\n  [BEST] Best Model: {best_model_name.upper()} (R2 = {best_score:.4f})")

        return pd.DataFrame(eval_results)

    def plot_model_comparison(self, eval_df: pd.DataFrame, output_dir: Path):
        """Create comparison plots for all models."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Bar chart: R2, RMSE, MAE comparison
        fig, axes = plt.subplots(1, 3, figsize=(15, 4))

        metrics = ["R2", "RMSE", "MAE"]
        for idx, metric in enumerate(metrics):
            ax = axes[idx]
            colors = ['#2ecc71' if val == eval_df[metric].max() else '#3498db'
                      for val in eval_df[metric]]
            ax.bar(eval_df["Model"], eval_df[metric], color=colors, alpha=0.8, edgecolor='black')
            ax.set_ylabel(metric, fontsize=11, fontweight='bold')
            ax.set_xlabel('Model', fontsize=11, fontweight='bold')
            ax.set_title(f'{metric} Comparison', fontsize=12, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            for i, v in enumerate(eval_df[metric]):
                ax.text(i, v + (eval_df[metric].max() * 0.02), f'{v:.3f}', ha='center', fontweight='bold')

        plt.tight_layout()
        plt.savefig(output_dir / "model_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  [OK] {output_dir / 'model_comparison.png'}")

    def plot_predictions_vs_actual(self, X_test: pd.DataFrame, y_test: pd.Series, output_dir: Path):
        """Plot predicted vs actual values with confidence intervals."""
        output_dir.mkdir(parents=True, exist_ok=True)

        y_pred = self.best_model.predict(X_test)
        residuals = y_test.values - y_pred

        # Scatter plot with diagonal line
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Predictions vs Actual
        ax = axes[0]
        ax.scatter(y_test, y_pred, alpha=0.6, s=60, edgecolor='black', linewidth=0.5)
        min_val = min(y_test.min(), y_pred.min())
        max_val = max(y_test.max(), y_pred.max())
        ax.plot([min_val, max_val], [min_val, max_val], 'r--', lw=2, label='Perfect Prediction')
        ax.set_xlabel('Actual Values', fontsize=11, fontweight='bold')
        ax.set_ylabel('Predicted Values', fontsize=11, fontweight='bold')
        ax.set_title('Predictions vs Actual', fontsize=12, fontweight='bold')
        ax.grid(alpha=0.3)
        ax.legend()

        # Residuals plot
        ax = axes[1]
        ax.scatter(y_pred, residuals, alpha=0.6, s=60, edgecolor='black', linewidth=0.5, color='coral')
        ax.axhline(y=0, color='r', linestyle='--', lw=2)
        ax.set_xlabel('Predicted Values', fontsize=11, fontweight='bold')
        ax.set_ylabel('Residuals', fontsize=11, fontweight='bold')
        ax.set_title('Residuals Plot', fontsize=12, fontweight='bold')
        ax.grid(alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_dir / "predictions_vs_actual.png", dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  [OK] {output_dir / 'predictions_vs_actual.png'}")

    def plot_residual_analysis(self, X_test: pd.DataFrame, y_test: pd.Series, output_dir: Path):
        """Analyze residuals distribution and patterns."""
        output_dir.mkdir(parents=True, exist_ok=True)

        y_pred = self.best_model.predict(X_test)
        residuals = y_test.values - y_pred

        fig, axes = plt.subplots(2, 2, figsize=(12, 10))

        # Histogram of residuals
        ax = axes[0, 0]
        ax.hist(residuals, bins=20, color='#3498db', alpha=0.7, edgecolor='black')
        ax.axvline(x=0, color='r', linestyle='--', lw=2, label='Zero Error')
        ax.set_xlabel('Residuals', fontsize=11, fontweight='bold')
        ax.set_ylabel('Frequency', fontsize=11, fontweight='bold')
        ax.set_title('Residuals Distribution', fontsize=12, fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)

        # Q-Q plot (normality check)
        ax = axes[0, 1]
        from scipy import stats
        stats.probplot(residuals, dist="norm", plot=ax)
        ax.set_title('Q-Q Plot (Normality Check)', fontsize=12, fontweight='bold')
        ax.grid(alpha=0.3)

        # Residuals by predicted value
        ax = axes[1, 0]
        ax.scatter(y_pred, residuals, alpha=0.6, s=60, edgecolor='black', linewidth=0.5, color='coral')
        ax.axhline(y=0, color='r', linestyle='--', lw=2)
        ax.set_xlabel('Predicted Values', fontsize=11, fontweight='bold')
        ax.set_ylabel('Residuals', fontsize=11, fontweight='bold')
        ax.set_title('Residuals vs Fitted Values', fontsize=12, fontweight='bold')
        ax.grid(alpha=0.3)

        # Absolute residuals by predicted value
        ax = axes[1, 1]
        ax.scatter(y_pred, np.abs(residuals), alpha=0.6, s=60, edgecolor='black', linewidth=0.5, color='green')
        ax.set_xlabel('Predicted Values', fontsize=11, fontweight='bold')
        ax.set_ylabel('Absolute Residuals', fontsize=11, fontweight='bold')
        ax.set_title('Absolute Errors vs Fitted Values', fontsize=12, fontweight='bold')
        ax.grid(alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_dir / "residual_analysis.png", dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  [OK] {output_dir / 'residual_analysis.png'}")

    def plot_feature_importance(self, output_dir: Path):
        """Plot feature importance for tree-based models."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get feature importance from best model if it's tree-based
        if hasattr(self.best_model, 'feature_importances_'):
            importances = self.best_model.feature_importances_
            indices = np.argsort(importances)[-15:]  # Top 15 features

            fig, ax = plt.subplots(figsize=(10, 6))
            ax.barh(range(len(indices)), importances[indices], color='#2ecc71', alpha=0.8, edgecolor='black')
            ax.set_yticks(range(len(indices)))
            ax.set_yticklabels([self.feature_names[i] for i in indices])
            ax.set_xlabel('Importance Score', fontsize=11, fontweight='bold')
            ax.set_title(f'Top 15 Feature Importance ({self.best_model_name.upper()})', fontsize=12, fontweight='bold')
            ax.grid(axis='x', alpha=0.3)

            plt.tight_layout()
            plt.savefig(output_dir / "feature_importance.png", dpi=300, bbox_inches='tight')
            plt.close()
            print(f"  [OK] {output_dir / 'feature_importance.png'}")
        elif hasattr(self.best_model, 'coef_'):
            # For linear models, use coefficient magnitude
            coefs = np.abs(self.best_model.coef_)
            indices = np.argsort(coefs)[-15:]

            fig, ax = plt.subplots(figsize=(10, 6))
            ax.barh(range(len(indices)), coefs[indices], color='#9b59b6', alpha=0.8, edgecolor='black')
            ax.set_yticks(range(len(indices)))
            ax.set_yticklabels([self.feature_names[i] for i in indices])
            ax.set_xlabel('Coefficient Magnitude', fontsize=11, fontweight='bold')
            ax.set_title(f'Top 15 Feature Importance ({self.best_model_name.upper()})', fontsize=12, fontweight='bold')
            ax.grid(axis='x', alpha=0.3)

            plt.tight_layout()
            plt.savefig(output_dir / "feature_importance.png", dpi=300, bbox_inches='tight')
            plt.close()
            print(f"  [OK] {output_dir / 'feature_importance.png'}")

    def plot_error_distribution(self, X_test: pd.DataFrame, y_test: pd.Series, output_dir: Path):
        """Plot error metrics distribution across test set."""
        output_dir.mkdir(parents=True, exist_ok=True)

        y_pred = self.best_model.predict(X_test)
        errors = np.abs(y_test.values - y_pred)

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Histogram of absolute errors
        ax = axes[0]
        ax.hist(errors, bins=20, color='#e74c3c', alpha=0.7, edgecolor='black')
        ax.axvline(x=errors.mean(), color='b', linestyle='--', lw=2, label=f'Mean: {errors.mean():.3f}')
        ax.axvline(x=np.median(errors), color='g', linestyle='--', lw=2, label=f'Median: {np.median(errors):.3f}')
        ax.set_xlabel('Absolute Error', fontsize=11, fontweight='bold')
        ax.set_ylabel('Frequency', fontsize=11, fontweight='bold')
        ax.set_title('Distribution of Absolute Errors', fontsize=12, fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)

        # Box plot of errors
        ax = axes[1]
        bp = ax.boxplot([errors], labels=[self.best_model_name.upper()], patch_artist=True)
        for patch in bp['boxes']:
            patch.set_facecolor('#3498db')
            patch.set_alpha(0.7)
        ax.set_ylabel('Absolute Error', fontsize=11, fontweight='bold')
        ax.set_title('Error Distribution (Box Plot)', fontsize=12, fontweight='bold')
        ax.grid(alpha=0.3, axis='y')

        plt.tight_layout()
        plt.savefig(output_dir / "error_distribution.png", dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  [OK] {output_dir / 'error_distribution.png'}")

    def save_results(self, output_dir: Path, X_train: pd.DataFrame, X_test: pd.DataFrame,
                     y_train: pd.Series, y_test: pd.Series, eval_df: pd.DataFrame,
                     feature_columns: List[str]):
        """Save all results to output directory."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[SAVE] Saving Results to {output_dir}:")

        # Preprocessed data
        preprocess_dir = output_dir / "preprocessed"
        preprocess_dir.mkdir(exist_ok=True)

        train_df = X_train.copy()
        train_df["target"] = y_train.values
        train_df.to_csv(preprocess_dir / "train_preprocessed.csv", index=False)
        print(f"  [OK] {preprocess_dir / 'train_preprocessed.csv'}")

        test_df = X_test.copy()
        test_df["target"] = y_test.values
        test_df.to_csv(preprocess_dir / "test_preprocessed.csv", index=False)
        print(f"  [OK] {preprocess_dir / 'test_preprocessed.csv'}")

        # Models
        model_dir = output_dir / "models"
        model_dir.mkdir(exist_ok=True)

        for model_name, model in self.models.items():
            model_path = model_dir / f"{model_name}.joblib"
            joblib.dump(model, model_path)
            print(f"  [OK] {model_path}")

        # Results
        results_dir = output_dir / "results"
        results_dir.mkdir(exist_ok=True)

        eval_df.to_csv(results_dir / "model_comparison.csv", index=False)
        print(f"  [OK] {results_dir / 'model_comparison.csv'}")

        # Predictions
        y_pred = self.best_model.predict(X_test)
        pred_df = pd.DataFrame({
            "actual": y_test.values,
            "predicted": y_pred,
            "residual": y_test.values - y_pred,
            "absolute_error": np.abs(y_test.values - y_pred)
        })
        pred_df.to_csv(results_dir / "predictions_test.csv", index=False)
        print(f"  [OK] {results_dir / 'predictions_test.csv'}")

        # Visualizations
        plots_dir = output_dir / "plots"
        plots_dir.mkdir(exist_ok=True)

        print(f"\n[INFO] Generating visualizations:")
        self.plot_model_comparison(eval_df, plots_dir)
        self.plot_predictions_vs_actual(X_test, y_test, plots_dir)
        self.plot_residual_analysis(X_test, y_test, plots_dir)
        self.plot_feature_importance(plots_dir)
        self.plot_error_distribution(X_test, y_test, plots_dir)

        # Config snapshot
        config_path = output_dir / "config_used.yaml"
        with open(config_path, "w") as f:
            yaml.dump(self.config, f, default_flow_style=False)
        print(f"\n  [OK] {config_path}")

        # Metrics JSON
        metrics_dict = {
            "best_model": self.best_model_name,
            "metrics": eval_df.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat(),
            "test_size": len(X_test),
            "train_size": len(X_train),
            "n_features": len(self.feature_names)
        }
        metrics_path = output_dir / "model_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics_dict, f, indent=2)
        print(f"  [OK] {metrics_path}")

        # Summary report
        summary_path = output_dir / "ANALYSIS_SUMMARY.txt"
        with open(summary_path, "w") as f:
            f.write("=" * 70 + "\n")
            f.write("REGRESSION ANALYSIS SUMMARY\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Best Model: {self.best_model_name.upper()}\n\n")
            f.write("MODEL PERFORMANCE (Test Set):\n")
            f.write("-" * 70 + "\n")
            for _, row in eval_df.iterrows():
                f.write(f"\n{row['Model']}:\n")
                f.write(f"  R2 Score:  {row['R2']:.4f} (variance explained)\n")
                f.write(f"  RMSE:      {row['RMSE']:.4f} (root mean squared error)\n")
                f.write(f"  MAE:       {row['MAE']:.4f} (mean absolute error)\n")
            f.write("\n" + "=" * 70 + "\n")
            f.write("DATASET INFORMATION:\n")
            f.write("-" * 70 + "\n")
            f.write(f"Training samples: {len(X_train)}\n")
            f.write(f"Test samples:     {len(X_test)}\n")
            f.write(f"Total features:   {len(self.feature_names)}\n")
            f.write(f"Train/test ratio: {len(X_train)/(len(X_train)+len(X_test)):.1%}\n")
            f.write("\n" + "=" * 70 + "\n")
            f.write("OUTPUT FILES:\n")
            f.write("-" * 70 + "\n")
            f.write("Preprocessed data:\n")
            f.write("  - train_preprocessed.csv\n")
            f.write("  - test_preprocessed.csv\n\n")
            f.write("Trained models:\n")
            for model_name in self.models.keys():
                f.write(f"  - {model_name}.joblib\n")
            f.write("\nResults and visualizations:\n")
            f.write("  - model_comparison.csv\n")
            f.write("  - predictions_test.csv\n")
            f.write("  - model_comparison.png\n")
            f.write("  - predictions_vs_actual.png\n")
            f.write("  - residual_analysis.png\n")
            f.write("  - feature_importance.png\n")
            f.write("  - error_distribution.png\n")
            f.write("\n" + "=" * 70 + "\n")

        print(f"  [OK] {summary_path}")


def load_default_config() -> Dict[str, Any]:
    """Load default configuration."""
    return {
        "preprocessing": {
            "imputation_method": "mice",
            "scaling": True,
            "test_split_ratio": 0.2,
            "random_state": 42
        },
        "training": {
            "models": ["ridge", "rf", "gb"],
            "cv": 5,
            "n_jobs": -1,
            "param_grids": {
                "ridge": {
                    "alpha": [0.01, 0.1, 1.0, 10.0, 100.0]
                },
                "rf": {
                    "n_estimators": [100, 200, 500],
                    "max_depth": [5, 10, None]
                },
                "gb": {
                    "n_estimators": [100, 200],
                    "learning_rate": [0.01, 0.1]
                }
            }
        },
        "evaluation": {
            "scoring": ["r2", "rmse", "mae"],
            "best_metric": "r2",
            "plots": True,
            "report": True
        },
        "output": {
            "directory": None,
            "save_models": True,
            "save_preprocessed": True
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="Regression Pipeline for Medical Data Analysis"
    )
    parser.add_argument("--input", required=True, help="Input CSV file path")
    parser.add_argument("--target", required=True, help="Target column name")
    parser.add_argument("--config", help="Optional YAML config file")
    parser.add_argument("--output", help="Output directory (auto-generated if not specified)")

    args = parser.parse_args()

    # Load config
    if args.config:
        with open(args.config, "r") as f:
            config = yaml.safe_load(f)
    else:
        config = load_default_config()

    # Output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"regression_analysis_{timestamp}")

    # Run pipeline
    pipeline = RegressionPipeline(config)

    # Load and preprocess
    df = pipeline.load_data(args.input)
    X_train, X_test, y_train, y_test, feature_columns = pipeline.preprocess_data(df, args.target)

    # Train
    pipeline.train_models(X_train, y_train)

    # Evaluate
    eval_df = pipeline.evaluate_models(X_test, y_test)

    # Save
    pipeline.save_results(output_dir, X_train, X_test, y_train, y_test, eval_df, feature_columns)

    print(f"\n[DONE] Pipeline complete! Results saved to: {output_dir}")


if __name__ == "__main__":
    main()
