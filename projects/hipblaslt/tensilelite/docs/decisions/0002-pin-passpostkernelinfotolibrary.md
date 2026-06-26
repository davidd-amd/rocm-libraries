# 0002 — Pin passPostKernelInfoToLibrary before extraction

**Status:** accepted  (date 2026-06-26)

**Decision:** Add behavioral characterization for
`passPostKernelInfoToLibrary` against its in-place implementation
(`Run.py` 308-373) before it is moved to `Tuning.py` (NBA-10).

**Why:** It is the only develop-only function in the decomposition scope
with zero behavioral assertion — `test_r7` only ever `patch.object(M,
...)`'s it to a no-op (8 sites). Moving an unasserted function would be an
untested relocation of develop-only logic (the full per-`sizeMapping`
write-back into both `masterLibrary.solutions` and `lazyLibraries`, the
`AdaptiveGemmNTAB` `.get` default, and the `KeyError` diagnostic branch).
The pin makes NBA-10 a behavior-preserving move that the suite can verify.

**Alternatives rejected:** *Move it under the existing no-op patches and
trust the run() path* — rejected: the run() char suite never exercises the
real write-back, so a regression would be silent. Would win only if the
field set were already covered elsewhere (it is not).

**Validation:** `pytest TensileCreateLibraryRun/test_run_helpers_char.py`
= 25 passed (3 new). No production symbol moved.

**History (updates only):**
- 2026-06-26 — initial record (NBA-0c).
