# MEMORY — Curated Long-Term Memory

> Distilled wisdom, not raw logs. Raw events live in `memory/YYYY-MM-DD.md`.
> Loaded ONLY in main sessions (direct DMs with the human). Never loaded in
> group chats or shared channels — see `AGENTS.md` §Memory.
>
> **Size cap: 200 lines.** If this file exceeds 200 lines, the
> `memory-rotation` heartbeat task will compress the oldest entries in each
> section before adding new ones.

## What NEVER goes into this file

Hard exclusions. If you find yourself about to write any of the below, stop
and either (a) drop it entirely, or (b) keep it only in the per-job
`reproducibility/` folder where audit-trail access is justified.

- **Credentials.** No FlowHub `AccessKey` / `AccessSecret`, no Feishu app
  secrets, no API tokens, no `fkit login` arguments, no Doubao/Volcengine
  keys. Mirror `SOUL.md` red lines.
- **Patient-identifying metadata.** No sample IDs tied to real names, no
  hospital MRNs, no dates of birth, no addresses, no phone numbers. If a CSV
  has a PHI column and you noticed it, write only "PHI column observed in
  job <id>; flagged for user" — never the values.
- **Raw sequencing data or sample contents.** Paths are OK; contents are not.
- **Third-party private data.** Anything the user shared about a collaborator,
  unpublished hypothesis, or pre-print under embargo.
- **Session-transient state.** Current working directory, current job ID,
  open file handles — these belong in the live session, not long-term memory.
- **Speculation about the user.** Only record facts the user stated directly
  or behavior observed across ≥3 sessions. Mark confidence: `[stated]`,
  `[observed]`, `[inferred]`.

## User context

_Things the user has told me directly about themselves, their work, or their
preferences. Confidence tag on every entry._

(empty)

## Operational lessons

_Patterns learned from running pipelines and skills. Failure modes, gotchas,
non-obvious working configurations. Update `AGENTS.md` / `TOOLS.md` /
`skills/<name>/SKILL.md` first if the lesson is rule-shaped; only record here
if it's recollection-shaped (e.g., "we tried X on dataset Y and it
underperformed Z")._

(empty)

## Recent jobs

_One line per completed job, newest first. Format:
`<YYYY-MM-DD> <job-id> <pipeline> <outcome> <one-line note>`.
Older entries get pruned by `memory-rotation` once this section exceeds
~30 lines._

(empty)

## Open questions

_Things the user asked me to remember to ask about later, or unresolved
methodological choices waiting on user input. Clear out entries once
answered._

(empty)
