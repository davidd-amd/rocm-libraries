# 0006 — Extract stinky-asm ELF verification to IO.py (with monkeypatch retarget)

**Status:** accepted  (date 2026-06-26)

**Decision:** Move `_stinky_asm_verify_wanted`, `_stinky_out`,
`_verify_stinky_asm_comment_vs_elf_text` (Run.py, post-NBA-2 lines ~106-162)
into `IO.py` with their deps (os, isaToGfx, globalParameters, IsaVersion,
printExit, verify_stinky_paths), re-import into Run via the EOF block, and
**retarget the 16 bare-name monkeypatch sites** (`isaToGfx`,
`verify_stinky_paths`, `_stinky_out`) from `M` to `IO` in the SAME commit.

**Why:** These functions read module globals that the helper/orchestration char
tests patch on `M = import_module('...Run')`. A moved function resolves free
variables in ITS OWN module's `__globals__`, so a bare-name `setattr(M, ...)`
silently no-ops after the move (RULE C/D). The 16 bare-name sites — including the
MULTILINE `setattr(M, "verify_stinky_paths", ...)` at
test_run_orchestration_char.py:164 that a single-line grep missed (caught by the
audit critic) — are retargeted to `IO`. The shared-singleton patches
(`setitem(M.globalParameters, ...)`, `setattr(M.os, "write", ...)`) are LEFT as
`M.*`: `globalParameters` and `os` are the same objects in Run and IO, so the
mutation is visible to the moved function without retargeting (verified).

**Alternatives rejected:** *Retarget all M-patches uniformly, including
globalParameters/os* — rejected: needless churn, and empirically those shared
objects don't need it; over-retargeting also risks AttributeError if a target
module lacks the name. *Leave the bare-name patches on M and rely on Run keeping
the import* — rejected: the moved function never reads Run's binding, so those
patches would no-op (this is the proposal-3 defect).

**Validation:** import-smoke OK (no cycle; `R._verify_... is IO._verify_...`).
A discriminating probe (distinct sentinels on `M.` vs `IO.`) confirms the moved
function reads `IO.verify_stinky_paths`/`IO._stinky_out`, proving the retarget is
effective (not merely test-passing). 97 passed in TensileCreateLibraryRun/.

**History (updates only):**
- 2026-06-26 — initial record (NBA-3).
