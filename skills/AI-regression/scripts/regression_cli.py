#!/usr/bin/env python
"""CLI for the regression pipeline."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import importlib.resources
import joblib
import pandas as pd
import typer
import yaml
from sklearn.metrics import get_scorer

from AI_toolbox.Pipelines.Regression_pipeline import (
    preprocessing_df,
    preprocessing_pipeline,
    preprocessing_test,
)
from AI_toolbox.Preprocessing.Dataset_split import KFold_split, dataset_split


# Get default config path
try:
    default_config_path = str(importlib.resources.files("AI_toolbox.config") / "regression_config.yaml")
except (AttributeError, FileNotFoundError, ModuleNotFoundError):
    # Fallback for direct execution
    default_config_path = "AI_toolbox/config/regression_config.yaml"

app = typer.Typer()


def load_yaml(path: str) -> dict:
    """Load YAML configuration file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_data(config: dict, scope: str = "preprocessing") -> tuple:
    """Load data from CSV/TSV file.

    scope='preprocessing': use preprocessing.input/target (fallback to legacy root input/target)
    scope='training': use training.input/target first, then fallback to preprocessing.input/target
    """
    pre_cfg = config.get("preprocessing", {})
    if scope == "training":
        train_cfg = config.get("training", {})
        input_cfg = train_cfg.get("input", pre_cfg.get("input", config.get("input", {})))
        target_cfg = train_cfg.get("target", pre_cfg.get("target", config.get("target", {})))
    else:
        input_cfg = pre_cfg.get("input", config.get("input", {}))
        target_cfg = pre_cfg.get("target", config.get("target", {}))

    path = input_cfg["path"]
    delimiter = input_cfg.get("delimiter", "\t")
    index_col = input_cfg.get("index_col")
    drop_cols = input_cfg.get("drop_cols", [])

    df = pd.read_csv(path, sep=delimiter)
    if index_col and index_col in df.columns:
        df.set_index(index_col, inplace=True)
    df = df.drop(columns=drop_cols, errors="ignore")

    target_col = target_cfg.get("column")
    if target_col and target_col in df.columns:
        y = df[target_col]
        X = df.drop(columns=[target_col])
    else:
        X = df
        y = None
    return X, y


def save_yaml_snapshot(cfg: dict, out_dir: Path, name: str = "used_config.yaml") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / name
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
    return p


def get_preprocessing_split_cfg(config: dict) -> dict:
    pre_cfg = config.get("preprocessing", {})
    return pre_cfg.get("split", config.get("split", {}))


def get_preprocessing_output_cfg(config: dict) -> dict:
    pre_cfg = config.get("preprocessing", {})
    return pre_cfg.get("output", config.get("output", {}))


def get_preprocessing_logging_cfg(config: dict) -> dict:
    pre_cfg = config.get("preprocessing", {})
    return pre_cfg.get("logging", config.get("logging", {}))


def get_training_input_cfg(config: dict) -> dict:
    """Get training input config with backward compatibility."""
    training_cfg = config.get("training", {})
    inp = training_cfg.get("input", {})
    return {
        "source": inp.get("source", training_cfg.get("input_source", "preprocessed")),
        "raw": inp.get("raw", inp if isinstance(inp, dict) else {}),
        "processed": inp.get("processed", training_cfg.get("data", {})),
    }


def read_table(path: Path, fmt: str) -> pd.DataFrame:
    fmt = fmt.lower()
    if fmt == "csv":
        return pd.read_csv(path)
    if fmt == "parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, sep="\t")


def split_features_target(df: pd.DataFrame, config: dict) -> tuple:
    """Extract X/y from a processed dataframe, recovering y by __row_id__ when needed."""
    pre_cfg = config.get("preprocessing", {})
    target_cfg = pre_cfg.get("target", config.get("target", {}))
    target_col = target_cfg.get("column")

    if target_col and target_col in df.columns:
        y = df[target_col]
        drop_cols = [target_col]
        if "__row_id__" in df.columns:
            drop_cols.append("__row_id__")
        X = df.drop(columns=drop_cols)
        return X, y

    if "__row_id__" not in df.columns:
        raise ValueError(
            "预处理输出不包含目标列，且缺少 '__row_id__'。"
            "请重新运行 preprocess，并在 output.save_row_id=true 后再运行 train。"
        )

    raw_X, raw_y = load_data(config)
    if raw_y is None:
        pre_cfg = config.get("preprocessing", {})
        input_cfg = pre_cfg.get("input", config.get("input", {}))
        target_cfg = pre_cfg.get("target", config.get("target", {}))
        path = input_cfg.get("path", "?")
        target_col = target_cfg.get("column", "?")
        raise ValueError(
            "原始输入中未找到目标列，无法从 '__row_id__' 恢复 y。"
            f"请检查 preprocessing.input.path 指向的原始数据文件（当前: {path}）"
            f"且包含 preprocessing.target.column（当前: {target_col}）。"
            "若尚未运行 preprocess，请先运行 regression-cli preprocess；"
            "若已用新数据重新 preprocess，请确保 config 中路径与目标列名正确。"
        )

    raw_index = raw_X.index if isinstance(raw_X, pd.DataFrame) else pd.RangeIndex(len(raw_y))
    lookup = pd.Series(raw_y.values, index=raw_index)
    row_ids = df["__row_id__"]
    try:
        y = lookup.loc[row_ids].reset_index(drop=True)
    except KeyError as exc:
        raise ValueError("预处理输出中的 '__row_id__' 与原始输入索引不匹配，无法恢复 y。") from exc

    X = df.drop(columns=["__row_id__"])
    return X, y


def discover_processed_files(config: dict) -> dict:
    """Discover and validate processed train/test file pairs for training."""
    data_cfg = get_training_input_cfg(config).get("processed", {})
    output_cfg = get_preprocessing_output_cfg(config)
    split_method = str(get_preprocessing_split_cfg(config).get("method", "train_test")).lower()

    mode = data_cfg.get("mode")
    if mode is None:
        if split_method in {"kfold", "cv"}:
            mode = "outer_cv"
        elif split_method == "full":
            mode = "full"
        else:
            mode = "single_split"

    directory = Path(data_cfg.get("directory", output_cfg.get("directory", "Data/Processed")))
    fmt = str(data_cfg.get("format", output_cfg.get("format", "tsv"))).lower()
    single_path = data_cfg.get("path")
    if not single_path and not directory.exists():
        raise FileNotFoundError(f"未找到 processed 数据目录: {directory}")

    if mode in {"single_split", "full"}:
        if single_path:
            p = Path(single_path)
            if not p.exists():
                raise FileNotFoundError(f"{mode} 指定的 processed 文件不存在: {p}")
            return {"mode": mode, "format": fmt, "pairs": [(None, p, None)]}

        if mode == "full":
            full_path = directory / f"full_preprocessed.{fmt}"
            if not full_path.exists():
                raise FileNotFoundError(f"full 模式需要 full_preprocessed.{fmt}，缺失: {full_path}")
            return {"mode": "full", "format": fmt, "pairs": [(None, full_path, None)]}

        train_path = directory / f"train_preprocessed.{fmt}"
        test_path = directory / f"test_preprocessed.{fmt}"
        missing = [str(p) for p in [train_path, test_path] if not p.exists()]
        if missing:
            raise FileNotFoundError(
                f"single_split 模式需要匹配文件 train/test_preprocessed，缺失: {missing}"
            )
        return {"mode": mode, "format": fmt, "pairs": [(None, train_path, test_path)]}

    if mode == "outer_cv":
        train_pat = re.compile(rf"^train_fold(\d+)_preprocessed\.{re.escape(fmt)}$")
        test_pat = re.compile(rf"^test_fold(\d+)_preprocessed\.{re.escape(fmt)}$")

        train_map = {}
        test_map = {}
        for p in directory.iterdir():
            if not p.is_file():
                continue
            m_train = train_pat.match(p.name)
            if m_train:
                train_map[int(m_train.group(1))] = p
            m_test = test_pat.match(p.name)
            if m_test:
                test_map[int(m_test.group(1))] = p

        train_ids = set(train_map.keys())
        test_ids = set(test_map.keys())
        if not train_ids and not test_ids:
            raise FileNotFoundError(
                "outer_cv 模式未发现 train_fold*_preprocessed / test_fold*_preprocessed 文件。"
            )
        if train_ids != test_ids:
            only_train = sorted(train_ids - test_ids)
            only_test = sorted(test_ids - train_ids)
            raise ValueError(f"outer_cv 文件不匹配：仅 train 有 {only_train}；仅 test 有 {only_test}。")

        pairs = [(fid, train_map[fid], test_map[fid]) for fid in sorted(train_ids)]
        return {"mode": mode, "format": fmt, "pairs": pairs}

    raise ValueError("training.input.processed.mode 必须是 single_split、full 或 outer_cv。")


def load_training_raw_data(config: dict) -> tuple:
    """Load raw training data using training.input.raw, then fallback to preprocessing input."""
    pre_cfg = config.get("preprocessing", {})
    training_cfg = config.get("training", {})
    inp_cfg = get_training_input_cfg(config)
    raw_cfg = inp_cfg.get("raw", {}) or {}

    input_cfg = raw_cfg if "path" in raw_cfg else pre_cfg.get("input", config.get("input", {}))
    target_col = raw_cfg.get("target_column")
    if target_col is None:
        target_col = training_cfg.get("target", {}).get("column")
    if target_col is None:
        target_col = pre_cfg.get("target", config.get("target", {})).get("column")

    path = input_cfg["path"]
    delimiter = input_cfg.get("delimiter", "\t")
    index_col = input_cfg.get("index_col")
    drop_cols = input_cfg.get("drop_cols", [])

    df = pd.read_csv(path, sep=delimiter)
    if index_col and index_col in df.columns:
        df.set_index(index_col, inplace=True)
    df = df.drop(columns=drop_cols, errors="ignore")

    if target_col and target_col in df.columns:
        y = df[target_col]
        X = df.drop(columns=[target_col])
    else:
        X = df
        y = None
    return X, y


def load_training_data(config: dict) -> dict:
    """Load training datasets from preprocess output or raw input."""
    source = get_training_input_cfg(config).get("source", "preprocessed")

    if source == "raw":
        X, y = load_training_raw_data(config)
        return {"mode": "single_split", "datasets": [(None, X, y, None, None)]}

    processed_info = discover_processed_files(config)
    datasets = []
    for fold_id, train_path, test_path in processed_info["pairs"]:
        train_df = read_table(train_path, processed_info["format"])
        X_train, y_train = split_features_target(train_df, config)
        if test_path is None:
            X_test, y_test = None, None
        else:
            test_df = read_table(test_path, processed_info["format"])
            X_test, y_test = split_features_target(test_df, config)
        datasets.append((fold_id, X_train, y_train, X_test, y_test))
    return {"mode": processed_info["mode"], "datasets": datasets}


def save_table(df: pd.DataFrame, path: Path, fmt: str = "tsv") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt.lower()
    if fmt == "csv":
        df.to_csv(path, index=False)
    elif fmt == "parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, sep="\t", index=False, na_rep="NA")
    return path


def save_preprocess_artifact(artifact: dict, config: dict, fold: int | None = None) -> Path:
    output_cfg = get_preprocessing_output_cfg(config)
    out_dir = Path(output_cfg.get("directory", "Data/Processed"))
    name = output_cfg.get("preprocess_artifact_name", "preprocess_artifact")
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / (f"{name}.joblib" if fold is None else f"{name}_fold{fold}.joblib")
    joblib.dump(artifact, p)
    return p


def load_preprocess_artifact_for_predict(config: dict) -> dict:
    inf_cfg = config.get("predict", config.get("inference", {}))
    preproc_cfg = inf_cfg.get("preprocessing", {})
    if not preproc_cfg.get("use_artifact", False):
        return {}

    artifact_path = preproc_cfg.get("artifact_path")
    if artifact_path:
        p = Path(artifact_path).expanduser()
    else:
        out_cfg = get_preprocessing_output_cfg(config)
        out_dir = Path(out_cfg.get("directory", "Data/Processed"))
        name = out_cfg.get("preprocess_artifact_name", "preprocess_artifact")
        p = out_dir / f"{name}.joblib"

    if not p.exists():
        raise FileNotFoundError(f"预处理 artifact 不存在: {p}")
    art = joblib.load(p)
    if not isinstance(art, dict):
        raise ValueError("预处理 artifact 格式错误，应为 dict。")
    return art


def save_preprocessed_results(train_df: pd.DataFrame, test_df: pd.DataFrame, config: dict, fold: int | None = None):
    output_cfg = get_preprocessing_output_cfg(config)
    output_dir = output_cfg["directory"]
    fmt = output_cfg.get("format", "tsv")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    if fold is not None:
        train_file = f"{output_dir}/train_fold{fold}_preprocessed.{fmt}"
        test_file = f"{output_dir}/test_fold{fold}_preprocessed.{fmt}"
    else:
        train_file = f"{output_dir}/train_preprocessed.{fmt}"
        test_file = f"{output_dir}/test_preprocessed.{fmt}"

    save_row_id = output_cfg.get("save_row_id", True)
    train_to_save = train_df.copy()
    test_to_save = test_df.copy()
    if save_row_id:
        train_to_save.insert(0, "__row_id__", train_to_save.index)
        test_to_save.insert(0, "__row_id__", test_to_save.index)

    if fmt == "csv":
        train_to_save.to_csv(train_file, index=False)
        test_to_save.to_csv(test_file, index=False)
    else:
        train_to_save.to_csv(train_file, sep="\t", index=False, na_rep="NA")
        test_to_save.to_csv(test_file, sep="\t", index=False, na_rep="NA")
    return train_file, test_file


@app.command()
def preprocess(
    config: str = typer.Option(default_config_path, "-c", "--config", help="Config file path"),
):
    """Preprocess regression data pipeline."""
    cfg = load_yaml(config)
    X, y = load_data(cfg)

    verbose = get_preprocessing_logging_cfg(cfg).get("verbose", True)
    if verbose:
        print("\n📊 Regression Preprocessing Pipeline")
        print(f"   Data shape: {X.shape}")
        print(f"   Split method: {get_preprocessing_split_cfg(cfg).get('method', 'train_test')}")

    pre_cfg = cfg.get("preprocessing", {})
    features_cfg = pre_cfg.get("features", cfg.get("features", {}))
    cat_features = features_cfg.get("categorical", [])
    split_cfg = get_preprocessing_split_cfg(cfg)
    output_cfg = get_preprocessing_output_cfg(cfg)
    save_artifact = output_cfg.get("save_preprocess_artifact", False)
    impute_method = pre_cfg.get("imputation_method", "mice")

    split_method = str(split_cfg.get("method", "train_test"))
    split_method_lower = split_method.lower()

    if split_method_lower == "full":
        train_df, categories, remove_features, train_mean, train_std, num_features, ref_df_imputed = preprocessing_df(
            X, cat_features, impute_method=impute_method, verbose=verbose
        )
        ref_df = train_df.copy()
        if y is not None:
            target_col = pre_cfg.get("target", cfg.get("target", {})).get("column")
            if target_col:
                train_df[target_col] = y.loc[train_df.index]
        if output_cfg.get("save_row_id", True):
            train_df.insert(0, "__row_id__", train_df.index)
        out_dir = Path(output_cfg.get("directory", "Data/Processed"))
        out_fmt = output_cfg.get("format", "tsv")
        full_path = out_dir / f"full_preprocessed.{out_fmt}"
        if save_artifact:
            artifact = {
                "split_method": "full",
                "fold": None,
                "cat_features": cat_features,
                "imputation_method": impute_method,
                "categories": categories,
                "remove_features": remove_features,
                "ref_mean": train_mean,
                "ref_std": train_std,
                "num_features": num_features,
                "ref_df": ref_df,
                "ref_df_imputed": ref_df_imputed,
                "feature_columns": list(ref_df.columns),
                "target_column": pre_cfg.get("target", cfg.get("target", {})).get("column"),
            }
            art_path = save_preprocess_artifact(artifact, cfg)
            if verbose:
                print(f"✅ Artifact: {art_path}")
        if output_cfg.get("save", True):
            save_table(train_df, full_path, out_fmt)
            if output_cfg.get("save_config_snapshot", True):
                save_yaml_snapshot(cfg, out_dir, "preprocess_config_used.yaml")
            if verbose:
                print(f"✅ Full: {full_path} {train_df.shape}")
        if verbose:
            print("✨ Done!")
        return

    # train_test / kfold
    result = preprocessing_pipeline(
        X,
        y,
        cat_features,
        split_method="train_test" if split_method_lower == "train_test" else "kfold",
        train_test_ratio=split_cfg.get("train_test_ratio", 0.8),
        n_splits=split_cfg.get("n_splits", 5),
        impute_method=impute_method,
        verbose=verbose,
    )

    if split_method_lower == "train_test":
        X_train, X_test, _y_train, _y_test = result
        if save_artifact:
            raw_train, _raw_test = dataset_split(
                X,
                train_test_ratio=split_cfg.get("train_test_ratio", 0.8),
                random_state=split_cfg.get("random_state", 42),
                verbose=False,
            )
            ref_df, categories, remove_features, train_mean, train_std, num_features, ref_df_imputed = preprocessing_df(
                raw_train.copy(), cat_features, impute_method=impute_method, verbose=False
            )
            artifact = {
                "split_method": "train_test",
                "fold": None,
                "cat_features": cat_features,
                "imputation_method": impute_method,
                "categories": categories,
                "remove_features": remove_features,
                "ref_mean": train_mean,
                "ref_std": train_std,
                "num_features": num_features,
                "ref_df": ref_df,
                "ref_df_imputed": ref_df_imputed,
                "feature_columns": list(ref_df.columns),
                "target_column": pre_cfg.get("target", cfg.get("target", {})).get("column"),
            }
            art_path = save_preprocess_artifact(artifact, cfg)
            if verbose:
                print(f"✅ Artifact: {art_path}")
        if output_cfg.get("save", True):
            target_col = pre_cfg.get("target", cfg.get("target", {})).get("column")
            train_to_save = X_train.copy()
            test_to_save = X_test.copy()
            if target_col and _y_train is not None and _y_test is not None:
                train_to_save[target_col] = _y_train.values
                test_to_save[target_col] = _y_test.values
            train_file, test_file = save_preprocessed_results(train_to_save, test_to_save, cfg)
            if output_cfg.get("save_config_snapshot", True):
                save_yaml_snapshot(cfg, Path(output_cfg["directory"]), "preprocess_config_used.yaml")
            if verbose:
                print(f"✅ Train: {train_file} {X_train.shape}")
                print(f"✅ Test: {test_file} {X_test.shape}")
    else:
        raw_gen = None
        if save_artifact:
            rs = split_cfg.get("random_state", 42)
            ns = split_cfg.get("n_splits", 5)
            raw_gen = KFold_split(X, n_splits=ns, random_state=rs, verbose=False)

        target_col = pre_cfg.get("target", cfg.get("target", {})).get("column")
        for fold_idx, fold_data in enumerate(result, 1):
            X_train, X_test, _y_train, _y_test = fold_data[:4]
            if output_cfg.get("save", True):
                train_to_save = X_train.copy()
                test_to_save = X_test.copy()
                if target_col and _y_train is not None and _y_test is not None:
                    train_to_save[target_col] = _y_train.values
                    test_to_save[target_col] = _y_test.values
                save_preprocessed_results(train_to_save, test_to_save, cfg, fold=fold_idx)
            if save_artifact and raw_gen is not None:
                raw_train, _raw_test, _train_idx, _test_idx = next(raw_gen)
                ref_df, categories, remove_features, train_mean, train_std, num_features, ref_df_imputed = preprocessing_df(
                    raw_train.copy(), cat_features, impute_method=impute_method, verbose=False
                )
                artifact = {
                    "split_method": "kfold",
                    "fold": fold_idx,
                    "cat_features": cat_features,
                    "imputation_method": impute_method,
                    "categories": categories,
                    "remove_features": remove_features,
                    "ref_mean": train_mean,
                    "ref_std": train_std,
                    "num_features": num_features,
                    "ref_df": ref_df,
                    "ref_df_imputed": ref_df_imputed,
                    "feature_columns": list(ref_df.columns),
                    "target_column": pre_cfg.get("target", cfg.get("target", {})).get("column"),
                }
                art_path = save_preprocess_artifact(artifact, cfg, fold=fold_idx)
                if verbose:
                    print(f"✅ Artifact Fold {fold_idx}: {art_path}")
            if verbose:
                print(f"✅ Fold {fold_idx}: Train {X_train.shape}, Test {X_test.shape}")
        if output_cfg.get("save_config_snapshot", True):
            out_dir = Path(output_cfg.get("directory", "Data/Processed"))
            save_yaml_snapshot(cfg, out_dir, "preprocess_config_used.yaml")

    if verbose:
        print("✨ Done!")


@app.command()
def train(
    config: str = typer.Option(default_config_path, "-c", "--config", help="Config file path"),
):
    """Run regressor operations: cross_validate/fit."""
    from AI_toolbox.Modelling.Regression.simple_regressor import SimpleRegressor

    cfg = load_yaml(config)
    loaded = load_training_data(cfg)
    data_mode = loaded["mode"]
    datasets = loaded["datasets"]
    if not datasets:
        raise typer.BadParameter("No training dataset found.")

    training_cfg = cfg.get("training", {})
    models = training_cfg.get("models", [])
    if not models:
        raise typer.BadParameter("training.models is required and cannot be empty.")

    operations = training_cfg.get("operations", ["cross_validate"])
    if isinstance(operations, str):
        operations = [operations]
    valid_ops = {"cross_validate", "fit"}
    invalid_ops = [op for op in operations if op not in valid_ops]
    if invalid_ops:
        raise typer.BadParameter(f"Unsupported training.operations: {invalid_ops}")

    verbose = training_cfg.get("logging", {}).get("verbose", get_preprocessing_logging_cfg(cfg).get("verbose", True))
    random_state = training_cfg.get("random_state", get_preprocessing_split_cfg(cfg).get("random_state", 0))
    reg = SimpleRegressor(random_state=random_state)

    out_cfg = training_cfg.get("output", {})
    out_fmt = out_cfg.get("format", "tsv")
    save_outputs = out_cfg.get("save", True)
    cv_out_dir = Path(out_cfg.get("cross_validate_dir", "Regression-result/cross_validate"))
    model_out_dir = Path(out_cfg.get("model_dir", "Regression-result/model"))

    best_model = None
    best_params: dict[str, Any] = {}
    fold_df = None
    summary_df = None
    outer_eval_df = None

    if "cross_validate" in operations:
        if data_mode in {"single_split", "full"}:
            _fold_id, X, y, _X_test, _y_test = datasets[0]
            if y is None:
                raise typer.BadParameter("target.column not found in training data; training requires y.")
            fold_df, summary_df = reg.cross_validate(
                X=X,
                y=y,
                models=models,
                param_grid=training_cfg.get("param_grid", {}),
                cv=training_cfg.get("cv", 5),
                scoring=training_cfg.get("scoring", "r2"),
                n_jobs=training_cfg.get("n_jobs", -1),
                rename_single_score=training_cfg.get("rename_single_score", True),
            )
        else:
            all_fold = []
            all_summary = []
            all_outer_eval = []

            best_cfg = training_cfg.get("best_model", {})
            metric = best_cfg.get("metric", "r2")
            mode = best_cfg.get("mode", "max")

            metric_col = metric if str(metric).startswith("test_") else f"test_{metric}_mean"
            if not metric_col.endswith("_mean"):
                metric_col = f"{metric_col}_mean"

            scoring_cfg = training_cfg.get("scoring", "r2")
            if isinstance(scoring_cfg, str):
                scoring_map = {scoring_cfg: scoring_cfg}
            elif isinstance(scoring_cfg, list):
                scoring_map = {m: m for m in scoring_cfg}
            elif isinstance(scoring_cfg, dict):
                scoring_map = dict(scoring_cfg)
            else:
                raise typer.BadParameter("training.scoring 必须是 str、list[str] 或 dict。")

            for fold_id, X_train, y_train, X_test, y_test in datasets:
                if y_train is None:
                    raise typer.BadParameter("target.column not found in training data; training requires y.")
                if X_test is None or y_test is None:
                    raise typer.BadParameter("outer_cv 需要每个外层 fold 的测试集。")
                if verbose:
                    print(f"\nOuter fold {fold_id}:")

                fold_i, summary_i = reg.cross_validate(
                    X=X_train,
                    y=y_train,
                    models=models,
                    param_grid=training_cfg.get("param_grid", {}),
                    cv=training_cfg.get("cv", 5),
                    scoring=training_cfg.get("scoring", "r2"),
                    n_jobs=training_cfg.get("n_jobs", -1),
                    rename_single_score=training_cfg.get("rename_single_score", True),
                )
                fold_i.insert(0, "outer_fold", fold_id)
                summary_i.insert(0, "outer_fold", fold_id)
                all_fold.append(fold_i)
                all_summary.append(summary_i)

                if metric_col not in summary_i.columns:
                    raise typer.BadParameter(
                        f"best_model.metric='{metric}' 无法在 summary 中找到对应列（期望 {metric_col}）。"
                    )

                ascending = mode == "min"
                best_row_i = summary_i.sort_values(metric_col, ascending=ascending).iloc[0]
                best_model_i = best_row_i["model"]
                best_params_i = best_row_i["params_dict"] or {}
                est_i = reg.create(best_model_i, **best_params_i)
                est_i.fit(X_train, y_train)

                outer_row = {
                    "outer_fold": fold_id,
                    "best_model": best_model_i,
                    "best_params": str(best_params_i),
                    "selected_metric": metric_col,
                    "selected_metric_inner_cv": best_row_i[metric_col],
                }
                for alias, scorer_name in scoring_map.items():
                    scorer = get_scorer(scorer_name)
                    outer_row[f"outer_test_{alias}"] = scorer(est_i, X_test, y_test)
                all_outer_eval.append(outer_row)

            fold_df = pd.concat(all_fold, ignore_index=True)
            summary_df = pd.concat(all_summary, ignore_index=True)
            outer_eval_df = pd.DataFrame(all_outer_eval)
            if not outer_eval_df.empty:
                metric_cols = [f"outer_test_{alias}" for alias in scoring_map.keys()]
                sd_cols = [f"{c}_sd" for c in metric_cols]
                for c in sd_cols:
                    if c not in outer_eval_df.columns:
                        outer_eval_df[c] = pd.NA
                avg_row = {
                    "outer_fold": "mean",
                    "best_model": "",
                    "best_params": "",
                    "selected_metric": "",
                    "selected_metric_inner_cv": "",
                }
                for c in metric_cols:
                    avg_row[c] = outer_eval_df[c].mean()
                    avg_row[f"{c}_sd"] = outer_eval_df[c].std(ddof=1)
                outer_eval_df = pd.concat([outer_eval_df, pd.DataFrame([avg_row])], ignore_index=True)

        if save_outputs:
            fold_path = cv_out_dir / f"cv_fold_results.{out_fmt}"
            save_table(fold_df, fold_path, out_fmt)
            if verbose:
                print(f"Saved CV fold results: {fold_path}")
            summary_path = cv_out_dir / f"cv_summary_results.{out_fmt}"
            save_table(summary_df, summary_path, out_fmt)
            if verbose:
                print(f"Saved CV summary results: {summary_path}")
            if data_mode == "outer_cv" and outer_eval_df is not None:
                outer_eval_path = cv_out_dir / f"outer_test_evaluation.{out_fmt}"
                save_table(outer_eval_df, outer_eval_path, out_fmt)
                if verbose:
                    print(f"Saved outer test evaluation: {outer_eval_path}")

        best_cfg = training_cfg.get("best_model", {})
        metric = best_cfg.get("metric")
        mode = best_cfg.get("mode", "max")
        if metric and summary_df is not None:
            metric_col = metric if str(metric).startswith("test_") else f"test_{metric}_mean"
            if not metric_col.endswith("_mean"):
                metric_col = f"{metric_col}_mean"
            if metric_col not in summary_df.columns:
                raise typer.BadParameter(f"best_model.metric='{metric}' 对应列不存在：{metric_col}")
            ascending = mode == "min"
            best_row = summary_df.sort_values(metric_col, ascending=ascending).iloc[0]
            best_model = best_row["model"]
            best_params = best_row["params_dict"] or {}

    if "fit" in operations:
        if data_mode == "outer_cv":
            if verbose:
                print("\n⏭ 当前为 outer_cv 模式，跳过 fit（无单一训练集）。若需保存模型，请改用 single_split/full 或 source=raw 后重新 train。")
        else:
            _fold_id, X, y, _X_test, _y_test = datasets[0]
            if y is None:
                raise typer.BadParameter("target.column not found in training data; fit requires y.")

            if training_cfg.get("fit_best_from_cv", True) and best_model is not None:
                models_to_fit = [best_model]
                model_params = {best_model: best_params}
            else:
                models_to_fit = models
                model_params = training_cfg.get("model_params", {}) or {}

            reg.fit(X, y, models=models_to_fit, model_params=model_params)

            if save_outputs:
                model_out_dir.mkdir(parents=True, exist_ok=True)
                for m, est in reg.fitted_.items():
                    model_pkg = {
                        "model": est,
                        "model_name": m,
                        "saved_at": datetime.utcnow().isoformat() + "Z",
                        "input_source": training_cfg.get("input", {}).get("source", "preprocessed"),
                        "training_input_raw": training_cfg.get("input", {}).get("raw", {}),
                        "training_input_processed": training_cfg.get("input", {}).get("processed", {}),
                        "target_column": cfg.get("preprocessing", {}).get("target", {}).get("column"),
                        "feature_columns": list(X.columns) if hasattr(X, "columns") else None,
                        "best_model": best_model,
                        "best_params": best_params,
                    }
                    model_path = model_out_dir / f"{m}.joblib"
                    joblib.dump(model_pkg, model_path)
                    if verbose:
                        print(f"Saved model package: {model_path}")

    if out_cfg.get("save_config_snapshot", True):
        snapshot_dir = model_out_dir if ("fit" in operations and data_mode != "outer_cv") else cv_out_dir
        save_yaml_snapshot(cfg, snapshot_dir, "train_config_used.yaml")


@app.command()
def predict(
    config: str = typer.Option(default_config_path, "-c", "--config", help="Config file path"),
):
    """Run regression prediction using a saved model package."""
    cfg = load_yaml(config)
    inf_cfg = cfg.get("predict", cfg.get("inference", {}))
    if not inf_cfg:
        raise typer.BadParameter("Missing `predict` section in config.")

    model_path = Path(inf_cfg.get("model_path", ""))
    if not model_path.exists():
        raise FileNotFoundError(
            f"模型文件不存在: {model_path}\n"
            "若此前使用 outer_cv 仅做了 cross_validate，则不会保存模型。"
            "请先用 single_split 或 full 或 source=raw 运行 train 以保存 .joblib，"
            "再将 predict.model_path 改为该文件路径后重新执行 predict。"
        )

    input_cfg = inf_cfg.get("input", {})
    data_path = input_cfg.get("path")
    if not data_path:
        raise typer.BadParameter("predict.input.path is required.")

    delimiter = input_cfg.get("delimiter", "\t")
    index_col = input_cfg.get("index_col")
    drop_cols = input_cfg.get("drop_cols", [])

    df = pd.read_csv(data_path, sep=delimiter)
    if index_col and index_col in df.columns:
        df.set_index(index_col, inplace=True)
    if drop_cols:
        df = df.drop(columns=drop_cols, errors="ignore")

    artifact = load_preprocess_artifact_for_predict(cfg)
    if artifact:
        X_df = preprocessing_test(
            df.copy(),
            cat_features=artifact.get("cat_features", []),
            categories=artifact.get("categories"),
            remove_features=artifact.get("remove_features"),
            ref_mean=artifact.get("ref_mean"),
            ref_std=artifact.get("ref_std"),
            ref_df=artifact.get("ref_df"),
            ref_df_imputed=artifact.get("ref_df_imputed"),
            num_features=artifact.get("num_features"),
            impute_method=artifact.get("imputation_method", "mice"),
        )
    else:
        X_df = df

    pkg = joblib.load(model_path)
    est = pkg["model"] if isinstance(pkg, dict) and "model" in pkg else pkg
    feature_cols = pkg.get("feature_columns") if isinstance(pkg, dict) else None

    X = X_df
    if feature_cols:
        missing = [c for c in feature_cols if c not in X.columns]
        if missing:
            raise typer.BadParameter(f"Inference input missing required columns: {missing}")
        X = X[feature_cols]

    out_cfg = inf_cfg.get("output", {})
    out_fmt = out_cfg.get("format", "tsv")
    out_dir = Path(out_cfg.get("directory", "Regression-result/prediction"))
    save_outputs = out_cfg.get("save", True)
    verbose = inf_cfg.get("logging", {}).get("verbose", True)

    pred = est.predict(X)
    pred_df = pd.DataFrame(
        {"index": X.index if hasattr(X, "index") else range(len(pred)), "prediction": pred}
    )
    if save_outputs:
        pred_path = out_dir / f"predictions.{out_fmt}"
        save_table(pred_df, pred_path, out_fmt)
        if verbose:
            print(f"Saved predictions: {pred_path}")
    if out_cfg.get("save_config_snapshot", True):
        save_yaml_snapshot(cfg, out_dir, "predict_config_used.yaml")


@app.command()
def config_template():
    """Show configuration template."""
    template = """
preprocessing:
  input:
    path: "Data/Raw/your_regression_data.csv"   # input file path
    delimiter: ","                              # CSV/TSV delimiter
    index_col: null                             # optional index column (null to skip)
    drop_cols: []                               # columns dropped before preprocessing
  target:
    column: "y"                                 # regression target column
  features:
    categorical: []                             # categorical columns for one-hot encoding
  imputation_method: "mice"                     # mean, median, knn, mice, none
  split:
    method: "kfold"                             # train_test, kfold, full
    n_splits: 5                                 # used by kfold
    train_test_ratio: 0.8                       # used only by train_test
    random_state: 42                            # split random seed
  output:
    directory: "Data/Processed"
    format: "tsv"                               # csv, tsv, parquet
    save: true
    save_row_id: true
    save_preprocess_artifact: false
    preprocess_artifact_name: "preprocess_artifact"
    save_config_snapshot: true
  logging:
    verbose: true

training:
  input:
    source: "preprocessed"                      # raw | preprocessed
    raw:
      path: "Data/Raw/your_regression_data.csv"
      delimiter: ","
      index_col: null
      drop_cols: []
      target_column: "y"
    processed:
      mode: "outer_cv"                          # single_split | full | outer_cv
      directory: "Data/Processed"
      format: "tsv"
      path: null
  random_state: 123
  operations: ["cross_validate", "fit"]         # cross_validate, fit
  models: ["ridge", "rf"]
  model_params: {}
  param_grid:
    ridge:
      alpha: [0.1, 1.0, 10.0]
    rf:
      n_estimators: [200, 500]
      max_depth: [null, 10, 20]
  cv: 5
  scoring: {"r2": "r2", "rmse": "neg_root_mean_squared_error", "mae": "neg_mean_absolute_error"}
  n_jobs: -1
  rename_single_score: true
  best_model:
    metric: "test_r2_mean"
    mode: "max"
  fit_best_from_cv: true
  output:
    cross_validate_dir: "Regression-result/cross_validate"
    model_dir: "Regression-result/model"
    format: "tsv"
    save: true
    save_config_snapshot: true

predict:
  model_path: "Regression-result/model/ridge.joblib"
  input:
    path: "Data/Raw/your_regression_data.csv"
    delimiter: ","
    index_col: null
    drop_cols: []
  preprocessing:
    use_artifact: false
    artifact_path: null
  output:
    directory: "Regression-result/prediction"
    format: "tsv"
    save: true
    save_config_snapshot: true
  logging:
    verbose: true
"""
    print(template)


if __name__ == "__main__":
    app()
