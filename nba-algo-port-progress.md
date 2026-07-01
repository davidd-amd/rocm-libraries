# NBA algo port — progress (durable scratch)

Re-read after any compaction. Plan: `.handoff/nba-algo-port/{README,goal-1,goal-2,goal-3}.md`.

## Baselines (captured pre-change, Group 1)

- **Char suite**: `4981 passed, 220 skipped, 1060 deselected` (`-m unit`, serial, in
  `hsc` container `/repo/.claude/worktrees/parallel-build-algo/projects/hipblaslt/tensilelite`,
  `.tox/unit/bin/python -m pytest -q -m unit`). 753 snapshots passed. Runtime ~12min.
- **gfx90a artifacts (dev SUBSET, 15 files)**: fingerprint at
  `.handoff/build-timing/fp-baseline-subset.txt`. Harness `diff_artifacts.sh`
  validated: two identical-code builds report `IDENTICAL`.
- **import-smoke**: `import Tensile.TensileCreateLibrary.Run` clean.

## Env (validated)

- Char + import-smoke: container **`hsc`** (repo mounted at `/repo`), venv
  `.tox/unit`. `docker exec hsc bash -lc 'cd /repo/.claude/worktrees/parallel-build-algo/projects/hipblaslt/tensilelite && .tox/unit/bin/python -m pytest -q -m unit -p no:cacheprovider'`.
- gfx90a build/fingerprint: `.handoff/build-timing/diff_artifacts.sh {capture <name>|<a> <b>} {SUBSET|FULL}`
  (image `tensilelite-char:gpumocks`, prebuilt rocisa). SUBSET build ~60s.
- A/B: `.handoff/build-timing/run_ab.sh <runs> <warmups> {SUBSET|FULL}`.

## Build nondeterminism (MEASURED, benign — informs the equiv gate)

The gfx90a build is NOT byte-deterministic. Two identical-code builds differ in
exactly two ways, both benign and both handled by `diff_artifacts.sh`:
1. **`__hip_cuid_<hash>`** — compiler-generated compilation-unit id, varies per
   compile. Appears in the `.hsaco` symtab (1461/1462 syms identical, only the
   cuid differs), the `.co` byte layout/size (±hundreds of bytes), and embedded
   in the lazy-master `.dat`. Filtered/normalized out of the fingerprint.
2. **lazy-master `.dat` entry order** — the placeholder->library map serializes
   in parallel-completion order, which drifts run-to-run; the entry SET is
   identical (`Half`/`BFloat16`, `HH`/`BB` entries swap). Fingerprint uses the
   order-independent printable-token set. Semantically equivalent (map lookup).

Fingerprint scheme: `.hsaco`/`.co-inner` = defined-symbol set minus cuid;
`.dat.zlib` = decompressed size + cuid-normalized order-independent token-set sha;
other files = byte sha. Inventory (filenames) must match exactly.

## Divergence: branch vs nba-final code-object naming (CRITICAL for the port)

nba-final's `getCoFileNames`/`schedule` (Logic.py) depend on
`CodeObjectName.codeObjectFileBaseName` + `LibraryIO.DataIndex`, NEITHER of which
exists on this branch. The branch builds the lazy placeholder name inline across
`SolutionLibrary.py`: `selection()` (types/features @492-539), `predicates()`
(placeholderStr @451), `performanceMetric()` (@438), `operationIdentifier()`
(@426), `hardware()` (CU + optional `_ID<chipid>` + device @363-379).

nba-final's `codeObjectFileBaseName` is a flattened copy of that assembly but is
STALE vs the branch — it lacks: `computeInputTypeA/B` split, `_MXA/_MXB` blocks,
sparse `metadataLayout` (`ML`), the f32XdlMathOp guard on both compute types, and
the `_ID<chipid>` hardware suffix. Porting it verbatim would compute WRONG cofile
names (only matters once run() is rewired in Group 2, but must be reconciled).

Plan: port `codeObjectFileBaseName` (new `CodeObjectName.py`) + `DataIndex`
(into `LibraryIO.py`) as ADDITIVE infra, re-derived to match the branch naming
exactly; add a name-equivalence verification vs real `SolutionLibrary` output.

## Symbol work-list status

| Unit | target | status |
| ---- | ------ | ------ |
| baseline + diff_artifacts.sh | .handoff/build-timing | DONE |
| CodeObjectName.codeObjectFileBaseName (infra) | new module | TODO |
| DataIndex (infra) | LibraryIO.py | TODO |
| schedule | Logic.py | TODO |
| getCoFileNames | Logic.py | TODO |
| Parallel.py engine (ParallelMapConfig + return_as + procs) | Common/Parallel.py | TODO |
| generateSolutionsAndLibraries | IO.py | TODO |
| generateParentLibrary | IO.py | TODO |
| buildAssemblyKernels | Run.py | TODO |
| processMsl | Run.py | TODO |
| buildCoAndHelpers | Run.py | TODO |
| extractBuildResults | Run.py | TODO |
