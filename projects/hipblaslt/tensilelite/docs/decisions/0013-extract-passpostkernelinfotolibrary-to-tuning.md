# 0013 — Extract passPostKernelInfoToLibrary to Tuning.py

**Status:** accepted  (date 2026-06-26)

**Decision:** Move the 66-LOC develop-only library write-back
`passPostKernelInfoToLibrary` into `Tuning.py` and re-import into Run via the EOF
`from .Tuning import …` block. Tuning gains `getKernelFileBase` (added to its
existing `Tensile.SolutionStructs.Naming` import) — the function's only
dependency. Every develop-only `sizeMapping` field is copied verbatim
(`CUOccupancy`, `MathClocksUnrolledLoop`, `PrefetchGlobalRead`, `NonTemporalA/B/D`,
`adaptiveGemmNTAB`, `WaveSeparateGlobalReadA/B`, `UnrollLoopSwapGlobalReadOrder`,
`DirectToVgprA/B`) along with both KeyError diagnostic branches (masterLibrary +
lazyLibrary).

**Monkeypatch retarget (RULE C):** the moved function reads `getKernelFileBase`
in Tuning's `__globals__`, so the three NBA-0c direct-call tests
(`test_run_helpers_char.py:241,271,281`) had their
`monkeypatch.setattr(M, "getKernelFileBase", …)` retargeted to
`setattr(Tuning, …)` in this same commit. Leaving them on `M` would silently
no-op and the tests would run against the real `getKernelFileBase`.

**Why gated on NBA-0c:** before NBA-0c this function was only ever
`patch.object(M,…)`'d to a no-op in test_r7 (zero behavioral assertion). NBA-0c
pinned its real output first, so this relocation of develop-only logic is
behaviorally guarded — that is why NBA-0c is a hard dependency. Run keeps its own
`getKernelFileBase` import (still used by `processKernelSource` and
`writeSolutionsAndKernels`).

**Alternatives rejected:** *Move it without NBA-0c* — rejected: an untested
relocation of develop-only write-back logic; a silent regression would not be
caught by any assertion.

**Validation:** import-smoke OK; `R.passPostKernelInfoToLibrary is
T.passPostKernelInfoToLibrary` and `…__globals__ is Tuning.__dict__` (sentinel
proof the retarget is effective). 97 passed in TensileCreateLibraryRun/ including
the NBA-0c masterLibrary/lazyLibrary write-back + KeyError-diagnostic cases.

**History (updates only):**
- 2026-06-26 — initial record (NBA-10).
