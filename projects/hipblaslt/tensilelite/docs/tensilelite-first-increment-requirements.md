# TensileLite staged code-generation requirements: first increment

These requirements record the outcome of the design thread. The first increment makes the existing kernel-generation phases explicit and names the data each phase owns. The handwritten assembly generator remains in place. A pass is introduced only when it rewrites code that the generator has already emitted.

## First increment

1. Split generation into explicit stages that already exist as methods: pre-loop, main loop, no-load loop, tail loop, and post-loop.
2. Move only two self-contained transforms into passes in this increment: dead accumulator initialization and register allocation.
3. Keep `SourceSwap` inside the loop stage. A late pass that rewrites only the matrix instruction is out of scope because the swap also changes where results land in the accumulator, and the store path depends on that layout.
4. Relocate existing generation code in this increment. Do not convert an entire stage into a pass.
5. Land the work as small commits. New-product branches take commits from public `develop` on their own cadence, so each commit must be usable independently on that cadence.

## Data each stage receives

6. Broadcast one immutable shared configuration to every stage. It holds values that span phases: problem type, tile geometry, instruction-set architecture, and wavefront size. No stage writes to it.
7. Give each stage its own immutable configuration. Pre-loop owns workgroup mapping and prefetch. The loop owns the schedule, depth-U, and matrix instruction. Post-loop owns activation, global-split-U reduction, and non-temporal stores.
8. Give each stage its own state, and pass that state into the next stage as an argument. Pre-loop, loop, and post-loop parameters stop sharing one flat `Solution._state`. Mutable fields stop living in the `KernelWriter` object's single `self.states` value that every phase mutates.
9. Keep the scalar and vector register pools as shared physical resources across phases until the allocation pass described below owns index assignment.
10. Compute each address or register layout once and pass it forward. Components stop recomputing the same layout independently.

## Named pieces this increment introduces

11. **Accumulator layout.** `SourceSwap` copies the loop, swaps the source registers of the matrix instruction, and fixes addresses inside the loop. The only value that crosses into post-loop is the mapping from accumulators to output coordinates. Post-loop reads that layout. The separate swapped and unswapped store paths become one path that accepts the layout as input.
12. **Loop state.** The Adaptive General Matrix Multiplication (GEMM) NTAB path stops copying `self.states` with `deepcopy` and restoring it. Re-running the loop means running the loop stage again with its own loop state.
13. **Virtual registers and one allocation pass.** Generation emits virtual registers. One pass assigns physical indices after the generator can see every live range. `RegisterPool.checkOut` and `RegisterPool.checkIn` stop assigning the lowest free index at the moment of each call.

## Dead-initialization pass

14. The generator always emits the naive pre-loop `v_mov` that zeroes the accumulator.
15. A later dead-code pass deletes that initialization only when a later write dominates the first use, meaning that the write executes first on every path to that use. The current case is the first Wave Matrix Multiply-Accumulate (WMMA) iteration, which writes the accumulator itself.
16. When the main loop does not run (`numIter == 0`), the initialization remains because nothing else zeroes the accumulator.
17. The pass uses an analysis layer that can query and edit the existing `Module` and `CodeModules` graph. The containers already exist.

## Where a feature is allowed to live

A feature stays inline in the generator when any one of these conditions is true:

- Correctness depends on instruction order or interleaving.
- Correctness depends on a hardware counter, such as `s_wait_dscnt` versus `tensorcnt`.
- The feature threads a physical memory layout through many address calculations.
- The feature selects an instruction because of an accuracy budget that only this generator knows.
- Placement is keyed to a loop or schedule index such as `PrefetchGlobalRead` or `_ScheduleIterAlg`.

A feature becomes a pass when it rewrites an already-correct kernel, an analysis proves the rewrite is safe, callers do not depend on the exact choice, or the emitter cannot see the required information locally. Register indices and the whole-accumulator layout are the two cases named here.

18. Keep `splitTDM` inline. It places `tensor_load_to_lds` after the Local Data Share (LDS) buffer swap, at iteration indexes derived from prefetch and the schedule. This placement prevents the asynchronous load from overwriting MX-scale LDS while the current wave is still reading it.
19. Keep LDS bank-conflict padding inline. Every local-read address calculation must apply the same padding.
20. Keep fast reciprocal selection under this generator's control. Workgroup mapping and Gaussian Error Linear Unit (GELU) generation retain their chosen `v_rcp` width. The generator either emits that instruction directly or emits a fast-divide node that carries the tolerance and lowers the node itself.
21. Before moving a feature, its owner classifies it with this rule. The classification is required input to the design.

## Tests

22. Before moving tangled code, add tests that save the current generated bytes as the expected result.
23. The accumulator-layout and loop-state changes preserve the generated bytes exactly.
24. Register allocation preserves the instruction stream except for register-index substitutions. A byte-for-byte comparison is not the correct check for this change.
25. While a section remains tangled, the saved bytes detect unintended changes. Once the behavior has a name, a FileCheck pattern or a unit test of the pass covers it. Remove the saved-byte check for that behavior after the focused test replaces it.
26. Keep both forms of testing in the tree during the migration because they apply at different points in the sequence.

## Explicitly later

27. After the stage boundaries exist, decide whether any stage is worth converting into a pass. `SourceSwap` is the example that waits.
28. Do not adopt Multi-Level Intermediate Representation (MLIR) as the generator, and do not turn every feature into a pass.
29. A tile-level programming model and language-level constructs such as functions, loops, and conditionals were raised as a possible direction. They are not requirements of this increment.
30. The lowering rules for runtime code generation and per-architecture isolation were identified as necessary discipline but were not specified in this thread.

## Why this is the agreed sequence

The thread agrees on sequencing. YangWen's first step is the stage split plus the two passes. T.J. adds the three named pieces, the two different byte checks, and the small-commit requirement. Matt's question about whether both changes are passes is answered by moving `SourceSwap` only after the stage boundary exists. CY's frontend-versus-backend and tile-level comments remain outside this list because the thread did not adopt them as work for this increment.
