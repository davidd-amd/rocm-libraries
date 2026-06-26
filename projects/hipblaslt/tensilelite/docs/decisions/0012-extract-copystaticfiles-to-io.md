# 0012 — Extract copyStaticFiles to IO.py

**Status:** accepted  (date 2026-06-26)

**Decision:** Move `copyStaticFiles` (with its `@timing` decorator) into `IO.py`
and re-import it into Run via the EOF `from .IO import …` block. IO gains the
`shutil`, `SOURCE_PATH`, and `timing` imports the function needs. The develop
static-file list is preserved verbatim (`TensileTypes.h`, `tensile_bfloat16.h`,
`tensile_float8_bfloat8.h`, `KernelHeader.h`, `ReductionTemplate.h`,
`memory_gfx.h`) — notably it does NOT include `tensile_float8_bfloat8_bc.h`,
which is a template-only file absent on develop.

**Why:** `copyStaticFiles` is one of the six package re-exports
(`__init__.py` re-exports it from `.Run`); ClientWriter/BenchmarkProblems consume
it from the package root. The back-import keeps `.Run.copyStaticFiles` valid, so
the `__init__` chain (`__init__` → `.Run` → `.IO`) stays intact and the external
root-consumers are undisturbed (RULE B). It reads no monkeypatched Run global, so
NBA-9 carries ZERO monkeypatch retargets (audit table).

**Alternatives rejected:** *Leave it in Run* — it is a disk-side static-asset
copier, cohesive with IO's serialization responsibility; keeping it in Run works
against the layered decomposition for no benefit.

**Validation:** import-smoke OK (`copyStaticFiles` resolves via both `Run` and the
package facade); 97 passed in TensileCreateLibraryRun/ including the test_r7
`copyStaticFiles` cases and the NBA-0d import-surface pin.

**History (updates only):**
- 2026-06-26 — initial record (NBA-9).
