# 0017 — Placement of generateKernelHelperObjects (keep in Run.py)

**Status:** accepted  (date 2026-06-26)

**Decision:** Keep `generateKernelHelperObjects` defined in `Run.py`; do NOT move
it to Logic or IO. Documentation-only — no code moves in this issue, so the
RULE G chokepoint import is undisturbed.

**Why:** The `_codegen` characterization harness imports it directly from the
Run module — `codegen_harness.py:260` does
`from Tensile.TensileCreateLibrary.Run import generateKernelObjectsFromSolutions,
generateKernelHelperObjects`, and the `_codegen/test_r2_kwconv_char.py` /
`test_r3_kwfeat_char.py` suites call it positionally. The companion
`generateKernelObjectsFromSolutions` was moved to Logic (NBA-8) but is
back-imported into Run, so the harness still resolves both from Run today.
Leaving `generateKernelHelperObjects` physically in Run (rather than moving it
and adding yet another back-import) keeps it next to `processKernelSource` and
the shared `KernelCodeGenResult`/`KernelMinResult` contract it is conceptually
part of, and matches the nba-final template, which also keeps it in the Run
shell. It reads `kernelObjectNameCallables`/`initHelperKernelObjects`/
`itertools` — all already imported in Run — so there is no import-hygiene reason
to move it.

**Alternatives rejected:** *Move to Logic by the "derivation pass" listing rule +
re-export* — would be consistent with NBA-8's `generateKernelObjectsFromSolutions`
placement and is the option that would win **if Run.py is later converted to a
package** (the back-import shim is cheap but is still an extra indirection). For
this port it adds a back-import and a potential retarget surface for no
behavioral or cycle benefit, so it is deferred. The condition that would flip the
decision: a future Run→package conversion where keeping leaf logic out of the
package `__init__` is desirable.

**Validation:** `grep` confirms `generateKernelHelperObjects` is defined only in
Run.py (absent from IO/Logic/Tuning) and the harness import path resolves; the
`_codegen` suites (which exercise it) remain green from the Stage-4 gate. No code
change in this commit.

**History (updates only):**
- 2026-06-26 — initial record (NBA-14).
