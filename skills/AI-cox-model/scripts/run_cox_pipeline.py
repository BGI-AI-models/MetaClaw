#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main orchestrator for Cox survival analysis skill.

This script coordinates:
1. Dependency installation
2. Configuration setup/validation
3. Data validation
4. Cox pipeline execution (using AI_toolbox)
5. PDF report generation
6. Results summary and recommendations
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

# Add skill scripts to path
SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from install_dependencies import check_and_install_packages
from config_manager import (
    create_default_config,
    load_config,
    save_config,
    print_config_summary,
)
from data_validator import (
    validate_data_exists,
    validate_data_loads,
    validate_config_against_data,
    print_validation_summary,
)
from generate_pdf_report import create_pdf_report


def run_cox_analysis(
    data_path: str,
    mode: str = "longitudinal",
    config_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    skip_install: bool = False,
) -> Dict[str, Any]:
    """
    Run complete Cox survival analysis pipeline.

    Parameters
    ----------
    data_path : str
        Path to CSV/TSV data file
    mode : str
        "longitudinal" or "single_row"
    config_path : str, optional
        Path to existing YAML config. If None, creates default config.
    output_dir : str, optional
        Output directory. If None, uses "cox_survival_results"
    skip_install : bool
        Skip dependency installation?

    Returns
    -------
    results : dict
        Results dictionary containing analysis outputs
    """

    print("\n" + "=" * 70)
    print("COX SURVIVAL ANALYSIS PIPELINE")
    print("=" * 70)

    # Step 1: Install dependencies
    if not skip_install:
        print("\n[1/5] Checking dependencies...")
        if not check_and_install_packages():
            print("ERROR: Failed to install dependencies")
            return {}

    # Step 2: Setup configuration
    print("\n[2/5] Setting up configuration...")

    # Import the Cox module from AI_toolbox
    try:
        from AI_toolbox.Modelling.cox_model import (
            CoxPipelineConfig,
            run_survival_pipeline,
        )
    except ImportError as e:
        print(f"ERROR: Could not import Cox model from AI_toolbox: {e}")
        print("Please ensure AI_toolbox is installed and in PYTHONPATH")
        return {}

    # Load or create config
    if config_path and os.path.exists(config_path):
        config_dict = load_config(config_path)
        print(f"✓ Loaded config from: {config_path}")
    else:
        config_dict = create_default_config(
            data_path=data_path,
            mode=mode,
            output_file=None,
        )
        config_path = os.path.join(output_dir or "cox_survival_results", "config.yaml")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        save_config(config_dict, config_path)
        print(f"✓ Created default config: {config_path}")

    # Update output directory
    if output_dir:
        config_dict["result_dir"] = output_dir
    os.makedirs(config_dict["result_dir"], exist_ok=True)

    print_config_summary(config_dict)

    # Step 3: Validate data
    print("[3/5] Validating data...")
    try:
        validate_data_exists(data_path)
        df = validate_data_loads(data_path)
        validate_config_against_data(config_dict, df)
        print_validation_summary(df, config_dict)
        print("✓ Data validation passed")
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        return {}

    # Step 4: Run Cox pipeline
    print("[4/5] Running Cox survival analysis...")
    try:
        # Convert config dict to CoxPipelineConfig
        cox_config = CoxPipelineConfig(**config_dict)

        # Run pipeline
        results = run_survival_pipeline(cox_config)
        print("✓ Cox pipeline completed successfully")
    except Exception as e:
        print(f"ERROR in Cox pipeline: {e}")
        import traceback
        traceback.print_exc()
        return {}

    # Step 5: Generate PDF report
    print("[5/5] Generating PDF report...")
    try:
        pdf_path = create_pdf_report(
            config_dict["result_dir"],
            config_dict,
            results,
            output_filename="survival_analysis_report.pdf",
        )
        print(f"✓ PDF report saved: {pdf_path}")
    except Exception as e:
        print(f"WARNING: Could not generate PDF report: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"\nResults saved to: {config_dict['result_dir']}")
    print("\nOutput files:")
    print("  📊 Plots:")
    print("     - km_risk_stratified.png (Kaplan-Meier curves)")
    print("     - forest_plot.png (Variable effects)")
    print("  📈 Statistical Results (CSV):")
    print("     - lasso_selected_variables.tsv (Selected predictors)")
    print("     - lasso_cv_results.tsv (Cross-validation performance)")
    print("     - risk_group_summary.tsv (Risk group statistics)")
    if config_dict.get("check_ph_assumptions"):
        print("     - ph_test_results.tsv (PH assumption test)")
    if config_dict.get("run_univariate"):
        print("     - univariate_cox_results.tsv (Univariate analysis)")
    print("  📄 Report:")
    print("     - survival_analysis_report.pdf (Summary report)")
    print("  ⚙️  Configuration:")
    print("     - config.yaml (Analysis settings)")
    print("     - pipeline_config_summary.json (Run metadata)")

    # Provide recommendations
    print("\n" + "=" * 70)
    print("NEXT STEPS & RECOMMENDATIONS")
    print("=" * 70)

    c_index = results.get("c_index", 0)
    selected_vars = results.get("selected_vars")

    recommendations = []

    # C-index-based recommendations
    if c_index < 0.6:
        recommendations.append(
            "⚠ Model discrimination is weak (C-index < 0.6). Consider:\n"
            "   - Adding more clinical features\n"
            "   - Checking data quality and outliers\n"
            "   - Consulting a biostatistician"
        )
    elif c_index < 0.7:
        recommendations.append(
            "📌 Model shows moderate discrimination. You may want to:\n"
            "   - Run univariate analysis to identify strong individual predictors\n"
            "   - Try Elastic Net (less aggressive) for different variable selection"
        )
    else:
        recommendations.append(
            "✓ Model shows good to excellent discrimination. Results are promising!"
        )

    # Variable selection recommendations
    if selected_vars is not None:
        if len(selected_vars) == 0:
            recommendations.append(
                "📌 LASSO selected no variables (very conservative). Consider:\n"
                "   - Reducing the lasso_coef_threshold for less aggressive selection\n"
                "   - Running univariate analysis to identify candidates"
            )
        elif len(selected_vars) > 10:
            recommendations.append(
                "📌 Many variables selected. Consider:\n"
                "   - Running univariate to focus on strongest predictors\n"
                "   - Using Elastic Net for a balance between sparsity and flexibility"
            )

    # PH assumption recommendations
    ph_results_path = os.path.join(config_dict["result_dir"], "ph_test_results.tsv")
    if os.path.exists(ph_results_path):
        recommendations.append(
            "📌 Proportional hazards assumption was tested.\n"
            "   Review ph_test_results.tsv for details. Significant violations (p<0.05)\n"
            "   may indicate time-varying effects in your data."
        )

    # Sample size recommendations
    n_samples = len(results.get("final_df", []))
    n_events = int(results.get("final_df", {}).get("event", []).sum()) if "final_df" in results else 0
    if n_events < 20:
        recommendations.append(
            f"⚠ Limited events ({n_events}). Models may be unstable.\n"
            "   Consider external validation or consultation with a statistician."
        )

    for rec in recommendations:
        print(f"\n{rec}")

    print("\n" + "=" * 70 + "\n")

    return results


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Cox Proportional Hazards Survival Analysis"
    )
    parser.add_argument("data_path", help="Path to CSV/TSV data file")
    parser.add_argument(
        "--mode",
        choices=["longitudinal", "single_row"],
        default="longitudinal",
        help="Data format (default: longitudinal)",
    )
    parser.add_argument(
        "--config",
        help="Path to existing YAML config (optional)",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory (default: cox_survival_results)",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip dependency installation",
    )

    args = parser.parse_args()

    results = run_cox_analysis(
        data_path=args.data_path,
        mode=args.mode,
        config_path=args.config,
        output_dir=args.output_dir,
        skip_install=args.skip_install,
    )

    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
