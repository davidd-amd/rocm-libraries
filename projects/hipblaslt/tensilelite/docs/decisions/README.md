# TensileLite architecture decision records

One file per non-trivial decision affecting the TensileLite build/codegen surface
(`Tensile/TensileCreateLibrary/`, the build orchestration, the toolchain wiring).

This log is the build-refactor peer of
`Tensile/Tests/unit/characterization/DECISIONS.md`, which is scoped to the
characterization suite's add-only coverage choices. Build/codegen architecture
decisions live here instead so the two logs stay distinct.

Each ADR is a flat `NNNN-kebab-title.md` add. "One ADR per commit" is a
single-file add (no index churn); "ADR update" is a one-line append to the
record's **History** section. Use the template below.

```
# NNNN — <title>

**Status:** proposed | accepted | superseded-by NNNN  (date YYYY-MM-DD)

**Decision:** <the one choice made, imperative, 1-3 sentences>

**Why:** <the load-bearing reason; cite files/line ranges or measured numbers, not vibes>

**Alternatives rejected:** <name >=1 real alternative and the condition under which it would have won; 'none' only if genuinely none>

**Validation:** <the exact test-gate command run for this commit and its result, e.g. tox -e unit = N passed / M skipped>

**History (updates only):**
- YYYY-MM-DD — <what changed and why, on ADR updates>
```

## Index

- [0001 — TensileCreateLibrary decomposition: extract-then-reexport](0001-tensilecreatelibrary-decomposition.md)
- [0002 — Pin passPostKernelInfoToLibrary before extraction](0002-pin-passpostkernelinfotolibrary.md)
- [0003 — Executable import-surface contract for the port](0003-lock-import-surface.md)
- [0004 — Pin the TCL emitter return contract and normalize the __init__ facade](0004-pin-tcl-emitter-and-normalize-facade.md)
- [0005 — Extract path helpers to IO.py](0005-extract-path-helpers-to-io.md)
- [0006 — Extract stinky-asm ELF verification to IO.py](0006-extract-stinky-verify-to-io.md)
- [0007 — Extract mem-compression helpers to IO.py](0007-extract-mem-compression-to-io.md)
- [0008 — Extract fallback-rename helpers to Logic.py](0008-extract-fallback-rename-to-logic.md)
- [0009 — Extract generateKernelObjectsFromSolutions to Logic.py](0009-extract-generatekernelobjects-to-logic.md)
- [0010 — Extract validity-pruning + post-kernel-to-solution to Tuning.py](0010-extract-validity-pruning-to-tuning.md)
- [0011 — Extract writeAssembly + writeHelpers to IO.py](0011-extract-write-primitives-to-io.md)
- [0012 — Extract copyStaticFiles to IO.py](0012-extract-copystaticfiles-to-io.md)
- [0013 — Extract passPostKernelInfoToLibrary to Tuning.py](0013-extract-passpostkernelinfotolibrary-to-tuning.md)
- [0014 — Extract generateLogicDataAndSolutions to Logic.py](0014-extract-generatelogicdataandsolutions-to-logic.md)
- [0015 — Extract writeSolutionsAndKernelsTCL (live emitter) to Tuning.py](0015-extract-tcl-emitter-to-tuning.md)
- [0016 — Extract writeSolutionsAndKernels (public emitter) to Tuning.py](0016-extract-legacy-emitter-to-tuning.md)
- [0017 — Placement of generateKernelHelperObjects (keep in Run.py)](0017-helper-objects-placement.md)
