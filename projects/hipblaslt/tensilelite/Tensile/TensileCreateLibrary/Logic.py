################################################################################
#
# Copyright (C) 2022-2025 Advanced Micro Devices, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
################################################################################

"""Logic-file discovery and solution derivation for TensileCreateLibrary.

Houses the per-arch fallback-placeholder rename helpers, the unique-kernel
object derivation, and the logic-load + per-arch merge + reindex core
(generateLogicDataAndSolutions). Populated incrementally by the NBA-*
decomposition; names are re-imported back into Run.py so existing imports keep
resolving.
"""

import copy
import itertools

from Tensile import LibraryIO
from Tensile.Common import ParallelMap2, print1
from Tensile.SolutionLibrary import MasterSolutionLibrary, PlaceholderLibrary
from Tensile.SolutionStructs.Naming import getKeyNoInternalArgs
from Tensile.SolutionStructs.Solution import mergeTypeMismatchCollector, printTypeMismatchSummary
from Tensile.Toolchain.Component import Assembler
from Tensile.Utilities.Decorators.Timing import timing


@timing
def generateKernelObjectsFromSolutions(solutions):
    kernels = []
    kernelNames = set()
    for solution in solutions:
        solutionKernels = solution.getKernels()
        for kernel in solutionKernels:
            kName = getKeyNoInternalArgs(kernel, False)
            if kName not in kernelNames:
                kernels.append(kernel)
                kernelNames.add(kName)
    return kernels


def _renameFallbackPlaceholders(node, arch: str) -> None:
    """Walk a library tree, appending "_<arch>" to fallback PlaceholderLibrary names.

    Mutates `filenamePrefix` on every PlaceholderLibrary leaf whose existing
    prefix already encodes a fallback (i.e. came from the merged-in fallback
    master library and therefore ends with "_fallback") and which has not yet
    been arch-suffixed. Idempotent: a prefix already ending in "_<arch>"
    is left alone so a second pass cannot double-suffix.
    """
    if node is None:
        return
    if isinstance(node, PlaceholderLibrary):
        if "_fallback" in node.filenamePrefix and not node.filenamePrefix.endswith("_" + arch):
            node.filenamePrefix = node.filenamePrefix + "_" + arch
        return
    rows = getattr(node, "rows", None)
    if rows:
        for row in rows:
            _renameFallbackPlaceholders(row.get("library"), arch)
    mapping = getattr(node, "mapping", None)
    if mapping:
        for child in mapping.values():
            _renameFallbackPlaceholders(child, arch)


def renameFallbacksPerArch(masterLibraries) -> None:
    """Make merged-in fallback lazy-library filenames arch-specific.

    `MasterSolutionLibrary.merge` aliases the same fallback lazy library across
    every per-arch master that absorbs it (keys collide on the un-suffixed
    "_fallback" name). That alias means the per-arch *_fallback.dat files are
    written with overlapping filenames carrying different solution-index spaces,
    and the per-arch Mapping write loop's `name.endswith("_<arch>")` filter drops
    every fallback entry — runtime then can't resolve fallback-served dtypes.

    Per-arch deep-copy here splits the alias and arch-suffixes both the
    `lazyLibraries` dict keys and the matching PlaceholderLibrary nodes inside
    the master library tree, so:
      - on-disk filenames diverge (no overlay collision),
      - the per-arch Mapping filter matches "_fallback_<arch>" naturally, and
      - each arch keeps its own re-indexed copy of the fallback solutions.
    """
    for arch in list(masterLibraries.keys()):
        master = copy.deepcopy(masterLibraries[arch])
        masterLibraries[arch] = master
        renamed = {}
        for name, lib in master.lazyLibraries.items():
            if "_fallback" in name and not name.endswith("_" + arch):
                renamed[name + "_" + arch] = lib
            else:
                renamed[name] = lib
        master.lazyLibraries = renamed
        _renameFallbackPlaceholders(master.library, arch)


@timing
def generateLogicDataAndSolutions(logicFiles, args, assembler: Assembler, isaInfoMap):

    if ";" in args["Architecture"]:
        archs = args["Architecture"].split(";")  # user arg list format
    else:
        archs = args["Architecture"].split("_")  # workaround for cmake list in list issue

    solutions = []
    masterLibraries = {}
    nextSolIndex = 0
    splitGSU = False
    printSolutionRejectionReason = True
    printIndexAssignmentInfo = False

    fIter = zip(
        logicFiles,
        itertools.repeat(assembler),
        itertools.repeat(splitGSU),
        itertools.repeat(printSolutionRejectionReason),
        itertools.repeat(printIndexAssignmentInfo),
        itertools.repeat(isaInfoMap),
        itertools.repeat(args["LazyLibraryLoading"]),
    )

    def libraryIter(lib: MasterSolutionLibrary):
        if len(lib.solutions):
            for i, s in enumerate(lib.solutions.items()):
                yield (i, *s)
        else:
            for _, lazyLib in lib.lazyLibraries.items():
                yield from libraryIter(lazyLib)

    for library in ParallelMap2(
        LibraryIO.parseLibraryLogicFile, fIter, "Loading Logics...", return_as="generator_unordered"
    ):
        _, architectureName, _, _, _, newLibrary, typeMismatches = library
        mergeTypeMismatchCollector(typeMismatches)

        if architectureName == "":
            continue

        if architectureName in masterLibraries:
            nextSolIndex = masterLibraries[architectureName].merge(newLibrary, nextSolIndex)
        else:
            masterLibraries[architectureName] = newLibrary
            masterLibraries[architectureName].version = args["CodeObjectVersion"]

    # After all YAML files have been parsed and Solution objects created,
    # print a summary of any type mismatches that were collected.
    printTypeMismatchSummary(len(logicFiles))

    # Sort masterLibraries to make global soln index values deterministic
    solnReIndex = 0
    masterLibraries = dict(sorted(masterLibraries.items()))
    for _, masterLibrary in masterLibraries.items():
        for _, sol in masterLibrary.solutions.items():
            sol.index = solnReIndex
            solnReIndex += 1
        # Sort masterLibrary to make global soln index values deterministic
        masterLibrary.lazyLibraries = dict(sorted(masterLibrary.lazyLibraries.items()))
        for name, lib in masterLibrary.lazyLibraries.items():
            # Sort solns by the lib logic file they were generated from
            lib.solutions = {
                k: lib.solutions[k]
                for k in sorted(lib.solutions, key=lambda idx: lib.solutions[idx].srcName)
            }
            for _, sol in lib.solutions.items():
                sol.index = solnReIndex
                solnReIndex += 1

    if args["GenSolTable"]:
        matchTable = {}
        # Match yaml file solutions to solution index
        for _, masterLibrary in masterLibraries.items():
            for _, _, s in libraryIter(masterLibrary):
                matchTable[s.index] = [s.srcName, s.libraryLogicIndex]
        LibraryIO.write("MatchTable", matchTable)

    fallbackAdded = "fallback" in masterLibraries.keys()
    if fallbackAdded:
        for key, value in masterLibraries.items():
            if key != "fallback":
                value.merge(masterLibraries["fallback"])
        masterLibraries.pop("fallback")
    if fallbackAdded:
        # Must run AFTER merge (so per-arch masters carry their own fallback
        # entries) and BEFORE the codeObjectFile-assignment loop below (which
        # snapshots the dict key as the on-disk filename for each solution).
        renameFallbacksPerArch(masterLibraries)
    solIndex = []
    for _, masterLibrary in masterLibraries.items():
        for _, sol in masterLibrary.solutions.items():
            solutions.append(sol.originalSolution)
            solIndex.append(sol.index)
        for name, lib in masterLibrary.lazyLibraries.items():
            for _, sol in lib.solutions.items():
                sol.originalSolution._state["codeObjectFile"] = name
                solutions.append(sol.originalSolution)
                solIndex.append(sol.index)

    # Get the solution index and it's codeObjectFile name
    codeObjectFilesIndex = {}
    for solution, index in zip(solutions, solIndex):
        if "codeObjectFile" in solution._state and solution._state["codeObjectFile"] is not None:
            if solution._state["codeObjectFile"] in codeObjectFilesIndex:
                codeObjectFilesIndex[solution._state["codeObjectFile"]] = min(index, codeObjectFilesIndex[solution._state["codeObjectFile"]])
            else:
                codeObjectFilesIndex[solution._state["codeObjectFile"]] = index

    # Reorder to int: name format
    codeObjectFilesIndex = {v: k for k, v in codeObjectFilesIndex.items()}
    # Reorder to maintain ascending order by index
    codeObjectFilesIndex = dict(sorted(codeObjectFilesIndex.items()))

    # remove duplicates while preserving order
    numSoln = len(solutions)
    solutions = dict.fromkeys(solutions).keys()

    print1(f"Number of solutions parsed: {numSoln}")
    print1(f"Number of unique solutions: {len(solutions)}")

    return solutions, masterLibraries, codeObjectFilesIndex
