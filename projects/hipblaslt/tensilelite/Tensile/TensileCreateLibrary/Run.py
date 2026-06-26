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

import glob
import itertools
import os
import shutil
from pathlib import Path
from timeit import default_timer as timer
from typing import List, NamedTuple, Optional, Union

from Tensile import LibraryIO
from Tensile.Common import (
    DebugConfig,
    ensurePath,
    HR,
    IsaVersion,
    ParallelMap2,
    print1,
    print2,
    printWarning,
    printExit,
    state,
    setVerbosity,
    getVerbosity,
)
from Tensile.Common.Architectures import gfxToIsa, isaToGfx, SUPPORTED_GFX, splitArchsFromPredicates, filterLogicFilesByPredicates
from Tensile.Common.Capabilities import makeIsaInfoMap
from Tensile.Common.GlobalParameters import assignGlobalParameters, globalParameters
from Tensile.SolutionStructs.Naming import getKernelFileBase, getKeyNoInternalArgs

from Tensile.CustomYamlLoader import load_logic_gfx_arch
from Tensile.KernelHelperNaming import kernelObjectNameCallables, initHelperKernelObjects
from Tensile.KernelWriterAssembly import KernelWriterAssembly
from Tensile.SolutionStructs import Solution
from Tensile.Toolchain.Assembly import makeAssemblyToolchain
from Tensile.Toolchain.Source import makeSourceToolchain
from Tensile.Toolchain.Validators import (
    ToolchainDefaults,
    validateToolchain,
)
from Tensile.Toolchain.Component import Assembler
from Tensile.Utilities.Decorators.Profile import profile

from .ParseArguments import parseArguments


class KernelCodeGenResult(NamedTuple):
    err: int
    src: Union[str, bytes]
    header: Optional[str]
    name: str
    targetObjFilename: str
    isa: IsaVersion
    wavefrontSize: int
    cuoccupancy: int
    pgr: int
    mathclk: int

class KernelMinResult(NamedTuple):
    err: int
    cuoccupancy: int
    pgr: int
    mathclk: int


def processKernelSource(kernelWriterAssembly, data, outOptions, splitGSU, kernel, compress = False) -> KernelCodeGenResult:
    """
    Generate source for a single kernel.
    Returns (error, source, header, kernelName).
    """
    kernelWriter = kernelWriterAssembly
    kernelWriter.setRocIsa(data, outOptions)
    asmFilename = getKernelFileBase(splitGSU, kernel)
    err, src = kernelWriter.getSourceFileString(kernel)
    if compress:
        src = memCompress(src)
    header = kernelWriter.getHeaderFileString(kernel)
    objFilename = kernel._state.get("codeObjectFile", None)
    pgr = int(kernel["PrefetchGlobalRead"])
    cuocc = kernel["CUOccupancy"]
    if cuocc <= 0 and getVerbosity() >= 2:
        print2(
            f"[codegen] CUOccupancy={cuocc} (<=0) after codegen for kernel {asmFilename}; "
            f"runtime will clamp to 1."
        )
    return KernelCodeGenResult(
        err, src, header, asmFilename, objFilename, tuple(kernel["ISA"]), \
        kernel["WavefrontSize"], cuocc, \
        pgr, kernel["MathClocksUnrolledLoop"]
    )


def generateKernelHelperObjects(solutions: List[Solution], cxxCompiler: str, isaInfoMap):
    """
    Generates a unique list of kernel helpers.

    Kernel helpers are used to generate hip source code kernels called
    before/after gemm kernels. This function creates a minimal list of
    kernel helpers required to support the solutions reuested in a build.
    The list of kernel helpers is then used to write Kernels.cpp/h to
    disk. To ensure the ActivationEnumHeaders are written first, the
    list is sorted such that those kernel helpers appear first.

    Args:
        solutions: a list of solutions to process.
        cxxCompiler: the full path to the cxxCompiler.

    Returns:
        List of kernel helpers.
    """
    khos = []
    visited = set()
    for solution in solutions:
        for kernelHelperType, callable in kernelObjectNameCallables():
            buildMask = []
            names = callable(solution)
            if names:
                sortByEnum = lambda x: ("Enum" in x, names.index(x))
                names = sorted(names, key=sortByEnum, reverse=True)
                for name in names:
                    if name not in visited:
                        visited.add(name)
                        buildMask.append(True)
                    else:
                        buildMask.append(False)
                if any(buildMask):
                    kho = initHelperKernelObjects(solution, kernelHelperType, cxxCompiler, isaInfoMap)
                    kho = list(itertools.compress(kho, buildMask))
                    if kho:
                        khos.extend(kho)
    khos = list(set(khos))
    sortByEnum = lambda x: ("Enum" in x.getKernelName(), khos.index(x))
    return sorted(khos, key=sortByEnum, reverse=True) # Ensure that we write Enum kernel helpers are first in list


################################################################################
# Tensile Create Library
################################################################################
@profile
def run():
    start = timer()
    print1("")
    print1(HR)
    print1("# Tensile Create Library")
    print2(HR)
    print2("")

    arguments = parseArguments()
    setVerbosity(arguments["PrintLevel"])
    outputPath = Path(ensurePath(os.path.abspath(arguments["OutputPath"])))
    cxxCompiler, _, offloadBundler, _, _ = validateToolchain(
        arguments["CxxCompiler"],
        arguments["CCompiler"],
        arguments["OffloadBundler"],
        arguments["Assembler"],
        ToolchainDefaults.HIP_CONFIG,
    )

    if ";" in arguments["Architecture"]:
        archs = arguments["Architecture"].split(";")
    else:
        archs = arguments["Architecture"].split("_")
    archs = SUPPORTED_GFX if "all" in archs else archs
    archs, requestedPredicateMap = splitArchsFromPredicates(archs)

    targetIsas = [gfxToIsa(a) for a in archs]
    isaInfoMap = makeIsaInfoMap(targetIsas, cxxCompiler)
    assignGlobalParameters(arguments, isaInfoMap)

    asmToolchain = makeAssemblyToolchain(
        cxxCompiler,
        offloadBundler,
        arguments["CodeObjectVersion"],
        arguments["BuildIdKind"],
        arguments["AsmDebug"],
    )
    srcToolchain = makeSourceToolchain(
        cxxCompiler,
        offloadBundler,
        arguments["AsanBuild"],
        arguments["BuildIdKind"],
        save_temps=False
    )

    print1(asmToolchain.assembler)
    print1(asmToolchain.bundler)

    if not os.path.exists(arguments["LogicPath"]):
        printExit(f"LogicPath {arguments['LogicPath']} doesn't exist")

    logicExtFormat = ".yaml"
    if arguments["LogicFormat"] == "yaml":
        pass
    elif arguments["LogicFormat"] == "json":
        logicExtFormat = ".json"
    else:
        printExit(f"Unrecognized LogicFormat: {arguments['LogicFormat']}")

    def archMatch(arch: str, archs: List[str]):
        return (arch in archs) or any(a.startswith(arch) for a in archs)

    def validLogicFile(p: Path):
        return p.suffix == logicExtFormat and (
            "all" in archs or archMatch(load_logic_gfx_arch(p), archs)
        )

    globPattern = os.path.join(
        arguments["LogicPath"], f"**/{arguments['LogicFilter']}{logicExtFormat}"
    )
    print1(f"# LogicFilter:       {globPattern}")
    logicFiles = [
        file for file in glob.iglob(globPattern, recursive=True)
    ]

    logicFiles = [file for file in logicFiles if validLogicFile(Path(file))]

    print1(f"# Experimental:      {arguments['Experimental']}")
    if not arguments["Experimental"]:
        logicFiles = [
            file for file in logicFiles if "experimental" not in map(str.lower, Path(file).parts)
        ]

    print1("# Archs: " + ' ,'.join(archs))
    if requestedPredicateMap:
        print1("# Predicates:\n" + "\n".join(f"#   {arch}: {', '.join(v) if v else 'all variants'}" for arch, v in requestedPredicateMap.items()))
        numPrior = len(logicFiles)
        logicFiles = filterLogicFilesByPredicates(logicFiles, requestedPredicateMap)
        print1(f"# Filtered {numPrior - len(logicFiles)} logic files not matching requested predicates")

    print1(f"# LibraryLogicFiles: {len(logicFiles)}")

    for logicFile in logicFiles:
        print2("#   %s" % logicFile)

    start_glds = timer()
    solutions, masterLibraries, libraryMapping = generateLogicDataAndSolutions(
        logicFiles, arguments, asmToolchain.assembler, isaInfoMap
    )
    stop_glds = timer()
    print(f"Time to load yaml files (s): {(stop_glds-start_glds):3.2f}")


    kernels = generateKernelObjectsFromSolutions(solutions)
    kernelHelperObjs = generateKernelHelperObjects(kernels, str(asmToolchain.assembler.path), isaInfoMap)
    kernelWriterAssembly = KernelWriterAssembly(asmToolchain.assembler, DebugConfig())

    copyStaticFiles(outputPath)

    start_wsk = timer()
    numKernels, uniqueKernels, kernelInfo = writeSolutionsAndKernelsTCL(
        outputPath,
        asmToolchain,
        srcToolchain,
        solutions,
        kernels,
        kernelHelperObjs,
        kernelWriterAssembly,
        archs,
        arguments["DisableAsmComments"],
        compress=arguments["UseCompression"],
        removeTemporaries=not arguments["KeepBuildTmp"],
    )
    stop_wsk = timer()
    print(f"Time to generate kernels (s): {(stop_wsk-start_wsk):3.2f}")

    archs = [ # is this really different than the other archs above?
        isaToGfx(arch)
        for arch in targetIsas
        if isaInfoMap[arch].asmCaps["SupportedISA"]
    ]
    # Per-base subdirs are created here (idempotent if writeSolutionsAndKernels*
    # already created them above). Each per-arch write below routes to its own
    # libraryDir(outputPath, archName).
    for base in _baseArchs(archs):
        ensurePath(libraryDir(outputPath, base))
    splitGSU = False

    start_pki = timer()
    passPostKernelInfoToLibrary(kernelInfo, uniqueKernels, masterLibraries, splitGSU)
    stop_pki = timer()
    print(f"Time to pass kernel info to library (s): {(stop_pki-start_pki):3.2f}")

    solDict = {}
    for solution in solutions:
        solutionKernels = solution.getKernels()
        for kernel in solutionKernels:
            kName = getKeyNoInternalArgs(kernel, False)
            if kName not in solDict:
                solDict["%s"%kName] = kernel

    # Split libraryMapping per arch and write one mapping file per arch into
    # that arch's per-base subdirectory. Every value ends in "_<arch>" because
    # tuned entries carry the arch natively and renameFallbacksPerArch
    # arch-suffixed every fallback entry before this point. Filtering on that
    # suffix keeps each arch's Mapping complete while letting builds produce
    # non-colliding mapping artifacts that survive overlay-style installs.
    for archName in archs:
        archMapping = {
            idx: name
            for idx, name in libraryMapping.items()
            if name.endswith("_" + archName)
        }
        if archMapping:
            archDir = libraryDir(outputPath, archName)
            archMappingFile = os.path.join(
                archDir, "TensileLiteLibrary_lazy_" + archName + "_Mapping"
            )
            LibraryIO.write(archMappingFile, archMapping, "msgpack")

    start_msl = timer()
    for archName, newMasterLibrary in masterLibraries.items():
        if archName in archs:
            archDir = libraryDir(outputPath, archName)
            def writeMsl(name, lib, archDir=archDir):
                filename = os.path.join(archDir, name)
                lib.applyNaming(splitGSU)
                LibraryIO.write(filename, state(lib), arguments["LibraryFormat"])

            if arguments["LazyLibraryLoading"]:
                masterFile = os.path.join(archDir, "TensileLibrary_lazy_" + archName)
            else:
                masterFile = os.path.join(archDir, "TensileLibrary_" + archName)
            newMasterLibrary.applyNaming(splitGSU)
            LibraryIO.write(masterFile, state(newMasterLibrary), arguments["LibraryFormat"])

            ParallelMap2(writeMsl,
                         newMasterLibrary.lazyLibraries.items(),
                         "Writing master solution libraries",
                         return_as="list")
    stop_msl = timer()
    print(f"Time to write master solution libraries (s): {(stop_msl-start_msl):3.2f}")

    if not arguments["KeepBuildTmp"]:
        buildTmp = Path(arguments["OutputPath"]).parent / "library" / "build_tmp"
        if buildTmp.exists() and buildTmp.is_dir():
            shutil.rmtree(buildTmp)
        buildTmp = Path(arguments["OutputPath"]) / "build_tmp"
        if buildTmp.exists() and buildTmp.is_dir():
            shutil.rmtree(buildTmp)
        else:
            printWarning(f"Cannot remove build_tmp")

    print("# Tensile Library Writer DONE")
    print(HR)
    print("")

    stop = timer()

    print(f"Total time (s): {(stop-start):3.2f}")
    print(f"Total kernels processed: {numKernels}")
    print(f"Kernels processed per second: {(numKernels/(stop-start)):3.2f}")
    print(f"KernelHelperObjs: {len(kernelHelperObjs)}")


from .IO import (
    _baseArchs,
    _stinky_asm_verify_wanted,
    _stinky_out,
    _verify_stinky_asm_comment_vs_elf_text,
    copyStaticFiles,
    libraryDir,
    libraryRoot,
    memCompress,
    memDecompress,
    tensileLibraryFile,
    writeAssembly,
    writeHelpers,
)
from .Logic import (
    _renameFallbackPlaceholders,
    generateKernelObjectsFromSolutions,
    generateLogicDataAndSolutions,
    renameFallbacksPerArch,
)
from .Tuning import (
    _checkInvalidSolutions,
    _checkInvalidSolutionsAndKernels,
    passPostKernelInfoToLibrary,
    passPostKernelInfoToSolution,
    removeInvalidSolutionsAndKernels,
    writeSolutionsAndKernels,
    writeSolutionsAndKernelsTCL,
)
