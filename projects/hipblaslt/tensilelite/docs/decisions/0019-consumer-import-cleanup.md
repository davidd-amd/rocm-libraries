# 0019 — Consumer-import cleanup: keep the Run back-import shims (no facade repoint)

**Status:** accepted  (date 2026-06-26)

**Decision:** Stop here. Keep `__init__.py` sourcing all six public names
(`copyStaticFiles`, `libraryDir`, `libraryRoot`, `run`, `tensileLibraryFile`,
`writeSolutionsAndKernels`) from `.Run`, keep every Run EOF back-import shim, and
do NOT migrate characterization tests off the `M = import_module('…Run')` shims.
The optional facade repoint (sourcing the six names from their real homes —
`.IO`/`.Tuning`) and the per-group consumer migration described in the NBA-16
issue are deliberately NOT performed.

**Why keep the shims:**
- They are zero-cost at runtime (a name re-export) and zero-risk: every consumer
  — the package facade, the three external root-consumers (`ClientWriter.py`,
  `BenchmarkProblems.py`, `GenerateSummations.py`), the `_codegen`/`LocalRead`
  harness chokepoint (`from …Run import`), the `__main__.run` entry, and the
  test suite's `M.*` bindings — resolves through `.Run` exactly as it did on
  develop. Nothing downstream needs to know a symbol now lives in IO/Logic/Tuning.
- The package `__init__` is consumed by `rocBLAS`/`hipBLASLt` `find_package(Tensile)`
  via the package root. Repointing its imports to `.IO`/`.Tuning` changes the
  canonical package import order (IO/Tuning would load before Run) for every
  external consumer — a real blast-radius change for a purely cosmetic gain. The
  `from .Run import …` form keeps the entry point's import graph identical to
  develop while the decomposition lives entirely behind it.
- Migrating each char-test group off the shims (and removing each shim in the same
  commit) is pure churn with no behavioral payoff; the shims are a permanent,
  intentional part of the architecture, not scaffolding to be torn down.

**Alternatives considered:**
- *Facade repoint to real homes (NBA-16 step 1).* Would make `__init__` document
  the true module of each name. Rejected for now: it alters the package import
  order observed by external `find_package` consumers for a cosmetic benefit; the
  back-import indirection already makes the real homes discoverable via the ADRs
  and the EOF block. Condition that would flip it: a future conversion of `Run.py`
  into a `Run/` package, where keeping leaf logic out of the package `__init__`
  becomes structurally necessary.
- *Per-group consumer migration off the shims.* Rejected: high churn, no payoff,
  and it would couple test files to internal module boundaries that the shims
  exist precisely to hide.

**Validation:** No code change in this issue. The shim architecture is proven by
the NBA-15 full gate (4981 passed / 220 skipped / 0 failed) and the NBA-0d
executable surface pin (`_PACKAGE_REEXPORTS` + `_RUN_BACKBONE` + `__main__.run`),
which assert every public/back-import name still resolves from `.Run` and the
package root.

**History (updates only):**
- 2026-06-26 — initial record (NBA-16): keep shims, skip facade repoint + consumer
  migration. Port complete (Stage 0-5, NBA-0…16).
