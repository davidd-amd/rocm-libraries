# 0004 — Pin the TCL emitter return contract and normalize the __init__ facade

**Status:** accepted  (date 2026-06-26)

**Decision:** Pin `writeSolutionsAndKernelsTCL` (the live emitter `run()`
calls at `Run.py:1036`) to its exact 3-tuple return shape
(`count:int, uniqueKernels:list, results:list`), and rewrite `__init__.py`
from a single-line import into an explicit multiline import of the same 6
names from `.Run`.

**Why:** `run()` unpacks the triple positionally, so the later move to
`Tuning.py` (NBA-12) must preserve that shape; an explicit assertion makes
the move verifiable. The multiline `__init__` is behavior-preserving today
(same 6 names, same source) but becomes the seam where NBA-16 can later
repoint individual names at their true home modules without reformatting.

**Alternatives rejected:** *Leave `__init__` as one line and repoint it in
NBA-16* — rejected only on ergonomics: normalizing now keeps the NBA-16
diff to source-path changes instead of mixing in a reformat. Behaviorally
identical, so either ordering is correct.

**Validation:** `pytest TensileCreateLibraryRun/ test_library_paths.py`
= 115 passed; init-smoke OK. `__init__` resolved symbol set unchanged
(guarded by NBA-0d).

**History (updates only):**
- 2026-06-26 — initial record (NBA-0e).
