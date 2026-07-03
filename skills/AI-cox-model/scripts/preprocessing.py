# -*- coding: utf-8 -*-
"""COX 建模前的预处理：编码、特征筛选、标准化、插补。"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

from AI_toolbox.Preprocessing.Encoding import onehot_encoding
from AI_toolbox.Preprocessing.Feature_selection import (
    remove_high_missing_features,
    remove_zero_variance_features,
)
from AI_toolbox.Preprocessing.Imputation import fill_missing_values
from AI_toolbox.Preprocessing.Scaling import standardize

from .config import CoxPipelineConfig


def preprocess_for_cox(
    cox_df: pd.DataFrame,
    config: CoxPipelineConfig,
    duration_col: str = "duration",
    event_col: str = "event",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    编码 → 剔除低质量特征 → 标准化 → 插补；保留 duration / event，其余为特征。
    返回 (final_df, preprocess_artifacts) 供建模与后续复现。
    """
    artifacts: Dict[str, Any] = {}
    df = cox_df.copy()

    y_duration = df[duration_col]
    y_event = df[event_col]
    exclude = {duration_col, event_col} | set(config.exclude_from_features or [])
    feature_cols = [c for c in df.columns if c not in exclude]
    X = df[feature_cols].copy()

    if config.cat_features:
        cat_in_x = [c for c in config.cat_features if c in X.columns]
        if cat_in_x:
            X, artifacts["categories"] = onehot_encoding(
                X, cat_features=cat_in_x, verbose=config.verbose
            )
            for ref in config.drop_ref_categories or []:
                if ref in X.columns:
                    X = X.drop(columns=[ref])

    X, zero_var = remove_zero_variance_features(X, verbose=config.verbose)
    artifacts["zero_variance_dropped"] = zero_var
    X, high_miss = remove_high_missing_features(
        X, missing_threshold=config.missing_threshold, verbose=config.verbose
    )
    artifacts["high_missing_dropped"] = high_miss

    X_scaled, mean, std, standardized_features = standardize(
        X, on_binary=config.scale_on_binary, verbose=config.verbose
    )
    artifacts["scale_mean"] = mean
    artifacts["scale_std"] = std
    artifacts["standardized_features"] = standardized_features

    X_imputed = fill_missing_values(
        X_scaled, X_scaled, method=config.impute_method, max_iter=10, verbose=config.verbose
    )

    final_df = pd.concat([X_imputed, y_duration, y_event], axis=1)
    artifacts["feature_columns"] = list(X_imputed.columns)
    return final_df, artifacts
