# 0010 — Extract validity-pruning + post-kernel-to-solution to Tuning.py

**Status:** accepted  (date 2026-06-26)

**Decision:** Move `_checkInvalidSolutionsAndKernels`, `_checkInvalidSolutions`,
`removeInvalidSolutionsAndKernels`, `passPostKernelInfoToSolution` into
`Tuning.py` (with functools, ParallelMap2, printExit, tqdm, getKeyNoInternalArgs,
getKernelNameMin) and re-import into Run via the EOF block. Retarget the 4
bare-name patches (getKeyNoInternalArgs ×2, ParallelMap2 ×1 [multiline],
getKernelNameMin ×1) from `M` to `Tuning` in the SAME commit.

**Why:** These four directly-tested functions read module globals the helpers
char tests patch on `M`. After the move they resolve those names in
`Tuning.__globals__`, so the bare-name patches must retarget (RULE C/D).
`_checkInvalidSolutions` is DEAD (no production caller) but test-bound; per the
user's no-deleting-dead-code rule it is moved verbatim and flagged here for the
owner. The ParallelMap2 worker `_checkInvalidSolutionsAndKernels` stays
top-level in Tuning (picklable).

**Alternatives rejected:** *Delete the dead `_checkInvalidSolutions`* — rejected
(scope discipline: no deleting dead code outside the active change). *Leave the 4
patches on M* — they would no-op against the moved functions (the central
landmine).

**Validation:** import-smoke OK (`R.removeInvalidSolutionsAndKernels is
T.removeInvalidSolutionsAndKernels`). Call-recording probe confirms
`passPostKernelInfoToSolution` reads `Tuning.getKernelNameMin` only ({'T'}).
97 passed in TensileCreateLibraryRun/.

**DEFERRED for owner:** `_checkInvalidSolutions` is dead code (no production
caller; only test-bound). Consider removal in a dedicated change.

**History (updates only):**
- 2026-06-26 — initial record (NBA-5).
