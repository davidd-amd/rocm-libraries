# NBA port plan — index & dependency graph

Recovering the `nba-final` `TensileCreateLibrary` decomposition onto current develop.

- **[ISSUES.md](ISSUES.md)** — the full, GitHub-issue-ready breakdown (21 issues, 6 stages), with per-issue steps, build-safety mechanism, test gate, ADR action, and acceptance criteria.
- **ADR home:** `projects/hipblaslt/tensilelite/docs/decisions/` — [ADR-0001](../../projects/hipblaslt/tensilelite/docs/decisions/0001-tensilecreatelibrary-decomposition.md) establishes the strategy; each NBA-* commit adds or updates an ADR.

## Core idea

Every commit **extracts a cohesive symbol group into a sibling module and, in the
same commit, re-imports those names back into `Run.py`**. So `import_module('…Run').<sym>`,
the `from …Run import` harness chokepoint, the 6-symbol `__init__` facade, and
`__main__.run` all keep resolving — the build and full characterization suite stay
green at every atomic commit.

## Stages & parallel waves

```
Stage 0  SAFETY NET (no production logic change)
  NBA-0  ADR home + ADR-0001                         [A]
  NBA-0b confirm/pin full-suite baseline   <-NBA-0   [A]
  NBA-0c pin passPostKernelInfoToLibrary             [A]  *critical path -> NBA-10
  NBA-0d executable import-surface pin                [A]
  NBA-0e pin TCL return contract + __init__ <-NBA-0  [B]

Stage 1  SCAFFOLD (single serialization point)
  NBA-1  empty IO.py / Logic.py / Tuning.py <-NBA-0  [C]   ALL stage 2+ depends on this

Stage 2  LEAF EXTRACTIONS — maximum parallelism (all <-NBA-1)
  NBA-2  path helpers      -> IO     <-NBA-0d         [D]
  NBA-3  stinky ELF verify -> IO     <-NBA-2  (+monkeypatch retarget) [D]
  NBA-4  mem-compression   -> IO                      [D]
  NBA-5  validity + post-kernel-to-solution -> Tuning [D]
  NBA-6  fallback rename   -> Logic                   [D]
  NBA-7  writeAssembly/writeHelpers -> IO  <-NBA-4    [D]
  NBA-8  generateKernelObjectsFromSolutions -> Logic  [D]
       (NBA-2/3/4/7 all append to Run import block + edit IO.py: land in quick succession)

Stage 3  LARGER BODIES (parallel across IO vs Logic vs Tuning)
  NBA-9  copyStaticFiles   -> IO     <-NBA-2          [E]
  NBA-10 passPostKernelInfoToLibrary -> Tuning <-NBA-0c,NBA-5 [E]
  NBA-11 generateLogicDataAndSolutions -> Logic <-NBA-6 (+LibraryIO retarget) [E]

Stage 4  EMITTERS (highest fanout/risk — serialize)
  NBA-12 writeSolutionsAndKernelsTCL (LIVE) -> Tuning <-NBA-2,3,5,7,0e [F]
  NBA-13 writeSolutionsAndKernels (public)  -> Tuning <-NBA-12          [F]

Stage 5  FINALIZE
  NBA-14 record generateKernelHelperObjects placement (ADR only) <-NBA-8 [G]
  NBA-15 slim Run.py + full no-regression gate <-7,9,10,11,13,14         [G]  (join point)
  NBA-16 OPTIONAL: repoint __init__ to true sources + migrate consumers <-NBA-15 [H]
```

## What can be worked in parallel

| Wave | Issues | Notes |
|------|--------|-------|
| 1 | NBA-0, NBA-0c, NBA-0d (group A) + NBA-0e (B, after NBA-0) | independent test-file / doc adds |
| 2 | NBA-1 | **serial bottleneck** — one commit, gates everything after |
| 3 | NBA-2, NBA-4, NBA-5, NBA-6, NBA-8 (+NBA-3 after 2, NBA-7 after 4) | the big parallel set; conflict only in Run.py import block (append-only, one line each) |
| 4 | NBA-9 ∥ NBA-10 ∥ NBA-11 | different target modules |
| 5 | NBA-12 then NBA-13 | shared Tuning.py + contract — one at a time |
| 6 | NBA-14 ∥ (NBA-15 join) → NBA-16 | |

## Top risks (see ISSUES.md "Global risks" for the full list)

1. **Monkeypatch free-variable resolution** — a moved function resolves globals in its *own* module namespace, so `monkeypatch.setattr(M_run, 'verify_stinky_paths'/'isaToGfx'/'LibraryIO.write', …)` silently no-ops after the move. Affected extractions retarget the patch to the new module **in the same commit**.
2. **Circular import** — `KernelCodeGenResult`/`KernelMinResult`/`processKernelSource` stay in `Run.py`; the `from .IO/.Logic/.Tuning import` back-import block sits at the **bottom** of `Run.py`. Import-smoke is the first gate of NBA-7/12/13.
3. **Live vs public emitter** — `run()` uses `writeSolutionsAndKernelsTCL`, not the public `writeSolutionsAndKernels`; both move to Tuning, neither is deleted. NBA-13 needs the BenchmarkProblems import-smoke + NBA-0d pin since the run() suite won't catch a break in the non-TCL path.
4. **rocisa nanobind SIGABRT** — set `ROCM_PATH`/`LD_LIBRARY_PATH`; never `--cov=<file>`; use tox envs. A green pytest is only meaningful if import-smoke passed first.
5. **Baseline drift** — re-confirm the develop full-suite count (NBA-0b) before trusting any delta in NBA-15.
