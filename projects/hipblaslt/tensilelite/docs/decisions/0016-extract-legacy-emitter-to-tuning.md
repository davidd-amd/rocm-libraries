# 0016 — Extract writeSolutionsAndKernels (public emitter) to Tuning.py

**Status:** accepted  (date 2026-06-26)

**Decision:** Move the public non-TCL emitter `writeSolutionsAndKernels` (Run.py
133-271) into `Tuning.py` and re-import into Run via the EOF `from .Tuning
import …` block. This is the package re-export consumed by `BenchmarkProblems.py`
from the package root; it is NOT in `run()`'s path (run() calls the TCL variant).
Tuning gains `itertools`, `shutil`, `globalParameters`, `timing_context`, and
`getVerbosity`/`printWarning` on top of the deps NBA-12 already added; it reuses
the NBA-12 sibling imports (`from .IO import …`, `from .Run import
processKernelSource`) and the Tuning-local `removeInvalidSolutionsAndKernels`/
`passPostKernelInfoToSolution`. No `KernelCodeGenResult` reference, so the bottom
`from .Run import processKernelSource` is the only Run-contract edge. Cycle-break
is identical to NBA-12 (bottom-of-module sibling imports + future annotations).

**Retargets: ZERO (empirically confirmed).** The audit claim "writeSolutionsAndKernels
is never directly called by any test" was verified: `grep` for
`.writeSolutionsAndKernels(` (non-TCL) across `Tensile/Tests/unit/` returns no
call site, and the only `TestWrite*` class in test_r7 is
`TestWriteSolutionsAndKernelsTCL` (NBA-12). The test_r7:30 header comment
referencing "writeSolutionsAndKernels (legacy orchestration)" is stale — no such
test class exists. The real consumer is `BenchmarkProblems.py:469` via the
package root, covered by the import-smoke + the NBA-0d surface pin, not by a
bare-name monkeypatch.

**Why serialize after NBA-12:** shared `Tuning.py` + the Run import-block + the
same cycle technique; landing them one at a time keeps each commit's import-smoke
the clean gate.

**Alternatives rejected:** *Leave it in Run* — it is a kernel emitter, cohesive
with the TCL emitter now in Tuning; splitting the two emitters across modules
would fragment the layer for no benefit.

**Validation:** import-smoke OK (no cycle); `R.writeSolutionsAndKernels is
T.writeSolutionsAndKernels is <package>.writeSolutionsAndKernels`, its
`__globals__ is Tuning.__dict__`, and `BenchmarkProblems.writeSolutionsAndKernels`
is the same object (facade intact). 106 passed across TensileCreateLibraryRun/ +
test_benchmarkProblems_solution_pool.py.

**History (updates only):**
- 2026-06-26 — initial record (NBA-13).
