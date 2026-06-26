# 0015 — Extract writeSolutionsAndKernelsTCL (live emitter) to Tuning.py

**Status:** accepted  (date 2026-06-26)

**Decision:** Move the process-parallel TCL emitter `writeSolutionsAndKernelsTCL`
— the live path `run()` invokes (Run.py:540, now via the back-import) — into
`Tuning.py` and re-import into Run via the EOF `from .Tuning import …` block.
Tuning gains the third-party deps at module top (`rocisa`, `Path`,
`ensurePath`/`print1`/`print2` from `Tensile.Common`, `isaToGfx`,
`KERNEL_HELPER_FILENAME_CPP/H` from `Tensile.KernelWriterBase`,
`buildAssemblyCodeObjectFiles`/`buildSourceCodeObjectFiles` from the toolchains;
`ParallelMap2`/`getKernelFileBase` were already present). `processKernelSource` is
the only Run-contract symbol it references (called, not annotated) — no
`KernelCodeGenResult` use here.

**Cycle break (the load-bearing detail):** Tuning's sibling imports
(`from .IO import libraryRoot, libraryDir, _baseArchs, writeAssembly,
writeHelpers, _stinky_asm_verify_wanted, _verify_stinky_asm_comment_vs_elf_text`
and `from .Run import processKernelSource`) sit at the BOTTOM of Tuning.py, after
all defs, with `from __future__ import annotations` at top. Putting `from .IO
import` at Tuning's TOP would deadlock: `import Tuning → IO (top) → IO bottom
`from .Run import` → Run EOF `from .Tuning import writeSolutionsAndKernelsTCL``
which is not yet defined → ImportError. Bottom placement means all Tuning
functions are bound before any sibling import runs, so every import order
resolves. Verified import-smoke clean Run-first, Tuning-first, and IO-first.

**Monkeypatch retarget (RULE C), 17 bare-name sites → Tuning** (all inside the
four `TestWriteSolutionsAndKernelsTCL` methods in test_r7 that call
`M.writeSolutionsAndKernelsTCL` directly): `ParallelMap2` (×4),
`buildAssemblyCodeObjectFiles` (×4), `buildSourceCodeObjectFiles` (×4),
`writeHelpers` (×4), `getKernelFileBase` (×1). Each name resolves in Tuning's
`__globals__` after the move (writeHelpers is the IO function bound into Tuning's
namespace by the bottom `from .IO import`), so an `M`-target would no-op. A
`Tuning` import handle was added to the test. The NBA-11 `ParallelMap2` patch in
the `generateLogicDataAndSolutions` test stays on `Logic`.

**Alternatives rejected:** *`from .IO import` at Tuning top* — rejected: deadlocks
on Tuning-first import (above). *Stringify only the Run-type annotations* — n/a;
TCL has no Run-type annotation, and the module-wide future-import is the
established cycle-break idiom (ADR-0011).

**Validation:** import-smoke OK in all three orders;
`R.writeSolutionsAndKernelsTCL is T.writeSolutionsAndKernelsTCL`, its
`__globals__ is Tuning.__dict__`, `T.processKernelSource is R.processKernelSource`.
97 passed in TensileCreateLibraryRun/ including the TCL class + the NBA-0e
return-shape (3-tuple) pin.

**History (updates only):**
- 2026-06-26 — initial record (NBA-12).
