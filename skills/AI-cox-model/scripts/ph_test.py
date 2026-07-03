# -*- coding: utf-8 -*-
"""比例风险（PH）假定检验（Schoenfeld 残差）。"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import pandas as pd

from lifelines import CoxPHFitter

logger = logging.getLogger(__name__)


def check_ph_assumptions(
    cph: CoxPHFitter,
    final_df: pd.DataFrame,
    result_dir: str,
    duration_col: str = "duration",
    event_col: str = "event",
    show_plots: bool = False,
) -> Optional[Dict[str, Any]]:
    """运行 lifelines 的 PH 假定检验（Schoenfeld 残差），并保存检验结果表。
    show_plots=True 时会绘制 LOWESS 诊断图，计算较慢（Bootstrapping lowess lines），默认关闭。
    """
    try:
        from lifelines.statistics import proportional_hazard_test

        res = proportional_hazard_test(
            cph, final_df, time_transform="rank"
        )
        out_path = os.path.join(result_dir, "ph_test_results.tsv")
        res.summary.to_csv(out_path, sep="\t")
        try:
            cph.check_assumptions(
                final_df, p_value_threshold=0.05, show_plots=show_plots
            )
        except Exception as e:
            logger.info("check_assumptions reported: %s", e)
        return res.summary.to_dict()
    except Exception as e:
        logger.warning("PH assumption check failed: %s", e)
        return None
