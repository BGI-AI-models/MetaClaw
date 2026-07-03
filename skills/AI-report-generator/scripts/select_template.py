"""Pick the most suitable report template for the current job.

The selector is intentionally lightweight and offline. It reads the registry
in ``assets/template_index.yaml`` and applies the cascade documented there:

    explicit name > pipeline match > required_dirs > any_dirs >
    keyword match in user prompt > priority tie-breaker > ``generic``

Usable both as a CLI (``python select_template.py --job-dir /job ...``) and as
a library (``select(...)`` returns a dict).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - YAML is part of the env
    yaml = None


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DEFAULT_REGISTRY = ASSETS_DIR / "template_index.yaml"


@dataclass
class Template:
    name: str
    file: str
    title: str = ""
    pipelines: list[str] = field(default_factory=list)
    required_dirs: list[str] = field(default_factory=list)
    any_dirs: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    priority: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


def _load_registry(path: Path) -> list[Template]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load the template registry")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[Template] = []
    for entry in data.get("templates", []):
        out.append(
            Template(
                name=entry["name"],
                file=entry.get("file", f"{entry['name']}.html.j2"),
                title=entry.get("title", entry["name"]),
                pipelines=[p.lower() for p in entry.get("pipelines", []) or []],
                required_dirs=entry.get("required_dirs", []) or [],
                any_dirs=entry.get("any_dirs", []) or [],
                keywords=entry.get("keywords", []) or [],
                priority=int(entry.get("priority", 0)),
                raw=entry,
            )
        )
    return out


def _existing_dirs(analysis_root: Path) -> set[str]:
    if not analysis_root.is_dir():
        return set()
    return {p.name.lower() for p in analysis_root.iterdir() if p.is_dir()}


def _keyword_hit(prompt: str, patterns: Iterable[str]) -> bool:
    if not prompt:
        return False
    p = prompt.lower()
    return any(re.search(pat, p, re.IGNORECASE) for pat in patterns)


@dataclass
class Decision:
    template: Template
    reason: str
    score: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.template.name,
            "file": self.template.file,
            "title": self.template.title,
            "reason": self.reason,
            "score": self.score,
        }


def select(
    *,
    user_prompt: str = "",
    pipeline: str = "",
    analysis_root: Path | str | None = None,
    explicit: str = "",
    registry_path: Path | str | None = None,
) -> Decision:
    """Return the chosen template along with the reason.

    Higher-priority signals win. Ties are broken by the ``priority`` field.
    """
    reg_path = Path(registry_path or DEFAULT_REGISTRY)
    templates = _load_registry(reg_path)
    by_name = {t.name: t for t in templates}

    # 1. Explicit override.
    if explicit:
        if explicit in by_name:
            return Decision(by_name[explicit], reason=f"explicit --template={explicit}", score=10_000)
        # Fall through with a warning embedded in reason.

    pipeline_l = (pipeline or "").lower().strip()
    dirs = _existing_dirs(Path(analysis_root)) if analysis_root else set()

    candidates: list[tuple[int, str, Template]] = []
    for t in templates:
        if t.name == "generic":
            continue
        score = 0
        reasons: list[str] = []

        if t.pipelines and pipeline_l and pipeline_l in t.pipelines:
            score += 1000
            reasons.append(f"pipeline={pipeline_l}")

        if t.required_dirs:
            missing = [d for d in t.required_dirs if d.lower() not in dirs]
            if missing:
                continue
            score += 500
            reasons.append(f"required_dirs ok ({','.join(t.required_dirs)})")

        if t.any_dirs:
            hit = [d for d in t.any_dirs if d.lower() in dirs]
            if hit:
                score += 200 + 50 * len(hit)
                reasons.append(f"dirs:{','.join(hit)}")

        if t.keywords and _keyword_hit(user_prompt, t.keywords):
            score += 150
            reasons.append("prompt-keyword")

        score += t.priority

        if score > t.priority:  # at least one signal fired
            candidates.append((score, "; ".join(reasons), t))

    if candidates:
        candidates.sort(key=lambda x: (-x[0], -x[2].priority, x[2].name))
        score, reason, t = candidates[0]
        return Decision(t, reason=reason, score=score)

    fallback = by_name.get("generic") or templates[-1]
    return Decision(fallback, reason="no specific match — fallback", score=0)


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job-dir", default="/job", help="Job working directory (contains analysis/ and stage/)")
    p.add_argument("--user-prompt", default="", help="Free-text prompt from the analyst")
    p.add_argument("--pipeline", default="", help="Pipeline name (overrides manifest)")
    p.add_argument("--template", default="", help="Force a specific template name")
    p.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    p.add_argument("--json", action="store_true", help="Print the decision as JSON")
    args = p.parse_args()

    job = Path(args.job_dir)
    pipeline = args.pipeline
    if not pipeline:
        manifest = job / "stage" / "manifest.json"
        if manifest.is_file():
            try:
                pipeline = json.loads(manifest.read_text(encoding="utf-8")).get("pipeline", "")
            except Exception:
                pipeline = ""

    decision = select(
        user_prompt=args.user_prompt,
        pipeline=pipeline,
        analysis_root=job / "analysis",
        explicit=args.template,
        registry_path=args.registry,
    )

    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
    else:
        print(f"{decision.template.name}\t{decision.template.file}\t# {decision.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
