# -*- coding: utf-8 -*-
"""单因素 Cox 回归。"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

import numpy as np
import pandas as pd

from lifelines import CoxPHFitter

logger = logging.getLogger(__name__)


def run_univariate_cox(
    final_df: pd.DataFrame,
    duration_col: str,
    event_col: str,
    result_dir: str,
    feature_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """对每个特征单独拟合 Cox，输出 HR、CI、p；结果保存到 result_dir。"""
    if feature_cols is None:
        feature_cols = [
            c for c in final_df.columns if c not in (duration_col, event_col)
        ]
    uni_results = []
    for col in feature_cols:
        use = final_df[[col, duration_col, event_col]].dropna()
        if use.shape[0] < 10 or use[event_col].sum() < 2:
            continue
        try:
            cph = CoxPHFitter()
            cph.fit(use, duration_col=duration_col, event_col=event_col)
            s = cph.summary
            uni_results.append({
                "variable": col,
                "coef": s.loc[col, "coef"],
                "HR": np.exp(s.loc[col, "coef"]),
                "CI_lower": np.exp(s.loc[col, "coef lower 95%"]),
                "CI_upper": np.exp(s.loc[col, "coef upper 95%"]),
                "p": s.loc[col, "p"],
            })
        except Exception as e:
            args = getattr(e, "args", None)
            if isinstance(args, tuple) and args:
                logger.warning("Univariate Cox failed for %s: %s", col, args[0])
    if not uni_results:
        return pd.DataFrame()
    out_df = pd.DataFrame(uni_results)
    out_path = os.path.join(result_dir, "univariate_cox_results.tsv")
    out_df.to_csv(out_path, sep="\t", index=False)
    return out_df
