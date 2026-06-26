# 0014 — Extract generateLogicDataAndSolutions to Logic.py

**Status:** accepted  (date 2026-06-26)

**Decision:** Move the ~120-LOC logic-load + per-arch merge + reindex + fallback +
codeObjectFilesIndex core `generateLogicDataAndSolutions` (with `@timing`) into
`Logic.py` and re-import into Run via the EOF `from .Logic import …` block. Logic
gains `itertools`, `LibraryIO`, `ParallelMap2`/`print1` (from `Tensile.Common`),
`MasterSolutionLibrary`, `mergeTypeMismatchCollector`/`printTypeMismatchSummary`,
and `Assembler`. `renameFallbacksPerArch` is already Logic-local (NBA-6), so its
call resolves intra-module with no Run round-trip. The function references no
Run-resident contract symbol, so Logic needs NO `from .Run import` and there is
no cycle.

**Monkeypatch handling (RULE C/D), per the verified audit:**
- RETARGET (bare name): the one `ParallelMap2` patch in the
  `generateLogicDataAndSolutions` direct-call test
  (`test_r7_createlib_deep_char.py:555`) →
  `patch.object(Logic, "ParallelMap2", …)`. The moved function reads
  `ParallelMap2` in Logic's `__globals__`, so an `M`-target would no-op. A `Logic`
  import handle was added to the test.
- LEAVE AS-IS (shared module singleton): `M.LibraryIO.parseLibraryLogicFile`
  (r7:520) and `M.LibraryIO.write` (orchestration) — `LibraryIO` is the same
  module object in Run and Logic (verified `R.LibraryIO is L.LibraryIO`), so
  mutating it via `M` stays visible to the moved function. This supersedes the
  earlier (incorrect) instruction to retarget `LibraryIO.write`. Run keeps its own
  `from Tensile import LibraryIO` because `run()` still calls `LibraryIO.write`.
- The other four `ParallelMap2` patches in `TestWriteSolutionsAndKernelsTCL`
  (334/372/398/430) belong to `writeSolutionsAndKernelsTCL` and are NBA-12's
  responsibility — left untouched here.

**Why:** logic-data assembly is core to the build algorithm and belongs in the
Logic layer next to the fallback-rename helpers it depends on; keeping it in Run
works against the decomposition for no benefit.

**Alternatives rejected:** *Retarget the LibraryIO patches too* — redundant and
churning; they are shared-singleton mutations that stay effective unmodified.

**Validation:** import-smoke OK; `R.generateLogicDataAndSolutions is
L.generateLogicDataAndSolutions`, its `__globals__ is Logic.__dict__` (retarget
sentinel proof), `R.LibraryIO is L.LibraryIO` (no-retarget justification),
`R.renameFallbacksPerArch is L.renameFallbacksPerArch` (intra-Logic call). 102
passed across TensileCreateLibraryRun/ + test_perArchFallbackRename.py.

**History (updates only):**
- 2026-06-26 — initial record (NBA-11).
