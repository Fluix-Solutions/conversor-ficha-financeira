# LESSONS - auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation - do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 - Test that the orchestrating entry point actually calls each tested helper, not only the helper in isolation
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `build-script` · harmful: 0
- features: build-windows
- evidence: M5 construir_portatil.py:187 (WIN-16) (build-script)
- last seen: 2026-09-11T17:54:22Z

### L-002 - Cover every CLI flag branch of a build script with a test that runs main with that flag
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `build-script` · harmful: 0
- features: build-windows
- evidence: M6 construir_portatil.py:241 (WIN-10) (build-script)
- last seen: 2026-09-11T17:54:23Z

### L-003 - Give every publishing CI workflow a non-publishing run path before using it as a verification gate
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `ci-workflow` · harmful: 0
- features: build-windows
- evidence: WIN-20 README.md:115-141; .github/workflows/windows.yml:16 (ci-workflow)
- last seen: 2026-09-11T17:54:23Z

### L-004 - Fail a release job when the target tag already exists on a commit other than the one that was built
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `ci-workflow` · harmful: 0
- features: build-windows
- evidence: WIN-01 .github/workflows/windows.yml:116-117 (ci-workflow)
- last seen: 2026-09-11T17:54:23Z

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
