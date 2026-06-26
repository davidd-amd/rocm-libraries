# 0007 — Extract mem-compression helpers to IO.py

**Status:** accepted  (date 2026-06-26)

**Decision:** Move `memCompress`/`memDecompress` into `IO.py` (with `pickle`,
`zlib`) and re-import into Run via the EOF block.

**Why:** Tiny, pure, zero monkeypatched-global reads (NBA-4 audit: zero
retargets). `processKernelSource` (stays in Run) calls `memCompress` via the
back-import; `writeAssembly` (moves to IO in NBA-7) will call IO-local
`memDecompress`. Both names stay test-bound on `.Run` (RULE C).

**Alternatives rejected:** *Keep them in Run* — they belong with the
serialization layer and `writeAssembly` (NBA-7) needs `memDecompress` IO-local;
keeping them in Run would force NBA-7 to round-trip through Run. Would win only
if nothing in IO used them (false).

**Validation:** import-smoke + roundtrip OK (`R.memCompress is IO.memCompress`,
`R.memDecompress(R.memCompress(x)) == x`); 66 passed across helpers + r7.

**History (updates only):**
- 2026-06-26 — initial record (NBA-4).
