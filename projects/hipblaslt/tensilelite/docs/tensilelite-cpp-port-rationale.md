# Potential benefits of porting TensileLite to C/C++

TensileLite currently spans Python and C/C++. Consolidating its implementation in C/C++ could reduce the boundaries between configuration, code generation, and runtime use. This document records the potential benefits that motivate evaluating such a port; it is not an implementation plan or a decision to proceed.

## Code maintainability and technical-debt reduction

A C/C++ implementation could use tools such as `clang-tidy` and compiler diagnostics across more of the codebase. These tools can identify some unused functions and classes, unreachable or suspicious branches, and other patterns that warrant review. Porting would also require each existing responsibility to be made explicit, creating an opportunity to remove code that no longer contributes to supported behavior and to reduce unnecessary coupling.

Static analysis would not replace tests or design review, and a port would not improve maintainability by itself. The benefit would come from combining stronger automated analysis with deliberate decisions about which existing abstractions and behaviors remain necessary.

## Runtime code generation

Keeping the code-generation pipeline in one language could allow an application to generate kernels from a structured description without coordinating separate Python and C/C++ processes. The AMD Code Object Manager (COMGR) library could provide in-process compilation and linking, avoiding shell commands that invoke `amdclang` or related tools when COMGR supports the required pipeline.

This arrangement could make runtime specialization easier to package and deploy. It would also provide one process in which to validate the input description, select code-generation options, produce a code object, and report failures.

## Bindings for other languages

A small, stable C interface for the required features would give other languages a narrow integration point. Python and Rust can both call a C application binary interface (ABI) through established foreign-function interfaces, without exposing TensileLite's internal C++ types.

The C interface would still require explicit ownership, error-handling, compatibility, and threading rules. Once those rules are defined, each language binding could remain thin and avoid duplicating the code-generation implementation.

## An intermediate representation for code-generation decisions

A consolidated implementation could introduce an intermediate representation (IR): a structured form that records code-generation decisions before they become assembly instructions. Developers could inspect and transform this representation instead of inferring earlier decisions from final assembly or tracing behavior across multiple methods.

An IR could separate problem description, lowering decisions, and instruction emission. That separation could make code-generation changes easier to review and test because each stage would expose concrete inputs and outputs. The exact productivity and debugging benefits would need validation through a prototype and representative TensileLite changes.
