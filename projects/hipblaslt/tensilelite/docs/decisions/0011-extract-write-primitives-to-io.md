# 0011 — Extract writeAssembly + writeHelpers to IO.py (cycle break)

**Status:** accepted  (date 2026-06-26)

**Decision:** Move `writeAssembly`/`writeHelpers` into `IO.py` and re-import into
Run via the EOF block. `writeAssembly` references the Run-resident contract
(`KernelCodeGenResult` annotation, `KernelMinResult` in body), creating an
IO→Run import edge. Break the resulting IO↔Run cycle by: (a)
`from __future__ import annotations` at IO top (annotations become lazy strings,
so the `KernelCodeGenResult` annotation needs nothing at def time), and (b)
placing `from .Run import KernelCodeGenResult, KernelMinResult` at the BOTTOM of
IO.py, after all IO defs. `KERNEL_HELPER_FILENAME_*` are writeHelpers parameters
(shadowing), so only Run (the call sites) imports them, not IO.

**Why:** With the back-import at IO's bottom and lazy annotations, whichever
module loads first has the other's needed names bound before use: importing Run
runs its EOF `from .IO import …` after KernelMinResult/KernelCodeGenResult are
defined; importing IO first runs IO's defs, then its bottom `from .Run import …`
which triggers Run whose EOF `from .IO import writeAssembly,…` finds those defs
already present. Zero monkeypatched-global reads (NBA-7 audit: zero retargets).

**Alternatives rejected:** *Put `from .Run import` above writeAssembly (to keep
the annotation as a live object)* — rejected: that breaks import-IO-first
(Run's EOF would import IO names not yet defined). *Stringify only
writeAssembly's annotation* — equivalent but more surgical; the module-wide
future-import is the idiomatic cycle fix and keeps the body byte-identical.

**Validation:** import-smoke from BOTH directions OK (Run-first: `R.writeAssembly
is IO.writeAssembly`, `IO.KernelMinResult is R.KernelMinResult`; IO-first:
`R.writeHelpers is IO.writeHelpers`); package + __main__ resolve. 97 passed in
TensileCreateLibraryRun/.

**History (updates only):**
- 2026-06-26 — initial record (NBA-7).
