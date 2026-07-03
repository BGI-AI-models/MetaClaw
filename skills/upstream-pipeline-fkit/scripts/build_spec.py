#!/usr/bin/env python3
"""Build a FlowHub `pipeline create` spec JSON for a job.

For every OPEN input port declared by `fkit flow inspect`, the script:

  1. Classifies the port as **file** or **directory**.
  2. Picks an upload that has the matching type (so a directory-expecting
     port never receives a single-file fileId, and vice versa).
  3. Falls back to the flow's own default file/directory when no upload
     matches.
  4. Records every port — bound or unbound, required or optional — in a
     printed binding table so the agent can show it to the user.
  5. Fails (exit 2) when any REQUIRED open port is unbound. Optional ports
     left empty exit 0 with a WARN line.

Binding precedence per port:

  (a) **Declarative routing** — `pipelines.yaml` ›
      `upstream.input_routing`. Each entry binds files (or directories)
      matched by glob against the basename to a specific port:

          input_routing:
            - { port: read1,      glob: "*_R1*.f*q*" }
            - { port: read2,      glob: "*_R2*.f*q*" }
            - { port: ref_db,     glob: "human_ref*", task: bowtie2 }
            - { port: contigs,    glob: "*.contigs.fa", required: false }
            # `glob` may be a LIST — matches if ANY pattern matches (OR), so a
            # file with a variable name need not be renamed on FlowHub:
            - { port: ref_genome, glob: ["*.fna", "*.fa", "*.fasta"] }

      Per-entry flags (all optional):
        required:    default true; false → no error if no match
        allow_reuse: default false; true → same upload can feed multiple ports
        multi:       default false; true → bind ALL matches as separate entries
        task:        scope to a single taskName when port names repeat
        use_default: default false; true → SKIP Phases 1–2 for this port and
                     fall straight through to Phase 3 (force the flow's
                     bundled default file/dir). Glob is ignored. Useful when
                     DATA_DIR happens to contain a file that would otherwise
                     match but you want the flow's curated reference instead
                     (e.g. SILVA bundled with the flow vs your loose copy).
        default:     default true; false → SKIP Phase 3 fallback for this
                     port. If Phases 1–2 don't bind it, leave it unbound
                     (required ports then hard-fail; optional ports get an
                     explicit "no fallback" entry in bindings_report.json).
                     Useful for production pipelines that must never silently
                     accept flow defaults.

  (b) **Heuristic** — for any port not covered by routing: try the port's
      `namePattern` (anchored fnmatch), then R1/R2 hints from the port name,
      considering only uploads whose own type (file vs directory) matches the
      port's expected type. Already-consumed fileIds are skipped.

  (c) **Flow default** — for ports still empty, use
      `defaultFiles[0].fileId` (or `defaultDirs[0].fileId`) from
      `flow inspect`. Required because spec.inputs replaces the template's
      inputFiles wholesale.

Strict rules:
  - Only bind to ports whose node has `openStatus == 1`.
  - File-typed ports never receive a directory fileId; directory-typed ports
    never receive a single-file fileId.
  - Fail loudly on missing REQUIRED inputs — silent fallthrough was the
    historical cause of "same fileId bound to every port".
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

import yaml


# ── helpers ──────────────────────────────────────────────────────────────

def load_json(path: Path) -> object:
    return json.loads(path.read_text())


def unwrap(obj):
    """fkit responses sometimes wrap the payload in {data: ...}."""
    if isinstance(obj, dict) and "data" in obj and not {"inputs", "nodes", "params"} & obj.keys():
        return obj["data"]
    return obj


_DIR_KIND_VALUES = {"dir", "folder", "directory"}
_FILE_KIND_VALUES = {"file", "files", "single", "regular"}


def is_dir_entry(it: dict) -> bool:
    """True if a remote `fkit ls` entry represents a directory, not a file."""
    kind = str(it.get("type") or it.get("kind") or it.get("fileType") or "").lower()
    if kind in _DIR_KIND_VALUES:
        return True
    if it.get("isFolder") is True or it.get("isDir") is True:
        return True
    return False


def index_remote(file_search: object) -> dict[str, tuple[str, bool]]:
    """Return {basename: (fileId, is_dir)} for every entry returned by `fkit ls`.

    Both files and directories are kept — port-type filtering happens at
    bind time, not at index time, so directory-expecting ports can still
    receive a directory upload.
    """
    payload = unwrap(file_search)
    items = payload if isinstance(payload, list) else payload.get("files") or payload.get("items") or []
    out: dict[str, tuple[str, bool]] = {}
    for it in items:
        name = it.get("name") or it.get("fileName") or ""
        fid = it.get("fileId") or it.get("id") or ""
        if not name or not fid:
            continue
        out[name.rsplit("/", 1)[-1]] = (fid, is_dir_entry(it))
    return out


def port_expects_dir(inp: dict) -> bool:
    """Best-effort: True if this flow input port wants a directory, not a file.

    FlowHub flows expose the port's intended type under any of several keys
    depending on flow version. Returns False (file) when nothing matches.
    """
    for field in ("inputType", "type", "dataType", "kind", "acceptType", "portType"):
        v = inp.get(field)
        if isinstance(v, str):
            vl = v.lower()
            if vl in _DIR_KIND_VALUES:
                return True
            if vl in _FILE_KIND_VALUES:
                return False
    if inp.get("isDirectory") is True or inp.get("acceptDirectory") is True:
        return True
    if inp.get("isFolder") is True:
        return True
    return False


def port_is_required(inp: dict) -> bool:
    """True unless the flow explicitly marks the port optional."""
    if inp.get("required") is False:
        return False
    if inp.get("optional") is True:
        return False
    return True


def default_fileid(inp: dict, want_dir: bool) -> str | None:
    """Pick the first applicable default fileId for this port."""
    # FlowHub often uses `defaultFiles` for files and a separate `defaultDirs`
    # for directories. Try both, in type-preferred order.
    primary = "defaultDirs" if want_dir else "defaultFiles"
    secondary = "defaultFiles" if want_dir else "defaultDirs"
    for field in (primary, secondary):
        for entry in (inp.get(field) or []):
            fid = entry.get("fileId")
            if fid:
                return fid
    return None


READ1_RE = re.compile(r"(?:^|[._-])(?:R?1|read1|fq1|input1|forward)(?:[._-]|$)", re.IGNORECASE)
READ2_RE = re.compile(r"(?:^|[._-])(?:R?2|read2|fq2|input2|reverse)(?:[._-]|$)", re.IGNORECASE)


def glob_match(name: str, pattern) -> bool:
    """Anchored fnmatch — the pattern must match the WHOLE basename.

    `pattern` may be a single glob string or a list of globs; a list matches
    when ANY of its patterns matches (logical OR). This lets a routing entry
    tolerate filename variation (e.g. a reference genome that may arrive as
    `ref_genome.fna`, `*_genomic.fna`, `*.fa`, or `*.fasta`) without forcing
    the user to rename the file on FlowHub.
    """
    if not pattern:
        return False
    patterns = [pattern] if isinstance(pattern, str) else list(pattern)
    return any(fnmatch.fnmatchcase(name, p) for p in patterns if p)


def filter_candidates(remote: dict[str, tuple[str, bool]],
                      want_dir: bool,
                      consumed: set[str]) -> list[tuple[str, str]]:
    """Return [(name, fileId), …] of unconsumed uploads matching the port type."""
    out = []
    for name in sorted(remote):
        fid, is_dir = remote[name]
        if fid in consumed:
            continue
        if is_dir != want_dir:
            continue
        out.append((name, fid))
    return out


def heuristic_pick(port_name: str, name_pattern: str,
                   candidates: list[tuple[str, str]]) -> str | None:
    if name_pattern:
        for name, fid in candidates:
            if glob_match(name, name_pattern):
                return fid
    want_r1 = bool(READ1_RE.search(port_name))
    want_r2 = bool(READ2_RE.search(port_name))
    if want_r1 or want_r2:
        for name, fid in candidates:
            if want_r1 and READ1_RE.search(name):
                return fid
            if want_r2 and READ2_RE.search(name):
                return fid
    return None


def filename_for(fid: str, remote: dict[str, tuple[str, bool]]) -> str:
    for name, (f, _) in remote.items():
        if f == fid:
            return name
    return "<unknown>"


# ── main ─────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--pipeline", required=True)
    ap.add_argument("--inspect", required=True, type=Path)
    ap.add_argument("--files", required=True, type=Path)
    ap.add_argument("--pipelines", required=True, type=Path)
    ap.add_argument("--overrides", required=True, type=Path)
    ap.add_argument("--flow-vid", required=True)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--report", type=Path,
                    help="Where to write the structured bindings_report.json. "
                         "If omitted, defaults to <output>.parent / "
                         "'bindings_report.json' (or "
                         "'bindings_report_<sample-id>.json' in batch mode).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Plan mode: write the spec to --output but tag the "
                         "report `mode=plan` and skip the closing "
                         "`wrote <output>` success line so the caller knows "
                         "no FlowHub submission should follow.")
    ap.add_argument("--sample-id", type=str, default="",
                    help="Batch mode: bind for ONE sample. spec.name and "
                         "spec.outputDir become openclaw-<job-id>-<sample-id> "
                         "(the suffix routes each FlowHub job's outputs into "
                         "its own /output/openclaw-<job-id>-<sample-id>/ dir). "
                         "When empty, the script runs in single-job mode.")
    args = ap.parse_args()

    inspect = unwrap(load_json(args.inspect))
    remote = index_remote(load_json(args.files))

    pipelines_yaml = yaml.safe_load(args.pipelines.read_text())["pipelines"]
    upstream_cfg = (pipelines_yaml[args.pipeline].get("upstream") or {})
    default_params = upstream_cfg.get("default_params") or []
    routing = upstream_cfg.get("input_routing") or []

    overrides = {}
    if args.overrides.exists():
        try:
            overrides = yaml.safe_load(args.overrides.read_text()) or {}
        except yaml.YAMLError:
            overrides = {}

    open_nodes = {
        n.get("nodeName"): int(n.get("openStatus", 0))
        for n in (inspect.get("nodes") or [])
    }

    # Classify every open port up front.
    # report[(task, port)] = {raw, expects_dir, required, source, fileId|None, filename|None}
    report: dict[tuple[str, str], dict] = {}
    for inp in inspect.get("inputs") or []:
        task = inp.get("taskName")
        port = inp.get("name")
        if open_nodes.get(task, 0) != 1:
            continue
        report[(task, port)] = {
            "raw": inp,
            "expects_dir": port_expects_dir(inp),
            "required": port_is_required(inp),
            "source": None,         # "routing" | "heuristic" | "default" | None
            "fileId": None,
            "filename": None,
        }

    inputs_out: list[dict] = []
    consumed: set[str] = set()
    errors: list[str] = []

    # Per-port policy derived from routing entries with use_default / default
    # flags. These short-circuit binding without needing a glob.
    #   force_default[(t,p)] = True  → skip Phases 1–2, only Phase 3 may bind
    #   no_default[(t,p)]    = True  → Phase 3 must NOT bind; leave unbound
    force_default: set[tuple[str, str]] = set()
    no_default:    set[tuple[str, str]] = set()
    for entry in routing:
        port_filter = entry.get("port")
        task_filter = entry.get("task")
        if entry.get("use_default") is True:
            for (t, p) in report:
                if (port_filter is None or p == port_filter) \
                   and (task_filter is None or t == task_filter):
                    force_default.add((t, p))
        if entry.get("default") is False:
            for (t, p) in report:
                if (port_filter is None or p == port_filter) \
                   and (task_filter is None or t == task_filter):
                    no_default.add((t, p))

    def bind(t: str, p: str, fid: str, source: str) -> None:
        inputs_out.append({"taskName": t, "taskPortName": p, "fileId": fid})
        consumed.add(fid)
        info = report[(t, p)]
        info["source"] = source
        info["fileId"] = fid
        info["filename"] = filename_for(fid, remote)

    # ── Phase 1: declarative input_routing ───────────────────────────────
    for entry in routing:
        # use_default / default-only entries have no glob to apply here.
        if entry.get("use_default") is True or "glob" not in entry:
            if "glob" not in entry and entry.get("use_default") is not True \
               and entry.get("default") is not False:
                errors.append(f"input_routing entry missing `glob` "
                              f"(and no use_default / default flag): {entry!r}")
            continue
        port_filter = entry.get("port")
        task_filter = entry.get("task")
        glob = entry.get("glob")
        required = entry.get("required", True)
        allow_reuse = entry.get("allow_reuse", False)
        multi = entry.get("multi", False)

        if not glob:
            errors.append(f"input_routing entry missing `glob`: {entry!r}")
            continue

        matched_ports = [
            (t, p) for (t, p) in report
            if (port_filter is None or p == port_filter)
            and (task_filter is None or t == task_filter)
        ]
        if not matched_ports:
            msg = (f"input_routing port={port_filter} task={task_filter}: "
                   f"no open port matches in flow_inspect.json")
            if required:
                errors.append(msg)
            else:
                print(f"WARN: {msg}", file=sys.stderr)
            continue

        for (t, p) in matched_ports:
            if (t, p) in force_default:
                continue  # use_default: true takes precedence over this glob
            info = report[(t, p)]
            want_dir = info["expects_dir"]
            # Candidates: matching type + not consumed (unless allow_reuse).
            candidates = [
                (name, fid) for name, (fid, is_dir) in sorted(remote.items())
                if is_dir == want_dir and (allow_reuse or fid not in consumed)
            ]
            matched_files = [(n, f) for n, f in candidates if glob_match(n, glob)]
            if not matched_files:
                if required:
                    type_label = "directory" if want_dir else "file"
                    errors.append(
                        f"input_routing port={p} task={t}: no {type_label} matches glob "
                        f"'{glob}' (uploads: {sorted(remote)})"
                    )
                continue
            picks = matched_files if multi else matched_files[:1]
            for name, fid in picks:
                if allow_reuse:
                    # Don't consume — but still record the binding.
                    inputs_out.append({"taskName": t, "taskPortName": p, "fileId": fid})
                    info["source"] = "routing"
                    info["fileId"] = fid
                    info["filename"] = name
                else:
                    bind(t, p, fid, "routing")

    # ── Phase 2: per-port heuristic for ports still empty ────────────────
    for (t, p), info in report.items():
        if info["source"] is not None:
            continue
        if (t, p) in force_default:
            continue  # use_default: true takes precedence over heuristics
        candidates = filter_candidates(remote, info["expects_dir"], consumed)
        picked = heuristic_pick(p or "", info["raw"].get("namePattern") or "", candidates)
        if picked:
            bind(t, p, picked, "heuristic")

    # ── Phase 3: flow-provided defaults ──────────────────────────────────
    for (t, p), info in report.items():
        if info["source"] is not None:
            continue
        if (t, p) in no_default:
            continue  # default: false explicitly forbids the fallback
        fid = default_fileid(info["raw"], info["expects_dir"])
        if fid:
            # Default fileId is FlowHub-side — it isn't in `remote`. We still
            # record it; filename is the default's display name if present.
            defaults = (info["raw"].get("defaultDirs") if info["expects_dir"]
                        else info["raw"].get("defaultFiles")) or []
            display = (defaults[0].get("name") or defaults[0].get("fileName")
                       or "(flow default)") if defaults else "(flow default)"
            inputs_out.append({"taskName": t, "taskPortName": p, "fileId": fid})
            info["source"] = "default"
            info["fileId"] = fid
            info["filename"] = display

    # ── Required check + report ──────────────────────────────────────────
    type_lbl = lambda d: "DIR " if d else "FILE"
    req_lbl  = lambda r: "required" if r else "optional"

    print("Port → input bindings:")
    if not report:
        print("  (flow exposes no open input ports)")
    for (t, p) in sorted(report):
        info = report[(t, p)]
        tag = f"[{type_lbl(info['expects_dir'])}, {req_lbl(info['required'])}]"
        if info["source"]:
            print(f"  {t}.{p:<20} {tag}  ←  {info['filename']}  ({info['source']})  [{info['fileId']}]")
        else:
            print(f"  {t}.{p:<20} {tag}  ←  (unbound)")

    missing_required = [
        (t, p) for (t, p), info in report.items()
        if info["source"] is None and info["required"]
    ]
    missing_optional = [
        (t, p) for (t, p), info in report.items()
        if info["source"] is None and not info["required"]
    ]
    if missing_optional:
        print("WARN: optional inputs left unbound (flow may use built-in fallback):",
              file=sys.stderr)
        for (t, p) in missing_optional:
            info = report[(t, p)]
            print(f"  - {t}.{p}  [{type_lbl(info['expects_dir']).strip()}]", file=sys.stderr)
    if missing_required:
        errors.append(
            "Missing REQUIRED inputs (no upload match, no flow default): "
            + ", ".join(f"{t}.{p}" for (t, p) in missing_required)
        )

    # ── Structured bindings report (consumed by run.sh / agent) ──────────
    # Always written, even on error, so the caller can read it back without
    # parsing stdout/stderr. `mode=plan` lets downstream code know whether
    # this was a dry run (no submission should follow). In batch mode the
    # default report path gains a `_<sample-id>` suffix so per-sample reports
    # do not overwrite each other.
    if args.report:
        report_path = args.report
    elif args.sample_id:
        report_path = args.output.parent / f"bindings_report_{args.sample_id}.json"
    else:
        report_path = args.output.parent / "bindings_report.json"
    def _entry(t: str, p: str) -> dict:
        info = report[(t, p)]
        return {
            "task":        t,
            "port":        p,
            "type":        "DIR" if info["expects_dir"] else "FILE",
            "required":    bool(info["required"]),
            "source":      info["source"],     # routing | heuristic | default | None
            "fileId":      info["fileId"],
            "filename":    info["filename"],
            "force_default": (t, p) in force_default,
            "no_default":    (t, p) in no_default,
        }
    structured = {
        "mode":        "plan" if args.dry_run else "submit",
        "job_id":      args.job_id,
        "sample_id":   args.sample_id or None,
        "pipeline":    args.pipeline,
        "flow_vid":    args.flow_vid,
        "bindings":    [_entry(t, p) for (t, p) in sorted(report)],
        "defaults_used":    [{"task": t, "port": p, "filename": report[(t, p)]["filename"]}
                              for (t, p) in sorted(report) if report[(t, p)]["source"] == "default"],
        "missing_required": [{"task": t, "port": p} for (t, p) in sorted(missing_required)],
        "missing_optional": [{"task": t, "port": p} for (t, p) in sorted(missing_optional)],
        "errors":      list(errors),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(structured, indent=2, ensure_ascii=False))

    if errors:
        print("ERRORS:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 2

    # ── params ───────────────────────────────────────────────────────────
    params_out = []
    for entry in default_params:
        task, key, val = entry.get("taskName"), entry.get("paramKey"), entry.get("paramValue")
        if not (task and key):
            continue
        ov = (overrides.get(task) or {}).get(key)
        params_out.append({
            "taskName": task,
            "paramKey": key,
            "paramValue": str(ov) if ov is not None else str(val),
        })

    # In batch mode the FlowHub-side name and output directory MUST be
    # unique per sample so concurrent submissions don't clobber each other.
    # The suffix convention `openclaw-<job-id>-<sample-id>` is what
    # phase_finalize uses when it downloads from
    # `/output/openclaw-<job-id>-<sample-id>/`.
    spec_name = (f"openclaw-{args.job_id}-{args.sample_id}"
                 if args.sample_id else f"openclaw-{args.job_id}")
    spec = {
        "name": spec_name,
        "flowVersionId": args.flow_vid,
        "outputDir": spec_name,
        "inputs": inputs_out,
        "params": params_out,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(spec, indent=2, ensure_ascii=False))
    if args.dry_run:
        print(f"[PLAN] wrote {args.output} (inputs={len(inputs_out)}, "
              f"params={len(params_out)})  — DRY RUN, no FlowHub submission")
        print(f"[PLAN] bindings report: {report_path}")
    else:
        print(f"wrote {args.output} (inputs={len(inputs_out)}, params={len(params_out)})")
        print(f"bindings report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

