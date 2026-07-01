# NBA parallel-build-algo — Group 1 port review

**Verdict: CLEAN** (no correctness or requirement gaps found)

Reviewed commits (after `b2f1930305a`):
- `a51330f4d49` harness (non-production, `.handoff/` + progress md only)
- `e450b4d13c6` schedule + getCoFileNames + naming infra (CodeObjectName.py, LibraryIO.DataIndex, Logic.py)
- `120cfc45ac8` Parallel.py engine reconcile (ParallelMapConfig + procs fix)
- `7afc84802e1` IO.py fused-pipeline helpers
- `24d88d14242` Run.py fused-pipeline helpers

Compared against source-of-truth `nba-final` tree and the branch's current `SolutionLibrary.py`, `LibraryIO.py`, `Toolchain/*`, and `TensileCreateLibrary/Logic.py`.

## Gaps found

None. No defect affecting correctness or violating the stated requirements was identified. All new symbols compile (`python -m py_compile` clean on all six changed files); full import could not be exercised only because the native `rocisa` extension is not built in this environment (known env limitation, not a code issue).

## Verified correct (coverage)

### Requirement 1 — additive only, run() unchanged
- `git diff b2f1930305a..HEAD` on `Run.py` shows exactly two hunks: the new helper defs inserted at line 155 (before `run()` at line 245) and three added names in the `from .IO import (...)` block. The `run()` body (lines 245–459) has **zero** diff.
- Grepped every named symbol (`schedule`, `getCoFileNames`, `generateSolutionsAndLibraries`, `generateParentLibrary`, `genLazyMasterSolutionLibrary`, `buildAssemblyKernels`, `processMsl`, `buildCoAndHelpers`, `extractBuildResults`, `updateMasterLibrary`, `updateParentMasterLibrary`). Each appears only in its own definition, in docstrings, in import statements, or in calls *inside the new helpers* (Run.py:210,212,225 are within `processMsl`/`extractBuildResults`, not `run()`). `run()` calls none of them.

### Requirement 2 — reconciled to the branch

**`CodeObjectName.codeObjectFileBaseName` (new file) vs branch `SolutionLibrary.py`** — matches.
- Concatenation order reproduces the branch's actual name-assembly order. `FromOriginalState` (SolutionLibrary.py:545-604) applies the lazy `libraryOrder = [hardware, operationIdentifier, performanceMetric, predicates, placeholder, selection]` by recursing on `[selection]` first, then applying `reversed([hardware, operationIdentifier, performanceMetric, predicates])`. Net emission order = selection → predicates → performanceMetric → operationIdentifier → hardware. `CodeObjectName.py` builds in exactly that order (selection @54-100, predicates @103, perf @106-111, opId @113-115, hardware @117-129).
- The `selection()` block is byte-equivalent (whitespace-normalized diff of CodeObjectName.py:55-100 vs SolutionLibrary.py:493-539 is empty). It correctly includes the branch-only pieces that nba-final's stale copy dropped: `computeInputTypeA/B` split (55-57 vs SL 494-496), `_MXA/_MXB` blocks (68-71 vs SL 522-525), sparse `metadataLayout` `"ML"` (94-96 vs SL 535-537), and `_UA` (99-100 vs SL 538-539). Confirmed via diff against nba-final's CodeObjectName.py that these were re-derived, not copied.
- `predicates` uses `problemType.placeholderStr(includeBatch=True, includeType=True)` (103) matching SL:450.
- `performanceMetric` uses `Tensile.Properties.Predicate` (imported line 25) — same class as SL's `Properties.Predicate` (SL:435).
- `hardware` reproduces the `_CU`, `_ID<chipid>` (gated on `pciChipId and supportsChipIdPredicate(devicePart)`), and `_<devicePart>` suffixes (117-129) matching `MasterSolutionLibrary.hardware` (SL:337-381). The chip-id list/scalar sanitization (`replace('Device ', '').strip()`) matches SL:372-378.
- `getCoFileNames` (Logic.py:65-84) correctly added `data["DeviceNames"]` (nba-final omitted it), which is required to feed the `_ID<chipid>` suffix. Field indices come from `LibraryIO.DataIndex`, whose values (PROBLEM_TYPE=4, DEVICE_PROPERTIES=2, DEVICE_NAMES=3, PERF_METRIC=10) match the positional layout in `parseLibraryLogicList` (LibraryIO.py:648-666) and `rawLibraryLogic` (LibraryIO.py:698-717). Verified real logic files carry index 10 = `"DeviceEfficiency"`, so the no-PerfMetric-suffix path matches SL for real inputs.

**`Parallel.py` (`120cfc45ac8`)** — matches.
- Legacy positional signature `ParallelMap2(function, objects, message="", enable=True, multiArg=True, return_as="list", procs=None)` is intact (Parallel.py:212-214).
- The adapter (231-235) correctly detects `isinstance(objects, ParallelMapConfig)`, rebinds `objects = message` (the true objects arrive 3rd positional), and unpacks `message, enable, multiArg, return_as, procs` from the config. Legacy callers (no config) skip this block untouched.
- The "procs fix" is correct: the duplicate `threadCount = CPUThreadCount(enable)` that clobbered the procs-aware line was removed, leaving `threadCount = procs if procs else CPUThreadCount(enable)` (241). With the default `procs=None`, this reduces to `CPUThreadCount(enable)` — identical to prior default behavior.
- Develop's per-task `globalParameters` path is preserved (259-270): `pcall = pcallWithGlobalParamsMultiArg if multiArg else pcallWithGlobalParamsSingleArg`, `pargs = zip(objects, itertools.repeat(globalParameters))`, `delayed(pcall)(function, a, params)`. Not dropped the way nba-final dropped it.
- `ParallelMapConfig` is exported via `Tensile.Common` (`Common/__init__.py` does `from .Parallel import *`; Parallel.py has no `__all__`, so the public class is exported). Nothing imports it yet — consistent with additive-only.

**`IO.py` (`7afc84802e1`)** — matches.
- `generateSolutionsAndLibraries` (IO.py:225-246) calls the branch's 7-arg `parseLibraryLogicFile(logicFile, assembler, False, True, False, isaInfoMap, lazy)`. Argument positions map to `(filename, assembler, splitGSU=False, printSolutionRejectionReason=True, printIndexAssignmentInfo=False, isaInfoMap, lazyLibraryLoading)` — exactly what `generateLogicDataAndSolutions` (Logic.py:190-201) uses. The removed 8-arg `DepthUConfig()` form (nba-final IO.py:40) is dropped.
- Accesses `libraryLogic.solutions / .architecture / .library`, all present on `LibraryLogic` NamedTuple (LibraryIO.py:493-501).
- `genLazyMasterSolutionLibrary` (248-254) and `generateParentLibrary` (257-273) both thread `splitGSU` into `applyNaming(splitGSU)`. Confirmed nba-final hardcoded `applyNaming(False)` (nba-final IO.py:104,112) — the develop `splitGSU` feature is restored (default `False`, overridable).
- `state` is imported from `Tensile.Common` (re-export of `Common/Utilities.state`); `write` from `Tensile.LibraryIO`. Both resolve.

**`Run.py` helpers (`24d88d14242`)** — matches.
- `buildAssemblyKernels` (Run.py:158-177) uses the branch `processKernelSource(kernelWriterAssembly, data, outOptions, splitGSU, k)` (Run.py:88, `compress` defaults False), unpacks `IO.writeAssembly`'s 4-tuple `for p, isa, wavefrontsize, _` (IO.py:165-178 returns `(path, isa, wfsize, minResult)`), and calls `assembler(isaToGfx(isa), wavefrontsize, str(p), str(p.with_suffix(".o")))` matching `Assembler.__call__(targetGfx, wavefrontSize, srcPath, destPath)` (Toolchain/Component.py:162). This is the correct reconcile vs nba-final's `_processKernelSource(..., False, False, None, k)` + 3-tuple unpack (nba-final Run.py:134,136).
- The `set(writeAssembly(...) for k in pksResults)` is safe: the 4-tuple is hashable (`KernelMinResult` is a NamedTuple of ints).
- `buildCoAndHelpers` (230-227) is a generic unary wrapper `unaryBuildCOFile(uniqueAsmKernels)`; it is signature-agnostic and compatible with a partial over the branch `buildAssemblyCodeObjectFiles(linker, bundler, kernels, destRoot, asmDir, compress=True)` (Toolchain/Assembly.py:52) — no `ROCmLdPath`, kernels 3rd positional. Actual binding of destRoot/asmDir is Group-2 wiring, not exercised here.
- `processMsl` (201-213) threads `splitGSU` into `genLazyMasterSolutionLibrary(..., splitGSU)` (develop feature preserved).
- Helper deps all present in Run.py: `os` (27), `Path` (29), `isaToGfx` (48), `processKernelSource` (88), `writeAssembly`/`genLazyMasterSolutionLibrary` imported (474/468). Names used only inside function bodies, resolved at call time — the trailing `from .IO import` block ordering is fine.

### Requirement 3 — no dropped develop behavior
Every develop-only behavior remains reachable: `splitGSU` threaded through `processMsl` / `genLazyMasterSolutionLibrary` / `generateParentLibrary`; per-task `globalParameters` preserved in `ParallelMap2`; chip-id + MX + metadataLayout naming present in `codeObjectFileBaseName`; the branch's 7-arg `parseLibraryLogicFile` (not the removed `DepthUConfig` form) is used. Memory compression (`memCompress`/`memDecompress`) is untouched and still imported in Run.py.

## Non-defect note (informational, no action required)
`getCoFileNames` sets `data["PerfMetric"] = None` when a logic file's index-10 field is absent/null (Logic.py:82), whereas `parseLibraryLogicList` omits the key entirely in that case. Fed into `codeObjectFileBaseName`, a literal `None` would take the non-DeviceEfficiency branch and build `Predicate(tag=None)`. This is a **pre-existing latent edge inherited verbatim from nba-final** (identical pattern in nba-final Logic.py:83 + CodeObjectName.py:58-59), it does not fire for any real logic file (all observed files carry index 10 = `"DeviceEfficiency"`), and the code path is not wired into `run()` in Group 1. It is not a regression introduced by this port and is out of scope for the Group-1 rubric; flagging only so Group 2 can harden it (e.g. `d.get("PerfMetric") or "DeviceEfficiency"`) if desired.
