# 0018 — Slim Run.py to orchestration core + back-imports

**Status:** accepted  (date 2026-06-26)

**Decision:** With all extractions landed (NBA-2…13), remove the now-dead
top-level imports from `Run.py` and confirm it defines only the orchestration
core plus the shared worker contract and the EOF back-import block. Run.py drops
from develop's **1138 LOC to 405 LOC**.

**What Run.py now defines (only):** `run()` (@profile), `processKernelSource`,
`generateKernelHelperObjects` (ADR-0017 keep-in-Run), the two NamedTuples
`KernelCodeGenResult`/`KernelMinResult`, and the single EOF back-import block
(`from .IO / .Logic / .Tuning import …`).

**Module map (LOC):** Run 405 · IO 223 · Logic 237 · Tuning 446.

**Dead-import removal (grep-verified, zero references in Run body lines):**
`rocisa`, `copy`, `functools`, `pickle`, `zlib`, `typing.Collection`,
`SOURCE_PATH`, `CHeader`, `tqdm`, `timing_context`, `getKernelNameMin`,
`KERNEL_HELPER_FILENAME_CPP/H`, `MasterSolutionLibrary`, `PlaceholderLibrary`,
`mergeTypeMismatchCollector`, `printTypeMismatchSummary`, `verify_stinky_paths`,
`buildAssemblyCodeObjectFiles`, `buildSourceCodeObjectFiles`, `timing`, and the
duplicate `printWarning`. Each was confirmed unused in the remaining Run body
(lines 86-394 pre-edit) and absent from the `_RUN_BACKBONE`/`_PACKAGE_REEXPORTS`
membership pins; the patches that referenced these names in tests are all
retargeted to IO/Tuning (NBA-3/10/12). `rocisa` is still imported transitively
(IO/Tuning import it; Run's EOF back-imports them), so removing the bare
`import rocisa` from Run does not change what loads.

**RULE D imports explicitly RETAINED** (read by tests via `M.*` shared-singleton
monkeypatches, even though now unused inside Run's own body): `os`, `shutil`,
`from Tensile import LibraryIO`, and `globalParameters`. `globalParameters` was
flagged dead-in-body but is kept deliberately — `run()`'s removed; the validity
and emitter passes that read it now live in Tuning, but the orchestration tests
still mutate `M.globalParameters`, which is the same singleton (`M.globalParameters
is IO.globalParameters`).

**Why:** the back-import block keeps every moved symbol importable from `.Run`
(RULE A) and the package facade intact (RULE B); the slim module is the readable
orchestration shell the decomposition set out to produce.

**Alternatives rejected:** *Also drop the RULE D imports since they are unused in
Run's body* — rejected: would break `test_run_orchestration_char.py` /
`test_r7_createlib_deep_char.py` monkeypatches that mutate `M.os`/`M.shutil`/
`M.LibraryIO`/`M.globalParameters` (RULE D). *Convert Run.py to a package* —
out of scope; the shim approach keeps the diff atomic and reversible.

**Validation:** import-smoke OK; RULE D imports confirmed still attributes of M;
full no-regression gate **4981 passed / 220 skipped / 0 failed** (346s) — exactly
the NBA-0b/Stage-2/3/4 baseline, zero regression across the whole port. Broad
char suites (TCLR + _codegen + LocalRead + ParseArguments + test_library_paths +
test_perArchFallbackRename) green.

**History (updates only):**
- 2026-06-26 — initial record (NBA-15). Final Run.py = 405 LOC (from 1138);
  full gate 4981/220/0.
