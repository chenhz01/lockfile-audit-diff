# ALIGNMENT.md — R13 alignment record (16 items)

Design source: `_r13_design.json` → repo `lockfile-audit-diff`,
domain 锁文件审计, sim `adjacent`. Date of record: 2026-10-11.

| # | Item | Evidence |
| --- | --- | --- |
| 1 | Repo name matches design entry | Directory `lockfile-audit-diff` == design JSON `name`. |
| 2 | Mechanism implemented as specified | Design mechanism "两版 lock 文件依赖树 diff+新增依赖风险标注（名字/版本/许可字段）" → `diff_locks` + `annotate_risks` (license/version/name fields) in core.py. |
| 3 | Pure Python standard library only | Imports: argparse, json, sys, collections.deque (+ os/tempfile in tests). |
| 4 | CLI entry via argparse | `core.py old new [--format] [--exit-zero]`; README quickstart runs as written. |
| 5 | self_test.py ≥40 cases, three categories | Functional (parsers, diff, depths, risks), exception paths (malformed JSON, missing files, bad deps type), extreme edge (50-level chain, 500-package lockfile, unicode names, cycles, empty inputs). |
| 6 | Final line `SUMMARY: PASS n/n` | `python self_test.py` ends with that exact line. |
| 7 | README first paragraph ≤60 words | Intro ~55 words (counted 2026-10-11). |
| 8 | README required sections present | All mandated sections incl. FAQ "When NOT to use" and 3 Core Assumptions. |
| 9 | why-not-X ≥3 alternatives with real anchors | Table lists BCS911/mcp-lockfile-audit (0★), Behnam1369/lockfile_audit (0★), ak40u/nextjs-railway-starter (0★) with stars from design JSON; differences paraphrased. |
| 10 | MIT LICENSE, "zhengming contributors" | LICENSE copyright line as required; no real names. |
| 11 | CHANGELOG v0.1.0 → v0.1.1 | CHANGELOG.md documents both versions dated 2026-10-11. |
| 12 | Two-round iteration, ≥1 dimension ≥20% | Round 2 added risk label `name-shape-mismatch` + per-risk summary counts — risk model 5 → 6 labels (+20%) — plus 10 new tests. Recorded in CHANGELOG v0.1.1. |
| 13 | Number discipline | Test counts quoted from self_test SUMMARY (repro: `python self_test.py`); README timings are reproducible approximations. |
| 14 | Zero secrets / zero real names | No keys; "zhengming contributors" copyright. |
| 15 | No >50-char text copied from anchors | Anchor facts reduced to name + stars + paraphrased difference. |
| 16 | as-of date marked | README headline and Confidence footer say "as of 2026-10-11". |
