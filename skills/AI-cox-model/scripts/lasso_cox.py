# -*- coding: utf-8 -*-
"""LASSO-Cox 与 Elastic Net：交叉验证选 penalizer、拟合、入选变量、Bootstrap C-index。"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from lifelines import CoxPHFitter
from lifelines.utils import k_fold_cross_validation

from .config import CoxPipelineConfig


def run_lasso_cox_cv(
    final_df: pd.DataFrame,
    config: CoxPipelineConfig,
    duration_col: str = "duration",
    event_col: str = "event",
) -> Tuple[CoxPHFitter, float, pd.DataFrame]:
    """交叉验证选最优 penalizer，拟合最终 LASSO-Cox，返回 (fitter, best_penalizer, cv_results_df)。"""
    penalizer_grid = config.penalizer_grid
    cv_scores = []
    for pen in penalizer_grid:
        cph = CoxPHFitter(penalizer=pen, l1_ratio=config.l1_ratio)
        scores = k_fold_cross_validation(
            cph,
            final_df,
            duration_col=duration_col,
            event_col=event_col,
            k=config.n_folds,
            scoring_method="concordance_index",
        )
        cv_scores.append(np.mean(scores))
    cv_df = pd.DataFrame({
        "penalizer": penalizer_grid,
        "cv_c_index": cv_scores,
    })
    best_penalizer = float(penalizer_grid[np.argmax(cv_scores)])
    cv_path = os.path.join(config.result_dir, "lasso_cv_results.tsv")
    cv_df.to_csv(cv_path, sep="\t", index=False)

    lasso_cph = CoxPHFitter(penalizer=best_penalizer, l1_ratio=config.l1_ratio)
    lasso_cph.fit(final_df, duration_col=duration_col, event_col=event_col)
    return lasso_cph, best_penalizer, cv_df


def get_selected_variables(
    cph: CoxPHFitter,
    threshold: float,
    result_dir: str,
) -> pd.DataFrame:
    """从 LASSO 结果中取系数绝对值 > threshold 的变量，并计算 HR、CI，保存 TSV。"""
    s = cph.summary.copy()
    s["HR"] = np.exp(s["coef"])
    s["CI_lower"] = np.exp(s["coef lower 95%"])
    s["CI_upper"] = np.exp(s["coef upper 95%"])
    selected = s[s["coef"].abs() > threshold]
    out_path = os.path.join(result_dir, "lasso_selected_variables.tsv")
    selected.to_csv(out_path, sep="\t")
    return selected


def bootstrap_c_index_ci(
    cph: CoxPHFitter,
    final_df: pd.DataFrame,
    duration_col: str,
    event_col: str,
    n_bootstrap: int = 200,
    random_state: Optional[int] = None,
) -> Tuple[float, float, float]:
    """Bootstrap 估计 C-index 的 95% 置信区间，返回 (c_index, ci_lower, ci_upper)。"""
    rng = np.random.default_rng(random_state)
    n = len(final_df)
    c_indices = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        sample = final_df.iloc[idx]
        try:
            cph_b = CoxPHFitter(penalizer=cph.penalizer, l1_ratio=cph.l1_ratio)
            cph_b.fit(sample, duration_col=duration_col, event_col=event_col)
            c_indices.append(cph_b.concordance_index_)
        except Exception:
            continue
    if not c_indices:
        return float(cph.concordance_index_), np.nan, np.nan
    c_indices = np.array(c_indices)
    return (
        float(cph.concordance_index_),
        float(np.percentile(c_indices, 2.5)),
        float(np.percentile(c_indices, 97.5)),
    )
