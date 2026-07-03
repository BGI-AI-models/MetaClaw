#!/usr/bin/env python3
"""
reference_skill-adapter.py — staged template; copy to
/job/reproducibility/generated_scripts/skill-adapter_<YYYYMMDD-HHMMSS>.py and
customize EXTERNAL_NAME / ADAPTED_NAME before running.

Static, sandbox-safe rewriter for external Skills. Reads
/job/stage/skill-adapter/<external-skill>/, emits drafts under
/job/analysis/skill-adapter/<adapted-name>/.

Strict (also enforced by the container; see SKILL.md):
  * Only ast.parse on external code — never exec/eval/compile/import it.
  * No pip install, no network, no subprocess to package managers.
  * All writes confined to /job/analysis/skill-adapter/.
"""
import argparse
import ast
import datetime
import hashlib
import json
import os
import re
import sys
import textwrap
from pathlib import Path

import yaml


STAGE_DIR     = Path("/job/stage/skill-adapter")
ANALYSIS_DIR  = Path("/job/analysis/skill-adapter")
GENERATED_DIR = Path("/job/reproducibility/generated_scripts")
SNAPSHOT_DIR  = Path("/job/reproducibility/skill_snapshots/skill-adapter")
ASSETS_DIR    = SNAPSHOT_DIR / "assets"

# Customize these two before running. Leaving either as None auto-derives
# (single subdir under STAGE_DIR; ADAPTED_NAME = slug of EXTERNAL_NAME).
EXTERNAL_NAME = None
ADAPTED_NAME  = None


NETWORK_MODULES = {
    "urllib", "urllib2", "urllib3", "requests", "httpx", "aiohttp",
    "socket", "http", "ftplib", "telnetlib", "smtplib", "paramiko",
    "websockets",
}
INSTALL_BINARIES = {
    "pip", "pip3", "conda", "mamba", "apt", "apt-get",
    "curl", "wget", "git",
}
INTERACTIVE_CALLS = {"input", "getpass.getpass", "click.prompt"}
WRITE_CALLS = {
    "open", "io.open",
    "pathlib.Path.write_text", "pathlib.Path.write_bytes",
    "shutil.copy", "shutil.copy2", "shutil.copyfile", "shutil.copytree",
}
EXEC_CALLS = {"exec", "eval", "compile", "importlib.import_module"}
OUT_OF_SANDBOX = re.compile(r"^(?:/etc|/var|/usr|/root|/home|/opt|~)(?:/|$)")
HARDCODED_PATH_PATTERNS = [
    (re.compile(r"^\./input(?:/|$)"),  "STAGE_DIR"),
    (re.compile(r"^\./output(?:/|$)"), "ANALYSIS_DIR"),
    (re.compile(r"^data/(?!/)"),       "STAGE_DIR"),
    (re.compile(r"^output/(?!/)"),     "ANALYSIS_DIR"),
]
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)


def main():
    parser = argparse.ArgumentParser(description="Adapt an external Skill (static).")
    parser.add_argument("--job-dir", default="/job",
                        help="ignored; paths fixed by contract")
    parser.parse_args()

    if not STAGE_DIR.is_dir():
        sys.stderr.write(f"missing input: {STAGE_DIR}\n")
        sys.exit(1)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    external = pick_external(STAGE_DIR)
    adapted  = ADAPTED_NAME or slug(external.name)
    out_dir  = ANALYSIS_DIR / adapted
    (out_dir / "scripts").mkdir(parents=True, exist_ok=True)

    py_files = sorted(p for p in external.rglob("*.py") if p.is_file())
    skill_md_path = first_match(external, ["SKILL.md", "skill.md", "*.md"])
    front, _ = parse_skill_md(skill_md_path) if skill_md_path else (None, "")

    findings, imports, per_file = [], set(), {}
    for f in py_files:
        ff, ii = analyze_file(f, external)
        per_file[str(f.relative_to(external))] = ff
        findings.extend(ff)
        imports |= ii

    images = yaml.safe_load((ASSETS_DIR / "image_packages.yaml").read_text())
    audit = build_audit(images, imports)
    verdict = recommend_image(audit)
    audit["recommended_image"] = verdict
    audit["detected_imports"] = sorted(imports)
    safe_write(out_dir / "dependencies_audit.json",
               json.dumps(audit, indent=2, sort_keys=True))

    entry = pick_entry(py_files)
    entry_findings = per_file.get(str(entry.relative_to(external)), []) if entry else []
    entry_src = entry.read_text(encoding="utf-8", errors="replace") if entry else ""
    body_comment = comment_block(annotate_unsafe(entry_src, entry_findings))

    intent = read_intent(STAGE_DIR / "intent.txt")
    description = (front or {}).get("description") or intent or "<TODO 描述触发时机/输入/输出>"
    description = " ".join(description.split())

    skill_md_out = render(
        (ASSETS_DIR / "template_SKILL.md").read_text(),
        NAME=adapted, IMAGE=verdict, SOURCE=external.name, DESCRIPTION=description,
    )
    ref_out = render(
        (ASSETS_DIR / "template_reference.py").read_text(),
        NAME=adapted, BODY_AS_COMMENT=body_comment,
    )
    safe_write(out_dir / "SKILL.md", skill_md_out)
    safe_write(out_dir / "scripts" / f"reference_{adapted}.py", ref_out)

    safe_write(out_dir / "naming_consistency.json", json.dumps({
        "folder": adapted,
        "frontmatter_name": adapted,
        "reference_filename": f"reference_{adapted}.py",
        "pipeline_yaml_entry": adapted,
        "consistent": True,
        "notes": "Names rendered identical from a single template variable.",
    }, indent=2))

    by_sev = {"block": [], "warn": [], "info": []}
    for f in findings:
        by_sev[f["severity"]].append(f)
    safe_write(out_dir / "unsafe_findings.json",
               json.dumps(by_sev, indent=2, sort_keys=True))

    report = render_report(external.name, adapted, py_files, imports,
                           audit, verdict, by_sev, entry)
    safe_write(out_dir / "adaptation_report.md", report)

    meta = {
        "skill": "skill-adapter",
        "packages": {"pyyaml": getattr(yaml, "__version__", "unknown")},
        "parameters": {
            "EXTERNAL_NAME": EXTERNAL_NAME or external.name,
            "ADAPTED_NAME": adapted,
            "recommended_image": verdict,
        },
        "random_seed": None,
        "decisions": (
            f"Static AST analysis of {len(py_files)} .py file(s); "
            f"{len(by_sev['block'])} block, {len(by_sev['warn'])} warn, "
            f"{len(by_sev['info'])} info findings. No external code executed. "
            "Outputs are drafts; human must review per contributor_guide.md §11."
        ),
        "external_source_sha256": hash_dir(external),
        "outputs": [
            f"analysis/skill-adapter/{adapted}/SKILL.md",
            f"analysis/skill-adapter/{adapted}/scripts/reference_{adapted}.py",
            f"analysis/skill-adapter/{adapted}/adaptation_report.md",
            f"analysis/skill-adapter/{adapted}/dependencies_audit.json",
            f"analysis/skill-adapter/{adapted}/naming_consistency.json",
            f"analysis/skill-adapter/{adapted}/unsafe_findings.json",
        ],
        "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
    }
    safe_write(ANALYSIS_DIR / "skill-adapter_meta.json",
               json.dumps(meta, indent=2, sort_keys=True))

    print(f"skill-adapter: drafted {adapted}/ from {external.name} — "
          f"{len(by_sev['block'])} block, {len(by_sev['warn'])} warn, "
          f"{len(by_sev['info'])} info; image={verdict}")


# ── helpers ──────────────────────────────────────────────────────────────────

def safe_write(path, content):
    p = Path(path).resolve()
    root = ANALYSIS_DIR.resolve()
    if p != root and not str(p).startswith(str(root) + os.sep):
        sys.stderr.write(f"sandbox violation: refusing write to {p}\n")
        sys.exit(2)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def slug(name):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return re.sub(r"-+", "-", s) or "adapted"


def first_match(folder, patterns):
    for pat in patterns:
        for hit in folder.glob(pat):
            if hit.is_file():
                return hit
    return None


def pick_external(stage_root):
    if EXTERNAL_NAME:
        p = stage_root / EXTERNAL_NAME
        if not p.is_dir():
            sys.stderr.write(f"EXTERNAL_NAME={EXTERNAL_NAME!r} but {p} not a directory\n")
            sys.exit(1)
        return p
    candidates = [d for d in stage_root.iterdir()
                  if d.is_dir() and not d.name.startswith(".")]
    if not candidates:
        sys.stderr.write(f"no external skill folder under {stage_root}\n")
        sys.exit(1)
    if len(candidates) > 1:
        names = [c.name for c in candidates]
        sys.stderr.write(
            f"multiple folders under {stage_root}: {names}; set EXTERNAL_NAME explicitly\n")
        sys.exit(1)
    return candidates[0]


def pick_entry(py_files):
    if not py_files:
        return None
    for f in py_files:
        if f.name.startswith("reference_"):
            return f
    for f in py_files:
        if f.name in {"main.py", "run.py", "__main__.py"}:
            return f
    return py_files[0]


def read_intent(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace").strip().splitlines()[0]
    except (FileNotFoundError, IndexError):
        return ""


def parse_skill_md(p):
    text = p.read_text(encoding="utf-8", errors="replace")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    try:
        return yaml.safe_load(m.group(1)) or {}, m.group(2)
    except yaml.YAMLError:
        return {}, m.group(2)


def qualified_name(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def first_argv_token(call):
    if not call.args:
        return None
    a = call.args[0]
    if isinstance(a, ast.Constant) and isinstance(a.value, str):
        toks = a.value.strip().split()
        return Path(toks[0]).name if toks else None
    if isinstance(a, ast.List) and a.elts:
        e = a.elts[0]
        if isinstance(e, ast.Constant) and isinstance(e.value, str):
            return Path(e.value).name
    return None


def first_str_literal(call):
    if call.args:
        a = call.args[0]
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            return a.value
    return None


def analyze_file(py_path, base):
    rel = str(py_path.relative_to(base))
    findings, imports = [], set()
    try:
        src = py_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        findings.append(make_finding("warn", "read-error", rel, 0, str(e)))
        return findings, imports
    try:
        tree = ast.parse(src, filename=str(py_path))
    except SyntaxError as e:
        findings.append(make_finding("warn", "syntax-error", rel, e.lineno or 0, str(e)))
        return findings, imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                imports.add(top)
                if top in NETWORK_MODULES:
                    findings.append(make_finding(
                        "block", "network-import", rel, node.lineno,
                        f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            imports.add(top)
            if top in NETWORK_MODULES:
                findings.append(make_finding(
                    "block", "network-import", rel, node.lineno,
                    f"from {node.module} import ..."))
        elif isinstance(node, ast.Call):
            fn = qualified_name(node.func)
            if fn in {"subprocess.run", "subprocess.call", "subprocess.Popen",
                      "subprocess.check_call", "subprocess.check_output",
                      "os.system", "os.popen"}:
                argv0 = first_argv_token(node)
                if argv0 in INSTALL_BINARIES:
                    findings.append(make_finding(
                        "block", "install-or-network-subprocess", rel,
                        node.lineno, f"{fn}({argv0!r}, ...)"))
            if fn in INTERACTIVE_CALLS:
                findings.append(make_finding(
                    "warn", "interactive-io", rel, node.lineno, f"{fn}()"))
            if fn in EXEC_CALLS:
                findings.append(make_finding(
                    "warn", "exec-eval", rel, node.lineno, f"{fn}(...)"))
            if fn in WRITE_CALLS:
                lit = first_str_literal(node)
                if lit and OUT_OF_SANDBOX.match(lit):
                    findings.append(make_finding(
                        "block", "out-of-sandbox-write", rel, node.lineno,
                        f"{fn}({lit!r}, ...)"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            for pattern, target in HARDCODED_PATH_PATTERNS:
                if pattern.match(node.value):
                    findings.append(make_finding(
                        "info", "hardcoded-path", rel, getattr(node, "lineno", 0),
                        f"{node.value!r} → use {target}"))
                    break

    return findings, imports


def make_finding(severity, kind, file, lineno, msg):
    return {"severity": severity, "kind": kind, "file": file,
            "line": lineno, "msg": msg}


def annotate_unsafe(src, findings):
    blocks = {}
    for f in findings:
        if f["severity"] == "block":
            blocks.setdefault(f["line"], []).append(f)
    if not blocks:
        return src
    out = []
    for i, line in enumerate(src.splitlines(), 1):
        for f in blocks.get(i, []):
            out.append(f"# TODO[skill-adapter] {f['kind']}: {f['msg']}")
        out.append(line)
    tail = "\n" if src.endswith("\n") else ""
    return "\n".join(out) + tail


def comment_block(src):
    if not src.strip():
        return "    #   (no entry .py found in external skill)"
    return "\n".join(f"    # {line}" if line else "    #" for line in src.splitlines())


def render(template, **fields):
    out = template
    for k, v in fields.items():
        out = out.replace(f"__{k}__", v)
    return out


def build_audit(images, imports):
    audit = {}
    for key, info in images.items():
        provided = set(info.get("python", []) or [])
        missing = sorted(i for i in imports
                         if i not in provided and not is_stdlib(i))
        covered = sorted(i for i in imports
                         if i in provided or is_stdlib(i))
        audit[key] = {
            "image": info.get("tag", key),
            "missing_python_packages": missing,
            "covered_imports": covered,
        }
    return audit


def recommend_image(audit):
    for key in ("base", "downstream", "downstream-dl"):
        info = audit.get(key)
        if info and not info["missing_python_packages"]:
            return info["image"]
    return audit.get("downstream", {}).get("image", "openclaw/downstream:1.0.0")


def is_stdlib(name):
    # sys.stdlib_module_names is available in Python ≥ 3.10; the base image
    # ships 3.12.
    return name in getattr(sys, "stdlib_module_names", frozenset())


def hash_dir(d):
    h = hashlib.sha256()
    for p in sorted(Path(d).rglob("*")):
        if p.is_file():
            h.update(p.relative_to(d).as_posix().encode())
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
    return h.hexdigest()


def render_report(external, adapted, py_files, imports, audit, verdict,
                  by_sev, entry):
    L = []
    L.append(f"# Adaptation Report — {external} → {adapted}\n")
    L.append(f"- Source: `/job/stage/skill-adapter/{external}`")
    L.append(f"- Draft : `/job/analysis/skill-adapter/{adapted}/`")
    L.append(f"- Recommended image: **{verdict}**")
    L.append(f"- Entry script: `{entry.name if entry else '(none)'}`\n")

    L.append("## Files scanned\n")
    if py_files:
        for f in py_files:
            L.append(f"- `{f.relative_to(Path('/job/stage/skill-adapter') / external)}`")
    else:
        L.append("_(no .py files)_")
    L.append("")

    L.append("## Imports detected\n")
    L.append(", ".join(f"`{i}`" for i in sorted(imports)) or "_(none)_")
    L.append("")

    L.append("## Dependency audit\n")
    for key in ("base", "downstream", "downstream-dl"):
        info = audit.get(key)
        if not info:
            continue
        miss = info["missing_python_packages"]
        flag = "✅" if not miss else f"❌ missing: {', '.join(miss)}"
        L.append(f"- `{info['image']}` — {flag}")
    all_missing = all(audit.get(k, {}).get("missing_python_packages")
                      for k in ("base", "downstream", "downstream-dl") if k in audit)
    if all_missing:
        L.append("")
        L.append("> ⚠️  Some imports are missing in **every** known image. See "
                 "contributor_guide.md §7 for how to extend an image (this skill "
                 "**will not** modify Dockerfiles automatically).")
    L.append("")

    for sev_label, sev_key in [("Blocking", "block"), ("Warnings", "warn"),
                               ("Info", "info")]:
        items = by_sev.get(sev_key, [])
        if not items:
            continue
        L.append(f"## {sev_label} ({len(items)})\n")
        for f in items:
            L.append(f"- `{f['file']}:{f['line']}` [{f['kind']}] {f['msg']}")
        L.append("")

    L.append("## Next steps (human)\n")
    L.append(f"1. Review `unsafe_findings.json` and edit "
             f"`scripts/reference_{adapted}.py` (every `# TODO[skill-adapter]` "
             "marker must be resolved).")
    L.append("2. Replace `<TODO ...>` placeholders in `SKILL.md`.")
    L.append("3. If `dependencies_audit.json` shows missing packages on the "
             "recommended image, see contributor_guide.md §7.")
    L.append(f"4. Move the draft `{adapted}/` to `skills/{adapted}/` and "
             "register it in `registry/pipelines.yaml` per contributor_guide.md §8.")
    L.append("5. End-to-end verify per contributor_guide.md §11.")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
