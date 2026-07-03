#!/usr/bin/env python3
"""Materialize FlowHub output into the local job's `stage/` directory.

Reads `upstream.output_to_stage` glob map from `pipelines.yaml`, scans the
downloaded `/openclaw/<job-id>/output/` tree, and copies (hardlinks where
possible) each match into `stage/<category>/`. Writes `stage/manifest.json` in
the same schema used by the local upstream (one section per category, sample
name as the key when discoverable).

The output port layouts on FlowHub mirror the per-tool subdirectories
documented in their flow templates, so glob patterns like
`*/fastp/*_fastp.json` work reliably without needing to inspect the flow
metadata at materialization time.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import sys
from pathlib import Path

import yaml


SAMPLE_RE = re.compile(r"(?P<sample>[A-Za-z0-9][A-Za-z0-9._-]*?)(?:_R?[12]|_clean|_fastp|_bracken|_humann|_kraken|\.|$)")


def sample_from_name(filename: str) -> str:
    """Best-effort extraction of a sample identifier from a filename."""
    base = filename.split("/")[-1]
    base = re.sub(r"\.(gz|bz2)$", "", base)
    base = re.sub(r"\.(json|tsv|csv|fastq|fq|fa|fasta|html|gff|annotations|bracken|kreport|kraken|out)$", "", base)
    m = SAMPLE_RE.match(base)
    return m.group("sample") if m else base


def link_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--pipeline", required=True)
    ap.add_argument("--pipelines", required=True, type=Path)
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--stage", required=True, type=Path)
    ap.add_argument("--sample-id", type=str, default="",
                    help="Batch per-sample mode. When set, all matched files "
                         "land at stage/<category>/<sample-id>/<basename> "
                         "(per-sample subdir to avoid collisions across "
                         "samples that produce identically-named outputs), "
                         "and instead of overwriting stage/manifest.json a "
                         "per-sample fragment is written to "
                         "stage/.manifest_fragments/<sample-id>.json. The "
                         "batch driver in run.sh merges fragments into the "
                         "final manifest after all samples finalize.")
    args = ap.parse_args()

    pipelines = yaml.safe_load(args.pipelines.read_text())["pipelines"]
    upstream_cfg = (pipelines[args.pipeline].get("upstream") or {})
    glob_map: dict[str, str] = upstream_cfg.get("output_to_stage") or {}
    if not glob_map:
        print(f"no output_to_stage map for pipeline={args.pipeline}; stage/ will be empty", file=sys.stderr)
        if args.sample_id:
            frag_dir = args.stage / ".manifest_fragments"
            frag_dir.mkdir(parents=True, exist_ok=True)
            (frag_dir / f"{args.sample_id}.json").write_text(json.dumps(
                {"sample_id": args.sample_id, "categories": {}}, indent=2))
        else:
            manifest = {"job_id": args.job_id, "pipeline": args.pipeline, "samples": []}
            (args.stage / "manifest.json").write_text(json.dumps(manifest, indent=2))
        return 0

    args.stage.mkdir(parents=True, exist_ok=True)
    src_root = args.src.resolve()
    all_files = [p for p in src_root.rglob("*") if p.is_file()]
    rel_files = [(p, str(p.relative_to(src_root)).replace(os.sep, "/")) for p in all_files]

    if args.sample_id:
        # ── Batch per-sample mode ───────────────────────────────────────
        categories: dict[str, list[str]] = {}
        for category, pattern in glob_map.items():
            cat_dir = args.stage / category / args.sample_id
            cat_dir.mkdir(parents=True, exist_ok=True)
            paths: list[str] = []
            for path, rel in rel_files:
                if fnmatch.fnmatch(rel, pattern):
                    target = cat_dir / path.name
                    link_or_copy(path, target)
                    paths.append(str(target.relative_to(args.stage)))
            categories[category] = sorted(paths)
            print(f"  [{args.sample_id}] {category}: {len(paths)} file(s) → {cat_dir}")
        frag_dir = args.stage / ".manifest_fragments"
        frag_dir.mkdir(parents=True, exist_ok=True)
        frag_path = frag_dir / f"{args.sample_id}.json"
        frag_path.write_text(json.dumps(
            {"sample_id": args.sample_id, "categories": categories},
            indent=2, ensure_ascii=False))
        print(f"manifest fragment: {frag_path}")
        return 0

    # ── Legacy single-job mode (unchanged) ──────────────────────────────
    manifest: dict[str, object] = {"job_id": args.job_id, "pipeline": args.pipeline}
    samples: set[str] = set()
    for category, pattern in glob_map.items():
        cat_dir = args.stage / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        cat_index: dict[str, str] = {}
        for path, rel in rel_files:
            if fnmatch.fnmatch(rel, pattern):
                target = cat_dir / path.name
                link_or_copy(path, target)
                sample = sample_from_name(path.name)
                samples.add(sample)
                cat_index[sample] = str(target.relative_to(args.stage))
        manifest[category] = cat_index
        print(f"  {category}: {len(cat_index)} file(s) → {cat_dir}")

    manifest["samples"] = sorted(samples)
    (args.stage / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"manifest: {args.stage / 'manifest.json'} (samples={len(samples)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

