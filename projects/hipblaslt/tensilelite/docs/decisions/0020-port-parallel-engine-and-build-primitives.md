# 0020 — Port the parallel-engine + build primitives (additive, run() untouched)

**Status:** accepted  (date 2026-06-30)

**Context:** The `tensilelite-new-build-algo` branch landed only the
*decomposition* of `TensileCreateLibrary` (slim `Run.py` + `IO/Logic/Tuning.py`).
The actual *fused parallel build algorithm* from the `nba-final` tree was never
ported. This is Group 1 of a 3-group port: land the parallel-engine upgrades and
the standalone build-helper functions **as additive code that `run()` does not
yet call**, so the gfx90a build output stays structurally identical while the
primitives Group 2 will wire become available and reconciled.

**Decision:** Port the following, each reconciled to the branch's *current*
signatures (not copied verbatim from the stale `nba-final` sources), all
importable and none referenced by `run()`:

- `Tensile/CodeObjectName.py` (new) — `codeObjectFileBaseName`, the cheap
  YAML-only twin of the lazy placeholder name that `SolutionLibrary` assembles.
  Re-derived to match the branch, which had drifted from `nba-final`: added the
  `computeInputTypeA/B` split, `_MXA/_MXB` blocks, sparse `metadataLayout` (`ML`),
  the both-compute-types `f32XdlMathOp` guard, and the `_ID<chipid>` hardware
  suffix gated on `supportsChipIdPredicate`.
- `Tensile/LibraryIO.py` — `DataIndex` IntEnum (positional logic-YAML field map).
- `Tensile/TensileCreateLibrary/Logic.py` — `distribute`, `getCoFileNames`
  (extended to also read `DeviceNames` for the chip-id suffix), `schedule`.
- `Tensile/Common/Parallel.py` — `ParallelMapConfig` + a backward-compatible
  adapter in `ParallelMap2` (accepts both the develop positional form
  `ParallelMap2(fn, objects, ...)` and the fused-pipeline form
  `ParallelMap2(fn, config, objects)`); fixed the dead `procs` path (a duplicate
  `threadCount = CPUThreadCount(enable)` line clobbered `procs if procs else …`).
  Develop's per-task `globalParameters` path (which `nba-final` dropped) is
  preserved for BOTH call forms.
- `Tensile/TensileCreateLibrary/IO.py` — `generateSolutionsAndLibraries`
  (branch 7-arg `parseLibraryLogicFile`, no removed `DepthUConfig`),
  `genLazyMasterSolutionLibrary`, `generateParentLibrary` — the last two thread
  `splitGSU` into `applyNaming(splitGSU)` (`nba-final` hardcoded `False`).
- `Tensile/TensileCreateLibrary/Run.py` — `buildAssemblyKernels` (branch
  `processKernelSource`/`KernelCodeGenResult` + `IO.writeAssembly` 4-tuple +
  `assembler(gfx, wf, src, obj)`), `processMsl`, `extractBuildResults`,
  `buildCoAndHelpers` (takes a pre-bound `buildAssemblyCodeObjectFiles` partial;
  the branch dropped `ROCmLdPath` and moved `kernels` to 3rd positional), plus
  the `updateMasterLibrary`/`updateParentMasterLibrary` reducers.

**Equivalence result (gfx90a):**
- Char suite `-m unit`: **4981 passed / 220 skipped / 0 failed** — exact parity
  with the pre-change baseline, with all Group-1 code committed.
- SUBSET (6 logic files) artifacts: **IDENTICAL** (structural fingerprint) after
  every commit — inventory + ELF symbol sets + metadata content all match.
- FULL gfx90a (199 artifacts, pre-change b2f1930 vs HEAD): **inventory MATCH,
  every symbol/token COUNT MATCH.** 96 `.co` differ only in symbol-name *sha*
  with identical counts. Confirmed benign by a noise-floor measurement: an
  identical-code **HEAD-vs-HEAD** FULL rebuild shows the same signature — 93 `.co`
  vary by symbol-name sha with **0** count/inventory diffs. So the 96 are
  per-compile toolchain nondeterminism, not this change (`run()` is untouched).
- Name equivalence: `codeObjectFileBaseName(getCoFileNames(f))` reproduces the
  real emitted `.co` basename for the full gfx90a logic set (external ground
  truth = the FULL build's actual filenames).

**Build nondeterminism (measured, benign — itemized per the equivalence rule):**
The gfx90a build is not byte-deterministic. Identical-code builds differ only via:
1. `__hip_cuid_<hash>` — compiler compilation-unit id (hsaco symtab, `.co` byte
   layout, embedded in the lazy `.dat`). Normalized out of the fingerprint.
2. lazy-master `.dat` entry ORDER — parallel-completion order of a map whose
   entry set is identical (semantically equal; map lookup is order-free).
   Fingerprinted by the order-independent token set.
3. `.co` inner defined-symbol NAMES on large multi-kernel objects — same count,
   per-compile-varying names (measured: ~93 of 199 vary even on an identical-code
   HEAD-vs-HEAD rebuild, always with matching counts). Counts + inventory are the
   load-bearing invariant and both MATCH. Group 2's `equiv_check.sh` fingerprints
   `.co` by inner-symbol COUNT for this reason.
The `diff_artifacts.sh` harness (`.handoff/build-timing/`) captures the stable
structure and tolerates 1–2; two identical-code builds report IDENTICAL.

**Alternatives considered:**
- *Copy `codeObjectFileBaseName` verbatim from `nba-final`.* Rejected: it was
  stale vs the branch and would compute wrong `.co` names (mis-grouping logic
  files once wired in Group 2). Re-derivation was verified against real emitted
  filenames.
- *Swap `ParallelMap2` to the `nba-final` `(fn, config, objects)` signature.*
  Rejected: breaks every develop positional call site. The adapter preserves both.
- *Drop the per-task `globalParameters` path like `nba-final`.* Rejected:
  load-bearing on develop; kept reachable.

**Validation:** import-smoke clean; the full acceptance import line resolves
(`schedule, getCoFileNames, generateSolutionsAndLibraries, generateParentLibrary,
buildCoAndHelpers, extractBuildResults, buildAssemblyKernels, processMsl,
ParallelMapConfig`); backward-compat `inspect.signature(ParallelMap2)` still has
`objects`. Independent fresh-context review verdict: CLEAN (see
`nba-algo-port-group1-review.md`) — it also surfaced the absent-PerfMetric
truthiness edge now hardened in `codeObjectFileBaseName`.

**History (updates only):**
- 2026-06-30 — initial record (Group 1 of the NBA algo port).
