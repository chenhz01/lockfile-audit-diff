# Changelog — lockfile-audit-diff

All notable changes. Format based on Keep a Changelog; versioning: SemVer.

## [0.1.1] - 2026-10-12

### Added
- MIT LICENSE file (was missing from the release candidate).

### Fixed
- Self-match bug in `annotate_risks`: a re-added package whose name exactly equals an existing dependency was flagged `typosquat-proximity` against itself (edit distance 0 ≤ 2). Exact name equality is now skipped before the proximity comparison; near-miss detection for genuinely similar names is unchanged.

### Verified
- Full release audit: `python self_test.py` → `SUMMARY: PASS 44/44` (44 cases across functional, exception/CLI, and extreme-edge tiers).

## [0.1.0] - 2026-10-11

### Added
- Lockfile parsing for pip-freeze style TXT (`name==version`) and a canonical JSON package list.
- Dependency-graph depth computation (BFS from root packages; cycles/orphans get depth -1).
- Diff report: added / removed / changed sets plus unchanged count.
- Risk annotations for added packages: license-unknown, pre-1.0, typosquat-proximity (edit distance ≤ 2 vs existing names), unparseable-version, deep-transitive (depth ≥ 4), each with a plain-language description table.
- CLI: JSON or text output, `--exit-zero`; exit codes 0 clean / 1 risks / 2 input error (missing/unparseable lockfiles).
- Self-test suite: 44 cases across functional, exception/CLI, and extreme-edge tiers.
