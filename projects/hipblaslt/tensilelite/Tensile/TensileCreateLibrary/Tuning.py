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

"""Kernel emission and post-kernel tuning passes for TensileCreateLibrary.

Houses the two kernel emitters (writeSolutionsAndKernelsTCL — the live build
path — and the public writeSolutionsAndKernels), the validity-pruning passes,
and the post-kernel write-backs to solutions and libraries. Populated
incrementally by the NBA-* decomposition; names are re-imported back into
Run.py so existing imports keep resolving.
"""

from __future__ import annotations

import functools
import rocisa

from pathlib import Path

from Tensile.Common import ParallelMap2, ensurePath, print1, print2, printExit, tqdm
from Tensile.Common.Architectures import isaToGfx
from Tensile.KernelWriterBase import KERNEL_HELPER_FILENAME_CPP, KERNEL_HELPER_FILENAME_H
from Tensile.SolutionStructs.Naming import getKernelFileBase, getKeyNoInternalArgs, getKernelNameMin
from Tensile.Toolchain.Assembly import buildAssemblyCodeObjectFiles
from Tensile.Toolchain.Source import buildSourceCodeObjectFiles


def _checkInvalidSolutionsAndKernels(errorTolerant, result, kernel):
    if result.err != 0:
        if not errorTolerant:
            print(
                "\nKernel generation failed for kernel: {}".format(
                    kernel["SolutionIndex"]
                )
            )
            print(kernel["SolutionNameMin"])
        return True
    return False

def _checkInvalidSolutions(splitGSU, removeKernelNames, solutions):
    invalids = []
    for solution in solutions:
        solutionKernels = solution.getKernels()
        for kernel in solutionKernels:
            kName = getKeyNoInternalArgs(kernel, splitGSU)
            if kName in removeKernelNames:
                invalids.append(True)
                break
        invalids.append(False)
    return invalids

def removeInvalidSolutionsAndKernels(results, kernels, solutions, errorTolerant, printLevel: bool, splitGSU: bool):
    removeKernelsAndResultsFlag = ParallelMap2(functools.partial(_checkInvalidSolutionsAndKernels, errorTolerant),
                                               zip(results, kernels), "check invalid kernels and results", return_as="list")

    if any(removeKernelsAndResultsFlag) and not errorTolerant:
        printExit("** kernel generation failure **")

    removeKernelNames = {getKeyNoInternalArgs(kernel, splitGSU) for invalid, kernel in zip(removeKernelsAndResultsFlag, kernels) if invalid}
    kernels[:] = [kernel for invalid, kernel in zip(removeKernelsAndResultsFlag, kernels) if not invalid]

    removeSolutionsFlag = []
    for solution in (
        tqdm(solutions, "Finding invalid solutions")
        if printLevel > 1
        else solutions
    ):
        solutionKernels = solution.getKernels()
        flag = False
        for kernel in solutionKernels:
            kName = getKeyNoInternalArgs(kernel, splitGSU)
            if kName in removeKernelNames:
                flag = True
                break
        removeSolutionsFlag.append(flag)

    solutions[:] = [solut for invalid, solut in zip(removeSolutionsFlag, solutions) if not invalid]
    results[:] = [rel for invalid, rel in zip(removeKernelsAndResultsFlag, results) if not invalid]

def passPostKernelInfoToSolution(results, kernels, solutions, splitGSU: bool):
    resultDict = {}
    for kernIdx, r in enumerate(results):
        kName = getKernelNameMin(kernels[kernIdx], splitGSU)
        resultDict["%s"%kName] = r
    for solution in solutions:
        solutionKernels = solution.getKernels()
        for kernel in solutionKernels:
            kName = getKernelNameMin(kernel, splitGSU)
            result = resultDict["%s"%kName]
            solution._state["CUOccupancy"] = result.cuoccupancy
            solution._state["PrefetchGlobalRead"] = result.pgr
            solution._state["MathClocksUnrolledLoop"] = result.mathclk

def passPostKernelInfoToLibrary(results, kernels, masterLibraries, splitGSU: bool):
    resultDict = {}
    for kernIdx, r in enumerate(results):
        kName = getKernelFileBase(splitGSU, kernels[kernIdx])
        resultDict["%s"%kName] = r
    for archName, masterLibrary in masterLibraries.items():
        for solIdx, sol in masterLibrary.solutions.items():
            solutionKernels = sol.originalSolution.getKernels()
            for kernel in solutionKernels:
                kName = getKernelFileBase(splitGSU, kernel)
                try:
                    result = resultDict["%s"%kName]
                    sol.sizeMapping.CUOccupancy = result.cuoccupancy
                    sol.sizeMapping.MathClocksUnrolledLoop = result.mathclk
                    sol.sizeMapping.PrefetchGlobalRead = sol.originalSolution._state['PrefetchGlobalRead']
                    sol.sizeMapping.NonTemporalA = sol.originalSolution._state['NonTemporalA']
                    sol.sizeMapping.NonTemporalB = sol.originalSolution._state['NonTemporalB']
                    sol.sizeMapping.adaptiveGemmNTAB = sol.originalSolution._state.get('AdaptiveGemmNTAB', 0)
                    sol.sizeMapping.NonTemporalD = sol.originalSolution._state['NonTemporalD']
                    sol.sizeMapping.WaveSeparateGlobalReadA = sol.originalSolution._state['WaveSeparateGlobalReadA']
                    sol.sizeMapping.WaveSeparateGlobalReadB = sol.originalSolution._state['WaveSeparateGlobalReadB']
                    sol.sizeMapping.UnrollLoopSwapGlobalReadOrder = sol.originalSolution._state['UnrollLoopSwapGlobalReadOrder']
                    sol.sizeMapping.DirectToVgprA = bool(sol.originalSolution._state['DirectToVgprA'])
                    sol.sizeMapping.DirectToVgprB = bool(sol.originalSolution._state['DirectToVgprB'])
                except KeyError:
                    print(f"\n{'='*80}")
                    print(f"ERROR: KeyError in masterLibrary.solutions")
                    print(f"Architecture: {archName}")
                    print(f"Solution Index: {solIdx}")
                    print(f"Solution source file: {getattr(sol, 'srcName', 'Unknown')}")
                    print(f"Solution library logic index: {getattr(sol, 'libraryLogicIndex', 'Unknown')}")
                    print(f"Missing kernel name: {kName}")
                    print(f"{'='*80}\n")
                    raise
        masterLibrary.lazyLibraries = dict(sorted(masterLibrary.lazyLibraries.items()))
        for name, lib in masterLibrary.lazyLibraries.items():
            for solIdx, sol in lib.solutions.items():
                solutionKernels = sol.originalSolution.getKernels()
                for kernel in solutionKernels:
                    kName = getKernelFileBase(splitGSU, kernel)
                    try:
                        result = resultDict["%s"%kName]
                        sol.sizeMapping.CUOccupancy = result.cuoccupancy
                        sol.sizeMapping.MathClocksUnrolledLoop = result.mathclk
                        sol.sizeMapping.PrefetchGlobalRead = sol.originalSolution._state['PrefetchGlobalRead']
                        sol.sizeMapping.NonTemporalA = sol.originalSolution._state['NonTemporalA']
                        sol.sizeMapping.NonTemporalB = sol.originalSolution._state['NonTemporalB']
                        sol.sizeMapping.adaptiveGemmNTAB = sol.originalSolution._state.get('AdaptiveGemmNTAB', 0)
                        sol.sizeMapping.NonTemporalD = sol.originalSolution._state['NonTemporalD']
                        sol.sizeMapping.WaveSeparateGlobalReadA = sol.originalSolution._state['WaveSeparateGlobalReadA']
                        sol.sizeMapping.WaveSeparateGlobalReadB = sol.originalSolution._state['WaveSeparateGlobalReadB']
                        sol.sizeMapping.UnrollLoopSwapGlobalReadOrder = sol.originalSolution._state['UnrollLoopSwapGlobalReadOrder']
                        sol.sizeMapping.DirectToVgprA = bool(sol.originalSolution._state['DirectToVgprA'])
                        sol.sizeMapping.DirectToVgprB = bool(sol.originalSolution._state['DirectToVgprB'])
                    except KeyError:
                        print(f"\n{'='*80}")
                        print(f"ERROR: KeyError in lazyLibrary")
                        print(f"Architecture: {archName}")
                        print(f"LazyLibrary name: {name}")
                        print(f"Solution Index: {solIdx}")
                        print(f"Solution source file: {getattr(sol, 'srcName', 'Unknown')}")
                        print(f"Solution library logic index: {getattr(sol, 'libraryLogicIndex', 'Unknown')}")
                        print(f"Missing kernel name: {kName}")
                        print(f"Total kernels in this solution: {len(solutionKernels)}")
                        print(f"{'='*80}\n")
                        raise


def writeSolutionsAndKernelsTCL(
    outputPath,
    asmToolchain,
    srcToolchain,
    solutions,
    kernels,
    kernelHelperObjs,
    kernelWriterAssembly,
    cmdlineArchs: List[str],
    disableAsmComments: bool=False,
    compress: bool=True,
    removeTemporaries: bool=True
):
    outputPath = Path(outputPath)
    # Builders fan out into <destRoot>/<base-arch>/ at the moment of write.
    # Pre-create the per-base subdirs so concurrent emit doesn't race mkdir.
    destRoot = ensurePath(libraryRoot(outputPath))
    for base in _baseArchs(cmdlineArchs):
        ensurePath(libraryDir(outputPath, base))
    buildTmpPath = ensurePath(outputPath / "build_tmp" / outputPath.stem.upper())
    assemblyTmpPath = ensurePath(
        buildTmpPath / "assembly"
    )  # Temp path for generated assembly files (.s)
    objectTmpPath = ensurePath(
        buildTmpPath / "code_object_tmp"
    )  # Temp path for HSA code object files (.hsaco)

    asmKernels = [k for k in kernels if k["KernelLanguage"] == "Assembly"]

    visited = set()
    duplicates = 0
    splitGSU = False
    for k in asmKernels:
        base = getKernelFileBase(splitGSU, k)
        k["BaseName"] = base
        k.duplicate = True if base in visited else False
        duplicates += k.duplicate
        print2(f"Duplicate: {base}")
        visited.add(base)
    print1(f"Number of duplicate kernels: {duplicates}")

    uniqueAsmKernels = [k for k in asmKernels if not k.duplicate]

    def assemble(ret, removeTemporaries: bool):
        asmPath, isa, wavefrontsize, result = ret
        o_path = asmPath.with_suffix(".o")
        asmToolchain.assembler(isaToGfx(isa), wavefrontsize, str(asmPath), str(o_path))
        if _stinky_asm_verify_wanted(isa):
            _verify_stinky_asm_comment_vs_elf_text(asmPath, o_path, asmPath.stem)
        if removeTemporaries:
            asmPath.unlink()
        return result

    unaryAssemble = functools.partial(assemble, removeTemporaries=removeTemporaries)

    outOptions = rocisa.rocIsa.getInstance().getOutputOptions()
    outOptions.outputNoComment = not disableAsmComments

    memcompress = len(uniqueAsmKernels) > 10000
    unaryProcessKernelSource = functools.partial(
        processKernelSource,
        kernelWriterAssembly,
        rocisa.rocIsa.getInstance().getData(),
        outOptions,
        splitGSU,
        compress = memcompress,
    )

    unaryWriteAssembly = functools.partial(writeAssembly, assemblyTmpPath)
    def compose(assemble, unaryWriteAssembly, unaryProcessKernelSource):
        def composed_function(kernel):
            processed_kernel = unaryProcessKernelSource(kernel)
            written_kernel = unaryWriteAssembly(processed_kernel)
            assembled_kernel = assemble(written_kernel)
            return processed_kernel
        return composed_function

    results = ParallelMap2(
        compose(unaryAssemble, unaryWriteAssembly, unaryProcessKernelSource),
        uniqueAsmKernels,
        "Generating assembly kernels",
        multiArg=False,
        return_as="list"
    )

    buildAssemblyCodeObjectFiles(
        asmToolchain.linker,
        asmToolchain.bundler,
        asmKernels,
        destRoot,
        assemblyTmpPath,
        compress,
    )

    writeHelpers(outputPath, kernelHelperObjs, KERNEL_HELPER_FILENAME_CPP, KERNEL_HELPER_FILENAME_H)
    srcKernelFile = Path(outputPath) / "Kernels.cpp"

    buildSourceCodeObjectFiles(
        srcToolchain.compiler,
        srcToolchain.bundler,
        destRoot,
        objectTmpPath,
        outputPath,
        srcKernelFile,
        cmdlineArchs,
    )

    return len(uniqueAsmKernels), uniqueAsmKernels, results


from .IO import (
    _baseArchs,
    _stinky_asm_verify_wanted,
    _verify_stinky_asm_comment_vs_elf_text,
    libraryDir,
    libraryRoot,
    writeAssembly,
    writeHelpers,
)
from .Run import processKernelSource
