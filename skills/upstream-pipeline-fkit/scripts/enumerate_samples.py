#!/usr/bin/env python3
"""Enumerate samples in a FlowHub directory listing for a batch upstream pipeline.

Input data for upstream analysis lives on FlowHub (never copied locally). The
caller (`run.sh`) produces a "comprehensive listing" JSON by running
`fkit ls <flowhub-path>` — and, for nested layouts, additionally
`fkit ls <subdir>` for each top-level folder — merging entries into a single
`file_search.json`-shaped document where each entry's `name` is the path
RELATIVE to the FlowHub DATA_DIR (e.g. ``sampleA/R1.fq.gz`` or ``metadata.tsv``)
and `type` is ``file`` or ``folder``.

This script consumes that listing and produces:

    {
      "data_dir":    "/Flowhub/abs/path",       # FlowHub path the listing came from
      "detect_mode": "subdirectories" | "paired_by_basename" | "single_file",
      "samples":     {"sampleA": ["sampleA/R1.fq.gz", ...], ...},   # relpaths
      "shared":      ["metadata.tsv", "ref_db", ...]                # relpaths
    }

The downstream consumer (run.sh + build_spec.py) uses **basenames** of these
relpaths to slice `file_search.json` per sample. Relpaths are preserved so the
audit trail makes the FlowHub layout obvious.

Detection modes (tried in order; first mode that finds ≥1 sample wins):

  subdirectories
      Each top-level subdir on FlowHub (``type == folder`` at depth 0) is one
      sample. Sample files = every regular file recorded under that subdir in
      the listing (paths with that subdir as first component). Top-level
      files (no path separator) are shared.

  paired_by_basename
      Group sequencing-like top-level files by the common stem before
      `_R1` / `_R2` (also `_1` / `_2`, `_read1` / `_read2`,
      `_forward` / `_reverse` — see PAIR_RE). Sample ID = the stem. Top-level
      non-matching files (metadata, reference DBs) → shared.

  single_file
      Every top-level sequencing-like file is its own sample.
      sample_id = the file stem with all extensions stripped
      (e.g. `sampleX.fastq.gz` → `sampleX`). Other top-level files → shared.

Rules:
  - "Sequencing-like" = matches SEQ_RE below. Metadata, reference DBs, sample
    sheets etc. are NEVER swept into samples by single_file or
    paired_by_basename modes — they fall through to `shared`.
  - sample IDs are sanitized to ``[A-Za-z0-9._-]+`` (FlowHub names must be
    URL/path-safe). Conflicts after sanitization fail loudly.
  - Returned paths are RELATIVE to DATA_DIR (matching the `name` field of the
    input listing). The caller resolves them back to fileIds via the same
    listing.

Exit codes:
  0 — at least one sample found.
  2 — no sample found by any mode. The pipeline is misconfigured for batch
      OR the FlowHub DATA_DIR is empty.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml


# Top-level filename matchers ────────────────────────────────────────────

# Things a metagenomic pipeline considers raw sequencing data.
SEQ_RE = re.compile(
    r"\.(?:fastq|fq|bam|cram|sra)(?:\.(?:gz|bz2|xz))?$",
    re.IGNORECASE,
)

# Paired-end suffix detection. Matches both `_R1` / `_R2` Illumina style and
# loose `_1` / `_2` / `_read1` / `_forward` variants.
PAIR_RE = re.compile(
    r"^(?P<stem>.+?)[._-](?:R?[12]|read[12]|fq[12]|input[12]|forward|reverse)"
    r"(?:[._-].*)?\.(?:fastq|fq|bam|cram|sra)(?:\.(?:gz|bz2|xz))?$",
    re.IGNORECASE,
)

# Sample IDs end up in FlowHub spec.name + spec.outputDir → must be safe.
SAFE_SAMPLE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")

_DIR_KIND_VALUES = {"dir", "folder", "directory"}


# ── helpers ─────────────────────────────────────────────────────────────


def sanitize(sample_id: str) -> str:
    return SAFE_SAMPLE_ID_RE.sub("_", sample_id).strip("._-") or "sample"


def is_seq_file(name: str) -> bool:
    return bool(SEQ_RE.search(name))


def strip_seq_ext(name: str) -> str:
    return SEQ_RE.sub("", name)


def unwrap(obj):
    """fkit responses sometimes wrap the payload in {data: ...}."""
    if isinstance(obj, dict) and "data" in obj:
        return obj["data"]
    return obj


def entry_is_dir(it: dict) -> bool:
    kind = str(it.get("type") or it.get("kind") or it.get("fileType") or "").lower()
    if kind in _DIR_KIND_VALUES:
        return True
    if it.get("isFolder") is True or it.get("isDir") is True:
        return True
    return False


def load_listing(path: Path) -> list[dict]:
    """Return a flat list of {name, type, fileId} entries (name is a relpath)."""
    payload = unwrap(json.loads(path.read_text()))
    if isinstance(payload, dict):
        items = payload.get("files") or payload.get("items") or []
    else:
        items = payload or []
    out = []
    for it in items:
        name = (it.get("name") or it.get("fileName") or "").strip()
        if not name:
            continue
        # Normalize FlowHub-style separators.
        name = name.replace("\\", "/").lstrip("/")
        out.append({
            "name":   name,
            "type":   "folder" if entry_is_dir(it) else "file",
            "fileId": it.get("fileId") or it.get("id") or "",
        })
    return out


def split_top_level(entries: list[dict]) -> tuple[list[dict], list[dict], dict[str, list[dict]]]:
    """Bucket entries into (top_files, top_dirs, nested_by_topdir).

    nested_by_topdir maps a top-level folder name → list of entries whose
    relpath starts with that folder. Useful for ``subdirectories`` mode.
    """
    top_files: list[dict] = []
    top_dirs:  list[dict] = []
    nested: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        if "/" not in e["name"]:
            if e["type"] == "folder":
                top_dirs.append(e)
            else:
                top_files.append(e)
        else:
            head = e["name"].split("/", 1)[0]
            nested[head].append(e)
    return top_files, top_dirs, dict(nested)


# ── detection modes ─────────────────────────────────────────────────────


def detect_subdirectories(entries: list[dict]) -> tuple[dict[str, list[str]], list[str]]:
    top_files, top_dirs, nested = split_top_level(entries)
    samples: dict[str, list[str]] = {}
    for d in sorted(top_dirs, key=lambda e: e["name"]):
        files = [e["name"] for e in nested.get(d["name"], []) if e["type"] == "file"]
        if files:
            samples[sanitize(d["name"])] = sorted(files)
    shared = sorted(e["name"] for e in top_files)
    return samples, shared


def detect_paired_by_basename(entries: list[dict]) -> tuple[dict[str, list[str]], list[str]]:
    top_files, _, _ = split_top_level(entries)
    grouped: dict[str, list[str]] = defaultdict(list)
    leftover: list[str] = []
    for e in sorted(top_files, key=lambda x: x["name"]):
        m = PAIR_RE.match(e["name"])
        if m:
            grouped[sanitize(m.group("stem"))].append(e["name"])
        else:
            leftover.append(e["name"])
    samples = {sid: sorted(files) for sid, files in grouped.items()}
    return samples, leftover


def detect_single_file(entries: list[dict]) -> tuple[dict[str, list[str]], list[str]]:
    top_files, _, _ = split_top_level(entries)
    samples: dict[str, list[str]] = {}
    leftover: list[str] = []
    for e in sorted(top_files, key=lambda x: x["name"]):
        if is_seq_file(e["name"]):
            sid = sanitize(strip_seq_ext(e["name"]))
            samples.setdefault(sid, []).append(e["name"])
        else:
            leftover.append(e["name"])
    return samples, leftover


MODES = {
    "subdirectories":     detect_subdirectories,
    "paired_by_basename": detect_paired_by_basename,
    "single_file":        detect_single_file,
}

DEFAULT_DETECT_ORDER = ["subdirectories", "paired_by_basename", "single_file"]


# ── main ────────────────────────────────────────────────────────────────


def resolve_modes(args) -> list[str]:
    if args.modes:
        modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    else:
        try:
            pipelines = yaml.safe_load(args.pipelines.read_text())["pipelines"]
            cfg = ((pipelines[args.pipeline].get("upstream") or {})
                   .get("batch") or {})
            modes = cfg.get("detect") or DEFAULT_DETECT_ORDER
        except Exception:
            modes = DEFAULT_DETECT_ORDER

    unknown = [m for m in modes if m not in MODES]
    if unknown:
        print(f"enumerate_samples: unknown detect mode(s): {unknown!r}; "
              f"valid={sorted(MODES)}", file=sys.stderr)
        sys.exit(2)
    return modes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listing", required=True, type=Path,
                    help="Comprehensive FlowHub listing JSON (fkit ls output, "
                         "recursively expanded for any top-level folders). "
                         "Entry `name` is a path relative to DATA_DIR.")
    ap.add_argument("--data-dir", required=True, type=str,
                    help="FlowHub absolute path the listing came from "
                         "(recorded in the output; not touched locally).")
    ap.add_argument("--pipelines", type=Path,
                    help="pipelines.yaml; used to read upstream.batch.detect "
                         "when --modes is omitted")
    ap.add_argument("--pipeline",  type=str,
                    help="pipeline name (paired with --pipelines)")
    ap.add_argument("--modes", type=str,
                    help="Explicit comma-separated mode list "
                         "(overrides pipelines.yaml). "
                         f"Available: {','.join(MODES)}")
    ap.add_argument("--out", type=Path,
                    help="Where to write the JSON result (default: stdout)")
    args = ap.parse_args()

    if not args.listing.is_file():
        print(f"enumerate_samples: listing not found: {args.listing}", file=sys.stderr)
        return 2

    entries = load_listing(args.listing)
    if not entries:
        print(f"enumerate_samples: empty FlowHub listing at {args.data_dir} "
              f"(file {args.listing}) — nothing to enumerate.", file=sys.stderr)
        return 2

    modes = resolve_modes(args)

    chosen_mode = None
    samples: dict[str, list[str]] = {}
    shared:  list[str] = []
    for mode in modes:
        s, sh = MODES[mode](entries)
        if s:
            chosen_mode = mode
            samples, shared = s, sh
            break

    if not samples:
        print(f"enumerate_samples: no samples detected in FlowHub path "
              f"{args.data_dir} via modes {modes}. Check the remote layout "
              f"and upstream.batch.detect order.", file=sys.stderr)
        return 2

    result = {
        "data_dir":    args.data_dir,         # FlowHub absolute path (string, not Path)
        "detect_mode": chosen_mode,
        "samples":     {sid: files for sid, files in sorted(samples.items())},
        "shared":      sorted(shared),
    }
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload)
        print(f"enumerate_samples: {len(samples)} sample(s) via "
              f"{chosen_mode} → {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
