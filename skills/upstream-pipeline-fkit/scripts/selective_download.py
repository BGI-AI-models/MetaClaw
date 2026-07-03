#!/usr/bin/env python3
"""selective_download.py — Pre-download glob filter for FlowHub outputs.

The legacy finalize step did `fkit download <remote_outdir> <local> -r`, pulling
the entire per-job (or per-sample) tree — gigabytes of intermediate FASTQ /
BAM / kraken tables — only to discard 99% of it locally via materialize_stage's
`fnmatch`. For real cohort sizes that wastes disk + time and can exceed the
host's `.fkit_download/` budget, blocking finalize indefinitely (see the
metagenomics-full × 20 sample blocker from 2026-06-09).

This helper does the filter **before** the download:

  1. Read `upstream.output_to_stage` from pipelines.yaml — a `category → glob`
     map (e.g. `profile: "*/metaphlan4/out_dir/*.txt"`). Lists are accepted
     and treated as alternates.
  2. Decompose each glob into:
        leading_dir_glob   — the part that matches the FlowHub outdir name
                              (`openclaw-<job-id>` or `openclaw-<job-id>-<sid>`),
                              usually `*`;
        relative_dir       — the literal sub-path under that outdir
                              (e.g. `metaphlan4/out_dir/`);
        basename_glob      — the filename pattern (e.g. `*.txt`,
                              `*.profiled_metagenome.txt`).
     For a metagenomics-full sample, the concrete remote layout is
     `/output/openclaw-<job-id>-<SRR-id>/metaphlan4/out_dir/<SRR-id>.profiled_metagenome.txt`,
     which the default glob `*/metaphlan4/out_dir/*.txt` covers; and so does the
     stricter `*/metaphlan4/out_dir/*.profiled_metagenome.txt` if a pipeline
     wants to lock the suffix.
  3. `fkit ls <remote_outdir>/<relative_dir>` to enumerate candidates.
  4. `fkit download <remote_file>` for each entry whose basename matches
     `basename_glob`, into
        <local_root>/<outdir_basename>/<relative_dir>/<basename>
     so the post-download tree still matches `materialize_stage.py`'s
     `fnmatch(rel_path, glob)` semantics (the leading `*` lines up with
     `<outdir_basename>`).

Skipping & resumability: a file that already exists locally and is non-empty
is left alone, so a re-invocation is cheap. A summary JSON is written to
`<local_root>/.selective_download_<sid_or_job>.json` for audit / diff.

Designed to be called from `run.sh` (replacing the bulk download) AND directly
from `gateway/recover_finalize.sh` to unblock a job whose previous finalize ran
the old bulk path.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import yaml


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a subprocess, capturing output. Caller decides what to do on rc != 0."""
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def fkit_ls(fkit: str, remote_dir: str) -> list[dict]:
    """List immediate children of a remote FlowHub dir as a flat list of dicts.

    Returns [] (with a warning) if the directory doesn't exist — the caller
    treats that as "no files match" rather than fatal, because output_to_stage
    can legitimately point at sub-dirs that one flow version writes and another
    skips.
    """
    cp = _run([fkit, "ls", remote_dir, "--limit", "1000", "--json"])
    if cp.returncode != 0:
        sys.stderr.write(f"[selective_download] WARN  fkit ls {remote_dir!r} "
                         f"failed (rc={cp.returncode}); treating as empty\n")
        if cp.stderr:
            sys.stderr.write("    " + cp.stderr.strip().replace("\n", "\n    ") + "\n")
        return []
    try:
        payload = json.loads(cp.stdout or "null")
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[selective_download] WARN  fkit ls returned non-JSON: {e}\n")
        return []
    if isinstance(payload, dict):
        payload = payload.get("data", payload.get("files") or payload.get("items") or [])
    return payload or []


def _is_dir(entry: dict) -> bool:
    kind = str(entry.get("type") or entry.get("kind") or entry.get("fileType") or "").lower()
    return kind in {"dir", "folder", "directory"} \
        or entry.get("isFolder") is True or entry.get("isDir") is True


def decompose_glob(pattern: str) -> tuple[str, str, str]:
    """Split a glob into (leading_dir_glob, relative_dir, basename_glob).

    Conventions:
      *  Patterns in pipelines.yaml are anchored at FlowHub's `/output/` root.
      *  The first segment matches the per-job outdir (`openclaw-<id>` or
         `openclaw-<id>-<sid>`). It is almost always literally `*` but we keep
         it as a glob string for flexibility.
      *  Everything between the first segment and the final filename portion
         must be literal (no wildcards) — that's the relative_dir we list with
         `fkit ls`. If a pattern needs nested wildcards (e.g.
         `*/foo/*/bar/*.txt`), this raises; pipelines.yaml authors should
         flatten the pattern or split it into two output_to_stage entries.
    """
    parts = [p for p in pattern.split("/") if p != ""]
    if not parts:
        raise ValueError(f"empty glob: {pattern!r}")
    leading = parts[0]
    basename = parts[-1]
    middle = parts[1:-1]
    for seg in middle:
        if any(c in seg for c in "*?[]"):
            raise ValueError(
                f"glob {pattern!r} has a wildcard in the middle segment {seg!r}; "
                "selective_download only supports `<dir-glob>/<literal-path>/<file-glob>`. "
                "Flatten the pattern or add a second output_to_stage entry."
            )
    relative_dir = "/".join(middle)
    return leading, relative_dir, basename


def collect_matches(
    fkit: str,
    remote_outdir: str,
    glob_map: dict[str, str | list[str]],
) -> list[tuple[str, str, str]]:
    """For each (category, glob), enumerate matching remote files.

    Returns a list of (category, remote_file_abspath, local_relpath) where
    local_relpath is the path RELATIVE to the local download root and is
    constructed as `<outdir_basename>/<relative_dir>/<basename>` so that
    `materialize_stage.py`'s `fnmatch(rel_path, original_glob)` still matches.
    """
    outdir = remote_outdir.rstrip("/")
    outdir_basename = outdir.rsplit("/", 1)[-1]
    results: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()  # (category, local_relpath) — de-dupe across alt globs

    for category, raw_patterns in glob_map.items():
        patterns = raw_patterns if isinstance(raw_patterns, list) else [raw_patterns]
        for pattern in patterns:
            try:
                _, rel_dir, base_glob = decompose_glob(pattern)
            except ValueError as e:
                sys.stderr.write(f"[selective_download] SKIP  category={category}: {e}\n")
                continue
            remote_dir = outdir + "/" + rel_dir if rel_dir else outdir
            entries = fkit_ls(fkit, remote_dir)
            for entry in entries:
                if _is_dir(entry):
                    continue
                name = (entry.get("name") or entry.get("fileName") or "").strip().lstrip("/")
                if not name:
                    continue
                base = name.rsplit("/", 1)[-1]
                if not fnmatch.fnmatch(base, base_glob):
                    continue
                remote_file = remote_dir.rstrip("/") + "/" + base
                local_rel = "/".join(
                    p for p in (outdir_basename, rel_dir, base) if p
                )
                key = (category, local_rel)
                if key in seen:
                    continue
                seen.add(key)
                results.append((category, remote_file, local_rel))
    return results


def fkit_download_one(fkit: str, remote_file: str, local_target_dir: Path) -> bool:
    """Download a single remote file into local_target_dir. Returns True on success."""
    local_target_dir.mkdir(parents=True, exist_ok=True)
    # `fkit download <SRC> <DEST>` positional; no -r for a single file.
    cp = _run([fkit, "download", remote_file, str(local_target_dir)])
    if cp.returncode != 0:
        sys.stderr.write(f"[selective_download] FAIL  download {remote_file!r} "
                         f"→ {local_target_dir} (rc={cp.returncode})\n")
        if cp.stderr:
            sys.stderr.write("    " + cp.stderr.strip().replace("\n", "\n    ") + "\n")
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipelines", required=True, type=Path,
                    help="Path to registry/pipelines.yaml")
    ap.add_argument("--pipeline", required=True,
                    help="Pipeline key under `pipelines:` in pipelines.yaml")
    ap.add_argument("--remote-outdir", required=True,
                    help="FlowHub output dir, e.g. /output/openclaw-<job-id>-<sid>/")
    ap.add_argument("--local-root", required=True, type=Path,
                    help="Local download root (the per-sample $SCRATCH/<sid> for batch, "
                         "or $SCRATCH for single-job mode).")
    ap.add_argument("--fkit", default=os.environ.get("FKIT", "fkit"),
                    help="fkit binary (defaults to $FKIT or 'fkit' on PATH)")
    ap.add_argument("--summary", type=Path, default=None,
                    help="Optional path to write a JSON audit of what was downloaded.")
    args = ap.parse_args()

    pipelines = yaml.safe_load(args.pipelines.read_text())["pipelines"]
    pipe = pipelines.get(args.pipeline)
    if pipe is None:
        sys.stderr.write(f"[selective_download] FAIL  unknown pipeline: {args.pipeline}\n")
        return 2
    glob_map: dict = (pipe.get("upstream") or {}).get("output_to_stage") or {}
    if not glob_map:
        sys.stderr.write(f"[selective_download] WARN  pipeline {args.pipeline} has no "
                         "upstream.output_to_stage — nothing to download.\n")
        return 0

    matches = collect_matches(args.fkit, args.remote_outdir, glob_map)
    if not matches:
        sys.stderr.write(
            f"[selective_download] WARN  no files matched output_to_stage globs "
            f"under {args.remote_outdir!r}. Check the flow finished and the\n"
            f"   output_to_stage map in pipelines.yaml is current.\n"
        )

    summary: list[dict] = []
    n_dl = n_skip = n_fail = 0
    for category, remote_file, local_rel in matches:
        local_path = args.local_root / local_rel
        if local_path.is_file() and local_path.stat().st_size > 0:
            print(f"[selective_download] SKIP  exists  {local_rel}")
            n_skip += 1
            summary.append({"category": category, "remote": remote_file,
                            "local": str(local_path), "status": "skipped_existing"})
            continue
        print(f"[selective_download] GET   {category:<10}  {remote_file}")
        ok = fkit_download_one(args.fkit, remote_file, local_path.parent)
        if not ok:
            n_fail += 1
            summary.append({"category": category, "remote": remote_file,
                            "local": str(local_path), "status": "download_failed"})
            continue
        # fkit deposits the file under local_path.parent with its remote basename;
        # if the remote basename differs from our expected local basename (unlikely
        # but possible with renames), surface it rather than failing silently.
        expected = local_path
        if not expected.is_file():
            # Look for any new file under parent matching our basename glob; rename.
            candidates = [p for p in local_path.parent.iterdir() if p.is_file()]
            # Best-effort: if exactly one new file appeared, take it.
            if len(candidates) == 1:
                candidates[0].rename(expected)
            else:
                sys.stderr.write(
                    f"[selective_download] WARN  downloaded file not found at "
                    f"{expected}; saw {[p.name for p in candidates]}\n"
                )
                n_fail += 1
                summary.append({"category": category, "remote": remote_file,
                                "local": str(local_path), "status": "missing_after_download"})
                continue
        n_dl += 1
        summary.append({"category": category, "remote": remote_file,
                        "local": str(local_path), "status": "downloaded"})

    print(f"[selective_download] done — downloaded={n_dl} skipped={n_skip} "
          f"failed={n_fail} (total matched={len(matches)})")

    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps({
            "remote_outdir": args.remote_outdir,
            "pipeline":      args.pipeline,
            "n_matched":     len(matches),
            "n_downloaded":  n_dl,
            "n_skipped":     n_skip,
            "n_failed":      n_fail,
            "entries":       summary,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    # Soft exit: a partial result is recoverable (re-run is cheap due to skip-existing).
    # Hard-fail only if the user asked for files but every download failed.
    if matches and n_fail and not n_dl and not n_skip:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
