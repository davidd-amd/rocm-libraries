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

import functools

from Tensile.Common import ParallelMap2, printExit, tqdm
from Tensile.SolutionStructs.Naming import getKeyNoInternalArgs, getKernelNameMin


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
