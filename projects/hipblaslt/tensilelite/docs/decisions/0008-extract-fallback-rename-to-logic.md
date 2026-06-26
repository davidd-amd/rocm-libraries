# 0008 — Extract fallback-rename helpers to Logic.py

**Status:** accepted  (date 2026-06-26)

**Decision:** Move `_renameFallbackPlaceholders` and `renameFallbacksPerArch`
into `Logic.py` (with `copy`, `PlaceholderLibrary`) and re-import into Run via
the EOF block. (Committed before NBA-5, so this is ADR 0008 by commit order;
the plan's provisional 0009 label refers to this same NBA-6 work.)

**Why:** Pure tree-walk + deep-copy logic with no monkeypatched-global reads
(NBA-6 audit: zero retargets). `renameFallbacksPerArch` is called by
`generateLogicDataAndSolutions` (still in Run for now) via the back-import, and
becomes intra-Logic once NBA-11 moves that caller. `renameFallbacksPerArch` is
imported by test_perArchFallbackRename.py via `from ...Run import` and both are
exercised via `M.` — the back-import keeps them resolving (RULE A/C).

**Alternatives rejected:** *Keep in Run* — they are logic-tree transforms that
belong with generateLogicDataAndSolutions (Logic); keeping them in Run would
force NBA-11's intra-module call to round-trip through Run.

**Validation:** import-smoke OK (`R.renameFallbacksPerArch is
L.renameFallbacksPerArch`); 102 passed across test_perArchFallbackRename.py +
TensileCreateLibraryRun/.

**History (updates only):**
- 2026-06-26 — initial record (NBA-6).
