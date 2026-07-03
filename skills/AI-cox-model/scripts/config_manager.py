#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manage Cox survival analysis configuration files (YAML)."""

import os
import yaml
from typing import Any, Dict, Optional


DEFAULT_CONFIG_TEMPLATE = {
    "data_path": "",
    "result_dir": "cox_survival_results",
    "mode": "longitudinal",  # or "single_row"
    "id_col": "ID",
    "time_col": "Examination Year",
    "event_status_col": "Event_Status",
    "baseline_filter_col": "Event_Status",
    "baseline_filter_value": 0,
    "duration_col": "duration",
    "event_col": "event",
    "drop_cols": ["ID", "Examination Year"],
    "exclude_from_features": [],
    "cat_features": ["Sex"],
    "drop_ref_categories": ["Sex_Female"],
    "missing_threshold": 50.0,
    "impute_method": "mice",
    "scale_on_binary": False,
    "penalizer_grid": None,
    "l1_ratio": 1.0,
    "n_folds": 5,
    "lasso_coef_threshold": 0.0001,
    "risk_n_groups": 3,
    "risk_group_labels": ["Low", "Medium", "High"],
    "time_unit": "Years",
    "km_ylabel": "Survival Probability",
    "run_univariate": False,
    "check_ph_assumptions": True,
    "check_ph_show_plots": False,
    "bootstrap_c_index": False,
    "bootstrap_n": 200,
    "save_preprocessed": True,
    "verbose": True,
}


def create_default_config(
    data_path: str,
    mode: str = "longitudinal",
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a default config dictionary.

    Parameters
    ----------
    data_path : str
        Path to input data (CSV/TSV)
    mode : str
        "longitudinal" or "single_row"
    output_file : str, optional
        If provided, save config to this YAML file

    Returns
    -------
    config : dict
        Configuration dictionary
    """
    config = DEFAULT_CONFIG_TEMPLATE.copy()
    config["data_path"] = data_path
    config["mode"] = mode

    if output_file:
        save_config(config, output_file)
        print(f"✓ Configuration saved to: {output_file}")

    return config


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config


def save_config(config: Dict[str, Any], output_path: str) -> None:
    """Save configuration to YAML file."""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def print_config_summary(config: Dict[str, Any]) -> None:
    """Print a human-readable config summary."""
    print("\n" + "=" * 70)
    print("CONFIGURATION SUMMARY")
    print("=" * 70)

    sections = {
        "Data Setup": [
            "data_path",
            "result_dir",
            "mode",
        ],
        "Column Mapping": [
            "duration_col",
            "event_col",
            "id_col",
            "time_col",
            "event_status_col",
        ],
        "Feature Selection": [
            "drop_cols",
            "exclude_from_features",
            "cat_features",
            "drop_ref_categories",
            "missing_threshold",
        ],
        "Preprocessing": [
            "impute_method",
            "scale_on_binary",
        ],
        "LASSO-Cox Model": [
            "l1_ratio",
            "n_folds",
            "lasso_coef_threshold",
        ],
        "Risk Stratification": [
            "risk_n_groups",
            "risk_group_labels",
            "time_unit",
        ],
        "Optional Analysis": [
            "run_univariate",
            "check_ph_assumptions",
            "bootstrap_c_index",
            "save_preprocessed",
        ],
    }

    for section, keys in sections.items():
        print(f"\n[{section}]")
        for key in keys:
            if key in config:
                value = config[key]
                if isinstance(value, list):
                    value_str = (
                        f"[{', '.join(str(v) for v in value)}]"
                        if len(value) <= 3
                        else f"[{len(value)} items]"
                    )
                else:
                    value_str = str(value)
                print(f"  {key}: {value_str}")

    print("\n" + "=" * 70 + "\n")


def update_config_field(
    config: Dict[str, Any], field: str, value: Any
) -> Dict[str, Any]:
    """
    Update a single field in config.

    Parameters
    ----------
    config : dict
        Configuration dictionary
    field : str
        Field name to update
    value : Any
        New value

    Returns
    -------
    config : dict
        Updated configuration
    """
    if field not in config:
        print(f"Warning: '{field}' is not a recognized config field.")
    config[field] = value
    return config


def get_config_field_info(field: str) -> str:
    """Get human-readable info about a config field."""
    field_descriptions = {
        "data_path": "Path to your CSV/TSV data file",
        "result_dir": "Output folder for all results",
        "mode": "Data format: 'longitudinal' (repeated visits) or 'single_row' (one row per patient)",
        "duration_col": "Column name for time-to-event (days, years, etc.)",
        "event_col": "Column name for event indicator (0=censored, 1=event occurred)",
        "id_col": "Column name for patient ID (longitudinal data only)",
        "time_col": "Column name for visit date/year (longitudinal data only)",
        "event_status_col": "Column with event status per visit (longitudinal data only)",
        "cat_features": "List of categorical columns to one-hot encode",
        "drop_cols": "Columns to exclude from analysis (e.g., identifiers)",
        "drop_ref_categories": "Reference categories to drop (avoids collinearity)",
        "missing_threshold": "Remove features with >X% missing values",
        "impute_method": "'mice' (recommended) or 'mean' for missing values",
        "l1_ratio": "1.0=LASSO (aggressive), <1=Elastic Net (less aggressive)",
        "n_folds": "Number of cross-validation folds (5-10 typical)",
        "risk_n_groups": "Number of risk groups (2-4 typical)",
        "run_univariate": "Also run single-factor Cox analysis? (true/false)",
        "check_ph_assumptions": "Test proportional hazards assumption? (true/false)",
        "bootstrap_c_index": "Compute bootstrap CI for model performance? (true/false)",
    }

    return field_descriptions.get(
        field, "No description available. See SKILL.md for details."
    )
