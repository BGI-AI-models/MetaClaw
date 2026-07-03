# -*- coding: utf-8 -*-
"""从纵向数据构建生存数据（duration / event）。"""

from __future__ import annotations

from typing import Any, Tuple

import pandas as pd

from .config import CoxPipelineConfig


def build_survival_from_longitudinal(
    data_df: pd.DataFrame,
    id_col: str,
    time_col: str,
    event_status_col: str,
    event_positive_value: Any = 1,
) -> pd.DataFrame:
    """
    从纵向数据构建生存数据：每人一行，duration = 到事件或删失的时间，event = 是否发生事件。

    Parameters
    ----------
    data_df : pd.DataFrame
        按 id_col 分组、每组按 time_col 排序的纵向数据
    id_col : str
        个体 ID 列名
    time_col : str
        时间/访视列名（数值型，如年份）
    event_status_col : str
        事件状态列名（如 0=未发生，1=发生）
    event_positive_value : Any
        表示“发生事件”的值

    Returns
    -------
    survival_df : pd.DataFrame
        列至少包含 id_col, duration, event
    """
    data_df = data_df.sort_values([id_col, time_col])

    def _build_one(group: pd.DataFrame) -> pd.Series:
        group = group.sort_values(time_col)
        t0 = group[time_col].iloc[0]
        event_rows = group[group[event_status_col] == event_positive_value]
        if not event_rows.empty:
            t_event = event_rows[time_col].iloc[0]
            duration = t_event - t0
            event = 1
        else:
            t_last = group[time_col].iloc[-1]
            duration = t_last - t0
            event = 0
        return pd.Series({"duration": duration, "event": event})

    g = data_df.groupby(id_col, group_keys=False)
    try:
        survival_df = g.apply(_build_one, include_groups=False).reset_index()
    except TypeError:
        # pandas < 2.2 无 include_groups 参数
        survival_df = g.apply(_build_one).reset_index()
    return survival_df


def get_baseline_and_survival(
    data_df: pd.DataFrame,
    config: CoxPipelineConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    纵向模式下：筛选基线人群、构建生存数据、合并基线协变量。
    返回 (cox_df, baseline_df)，其中 cox_df 含 duration, event 及基线特征。
    """
    data_df = data_df.sort_values([config.id_col, config.time_col])
    baseline = data_df.groupby(config.id_col).first().reset_index()

    if config.baseline_filter_col is not None:
        baseline = baseline[
            baseline[config.baseline_filter_col] == config.baseline_filter_value
        ].copy()
        valid_ids = baseline[config.id_col]
        long_df = data_df[data_df[config.id_col].isin(valid_ids)].copy()
    else:
        long_df = data_df.copy()

    survival_df = build_survival_from_longitudinal(
        long_df,
        id_col=config.id_col,
        time_col=config.time_col,
        event_status_col=config.event_status_col,
        event_positive_value=1,
    )

    cox_df = pd.merge(
        survival_df,
        baseline,
        on=config.id_col,
        how="left",
    )

    drop = [config.id_col, config.time_col] + [
        c
        for c in config.drop_cols
        if c in cox_df.columns and c != config.id_col and c != config.time_col
    ]
    cox_df = cox_df.drop(columns=drop, errors="ignore")
    return cox_df, baseline
