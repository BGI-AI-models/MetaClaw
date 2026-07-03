#!/usr/bin/env python3
"""
Data preprocessing module for classification pipeline.
Handles loading, encoding, imputation, scaling, and splitting.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, StratifiedKFold, KFold
import warnings

warnings.filterwarnings('ignore')


def load_data(data_path: str, verbose: bool = True) -> pd.DataFrame:
    """Load data from CSV, TSV, or Parquet file."""
    path = Path(data_path)

    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    if verbose:
        print(f"   Loading data from {path.name}...")

    if path.suffix == ".parquet":
        df = pd.read_parquet(data_path)
    elif path.suffix == ".csv":
        df = pd.read_csv(data_path)
    else:  # .tsv or generic text
        df = pd.read_csv(data_path, sep="\t")

    if verbose:
        print(f"   Shape: {df.shape}")

    return df


def handle_missing_values(
    df: pd.DataFrame,
    method: str = "mean",
    verbose: bool = True
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Handle missing values using specified method.

    Args:
        df: Input dataframe
        method: 'drop', 'mean', 'median', 'knn', 'mice'
        verbose: Print progress?

    Returns:
        Cleaned dataframe and metadata
    """
    missing_pct = df.isnull().sum() / len(df) * 100
    if missing_pct.sum() == 0:
        if verbose:
            print(f"   No missing values found")
        return df, {"method": "none", "cols_with_missing": []}

    cols_with_missing = missing_pct[missing_pct > 0].index.tolist()
    if verbose:
        print(f"   Missing values in {len(cols_with_missing)} columns")

    if method == "drop":
        df_clean = df.dropna()
        if verbose:
            print(f"   Dropped {len(df) - len(df_clean)} rows with missing values")
    elif method == "mean":
        df_clean = df.fillna(df.mean(numeric_only=True))
    elif method == "median":
        df_clean = df.fillna(df.median(numeric_only=True))
    elif method == "knn":
        try:
            from sklearn.impute import KNNImputer
            imputer = KNNImputer(n_neighbors=5)
            df_clean = pd.DataFrame(imputer.fit_transform(df), columns=df.columns)
        except Exception as e:
            if verbose:
                print(f"   KNN imputation failed, using mean: {e}")
            df_clean = df.fillna(df.mean(numeric_only=True))
    elif method == "mice":
        try:
            from sklearn.experimental import enable_iterative_imputer
            from sklearn.impute import IterativeImputer
            imputer = IterativeImputer(max_iter=10, random_state=42)
            df_clean = pd.DataFrame(imputer.fit_transform(df), columns=df.columns)
        except Exception as e:
            if verbose:
                print(f"   MICE imputation failed, using mean: {e}")
            df_clean = df.fillna(df.mean(numeric_only=True))
    else:
        df_clean = df

    return df_clean, {
        "method": method,
        "cols_with_missing": cols_with_missing,
        "rows_removed": len(df) - len(df_clean)
    }


def encode_categorical(
    df: pd.DataFrame,
    categorical_features: List[str],
    verbose: bool = True
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    One-hot encode categorical features.

    Args:
        df: Input dataframe
        categorical_features: List of categorical column names
        verbose: Print progress?

    Returns:
        Encoded dataframe and metadata
    """
    if not categorical_features:
        return df, {"method": "none", "encoded_cols": []}

    if verbose:
        print(f"   One-hot encoding {len(categorical_features)} categorical features")

    df_encoded = pd.get_dummies(df, columns=categorical_features, drop_first=True)

    encoded_cols = [c for c in df_encoded.columns if c not in df.columns or c.startswith(f"{categorical_features[0]}_")]
    return df_encoded, {
        "method": "one-hot",
        "encoded_cols": list(df_encoded.columns),
        "n_features_after": df_encoded.shape[1]
    }


def remove_zero_variance_features(
    df: pd.DataFrame,
    verbose: bool = True
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Remove features with zero variance (constant columns)."""
    initial_cols = df.shape[1]
    df_clean = df.loc[:, (df != df.iloc[0]).any()]

    removed = initial_cols - df_clean.shape[1]
    if verbose and removed > 0:
        print(f"   Removed {removed} zero-variance features")

    return df_clean, {"removed_count": removed}


def scale_features(
    X_train: pd.DataFrame,
    X_test: Optional[pd.DataFrame] = None,
    verbose: bool = True
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], StandardScaler]:
    """
    Standardize numeric features.

    Returns:
        Scaled training data, scaled test data (if provided), and the scaler
    """
    numeric_cols = X_train.select_dtypes(include=[np.number]).columns.tolist()

    if not numeric_cols:
        if verbose:
            print(f"   No numeric features to scale")
        return X_train, X_test, None

    if verbose:
        print(f"   Scaling {len(numeric_cols)} numeric features")

    scaler = StandardScaler()
    X_train_scaled = X_train.copy()
    X_train_scaled[numeric_cols] = scaler.fit_transform(X_train[numeric_cols])

    X_test_scaled = None
    if X_test is not None:
        X_test_scaled = X_test.copy()
        X_test_scaled[numeric_cols] = scaler.transform(X_test[numeric_cols])

    return X_train_scaled, X_test_scaled, scaler


def split_data(
    X: pd.DataFrame,
    y: pd.Series,
    strategy: str = "stratified_cv",
    test_size: float = 0.2,
    cv_folds: int = 5,
    random_state: int = 42,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Split data using specified strategy.

    Args:
        X, y: Features and labels
        strategy: 'train_test', 'cv', 'stratified_cv', 'full'
        test_size: Fraction for train/test split
        cv_folds: Number of CV folds
        random_state: Random seed
        verbose: Print progress?

    Returns:
        Dictionary with split data or generators
    """
    if verbose:
        print(f"   Splitting data ({strategy})...")

    if strategy == "train_test":
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=test_size,
            random_state=random_state,
            stratify=y if y.nunique() > 2 else None
        )
        if verbose:
            print(f"   Train: {X_train.shape[0]}, Test: {X_test.shape[0]}")
        return {
            "strategy": "train_test",
            "X_train": X_train,
            "y_train": y_train,
            "X_test": X_test,
            "y_test": y_test,
            "folds": None
        }

    elif strategy == "stratified_cv":
        skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
        folds = [(X.iloc[train_idx], X.iloc[test_idx], y.iloc[train_idx], y.iloc[test_idx])
                 for train_idx, test_idx in skf.split(X, y)]
        if verbose:
            print(f"   Created {cv_folds} stratified CV folds")
        return {
            "strategy": "stratified_cv",
            "X": X,
            "y": y,
            "folds": folds,
            "X_train": X,
            "y_train": y,
            "X_test": None,
            "y_test": None
        }

    elif strategy == "cv":
        kf = KFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
        folds = [(X.iloc[train_idx], X.iloc[test_idx], y.iloc[train_idx], y.iloc[test_idx])
                 for train_idx, test_idx in kf.split(X)]
        if verbose:
            print(f"   Created {cv_folds} CV folds")
        return {
            "strategy": "cv",
            "X": X,
            "y": y,
            "folds": folds,
            "X_train": X,
            "y_train": y,
            "X_test": None,
            "y_test": None
        }

    elif strategy == "full":
        if verbose:
            print(f"   Using full dataset (no split)")
        return {
            "strategy": "full",
            "X_train": X,
            "y_train": y,
            "X_test": None,
            "y_test": None,
            "folds": None
        }

    else:
        raise ValueError(f"Unknown split strategy: {strategy}")


def preprocess_data(
    data_path: str,
    target_column: str,
    exclude_columns: List[str] = None,
    categorical_features: List[str] = None,
    imputation_method: str = "mean",
    remove_high_missing: float = 90.0,
    scale_features_flag: bool = True,
    split_strategy: str = "stratified_cv",
    test_size: float = 0.2,
    cv_folds: int = 5,
    random_state: int = 42,
    output_dir: Optional[Path] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Complete preprocessing pipeline.

    Returns:
        Dictionary with preprocessed data and metadata
    """
    if verbose:
        print(f"   ─" * 40)

    # Step 1: Load
    df = load_data(data_path, verbose=verbose)

    # Step 2: Remove high-missing columns
    if remove_high_missing > 0:
        missing_pct = df.isnull().sum() / len(df) * 100
        high_missing_cols = missing_pct[missing_pct > remove_high_missing].index.tolist()
        if high_missing_cols and verbose:
            print(f"   Dropping columns with >{remove_high_missing}% missing: {high_missing_cols}")
        df = df.drop(columns=high_missing_cols, errors='ignore')

    # Step 3: Extract target
    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in data")

    y = df[target_column]
    df = df.drop(columns=[target_column])

    # Step 4: Drop excluded columns
    exclude_columns = exclude_columns or []
    df = df.drop(columns=exclude_columns, errors='ignore')

    # Step 5: Handle missing values
    df, _ = handle_missing_values(df, method=imputation_method, verbose=verbose)

    # Step 6: Encode categorical
    categorical_features = categorical_features or []
    df, _ = encode_categorical(df, categorical_features, verbose=verbose)

    # Step 7: Remove zero variance
    df, _ = remove_zero_variance_features(df, verbose=verbose)

    # Step 8: Scale features
    split_result = split_data(
        df, y,
        strategy=split_strategy,
        test_size=test_size,
        cv_folds=cv_folds,
        random_state=random_state,
        verbose=verbose
    )

    X_train = split_result["X_train"]
    y_train = split_result["y_train"]
    X_test = split_result.get("X_test")
    y_test = split_result.get("y_test")

    if scale_features_flag:
        X_train, X_test, scaler = scale_features(X_train, X_test, verbose=verbose)
    else:
        scaler = None

    # Step 9: Save preprocessed data
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        X_train.to_csv(output_dir / "train_processed.csv", index=False)
        if X_test is not None:
            X_test.to_csv(output_dir / "test_processed.csv", index=False)

        y_train.to_csv(output_dir / "train_labels.csv", index=False)
        if y_test is not None:
            y_test.to_csv(output_dir / "test_labels.csv", index=False)

        if verbose:
            print(f"   Saved preprocessed data to {output_dir}")

    if verbose:
        print(f"   ─" * 40)

    return {
        "X_train": X_train,
        "y_train": y_train,
        "X_test": X_test,
        "y_test": y_test,
        "scaler": scaler,
        "feature_names": list(X_train.columns),
        "target_classes": sorted(y_train.unique()),
        "split_strategy": split_strategy,
        "cv_folds": split_result.get("folds") if split_strategy in ["cv", "stratified_cv"] else None,
        "preprocessing_metadata": {
            "imputation_method": imputation_method,
            "categorical_features": categorical_features,
            "exclude_columns": exclude_columns,
            "n_features": X_train.shape[1],
            "n_samples_train": X_train.shape[0],
            "n_samples_test": X_test.shape[0] if X_test is not None else 0,
            "n_classes": len(y_train.unique()),
            "class_distribution": y_train.value_counts().to_dict()
        }
    }
