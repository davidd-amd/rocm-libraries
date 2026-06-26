# 0009 — Extract generateKernelObjectsFromSolutions to Logic.py

**Status:** accepted  (date 2026-06-26)

**Decision:** Move `generateKernelObjectsFromSolutions` (with `@timing`,
`getKeyNoInternalArgs`) into `Logic.py` with a BYTE-IDENTICAL `(solutions)`
signature, and re-import into Run via the EOF block.

**Why:** RULE G chokepoint — `_codegen/codegen_harness.py` and
`config_harness.py` do `from Tensile.TensileCreateLibrary.Run import
generateKernelObjectsFromSolutions`, and the `_codegen` + `LocalRead` test
families depend on it transitively. The back-import keeps that path resolving;
the signature must not drift. Zero monkeypatched-global reads (NBA-8 audit: zero
retargets).

**Alternatives rejected:** *Move generateKernelHelperObjects alongside it* —
deferred to NBA-14 (decided keep-in-Run); the harness imports it from Run too,
so moving it here would widen the blast radius without benefit.

**Validation:** chokepoint import OK (`from ...Run import
generateKernelObjectsFromSolutions`; `is` Logic's; signature `(solutions)`).
375 passed across _codegen/ + LocalRead/ + TensileCreateLibraryRun/
(PYTEST_EXIT=0).

**History (updates only):**
- 2026-06-26 — initial record (NBA-8).
