# -*- coding: utf-8 -*-
"""COX 生存分析流程配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

import numpy as np


@dataclass
class CoxPipelineConfig:
    """COX 生存分析流程的配置（泛用）"""

    # ----- 数据与路径 -----
    data_path: str = ""
    result_dir: str = "cox_survival_result"
    duration_col: str = "duration"
    event_col: str = "event"

    # ----- 纵向数据专用（mode="longitudinal" 时必填） -----
    mode: str = "longitudinal"  # "longitudinal" | "single_row"
    id_col: str = "ID"
    time_col: str = "Examination Year"
    event_status_col: str = "Carotid_Status"  # 0=未发生，1=发生
    baseline_filter_col: Optional[str] = "Carotid_Status"
    baseline_filter_value: Any = 0  # 基线时需满足的条件，如“基线无斑块”

    # ----- 特征与预处理 -----
    drop_cols: List[str] = field(
        default_factory=lambda: ["ID", "Examination Year", "Weight (kg)", "Height (cm)"]
    )
    cat_features: List[str] = field(default_factory=lambda: ["Sex"])
    drop_ref_categories: List[str] = field(default_factory=lambda: ["Sex_Female"])
    exclude_from_features: List[str] = field(default_factory=lambda: ["Carotid_Status"])
    missing_threshold: float = 50.0
    impute_method: str = "mice"
    scale_on_binary: bool = False

    # ----- LASSO-Cox -----
    penalizer_grid: Optional[np.ndarray] = None
    l1_ratio: float = 1.0  # 1.0=LASSO, <1=Elastic Net
    n_folds: int = 5
    lasso_coef_threshold: float = 1e-4

    # ----- 风险分层与输出 -----
    risk_n_groups: int = 3
    risk_group_labels: Optional[List[str]] = None
    time_unit: str = "Time"  # 时间轴单位，用于 KM 图 xlabel
    km_xlabel: Optional[str] = None  # None 则用 time_unit
    km_ylabel: str = "Survival Probability"

    # ----- 可选步骤 -----
    run_univariate: bool = False
    check_ph_assumptions: bool = True
    check_ph_show_plots: bool = False  # True 时会绘制 LOWESS 图，耗时长（Bootstrapping lowess lines）
    bootstrap_c_index: bool = False
    bootstrap_n: int = 200
    save_preprocessed: bool = True
    verbose: bool = True

    def __post_init__(self) -> None:
        if self.penalizer_grid is None:
            self.penalizer_grid = np.logspace(-4, 3, 40)
        if self.risk_group_labels is None:
            self.risk_group_labels = [f"Q{i+1}" for i in range(self.risk_n_groups)]
        os.makedirs(self.result_dir, exist_ok=True)


def get_carotid_example_config(
    data_path: str = "Data/Raw/Gulou_Carotid_data_test.csv",
    result_dir: str = "carotid_hsCRP_result",
) -> CoxPipelineConfig:
    """返回针对 Gulou 颈动脉数据的示例配置，与原 cox_model_pipeline 行为对齐。"""
    return CoxPipelineConfig(
        data_path=data_path,
        result_dir=result_dir,
        mode="longitudinal",
        id_col="ID",
        time_col="Examination Year",
        event_status_col="Carotid_Status",
        baseline_filter_col="Carotid_Status",
        baseline_filter_value=0,
        drop_cols=["ID", "Examination Year", "Weight (kg)", "Height (cm)"],
        cat_features=["Sex"],
        drop_ref_categories=["Sex_Female"],
        exclude_from_features=["Carotid_Status"],
        missing_threshold=50.0,
        impute_method="mice",
        run_univariate=False,
        check_ph_assumptions=True,
        risk_n_groups=3,
        risk_group_labels=["Low", "Medium", "High"],
        verbose=True,
    )
