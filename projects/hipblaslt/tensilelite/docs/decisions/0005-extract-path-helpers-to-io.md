# 0005 — Extract path helpers to IO.py

**Status:** accepted  (date 2026-06-26)

**Decision:** Move `libraryRoot`, `libraryDir`, `_baseArchs`,
`tensileLibraryFile` (Run.py 87-129) verbatim into `IO.py` and re-import them
back into Run.py via the EOF back-import block (RULE I). First extraction; it
establishes the EOF back-import block.

**Why:** These are pure path-layout helpers with no monkeypatched-global reads
(NBA-2 audit: zero retargets), so they are the safest leaf to move first.
`libraryDir`/`libraryRoot`/`tensileLibraryFile` are package re-exports consumed
from the root by ClientWriter/BenchmarkProblems/GenerateSummations; the
re-import keeps `.Run.<name>` and thus the `__init__` facade valid (RULE A/B).
`_baseArchs` is test-bound (RULE C). The colon-strip semantics in `libraryDir`
are matched at runtime by tensile_host.cpp with no Python signal, so the bodies
were moved byte-for-byte (no "cleanup").

**Alternatives rejected:** *Place the back-import next to the def or in the
top import block* — rejected per RULE I (EOF block) so the cycle-break ordering
is uniform across all extractions; mid-file placement would win only if a
module-load-time reference to a moved name existed (none do).

**Validation:** import-smoke OK (`R.libraryRoot is IO.libraryRoot`); 117 passed
across test_library_paths.py + TensileCreateLibraryRun/ + GenerateSummations/.

**History (updates only):**
- 2026-06-26 — initial record (NBA-2).
