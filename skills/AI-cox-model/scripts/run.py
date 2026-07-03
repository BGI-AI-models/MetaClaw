# -*- coding: utf-8 -*-
"""COX 生存分析主流程编排：读取数据 → 构建生存表 → 预处理 → 单因素(可选) → LASSO-Cox → PH 检验 → 风险分层与出图。"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import pandas as pd

from .config import CoxPipelineConfig
from .lasso_cox import bootstrap_c_index_ci, get_selected_variables, run_lasso_cox_cv
from .ph_test import check_ph_assumptions
from .preprocessing import preprocess_for_cox
from .survival_data import get_baseline_and_survival
from .univariate import run_univariate_cox
from .visualization import (
    add_risk_groups,
    plot_forest,
    plot_km_stratified,
    run_logrank,
)

logger = logging.getLogger(__name__)


def run_survival_pipeline(config: CoxPipelineConfig) -> Dict[str, Any]:
    """
    执行完整 COX 生存分析流程，结果写入 config.result_dir。

    Returns
    -------
    results : dict
        包含 cox_df, final_df, lasso_cph, selected_vars, c_index, best_penalizer 等
    """
    duration_col = config.duration_col
    event_col = config.event_col
    results: Dict[str, Any] = {}

    # 1) 读取与构建生存数据
    if not config.data_path:
        raise FileNotFoundError("请提供有效 data_path: " + str(config.data_path))
    if not os.path.isfile(config.data_path):
        raise FileNotFoundError("数据文件不存在: " + str(config.data_path))
    data_df = pd.read_csv(config.data_path)

    if config.mode == "longitudinal":
        cox_df, baseline_df = get_baseline_and_survival(data_df, config)
        results["baseline_df"] = baseline_df
    else:
        if duration_col not in data_df.columns or event_col not in data_df.columns:
            raise ValueError("single_row 模式需提供 duration 与 event 列")
        drop = [c for c in config.drop_cols if c in data_df.columns]
        cox_df = data_df.drop(columns=drop, errors="ignore").copy()

    results["cox_df"] = cox_df
    n_samples = len(cox_df)
    n_events = int(cox_df[event_col].sum())
    if config.verbose:
        logger.info("Survival data shape: %s (n_events=%d)", cox_df.shape, n_events)
    if n_events < 10:
        logger.warning("事件数较少 (n_events=%d)，LASSO-Cox 结果可能不稳定，建议谨慎解读。", n_events)

    # 2) 预处理
    final_df, artifacts = preprocess_for_cox(
        cox_df, config, duration_col=duration_col, event_col=event_col
    )
    results["preprocess_artifacts"] = artifacts
    if config.save_preprocessed:
        final_df.to_csv(
            os.path.join(config.result_dir, "preprocessed_cox_data.tsv"),
            sep="\t",
            index=False,
        )

    # 3) 可选：单因素 Cox
    if config.run_univariate:
        run_univariate_cox(
            final_df,
            duration_col=duration_col,
            event_col=event_col,
            result_dir=config.result_dir,
            feature_cols=artifacts.get("feature_columns"),
        )

    # 4) LASSO-Cox
    lasso_cph, best_penalizer, cv_df = run_lasso_cox_cv(
        final_df, config, duration_col=duration_col, event_col=event_col
    )
    results["lasso_cph"] = lasso_cph
    results["best_penalizer"] = best_penalizer
    results["c_index"] = lasso_cph.concordance_index_
    c_index_ci_str = ""
    if config.bootstrap_c_index:
        _, ci_lo, ci_hi = bootstrap_c_index_ci(
            lasso_cph,
            final_df,
            duration_col=duration_col,
            event_col=event_col,
            n_bootstrap=config.bootstrap_n,
        )
        results["c_index_ci"] = (ci_lo, ci_hi)
        c_index_ci_str = f"\nC-index 95% CI (Bootstrap): [{ci_lo:.4f}, {ci_hi:.4f}]"
    with open(os.path.join(config.result_dir, "lasso_c_index.txt"), "w", encoding="utf-8") as f:
        f.write(f"C-index: {lasso_cph.concordance_index_:.4f}\n")
        f.write(f"Best penalizer: {best_penalizer}\n")
        if c_index_ci_str:
            f.write(c_index_ci_str.strip() + "\n")

    # 5) 入选变量
    selected_vars = get_selected_variables(
        lasso_cph, config.lasso_coef_threshold, config.result_dir
    )
    results["selected_vars"] = selected_vars
    if config.verbose:
        logger.info("Selected variables: %s", selected_vars.index.tolist())

    # 6) 风险评分与分层
    final_df = final_df.copy()
    final_df["risk_score"] = lasso_cph.predict_partial_hazard(final_df)
    final_df = add_risk_groups(
        final_df,
        risk_score_col="risk_score",
        n_groups=config.risk_n_groups,
        labels=config.risk_group_labels,
    )
    results["final_df"] = final_df

    # 7) PH 假定（仅传入拟合时用到的列，避免 risk_group 等 object 列导致 cast 报错）
    if config.check_ph_assumptions:
        ph_cols = [duration_col, event_col] + list(lasso_cph.summary.index)
        ph_df = final_df[[c for c in ph_cols if c in final_df.columns]].copy()
        check_ph_assumptions(
            lasso_cph,
            ph_df,
            config.result_dir,
            duration_col=duration_col,
            event_col=event_col,
            show_plots=getattr(config, "check_ph_show_plots", False),
        )

    # 8) KM、Log-rank、森林图
    km_xlabel = getattr(config, "km_xlabel", None) or getattr(config, "time_unit", "Time")
    km_ylabel = getattr(config, "km_ylabel", "Survival Probability")
    plot_km_stratified(
        final_df,
        config.result_dir,
        duration_col=duration_col,
        event_col=event_col,
        title="LASSO-Cox Risk-Stratified Survival Curves",
        xlabel=km_xlabel,
        ylabel=km_ylabel,
    )
    run_logrank(final_df, config.result_dir, duration_col=duration_col, event_col=event_col)
    plot_forest(selected_vars, config.result_dir, title="LASSO-Cox Selected Variables")

    # 9) 风险分层统计
    risk_stats = (
        final_df.groupby("risk_group", observed=True)[event_col].agg(["count", "sum", "mean"])
    )
    risk_stats.to_csv(
        os.path.join(config.result_dir, "risk_group_summary.tsv"),
        sep="\t",
    )

    # 10) 保存配置摘要
    config_summary = {
        "data_path": config.data_path,
        "result_dir": config.result_dir,
        "mode": config.mode,
        "duration_col": duration_col,
        "event_col": event_col,
        "n_samples": len(final_df),
        "n_events": int(final_df[event_col].sum()),
        "c_index": float(lasso_cph.concordance_index_),
        "best_penalizer": float(best_penalizer),
        "n_selected_vars": len(selected_vars),
    }
    with open(
        os.path.join(config.result_dir, "pipeline_config_summary.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(config_summary, f, indent=2, ensure_ascii=False)

    if config.verbose:
        logger.info("Pipeline finished. Results in: %s", config.result_dir)
    return results
