---
name: weather-fetcher
description: Fetch current weather and produce a daily JSON summary.
---

# Weather Fetcher (synthetic example)

Tiny non-BioLine skill used to exercise skill-adapter. Demonstrates several
violations the adapter must catch: network call, interactive prompt,
hardcoded relative paths, and a `pip install` subprocess.

To exercise: copy this folder into a job's stage area at
`/data/output/<job-id>/stage/skill-adapter/weather-fetcher/`, then run the
skill-adaptation pipeline.
