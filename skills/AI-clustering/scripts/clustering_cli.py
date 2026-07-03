#!/usr/bin/env python
"""CLI for the clustering pipeline."""

import typer
import yaml
import pandas as pd
from pathlib import Path
import importlib.resources
import re
from typing import Any, Dict, List, Optional
import joblib
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from scipy.stats import chi2_contingency, fisher_exact
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
import seaborn as sns
import matplotlib.gridspec as gridspec
import warnings

warnings.filterwarnings('ignore')

from AI_toolbox.Modelling.Clustering.clustering import ClusteringModel
from AI_toolbox.Preprocessing.Imputation import fill_missing_values
from AI_toolbox.Preprocessing.Scaling import standardize
from AI_toolbox.Preprocessing.Encoding import onehot_encoding
from AI_toolbox.Preprocessing.Feature_selection import (
    remove_zero_variance_features,
    remove_high_missing_features
)

# Get default config path
try:
    default_config_path = str(importlib.resources.files("AI_toolbox.config") / "clustering_config.yaml")
except (AttributeError, FileNotFoundError, ModuleNotFoundError):
    default_config_path = "AI_toolbox/config/clustering_config.yaml"

app = typer.Typer()

def load_yaml(path: str) -> dict:
    """Load YAML configuration file."""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_yaml_snapshot(cfg: dict, out_dir: Path, name: str = "used_config.yaml") -> Path:
    """Save configuration snapshot for reproducibility."""
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / name
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
    return p

def get_preprocessing_cfg(config: dict) -> dict:
    """Get preprocessing configuration section."""
    return config.get("preprocessing", {})

def get_training_cfg(config: dict) -> dict:
    """Get training configuration section."""
    return config.get("training", {})

def get_apply_cfg(config: dict) -> dict:
    """Get apply configuration section."""
    return config.get("apply", {})

def load_data(config: dict, scope: str = "preprocessing") -> pd.DataFrame:
    """Load data from CSV/TSV file based on configuration."""
    if scope == "preprocessing":
        cfg = get_preprocessing_cfg(config).get("input", {})
    elif scope == "training":
        cfg = get_training_cfg(config).get("input", {}).get("processed", {})
        # Also fetch index_col and drop_cols from the training root level if not in processed
        training_root = get_training_cfg(config)
        if cfg.get('index_col') is None:
            cfg['index_col'] = training_root.get('index_col')
        if not cfg.get('drop_cols'):
            cfg['drop_cols'] = training_root.get('drop_cols', [])
    elif scope == "apply":
        cfg = get_apply_cfg(config).get("input", {})
    
    path = cfg.get('path')
    delimiter = cfg.get('delimiter', '\t')
    index_col = cfg.get('index_col')
    drop_cols = cfg.get('drop_cols', [])
    
    # Load data
    df = pd.read_csv(path, sep=delimiter)
    
    # Set index if specified
    if index_col and index_col in df.columns:
        df.set_index(index_col, inplace=True)
    
    print(f"Index column: {index_col}")
    # Drop the index before passing to model
    df = df.drop(columns=index_col, errors='ignore')
    
    # Drop additional columns if specified
    if drop_cols:
        df = df.drop(columns=drop_cols, errors='ignore')
        print(f"Dropped columns: {drop_cols}")
    
    return df

def save_table(df: pd.DataFrame, path: Path, fmt: str = "tsv") -> Path:
    """Save dataframe in the requested format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt.lower()
    if fmt == "csv":
        df.to_csv(path, index=True)
    elif fmt == "parquet":
        df.to_parquet(path, index=True)
    else:
        df.to_csv(path, sep="\t", index=True, na_rep="NA")
    return path

def save_model(model: Any, config: dict, model_name: str, feature_columns: List[str]) -> Path:
    """Save trained clustering model with metadata."""
    training_cfg = get_training_cfg(config)
    out_dir = Path(training_cfg.get("output", {}).get("directory", "Clustering-result/model"))
    out_dir.mkdir(parents=True, exist_ok=True)
    
    model_path = out_dir / f"{model_name}.joblib"
    
    # Create model package with metadata
    model_pkg = {
        "model": model,
        "model_name": model_name,
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "feature_columns": feature_columns,
        "n_clusters": model.n_clusters_,
        "config": config
    }
    
    joblib.dump(model_pkg, model_path)
    return model_path

def load_model(model_path: str) -> Dict[str, Any]:
    """Load a trained clustering model."""
    return joblib.load(model_path)

def preprocess_data(df: pd.DataFrame, config: dict) -> tuple:
    """Preprocess data according to configuration."""
    pre_cfg = get_preprocessing_cfg(config)
    features_cfg = pre_cfg.get("features", {})
    cat_features = features_cfg.get('categorical', [])
    impute_method = pre_cfg.get("imputation_method", "mean")
    remove_zero_var = pre_cfg.get("remove_zero_variance", True)
    missing_threshold = pre_cfg.get("missing_threshold", 50.0)
    standardize_numeric = pre_cfg.get("standardize", True)
    standardize_binary = pre_cfg.get("standardize_binary", False)
    
    verbose = pre_cfg.get("logging", {}).get("verbose", True)
    
    # One-hot encode categorical features
    if cat_features:
        if verbose:
            print(f"  One-hot encoding {len(cat_features)} categorical features...")
        df, categories = onehot_encoding(df, cat_features=cat_features, verbose=verbose)
    else:
        categories = None
    
    # Remove zero variance features
    if remove_zero_var:
        if verbose:
            print("  Removing zero variance features...")
        df, zero_var = remove_zero_variance_features(df, verbose=verbose)
    
    # Remove high missing features
    if verbose:
        print(f"  Removing features with > {missing_threshold}% missing values...")
    df, high_miss = remove_high_missing_features(df, missing_threshold=missing_threshold, verbose=verbose)
    
    # Standardize numeric features
    if standardize_numeric:
        if verbose:
            print("  Standardizing numeric features...")
        df, df_mean, df_std, num_features = standardize(df, on_binary=standardize_binary, verbose=verbose)
    else:
        df_mean = df_std = num_features = None
    
    # Impute missing values
    if verbose:
        print(f"  Imputing missing values using {impute_method} method...")
    df = fill_missing_values(df, df, method=impute_method, verbose=verbose)
    
    return df, {
        "categories": categories,
        "zero_var": zero_var if remove_zero_var else [],
        "high_miss": high_miss,
        "mean": df_mean,
        "std": df_std,
        "num_features": num_features
    }

@app.command()
def preprocess(
    config: str = typer.Option(default_config_path, "-c", "--config", help="Config file path")
):
    """Preprocess data for clustering."""
    cfg = load_yaml(config)
    pre_cfg = get_preprocessing_cfg(cfg)
    
    verbose = pre_cfg.get("logging", {}).get("verbose", True)
    if verbose:
        print("\n Clustering Preprocessing Pipeline")
    
    # Load raw data
    if verbose:
        print("Loading raw data...")
    df = load_data(cfg, scope="preprocessing")
    
    if verbose:
        print(f"Initial data shape: {df.shape}")
    
    # Preprocess data
    processed_df, artifact = preprocess_data(df, cfg)
    
    # Save preprocessed data
    output_cfg = pre_cfg.get("output", {})
    save_output = output_cfg.get("save", True)
    
    if save_output:
        output_dir = Path(output_cfg.get("directory", "Data/Processed"))
        fmt = output_cfg.get("format", "tsv")
        
        # Save preprocessed data
        output_path = output_dir / f"full_preprocessed.{fmt}"
        save_table(processed_df, output_path, fmt)
        
        if verbose:
            print(f"✅ Saved preprocessed data to {output_path} (shape: {processed_df.shape})")
        
        # Save preprocessing artifact
        if output_cfg.get("save_preprocess_artifact", True):
            artifact_path = output_dir / f"{output_cfg.get('preprocess_artifact_name', 'preprocess_artifact')}.joblib"
            joblib.dump(artifact, artifact_path)
            if verbose:
                print(f"✅ Saved preprocessing artifact to {artifact_path}")
    
    # Save config snapshot
    if output_cfg.get("save_config_snapshot", True) and save_output:
        save_yaml_snapshot(cfg, output_dir, "preprocess_config_used.yaml")
        if verbose:
            print(f"✅ Saved configuration snapshot")
    
    if verbose:
        print("✨ Preprocessing completed!")

@app.command()
def train(
    config: str = typer.Option(default_config_path, "-c", "--config", help="Config file path")
):
    """Train clustering models."""
    cfg = load_yaml(config)
    training_cfg = get_training_cfg(cfg)
    
    verbose = training_cfg.get("logging", {}).get("verbose", True)
    if verbose:
        print("\n🧠 Clustering Training Pipeline")
    
    # Load preprocessed data
    if verbose:
        print("Loading preprocessed data...")
    df = load_data(cfg, scope="training")
    
    if verbose:
        print(f"Preprocessed data shape: {df.shape}")
    
    # Get feature names prior convertion to numpy array
    feature_columns = df.columns.tolist()
    
    # Extract features (no target in clustering)
    X = df.values
    
    # Standardize data (if not already done in preprocessing)
    if not training_cfg.get("already_standardized", True):
        X = StandardScaler().fit_transform(X)
    
    # Get models to train
    models = training_cfg.get("models", ["kmeans"])
    if not models:
        raise typer.BadParameter("training.models cannot be empty")
    
    # Get operations
    operations = training_cfg.get("operations", ["fit"])
    if isinstance(operations, str):
        operations = [operations]
    
    # Train models
    for model_name in models:
        if verbose:
            print(f"\nTraining {model_name.upper()} model...")
        
        # Get model parameters
        model_params = training_cfg.get("model_params", {}).get(model_name, {})
        
        # Create clustering model
        clusterer = ClusteringModel(algorithm=model_name, **model_params)
        
        # Fit the model
        clusterer.fit(X)
        
        # Save the model
        if "fit" in operations:
            model_path = save_model(clusterer, cfg, model_name, feature_columns)
            if verbose:
                print(f"✅ Saved {model_name} model to {model_path}")
                print(f"   Found {clusterer.n_clusters_} clusters")
        
        # Hyperparameter tuning
        if "tune" in operations:
            if verbose:
                print(f"  Tuning {model_name} hyperparameters...")
            
            # Get tuning parameters
            tune_params = training_cfg.get("tune_params", {}).get(model_name, {})
            
            # Perform tuning
            with typer.progressbar(length=1, label=f"Tuning {model_name}") as progress:
                tuning_results = clusterer.tune_parameters(X, **tune_params)
                progress.update(1)
            
            # Update model with best parameters
            if tuning_results.get("best_params"):
                if verbose:
                    print(f"  Best parameters for {model_name}: {tuning_results['best_params']}")
                    print(f"  Best score: {tuning_results['best_score']:.4f}")
                
                # Retrain with best parameters
                best_params = tuning_results["best_params"].copy()
                # Remove n_neighbors if it's None (for SpectralClustering)
                if "n_neighbors" in best_params and best_params["n_neighbors"] is None:
                    del best_params["n_neighbors"]
                
                clusterer = ClusteringModel(algorithm=model_name, **best_params)
                clusterer.fit(X)
                
                # Save tuned model
                model_path = save_model(clusterer, cfg, f"{model_name}_tuned", feature_columns)
                if verbose:
                    print(f"✅ Saved tuned {model_name} model to {model_path}")
                    print(f"   Found {clusterer.n_clusters_} clusters")
            

            # Save tuning results
            if verbose:
                print("  Generating tuning visualization...")
            tuning_fig = clusterer.plot_tuning_results(tuning_results)
            result_dir = Path(training_cfg.get("output", {}).get("directory", "Clustering-result"))
            tuning_fig.savefig(result_dir / f"{model_name}_tuning.png")
            plt.close(tuning_fig)
            
            # Generate corresponding visualization if needed
            if training_cfg.get("output", {}).get("save_cluster_visualization", True):
                cluster_fig = clusterer.plot_clusters(
                    X=X,
                    title=f"{model_name.upper()} Clustering Results"
                )

                dpi = training_cfg.get("output", {}).get("visualization_dpi", 300)
                cluster_fig.savefig(
                    result_dir / f"{model_name}_clusters.png", 
                    bbox_inches='tight', 
                    dpi=dpi
                )
                plt.close(cluster_fig)
    
    # Save config snapshot
    output_cfg = training_cfg.get("output", {})
    if output_cfg.get("save_config_snapshot", True):
        result_dir = Path(output_cfg.get("directory", "Clustering-result"))
        save_yaml_snapshot(cfg, result_dir, "train_config_used.yaml")
        if verbose:
            print(f"✅ Saved configuration snapshot")
    

    if verbose:
        print("✨ Training completed!")

def run_ams_analysis(raw_df, target_col, processed_values, labels_dict, output_dir):
    """
    Perform AMS distribution analysis across clusters and generate visualization/report.
    Adapted from analyze_ams_clusters.py for CLI integration.
    """
    if target_col not in raw_df.columns:
        print(f"⚠️  Target column '{target_col}' not found in raw data. Skipping AMS analysis.")
        return

    target = raw_df[target_col]
    # Ensure index alignment if processed_values came from a dataframe that lost index
    # In this CLI flow, we reconstruct the DF with index before passing values usually, 
    # but here we assume raw_df index matches the row order of processed_values
    if len(raw_df) != len(processed_values):
        print("⚠️  Row count mismatch between raw data and processed features. Skipping AMS analysis.")
        return
    
    # Restore index for processed data context if needed, though we mostly use raw_df for target
    # The labels correspond to the rows in processed_values which match raw_df
    
    metrics = {}
    for name, labels in labels_dict.items():
        valid = labels != -1
        if valid.sum() < 2 or len(np.unique(labels[valid])) < 2:
            metrics[name] = {"silhouette": np.nan, "davies_bouldin": np.nan, "calinski_harabasz": np.nan}
            continue
        Xv = processed_values[valid]
        lv = labels[valid]
        metrics[name] = {
            "silhouette": round(silhouette_score(Xv, lv), 4),
            "davies_bouldin": round(davies_bouldin_score(Xv, lv), 4),
            "calinski_harabasz": round(calinski_harabasz_score(Xv, lv), 2),
        }

    ams_analyses = {}
    for name, labels in labels_dict.items():
        df = pd.DataFrame({"cluster": labels, "Target_AMS": target.values}, index=raw_df.index)
        valid_df = df[df["cluster"] != -1].copy()
        noise_n = (df["cluster"] == -1).sum()

        cross = pd.crosstab(valid_df["cluster"], valid_df["Target_AMS"])
        for c in [0, 1]:
            if c not in cross.columns:
                cross[c] = 0
        cross = cross[[0, 1]]
        cross.columns = ["AMS=0", "AMS=1"]
        cross["Total"] = cross.sum(axis=1)
        cross["AMS_rate"] = (cross["AMS=1"] / cross["Total"]).round(3)

        if cross.shape[0] == 2 and cross.shape[1] == 2:
            _, pval = fisher_exact(cross[["AMS=0", "AMS=1"]].values)
            test_name = "Fisher's exact"
        else:
            chi2, pval, dof, _ = chi2_contingency(cross[["AMS=0", "AMS=1"]].values)
            test_name = "Chi-squared"

        raw_feat = raw_df.loc[valid_df.index].drop(columns=[target_col], errors='ignore')
        numeric_cols = raw_feat.select_dtypes(include=np.number).columns.tolist()
        
        profile_summary = None
        if numeric_cols:
            feat_profiles = valid_df.copy()
            for col in numeric_cols:
                if col in raw_feat.columns:
                    feat_profiles[col] = raw_feat[col].values
            profile_summary = feat_profiles.groupby("cluster")[numeric_cols + ["Target_AMS"]].agg(['mean', 'std']).round(2)

        ams_analyses[name] = {
            "crosstab": cross,
            "pvalue": pval,
            "test": test_name,
            "noise_n": noise_n,
            "profile_summary": profile_summary,
        }

    # PCA
    pca = PCA(n_components=2, random_state=42)
    try:
        X_pca = pca.fit_transform(processed_values)
        pca_var = pca.explained_variance_ratio_
    except Exception as e:
        print(f"⚠️  PCA failed: {e}")
        X_pca = None
        pca_var = [0.0, 0.0]

    # Plotting
    plt.style.use('default')
    fig = plt.figure(figsize=(20, 18))
    fig.suptitle("AMS Clustering Analysis – Target_AMS Distribution Across Clusters", fontsize=16, fontweight='bold', y=0.98)

    model_names = list(labels_dict.keys())
    colors_ams = {0: "#4878CF", 1: "#D65F5F"}
    cluster_palette = ["#2ecc71", "#e74c3c", "#3498db", "#f39c12", "#9b59b6"]

    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35)

    for row, name in enumerate(model_names):
        if row >= 3: break # Limit to 3 models in plot grid if more exist
        labels = labels_dict[name]
        analysis = ams_analyses[name]
        cross = analysis["crosstab"]
        
        # Left: PCA
        ax1 = fig.add_subplot(gs[row, 0])
        if X_pca is not None:
            unique_clusters = sorted(np.unique(labels[labels != -1]))
            for ci, cl in enumerate(unique_clusters):
                mask_cl = labels == cl
                for ams_val, marker, size in [(0, 'o', 50), (1, '*', 120)]:
                    mask = mask_cl & (target.values == ams_val)
                    ax1.scatter(X_pca[mask, 0], X_pca[mask, 1],
                                c=cluster_palette[ci % len(cluster_palette)],
                                marker=marker, s=size, alpha=0.8,
                                edgecolors='white', linewidth=0.5,
                                label=f"C{cl} AMS={ams_val}" if ci == 0 else "")
            noise_mask = labels == -1
            if noise_mask.any():
                ax1.scatter(X_pca[noise_mask, 0], X_pca[noise_mask, 1],
                            c='gray', marker='x', s=60, alpha=0.6, label='Noise')
            ax1.set_xlabel(f"PC1 ({pca_var[0]:.1%})", fontsize=9)
            ax1.set_ylabel(f"PC2 ({pca_var[1]:.1%})", fontsize=9)
        ax1.set_title(f"{name}\nPCA (colour=cluster, ★=AMS+)", fontsize=9, fontweight='bold')
        ax1.tick_params(labelsize=8)

        # Middle: Bar chart
        ax2 = fig.add_subplot(gs[row, 1])
        clusters = cross.index.tolist()
        rates = cross["AMS_rate"].tolist()
        totals = cross["Total"].tolist()
        bar_colors = [cluster_palette[i % len(cluster_palette)] for i in range(len(clusters))]
        bars = ax2.bar([f"C{c}" for c in clusters], rates, color=bar_colors, edgecolor='white', linewidth=1.2)
        for bar, total, rate in zip(bars, totals, rates):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                     f"n={total}\n{rate:.0%}", ha='center', va='bottom', fontsize=8)
        ax2.axhline(target.mean(), color='black', linestyle='--', linewidth=1, alpha=0.6, label=f"Overall {target.mean():.1%}")
        max_rate = max(rates) if rates else 0
        ax2.set_ylim(0, min(1.0, max_rate + 0.25))
        ax2.set_ylabel("AMS+ Rate", fontsize=9)
        ax2.set_title(f"AMS+ Rate per Cluster\n{analysis['test']} p={analysis['pvalue']:.3f}", fontsize=9, fontweight='bold')
        ax2.legend(fontsize=7)
        ax2.tick_params(labelsize=8)

        # Right: Stacked bar
        ax3 = fig.add_subplot(gs[row, 2])
        ams0 = cross["AMS=0"].tolist()
        ams1 = cross["AMS=1"].tolist()
        x_pos = np.arange(len(clusters))
        ax3.bar(x_pos, ams0, color="#4878CF", label="AMS=0", edgecolor='white')
        ax3.bar(x_pos, ams1, bottom=ams0, color="#D65F5F", label="AMS=1", edgecolor='white')
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels([f"C{c}" for c in clusters], fontsize=8)
        ax3.set_ylabel("Count", fontsize=9)
        ax3.set_title(f"Cluster Composition\n(total n={len(raw_df)}, noise={analysis['noise_n']})", fontsize=9, fontweight='bold')
        ax3.legend(fontsize=8)
        ax3.tick_params(labelsize=8)

    out_path = Path(output_dir) / "AMS_cluster_analysis.png"
    plt.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"✅ Saved AMS analysis visualization to {out_path}")

    # Print Report
    print("\n" + "="*70)
    print("CLUSTERING ANALYSIS REPORT — AMS Distribution")
    print("="*70)
    print(f"\nTotal samples: {len(raw_df)}")
    print(f"AMS+ cases:    {target.sum()} ({target.mean():.1%})")
    
    for name in model_names:
        analysis = ams_analyses[name]
        m = metrics.get(name, {})
        cross = analysis["crosstab"]
        print(f"\n{'─'*60}")
        print(f"MODEL: {name}")
        print(f"{'─'*60}")
        if m:
            print(f"  Silhouette Score:        {m.get('silhouette', 'N/A')}")
            print(f"  Davies-Bouldin Index:    {m.get('davies_bouldin', 'N/A')}")
            print(f"  Calinski-Harabasz Score: {m.get('calinski_harabasz', 'N/A')}")
        if analysis['noise_n'] > 0:
            print(f"  Noise points:   {analysis['noise_n']}")
        print(f"\n  Cluster × Target_AMS cross-table:")
        print(cross.to_string())
        print(f"\n  Statistical test: {analysis['test']}, p-value = {analysis['pvalue']:.4f}")
        if analysis['pvalue'] < 0.05:
            print("  → SIGNIFICANT difference in AMS distribution across clusters (p<0.05)")
        else:
            print("  → No significant difference in AMS distribution (p≥0.05)")

    print("\n" + "="*70)

@app.command()
def apply(
    config: str = typer.Option(default_config_path, "-c", "--config", help="Config file path"),
    run_ams_analysis_flag: bool = typer.Option(False, "--ams-analysis", help="Run AMS distribution analysis if target column exists")
):
    """Apply trained clustering model to new data."""
    cfg = load_yaml(config)
    apply_cfg = get_apply_cfg(cfg)
    
    verbose = apply_cfg.get("logging", {}).get("verbose", True)
    if verbose:
        print("\n🔍 Clustering Application Pipeline")
    
    # Load model
    model_path = apply_cfg.get("model_path")
    if not model_path:
        raise typer.BadParameter("apply.model_path is required")
    
    if verbose:
        print(f"Loading model from {model_path}...")
    model_pkg = load_model(model_path)
    clusterer = model_pkg["model"]
    
    # Load new data (Raw data needed for AMS analysis if enabled)
    if verbose:
        print("Loading new data...")
    # We need the raw data frame to access Target_AMS later if requested
    # Re-use load_data but we might need to NOT drop the target column if we want to analyze it
    # However, load_data currently drops index_col and drop_cols. 
    # For AMS analysis, we need the Target_AMS column which is usually in drop_cols for training.
    # Strategy: Load raw data separately for the analysis part if needed.
    
    # Standard load for clustering (drops target)
    df = load_data(cfg, scope="apply")
    
    # If AMS analysis is requested, we need the original raw data with Target_AMS
    raw_df_for_analysis = None
    if run_ams_analysis_flag:
        input_cfg = get_apply_cfg(cfg).get("input", {})
        raw_path = input_cfg.get('path')
        delimiter = input_cfg.get('delimiter', ',')
        index_col = input_cfg.get('index_col')
        
        if raw_path:
            raw_df_for_analysis = pd.read_csv(raw_path, sep=delimiter)
            if index_col and index_col in raw_df_for_analysis.columns:
                raw_df_for_analysis.set_index(index_col, inplace=True)
            if verbose:
                print(f"Loaded raw data for AMS analysis: {raw_df_for_analysis.shape}")

    if verbose:
        print(f"New data shape (features): {df.shape}")
    
    # Apply preprocessing if configured
    if apply_cfg.get("preprocessing", {}).get("use_artifact", True):
        if verbose:
            print("Applying preprocessing artifact...")
        
        artifact_path = apply_cfg.get("preprocessing", {}).get("artifact_path")
        if not artifact_path:
            pre_cfg = get_preprocessing_cfg(cfg)
            output_cfg = pre_cfg.get("output", {})
            artifact_path = Path(output_cfg.get("directory", "Data/Processed")) / \
                           f"{output_cfg.get('preprocess_artifact_name', 'preprocess_artifact')}.joblib"
        
        artifact = joblib.load(artifact_path)
        
        features = df.copy()
        
        if artifact["categories"]:
            features, _ = onehot_encoding(
                features, 
                cat_features=artifact.get("cat_features", []),
                categories=artifact["categories"]
            )
        
        features = features.drop(
            columns=artifact["zero_var"] + artifact["high_miss"], 
            errors='ignore'
        )
        
        if artifact["mean"] is not None and artifact["std"] is not None:
            features, _, _, _ = standardize(
                features, 
                num_features=artifact["num_features"],
                mean=artifact["mean"],
                std=artifact["std"]
            )
        
        features = fill_missing_values(
            features, 
            features, 
            method=cfg.get("preprocessing", {}).get("imputation_method", "mean")
        )
        
        X = features
    else:
        X = df
    
    if isinstance(X, pd.DataFrame):
        X_values = X.values
    else:
        X_values = X
    
    # Apply clustering
    if verbose:
        print("Assigning clusters...")
    labels = clusterer.predict(X_values)
    
    # Prepare labels dict for analysis (mimicking the multiple models structure if needed, 
    # but apply usually runs one model. We wrap it for compatibility with analysis func)
    model_name = model_pkg.get("model_name", "Applied_Model")
    labels_dict = {model_name: labels}
    
    # Run AMS Analysis if requested and raw data available
    if run_ams_analysis_flag and raw_df_for_analysis is not None:
        if verbose:
            print("\nRunning AMS Distribution Analysis...")
        target_col = "Target_AMS" # Default, could be made configurable
        output_dir = Path(apply_cfg.get("output", {}).get("directory", "Clustering-result/apply"))
        run_ams_analysis(raw_df_for_analysis, target_col, X_values, labels_dict, output_dir)
    
    # Create results dataframe
    results_df = pd.DataFrame({
        "cluster": labels
    }, index=df.index)
    
    if hasattr(clusterer.model, "predict_proba") and apply_cfg.get("predict_proba", False):
        proba = clusterer.model.predict_proba(X_values)
        for i in range(proba.shape[1]):
            results_df[f"prob_cluster_{i}"] = proba[:, i]
    
    # Save results
    output_cfg = apply_cfg.get("output", {})
    save_output = output_cfg.get("save", True)
    
    if save_output:
        output_dir = Path(output_cfg.get("directory", "Clustering-result/apply"))
        fmt = output_cfg.get("format", "tsv")
        
        output_path = output_dir / f"cluster_assignments.{fmt}"
        save_table(results_df, output_path, fmt)
        
        if verbose:
            print(f"✅ Saved cluster assignments to {output_path}")
        
        if output_cfg.get("save_config_snapshot", True):
            save_yaml_snapshot(cfg, output_dir, "apply_config_used.yaml")
            if verbose:
                print(f"✅ Saved configuration snapshot")
    
    if verbose:
        print(f"✨ Applied clustering to {len(df)} samples with {clusterer.n_clusters_} clusters")

@app.command()
def unit_test(
    verbose: bool = typer.Option(True, "--verbose/--no-verbose", help="Enable verbose output")
):
    """Run unit tests for clustering models."""
    print("\n🧪 Running Clustering Unit Tests")
    
    try:
        # Import the unit test module
        from AI_toolbox.Modelling.Clustering.clustering_models_unit_test import (
            test_kmeans_functionality,
            test_dbscan_functionality,
            test_spectral_clustering_functionality,
            edge_case_testing
        )
        
        # Run tests
        print("==============================================")
        test_kmeans_functionality()
        print("KMeans Clustering Test Completed ✅")
        print("----------------------------------------------")
        
        test_dbscan_functionality()
        print("DBSCAN Clustering Test Completed ✅")
        print("----------------------------------------------")
        
        test_spectral_clustering_functionality()
        print("Spectral Clustering Test Completed ✅")
        print("----------------------------------------------")
        
        edge_case_testing()
        print("Edge Case Testing Completed ✅")
        print("==============================================")
        print("✅✅✅✅✅✅✅✅✅")
        print(" Clustering Unit Test Suite Completed Successfully ✅")
        print("✅✅✅✅✅✅✅✅✅")
        
    except Exception as e:
        print(f"❌ Unit test execution failed: {str(e)}")
        raise typer.Exit(code=1)

@app.command()
def config_template():
    """Show configuration template for clustering pipeline."""
    template = """
# Clustering Pipeline Configuration
# Edit this file to customize the clustering pipeline

preprocessing:
  input:
    path: "Data/Raw/data.csv"    # Input data file path
    delimiter: ","              # CSV/TSV delimiter
    index_col: null             # Index column name (null to skip)
    drop_cols: []               # Columns to drop
  features:
    categorical: []             # List of categorical feature names
  imputation_method: "mean"     # "mean", "median", "knn", "mice", or "none"
  remove_zero_variance: true    # Remove features with zero variance
  missing_threshold: 50.0       # % threshold for removing high-missing features
  standardize: true             # Standardize numeric features
  standardize_binary: false     # If true, binary columns are also standardized
  split:
    method: "full"              # Only "full" makes sense for clustering
  output:
    directory: "Data/Processed" # Output folder for preprocess results
    format: "tsv"               # "csv", "tsv", or "parquet"
    save: true                  # Whether to write preprocess outputs to disk
    save_row_id: true           # Add __row_id__ for reference in training
    save_preprocess_artifact: true  # Save fitted preprocessing artifact for future predict transform
    preprocess_artifact_name: "preprocess_artifact"  # Artifact filename prefix
    save_config_snapshot: true  # Save preprocess_config_used.yaml in output directory
  logging:
    verbose: true               # Print preprocessing progress logs

training:
  input:
    source: "preprocessed"      # Currently only "preprocessed" is supported
    processed:
      directory: "Data/Processed"  # Folder for processed files
      format: "tsv"             # "csv", "tsv", or "parquet"
      path: null                # Optional single processed file path
  random_state: 123             # Random seed for reproducibility
  logging:
    verbose: true               # Print training progress logs
  operations: ["fit", "tune"]   # "fit" and/or "tune"
  models: ["kmeans", "dbscan", "spectral"]  # Models to train
  model_params:               # Default parameters for each model
    kmeans:
      n_clusters: 8
      init: "k-means++"
      n_init: 10
    dbscan:
      eps: 0.5
      min_samples: 5
    spectral:
      n_clusters: 8
      affinity: "rbf"
  tune_params:                # Hyperparameter tuning configuration
    kmeans:
      n_clusters_range: [2, 10]  # Range of cluster numbers to try
      metric: "silhouette"     # "silhouette", "davies_bouldin", or "inertia"
    dbscan:
      eps_range: [0.1, 2.0]    # Range of eps values
      min_samples_range: [2, 20]  # Range of min_samples values
      metric: "silhouette"     # "silhouette" or "davies_bouldin"
    spectral:
      n_clusters_range: [2, 10]  # Range of cluster numbers
      affinity_options: ["rbf", "nearest_neighbors"]  # Affinity metrics to try
      n_neighbors_range: [5, 20]  # Range of n_neighbors (for nearest_neighbors)
      metric: "silhouette"     # "silhouette" or "davies_bouldin"
  output:
    directory: "Clustering-result"  # Output directory for training results
    format: "tsv"               # Table format for outputs
    save: true                  # Global write switch for training outputs
    save_config_snapshot: true  # Save train_config_used.yaml in output directory

apply:
  model_path: "Clustering-result/kmeans.joblib"  # Path to trained model
  input:
    path: "Data/Raw/new_data.csv"  # Input file for applying clustering
    delimiter: ","             # CSV/TSV delimiter
    index_col: null            # Index column name (null to skip)
    drop_cols: []              # Columns to drop
  preprocessing:
    use_artifact: true         # If true, apply saved preprocessing artifact
    artifact_path: null        # Optional artifact path (null = default)
  output:
    directory: "Clustering-result/apply"  # Output folder for apply results
    format: "tsv"              # "csv", "tsv", or "parquet"
    save: true                 # Whether to save results
    save_config_snapshot: true # Save apply_config_used.yaml in output directory
  logging:
    verbose: true              # Print apply progress logs
    predict_proba: false       # Output probability if model supports it

unit_test:
  verbose: true                # Enable verbose test output
"""
    print(template)

if __name__ == "__main__":
    app()