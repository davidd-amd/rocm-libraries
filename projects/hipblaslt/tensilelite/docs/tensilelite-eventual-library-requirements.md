# TensileLite eventual library: requirements and supported features

This list is what the library has to support after the stage split, so a later change is an addition at a named boundary. It combines the generation-design thread, the follow-up constraints on runtime generation and architectures, and the eight-slide developer brief (why, problems, organization, examples, safe execution, alternatives, impact, evidence).

The first-increment sequence stays in `tensilelite-first-increment-requirements.md`. This document is the end state that sequence has to leave possible.

## How a customization is added

A customization is a new variant of an existing feature, a new architecture, or a new kernel behavior. It is accepted when all of the following are true:

1. The change adds a module, a registration, or an architecture file at one existing boundary. It does not add a branch to `KernelWriter.py`, `KernelWriterAssembly.py`, or the library-build command for a variant those files already know how to dispatch.
2. The new module takes its inputs as arguments. It does not read or write `solution._state`, `writer.states`, `globalParameters`, or a process-global instruction scheduler.
3. The new module has a direct test. A full-kernel byte recording is the guard during the move. A focused test replaces that recording for the behavior once the behavior has a name.
4. Existing imports, the library-build command, and component dispatch keep working until a recorded test shows the old path has no callers. The old path is deleted only after that.
5. The change is one reason to edit. A fallback change and a publish change are different changes. An occupancy change is an occupancy change, not an edit inside the writer file.

The slide brief states the same bar as four problems: local testability, cohesion, mutable shared data, and extensibility. StreamK, the schedule-iteration algorithm (SIA), global-split-U (GSU), and scheduler variants are the named cases. Today each of those risks another branch in the central writer.

## Boundaries a customization uses

Each feature lives in one of these boundaries. The generation thread supplies the stage and pass boundaries. The slides supply the module and library-build boundaries. A module from the slide list belongs to one stage.

| Boundary | What is added there | What stays out |
| --- | --- | --- |
| Shared config | Values every stage reads: problem type, tile geometry, instruction-set architecture, wavefront size | Writes from any stage |
| Stage config and stage state | Values and mutable data owned by one phase, passed into the next phase as an argument | A flat `Solution._state` or one `self.states` mutated by every phase |
| Pre-loop stage | Workgroup mapping, prefetch, global-read address setup, signature and kernel-argument loads | Loop and store policy |
| Loop stage | Schedule, depth-U, matrix instruction, loop open/close, tail, no-load loop, local read/write | Store layout policy and activation |
| Post-loop stage | Activation, bias, amax, GSU reduction, non-temporal stores, global write | The flag that decided the loop's operand order |
| Pass | A rewrite of an already-emitted kernel: dead accumulator init, physical register assignment | A transform that must regenerate a later stage |
| Component variant | StreamK, SIA, GSU, scheduler | A new `if` in the writer |
| Architecture file | Instruction choice, capability flags, and address padding that exist only for one GPU architecture | Edits to shared stage modules, unless the algorithm changes for every architecture |
| Library-build phase | Path rules, validation, code generation, metadata, publishing, fallback, merge | A second responsibility in the same phase file |
| Format vs domain parse | YAML, JSON, and msgpack load/dump, separate from solution and library parsing | One file that owns both |

`KernelWriterAssembly` remains the caller-facing class. It composes the modules below. The public library-build command remains the command people run.

Slide after-state, placed in the stage that owns it:

- Pre-loop: `KernelSignature.py`, `KernelGraAddress.py`, `KernelGlobalRead.py` (increments, guard K, direct-to-LDS), `KernelPap.py` (prefetch-across-persistent), `KernelOccupancy.py`.
- Loop: `KernelLoop.py`, `KernelMfma.py`, `KernelLocalAddr.py`, `KernelLocalRW.py`, `KernelTdm.py`.
- Post-loop: `KernelStore.py`, `KernelEpilogue.py`.
- Cross-stage, explicit: `KernelGprAlloc.py` until the register-allocation pass owns physical indices; `KernelAsmUtils.py` and `KernelMemoryInstr.py` as shared helpers with arguments, not hidden writer state.
- Library build: `paths.py`, `validate.py`, `codegen.py`, `metadata.py`, `publish.py`, `fallback.py`, `merge.py`, with `codegen.py` a typed request and result around kernel-source generation.
- Library files: `LibraryIOFormat.py` for format primitives; domain parsing stays separate. Old `LibraryIO` names keep working while callers move.

## Where a new feature is allowed to live

A feature stays inside a stage module when any one of these is true:

- Correctness depends on instruction order or interleaving.
- Correctness depends on a hardware counter, such as `s_wait_dscnt` versus `tensorcnt`.
- It threads a physical memory layout through many address calculations.
- It selects an instruction because of an accuracy budget only this generator knows.
- Its placement is keyed to a loop or schedule index such as `PrefetchGlobalRead` or the schedule-iteration algorithm.

A feature is a pass when it rewrites an already-correct kernel, an analysis proves the rewrite is safe, callers do not depend on the exact choice, or the emitter cannot see the information locally.

This rule is how a feature owner classifies a customization before it is added. The classification is required input.

## Features the library continues to support

These behaviors exist today. The new structure has to carry them. A customization of one of them uses the boundary in the right-hand column.

### Generation pipeline

- Pre-loop, main loop, no-load loop, tail loop, and post-loop, as explicit stages. These phases already exist as methods. The library makes them arguments and return values.
- Shared config broadcast into every stage, with no stage writing it.
- Stage-local state. Re-running a loop is another run of the loop stage with its own loop state. The adaptive GEMM NTAB path stops copying `self.states` with `deepcopy` and restoring it.
- One address or register layout, computed once and passed forward. Components stop recomputing it.

### Matrix loop and accumulator

- Matrix-instruction emission (MFMA and WMMA), including operand order.
- Source-swap: the loop stage copies the loop body, swaps source registers, and fixes addresses. The value passed to post-loop is the accumulator layout: which accumulator holds which output coordinate. Post-loop reads that layout. The separate swapped and unswapped store paths become one store path that takes the layout.
- Dead accumulator initialization. The generator emits the pre-loop zeroing move. A later pass deletes it only when a later write dominates the first use. When the main loop does not run, the initialization stays. The current case is the first WMMA iteration.
- Register allocation. Generation emits virtual registers. One pass assigns physical indices after every live range is visible. Callers do not depend on which index a value receives.

### Features that stay inside the generator

- Split tensor-data-movement loads. Placement after the local-data-share (LDS) buffer swap stays in the loop stage, at iteration indexes from prefetch and the schedule. A pass that only sees an instruction graph drops the counter and iteration information this placement needs.
- LDS bank-conflict padding. Every local-read address calculation applies the same pad. The pad stays in the local-address path.
- Fast reciprocal selection for workgroup mapping and GELU. The generator emits the chosen reciprocal width, or it emits a fast-divide node that carries the tolerance and lowers that node itself.
- Prefetch-across-persistent, direct-to-LDS, and guard-K, in the pre-loop and global-read modules.
- Activation, bias, amax, and the final store, in the epilogue module.

### Variants that become registrations

- StreamK.
- Schedule-iteration algorithm (SIA).
- Global-split-U (GSU), including the post-loop reduction.
- Scheduler variants.
- Component lookup, including local read. Lookup and instruction emission stay stable. Pure helper math moves to a helper module with direct tests.

Adding one of these is a new variant module and a registration. It is not a new branch in the writer.

### Library build and files

- The library-build command keeps its current behavior while the implementation splits into the phase modules above.
- Format read and write for YAML, JSON, and msgpack, independent of solution and library parsing.
- Occupancy from LDS, VGPR, AGPR, and SGPR limits, including the update after the instruction pass reports the maximum VGPR count. Occupancy is testable without constructing the rest of the writer.

### Architectures and the instruction layer

- Every architecture that already emits through rocisa keeps emitting through rocisa. rocisa is the current layer that turns generator output into instructions.
- A replacement instruction layer covers those architectures, or the plan names who maintains rocisa and for which architectures. A newer architecture on a second layer, with older architectures left on rocisa, adds a stack and leaves the maintenance in place.
- Building that second layer only for gfx1250 is the same split.
- A new GPU architecture edits a named, bounded set of files: capability flags, instruction selection, and architecture-specific padding. It edits a shared stage module only when the algorithm changes for every architecture.
- The measured counterexample is hipBLASLt pull request 1710, merged 2025-03-10, which changed 299 files. Most added lines are solution libraries. The shared generator still moved, including `KernelWriter.py`, `KernelWriterAssembly.py`, `LocalRead.py`, and the instruction layer. That is the outcome this requirement rejects.

### Runtime generation

- The same stage pipeline runs at library execution time. The call takes a serializable request and returns the kernel artifact. It does not require the offline Python process, a fully constructed `Solution`, or process-global parameters.
- Offline tuning and runtime generation use that same request. A customization written against the stages is available on both paths.
- Shipping the Python generator, rocisa, and the assembler to every process that needs a kernel is not the runtime path.

### Ownership of an added component

- A change that adds a generator component this team will maintain is accepted when this team accepts ownership of it, including fixes after the authors move on. The rocisa landing is the cited case: it was marked needs-work, it merged, the expected build-time improvement was not observed by this team, and this team still supports it. Those review and build-time claims are from the follow-up conversation and were not re-checked against the original review thread.

## Proof that a customization did not change anything else

- Before moving tangled code, tests record the current generated bytes.
- A stage extraction, the accumulator-layout change, and the loop-state change preserve those bytes.
- Register allocation preserves the instruction stream except for register-index substitutions. The check compares the stream after register indices are normalized.
- While a section is tangled, the saved bytes detect unintended edits. Once the behavior has a name, a FileCheck pattern or a unit test of the pass or module covers it, and the saved-byte check for that behavior is removed.
- Both kinds of tests stay during the migration. Saved bytes are the guard while extracting. Focused tests are the guard after the boundary exists. Focused tests do not replace the byte recording before the split.
- Behavior-preserving changes keep the characterization recordings stable. A change that intentionally edits bytes says which substitution is allowed.

## What this library is not required to be

- A general MLIR compiler, or a generator in which every feature is a pass. Passes are for rewrites of an already-emitted kernel. The handwritten assembly generator remains the baseline for features whose correctness is the instruction order.
- A tile-level programming model. Language-level functions, loops, and conditionals were raised as a possible direction. They are not requirements of this library.
- A deletion of rocisa while any supported architecture still emits through it.
- A rename of the current files without moving responsibilities. Names follow the module boundaries.
- A single rewrite that changes behavior and structure in one change.

## Still unnamed

The follow-up conversation says this end-state list is probably incomplete until the remaining items are written down. The items already named are runtime generation, a bounded file set per architecture, and an explicit rocisa ownership outcome. Review of additions is at the level of this end state, not the stage mechanics.
