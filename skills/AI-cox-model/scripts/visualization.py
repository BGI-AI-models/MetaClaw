# -*- coding: utf-8 -*-
"""风险分层、KM 曲线、Log-rank 检验、森林图。"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test


def add_risk_groups(
    final_df: pd.DataFrame,
    risk_score_col: str = "risk_score",
    n_groups: int = 3,
    labels: Optional[List[str]] = None,
) -> pd.DataFrame:
    """按风险评分分位数分组，添加 risk_group 列。"""
    if labels is None:
        labels = [f"Q{i+1}" for i in range(n_groups)]
    final_df = final_df.copy()
    final_df["risk_group"] = pd.qcut(
        final_df[risk_score_col],
        q=n_groups,
        labels=labels,
        duplicates="drop",
    )
    return final_df


def plot_km_stratified(
    final_df: pd.DataFrame,
    result_dir: str,
    duration_col: str = "duration",
    event_col: str = "event",
    risk_group_col: str = "risk_group",
    title: str = "Risk-Stratified Survival Curves",
    xlabel: str = "Time",
    ylabel: str = "Survival Probability",
    figsize: Tuple[int, int] = (8, 6),
) -> None:
    """绘制分层 KM 曲线。"""
    kmf = KaplanMeierFitter()
    fig, ax = plt.subplots(figsize=figsize)
    groups = final_df[risk_group_col].dropna().unique()
    for g in sorted(groups, key=str):
        mask = final_df[risk_group_col] == g
        kmf.fit(
            final_df.loc[mask, duration_col],
            final_df.loc[mask, event_col],
            label=str(g),
        )
        kmf.plot_survival_function(ax=ax)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(result_dir, "km_risk_stratified.png"), dpi=300)
    plt.close()


def run_logrank(
    final_df: pd.DataFrame,
    result_dir: str,
    duration_col: str = "duration",
    event_col: str = "event",
    risk_group_col: str = "risk_group",
    compare_groups: Optional[Tuple[str, str]] = None,
) -> Optional[float]:
    """Log-rank 检验（默认比较最低组 vs 最高组），保存 p 值。"""
    groups = final_df[risk_group_col].dropna().unique()
    if len(groups) < 2:
        return None
    sorted_groups = sorted(groups, key=str)
    low_label = compare_groups[0] if compare_groups else sorted_groups[0]
    high_label = compare_groups[1] if compare_groups else sorted_groups[-1]
    low = final_df[final_df[risk_group_col] == low_label]
    high = final_df[final_df[risk_group_col] == high_label]
    res = logrank_test(
        low[duration_col],
        high[duration_col],
        event_observed_A=low[event_col],
        event_observed_B=high[event_col],
    )
    out_path = os.path.join(result_dir, "logrank_test.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"Log-rank p-value ({high_label} vs {low_label}): {res.p_value:.6f}\n")
    return res.p_value


def plot_forest(
    selected_vars: pd.DataFrame,
    result_dir: str,
    title: str = "Cox Selected Variables (HR with 95% CI)",
    figsize: Optional[Tuple[int, int]] = None,
) -> None:
    """森林图：仅对 selected_vars（含 HR, CI_lower, CI_upper 的 DataFrame）。"""
    if selected_vars is None or len(selected_vars) == 0:
        return
    if figsize is None:
        figsize = (8, max(4, len(selected_vars) * 0.5))
    fig, ax = plt.subplots(figsize=figsize)
    y_pos = np.arange(len(selected_vars))
    ax.errorbar(
        selected_vars["HR"],
        y_pos,
        xerr=[
            selected_vars["HR"] - selected_vars["CI_lower"],
            selected_vars["CI_upper"] - selected_vars["HR"],
        ],
        fmt="o",
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(selected_vars.index)
    ax.axvline(x=1, linestyle="--", color="gray")
    ax.set_xlabel("Hazard Ratio (95% CI)")
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(os.path.join(result_dir, "forest_plot.png"), dpi=300)
    plt.close()
