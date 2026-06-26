# 0001 — TensileCreateLibrary decomposition: extract-then-reexport

**Status:** proposed  (date 2026-06-26)

**Decision:** Recover the `nba-final` layered decomposition of
`Tensile/TensileCreateLibrary/` — slim `Run.py` orchestrator plus `IO.py`
(disk/serialization + path layout), `Logic.py` (logic-file discovery,
scheduling, fallback rename, unique-kernel derivation), and `Tuning.py` (the two
kernel emitters + validity pruning + post-kernel write-backs) — onto develop's
1138-LOC monolithic `Run.py`. Do it as a sequence of small atomic commits, each
of which **extracts a cohesive symbol group into a sibling module and, in the
same commit, re-imports those names back into the `Run` namespace** (and updates
`__init__.py` / any monkeypatch targets in the same commit). The shared worker
contract (`KernelCodeGenResult`, `KernelMinResult`, `processKernelSource`,
`generateKernelHelperObjects`) stays defined in `Run.py`, with the back-import
block at the **bottom** of the file to break the IO/Tuning→Run cycle.

**Why:** Consumers bind package internals two ways that must not break at any
commit: source code imports the 6-symbol public surface from the package root
(`ClientWriter.py`, `BenchmarkProblems.py`, `GenerateSummations.py` via
`__init__.py`), while the `_codegen`/`LocalRead` characterization harnesses and
`test_library_paths.py` / `test_perArchFallbackRename.py` import internals
directly via `from Tensile.TensileCreateLibrary.Run import ...` and via
`import_module('...Run').<attr>` (RULES A–H in `docs/nba-port-plan/ISSUES.md`).
Extract-then-reexport keeps every one of those resolving at each atomic commit,
so the build and the full characterization suite stay green throughout — the
user's hard requirement. `run()` calls the live `writeSolutionsAndKernelsTCL`
(Run.py:1036) and `passPostKernelInfoToLibrary` (Run.py:1065); both, plus the
non-TCL public `writeSolutionsAndKernels`, move to `Tuning.py` and none may be
deleted.

**Alternatives rejected:**
- *Convert `Run.py` into a `Run/` package* — would also preserve
  `Tensile.TensileCreateLibrary.Run.<attr>` resolution, but is a larger, riskier
  single move and complicates the monkeypatch-target story; it would win only if
  the back-import block proved unmaintainable.
- *Big-bang re-split matching nba-final verbatim* — rejected: nba-final predates
  develop's path-layout, stinky-asm ELF verification, src mem-compression, dual
  TCL/non-TCL emitters, occupancy/subtile-TDM write-backs, and arch-predicate
  filtering, so a verbatim drop would break the build and lose develop-only work.
- *Append build decisions to the characterization `DECISIONS.md`* — rejected: that
  log's charter is suite coverage choices; folding build-refactor ADRs in blurs
  two logs. Would win only if the team insists on exactly one file to read.

**Validation:** Per-commit gate (see `docs/nba-port-plan/ISSUES.md`):
import-smoke `python -c "import Tensile.TensileCreateLibrary as m; m.run"` FIRST,
then the affected characterization suite; full `tox -e unit -- -m unit
Tensile/Tests/unit` once per stage against the re-confirmed develop baseline
(NBA-0b). Baseline to confirm before trusting any delta: DECISIONS.md D15
(2466 passed / 201 skipped) — re-measure on this worktree, do not assume.

**History (updates only):**
- 2026-06-26 — initial record (NBA-0). Subsequent NBA-* commits append their
  per-issue decision + green proof here or supersede with a focused ADR.
- 2026-06-26 — NBA-0b: confirmed full-suite baseline on this untouched
  worktree via `tox -e unit -- -m unit Tensile/Tests/unit` =
  **4974 passed, 220 skipped, 0 failed** (753 syrupy snapshots passed; 16
  benign codegen warnings) in 372s. This supersedes the stale DECISIONS.md
  D15 figure (2466/201), which under-counted by ~2x; 4974/220 is the
  immutable baseline NBA-15 compares against. No production code changed.
