#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate data before Cox survival analysis."""

import os
import pandas as pd
from typing import Dict, List, Tuple, Any


def validate_data_exists(data_path: str) -> bool:
    """Check if data file exists."""
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Data file not found: {data_path}")
    return True


def validate_data_loads(data_path: str) -> pd.DataFrame:
    """Load and validate data can be read."""
    try:
        if data_path.endswith(".tsv"):
            df = pd.read_csv(data_path, sep="\t")
        else:
            df = pd.read_csv(data_path)
        return df
    except Exception as e:
        raise ValueError(f"Failed to load data: {e}")


def validate_required_columns(
    df: pd.DataFrame, required_cols: List[str], context: str = ""
) -> bool:
    """Check if required columns exist in dataframe."""
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        available = list(df.columns)
        raise ValueError(
            f"{context}\nMissing columns: {missing}\n"
            f"Available columns: {available}"
        )
    return True


def validate_event_column(df: pd.DataFrame, event_col: str) -> Tuple[bool, str]:
    """Validate event column has binary values."""
    unique_vals = df[event_col].dropna().unique()

    # Allow 0/1, True/False, or similar
    if not all(v in [0, 1, True, False] for v in unique_vals):
        raise ValueError(
            f"Event column '{event_col}' must be binary (0/1 or True/False). "
            f"Found values: {sorted(unique_vals)}"
        )

    n_events = int((df[event_col] == 1).sum())
    n_total = len(df)

    if n_events == 0:
        raise ValueError(f"No events found in '{event_col}' column")

    if n_events < 10:
        warning = (
            f"⚠ WARNING: Only {n_events} events found (out of {n_total} samples). "
            "Cox models may be unstable with few events. "
            "Consider consulting a statistician."
        )
        return True, warning

    return True, ""


def validate_duration_column(df: pd.DataFrame, duration_col: str) -> Tuple[bool, str]:
    """Validate duration column has positive numeric values."""
    try:
        durations = pd.to_numeric(df[duration_col], errors="coerce")
    except Exception as e:
        raise ValueError(f"Duration column '{duration_col}' is not numeric: {e}")

    missing_count = durations.isna().sum()
    if missing_count > 0:
        raise ValueError(
            f"Duration column '{duration_col}' has {missing_count} missing values"
        )

    if (durations <= 0).any():
        raise ValueError(
            f"Duration column '{duration_col}' contains non-positive values. "
            "Duration must be > 0."
        )

    return True, ""


def validate_categorical_columns(
    df: pd.DataFrame, cat_cols: List[str]
) -> Tuple[bool, Dict[str, int]]:
    """Validate categorical columns."""
    cat_info = {}

    for col in cat_cols:
        if col not in df.columns:
            raise ValueError(f"Categorical column '{col}' not found in data")

        unique_count = df[col].nunique()
        cat_info[col] = unique_count

        # Warn if too many categories (causes feature explosion after one-hot encoding)
        if unique_count > 20:
            print(
                f"⚠ WARNING: Categorical column '{col}' has {unique_count} unique values. "
                "This may create too many features. Consider grouping some categories."
            )

    return True, cat_info


def validate_missing_data(df: pd.DataFrame) -> Dict[str, float]:
    """Check missing data percentages."""
    missing_pct = (df.isna().sum() / len(df) * 100).round(2)
    missing_pct = missing_pct[missing_pct > 0].sort_values(ascending=False)

    if len(missing_pct) > 0:
        print("\nMissing Data Summary:")
        print("-" * 50)
        for col, pct in missing_pct.items():
            print(f"  {col}: {pct}%")

    return dict(missing_pct)


def validate_config_against_data(
    config: Dict[str, Any], df: pd.DataFrame
) -> Tuple[bool, List[str]]:
    """Validate configuration matches the data."""
    warnings = []

    # Check required columns based on mode
    if config.get("mode") == "longitudinal":
        required = [
            config.get("id_col"),
            config.get("time_col"),
            config.get("event_status_col"),
        ]
        required = [col for col in required if col]
        try:
            validate_required_columns(df, required, "Longitudinal mode")
        except ValueError as e:
            raise e

    else:  # single_row mode
        required = [
            config.get("duration_col"),
            config.get("event_col"),
        ]
        try:
            validate_required_columns(df, required, "Single-row mode")
        except ValueError as e:
            raise e

    # Validate event column
    event_col = config.get("event_col")
    if event_col and event_col in df.columns:
        _, warning = validate_event_column(df, event_col)
        if warning:
            warnings.append(warning)

    # Validate duration column
    duration_col = config.get("duration_col")
    if duration_col and duration_col in df.columns:
        _, warning = validate_duration_column(df, duration_col)
        if warning:
            warnings.append(warning)

    # Check categorical columns
    cat_cols = [c for c in config.get("cat_features", []) if c in df.columns]
    if cat_cols:
        validate_categorical_columns(df, cat_cols)

    # Check missing data
    missing_info = validate_missing_data(df)
    missing_threshold = config.get("missing_threshold", 50.0)
    high_missing = [col for col, pct in missing_info.items() if pct > missing_threshold]
    if high_missing:
        warnings.append(
            f"Columns with >{missing_threshold}% missing will be removed: {high_missing}"
        )

    return True, warnings


def print_validation_summary(df: pd.DataFrame, config: Dict[str, Any]) -> None:
    """Print data validation summary."""
    print("\n" + "=" * 70)
    print("DATA VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Shape: {df.shape[0]} samples × {df.shape[1]} features")
    print(f"Memory: {df.memory_usage(deep=True).sum() / 1e6:.2f} MB")

    event_col = config.get("event_col")
    if event_col and event_col in df.columns:
        n_events = int((df[event_col] == 1).sum())
        print(f"Events: {n_events} out of {len(df)} ({100*n_events/len(df):.1f}%)")

    print(f"Features: {df.shape[1]} columns")
    print(f"Missing: {df.isna().sum().sum()} cells ({100*df.isna().sum().sum()/(df.shape[0]*df.shape[1]):.1f}%)")
    print("=" * 70 + "\n")
