# 0003 — Executable import-surface contract for the port

**Status:** accepted  (date 2026-06-26)

**Decision:** Encode RULES A/B/F as three guard tests in
`test_run_orchestration_char.py`: the 6 package re-exports, every `.Run`
backbone symbol the decomposition moves (plus the shared contract that
stays), and the `__main__.run` attr.

**Why:** Consumers bind package internals two ways (package-root re-exports
for `ClientWriter`/`BenchmarkProblems`/`GenerateSummations`; direct
`.Run`/`import_module('...Run').<attr>` access for the char harnesses). An
extraction that drops a symbol would otherwise fail at a distant consumer
or — worse — pass locally while silently breaking an untested path. A
single source-level guard fails fast, at the commit that drops the symbol.

**Alternatives rejected:** *Rely on the downstream consumer suites to
catch a dropped symbol* — rejected: failures would be indirect and some
paths (non-TCL emitter) have no run()-path coverage. Would win only if
every consumer were already exercised, which the live-vs-public emitter
split disproves.

**Validation:** `pytest TensileCreateLibraryRun/test_run_orchestration_char.py`
= 31 passed (3 new). Pure additive guard; no production change.

**History (updates only):**
- 2026-06-26 — initial record (NBA-0d).
